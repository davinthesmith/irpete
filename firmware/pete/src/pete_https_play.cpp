#include "pete_https_play.h"

#include <cstring>

#include <ArduinoJson.h>
#include <BearSSLHelpers.h>
#include <ESP8266WiFi.h>
#include <WiFiServerSecureBearSSL.h>
#include <strings.h>

namespace pete {

namespace {

constexpr uint32_t kIoDeadlineMs = 20000;
constexpr size_t kMaxRequestBytes = 1536;
constexpr size_t kMaxBodyBytes = 384;
constexpr size_t kMaxLabelLen = 64;
constexpr size_t kMaxKindLen = 32;

BearSSL::WiFiServerSecure* g_srv = nullptr;
BearSSL::X509List* g_chain = nullptr;
BearSSL::PrivateKey* g_key = nullptr;

const char* g_bearer = nullptr;
PlayPipelineFn g_play = nullptr;
uint32_t g_sim_busy_ms = 0;

volatile bool g_play_busy = false;

void sendHttpLine(WiFiClient& c, const char* line) {
  c.print(line);
}

void sendHttpResponse(WiFiClient& c, int code, const char* reason, const char* json_body) {
  c.printf("HTTP/1.1 %d %s\r\n", code, reason);
  sendHttpLine(c, "Connection: close\r\n");
  sendHttpLine(c, "Content-Type: application/json\r\n");
  if (json_body) {
    c.printf("Content-Length: %u\r\n\r\n", static_cast<unsigned>(strlen(json_body)));
    c.print(json_body);
  } else {
    sendHttpLine(c, "Content-Length: 0\r\n\r\n");
  }
}

bool streqi(const char* a, const char* b) {
  return strcasecmp(a, b) == 0;
}

bool parseRequestLine(const char* line, char* method, size_t method_cap, char* target,
                      size_t target_cap) {
  const char* sp1 = strchr(line, ' ');
  if (!sp1) {
    return false;
  }
  const char* sp2 = strchr(sp1 + 1, ' ');
  if (!sp2) {
    return false;
  }
  size_t ml = static_cast<size_t>(sp1 - line);
  if (ml + 1 > method_cap) {
    return false;
  }
  memcpy(method, line, ml);
  method[ml] = '\0';

  size_t tl = static_cast<size_t>(sp2 - (sp1 + 1));
  if (tl + 1 > target_cap) {
    return false;
  }
  memcpy(target, sp1 + 1, tl);
  target[tl] = '\0';
  return true;
}

bool parseContentLength(const char* header_start, int* out_len) {
  const char* p = header_start;
  while (*p) {
    if (strncasecmp(p, "Content-Length:", 15) == 0) {
      p += 15;
      while (*p == ' ' || *p == '\t') {
        ++p;
      }
      *out_len = atoi(p);
      return true;
    }
    const char* nl = strstr(p, "\r\n");
    if (!nl) {
      break;
    }
    p = nl + 2;
  }
  return false;
}

bool extractBearer(const char* header_start, char* out, size_t cap) {
  const char* p = header_start;
  while (*p) {
    if (strncasecmp(p, "Authorization:", 14) == 0) {
      p += 14;
      while (*p == ' ' || *p == '\t') {
        ++p;
      }
      if (strncasecmp(p, "Bearer ", 7) != 0) {
        return false;
      }
      p += 7;
      size_t i = 0;
      while (*p && *p != '\r' && *p != '\n' && i + 1 < cap) {
        out[i++] = *p++;
      }
      out[i] = '\0';
      return i > 0;
    }
    const char* nl = strstr(p, "\r\n");
    if (!nl) {
      break;
    }
    p = nl + 2;
  }
  return false;
}

/**
 * While a play is in progress, lwIP may accept additional TLS handshakes into the pending queue.
 * Respond with 409 and close so curl overlap testing can observe busy behavior.
 */
void rejectPendingClients409() {
  if (!g_srv || !g_play_busy) {
    return;
  }
  while (g_srv->hasClient()) {
    BearSSL::WiFiClientSecure c = g_srv->accept();
    if (!c || !c.connected()) {
      break;
    }
    Serial.println(F("HTTPS: rejecting queued client (409 busy)"));
    sendHttpResponse(c, 409, "Conflict", "{\"error\":\"busy\"}");
    c.stop();
  }
}

bool readHttpRequest(WiFiClient& c, char* buf, size_t cap, size_t* total_out) {
  size_t n = 0;
  uint32_t deadline = millis() + kIoDeadlineMs;
  while (millis() < deadline && n < cap) {
    while (c.available() && n < cap) {
      buf[n++] = static_cast<char>(c.read());
      if (n >= 4) {
        if (buf[n - 4] == '\r' && buf[n - 3] == '\n' && buf[n - 2] == '\r' &&
            buf[n - 1] == '\n') {
          buf[n] = '\0';
          char* sep = strstr(buf, "\r\n\r\n");
          if (!sep) {
            return false;
          }
          int content_length = 0;
          if (!parseContentLength(buf, &content_length)) {
            content_length = 0;
          }
          if (content_length < 0 || static_cast<size_t>(content_length) > kMaxBodyBytes) {
            return false;
          }
          size_t header_end = static_cast<size_t>(sep - buf) + 4;
          size_t need = header_end + static_cast<size_t>(content_length);
          while (n < need && n < cap && millis() < deadline) {
            while (c.available() && n < cap) {
              buf[n++] = static_cast<char>(c.read());
            }
            yield();
          }
          if (n < need) {
            return false;
          }
          buf[n] = '\0';
          *total_out = n;
          return true;
        }
      }
    }
    yield();
  }
  *total_out = n;
  return false;
}

void handleOneClient(BearSSL::WiFiClientSecure& client) {
  char buf[kMaxRequestBytes + 1];
  size_t total = 0;
  if (!readHttpRequest(client, buf, sizeof(buf), &total)) {
    Serial.println(F("HTTPS: request read failed or oversize body"));
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"bad_request\"}");
    return;
  }

  char* sep = strstr(buf, "\r\n\r\n");
  if (!sep) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"bad_request\"}");
    return;
  }
  *sep = '\0';
  const char* headers_z = buf;
  const char* body = sep + 4;

  char method[16]{};
  char target[128]{};
  const char* req_line = headers_z;
  const char* hdr_start = strstr(req_line, "\r\n");
  if (!hdr_start) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"bad_request\"}");
    return;
  }
  char first_line[160]{};
  size_t flen = static_cast<size_t>(hdr_start - req_line);
  if (flen >= sizeof(first_line)) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"bad_request\"}");
    return;
  }
  memcpy(first_line, req_line, flen);
  first_line[flen] = '\0';
  const char* hdr_lines = hdr_start + 2;

  if (!parseRequestLine(first_line, method, sizeof(method), target, sizeof(target))) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"bad_request\"}");
    return;
  }

  if (!streqi(method, "POST") || strcmp(target, "/v1/play") != 0) {
    sendHttpResponse(client, 404, "Not Found", "{\"error\":\"not_found\"}");
    return;
  }

  char bearer[160]{};
  if (!extractBearer(hdr_lines, bearer, sizeof(bearer))) {
    Serial.println(F("HTTPS: missing Bearer"));
    sendHttpResponse(client, 401, "Unauthorized", "{\"error\":\"unauthorized\"}");
    return;
  }
  if (!g_bearer || strcmp(bearer, g_bearer) != 0) {
    Serial.println(F("HTTPS: wrong Bearer"));
    sendHttpResponse(client, 401, "Unauthorized", "{\"error\":\"unauthorized\"}");
    return;
  }

  if (g_play_busy) {
    Serial.println(F("HTTPS: busy (global)"));
    sendHttpResponse(client, 409, "Conflict", "{\"error\":\"busy\"}");
    return;
  }

  JsonDocument doc;
  DeserializationError jerr = deserializeJson(doc, body);
  if (jerr || !doc["label"].is<const char*>()) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"invalid_json\"}");
    return;
  }
  const char* label = doc["label"].as<const char*>();
  if (!label || label[0] == '\0' || strlen(label) > kMaxLabelLen) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"invalid_label\"}");
    return;
  }

  const char* kind = "ir";
  if (!doc["kind"].isNull()) {
    if (!doc["kind"].is<const char*>()) {
      sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"invalid_kind\"}");
      return;
    }
    const char* k = doc["kind"].as<const char*>();
    if (!k || k[0] == '\0' || strlen(k) > kMaxKindLen) {
      sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"invalid_kind\"}");
      return;
    }
    kind = k;
  }
  if (!streqi(kind, "ir")) {
    sendHttpResponse(client, 400, "Bad Request", "{\"error\":\"unknown_kind\"}");
    return;
  }

  Serial.println(F("HTTPS in: POST /v1/play"));
  Serial.print(F("play label: "));
  Serial.println(label);

  g_play_busy = true;

  if (g_sim_busy_ms > 0) {
    Serial.println(F("HTTPS: simulate busy window (reject overlapping clients with 409)"));
    uint32_t t0 = millis();
    while (millis() - t0 < g_sim_busy_ms) {
      rejectPendingClients409();
      yield();
      delay(5);
    }
  }

  peter::FetchResult fr = peter::FetchResult::InvalidEnvelope;
  Serial.println(F("phase: TLS out (Peter fetch)"));
  bool ok = g_play && g_play(label, &fr);
  if (ok) {
    Serial.println(F("HTTPS out: 200"));
    sendHttpResponse(client, 200, "OK", "{\"ok\":true}");
  } else {
    int code = 502;
    const char* reason = "Bad Gateway";
    const char* json = "{\"error\":\"upstream\"}";
    switch (fr) {
      case peter::FetchResult::NotFound:
        code = 404;
        reason = "Not Found";
        json = "{\"error\":\"unknown_label\"}";
        break;
      case peter::FetchResult::Unauthorized:
        code = 502;
        reason = "Bad Gateway";
        json = "{\"error\":\"peter_auth\"}";
        break;
      case peter::FetchResult::TlsError:
      case peter::FetchResult::HttpError:
      case peter::FetchResult::ServerError:
        code = 503;
        reason = "Service Unavailable";
        json = "{\"error\":\"peter_unreachable\"}";
        break;
      case peter::FetchResult::JsonError:
      case peter::FetchResult::InvalidEnvelope:
        code = 502;
        reason = "Bad Gateway";
        json = "{\"error\":\"bad_envelope\"}";
        break;
      default:
        break;
    }
    Serial.print(F("HTTPS out: "));
    Serial.println(code);
    sendHttpResponse(client, code, reason, json);
  }

  g_play_busy = false;
}

}  // namespace

bool httpsPlayInit(const HttpsPlayConfig& cfg) {
  if (!cfg.server_cert_pem || !cfg.server_private_key_pem || !cfg.bearer_token || !cfg.play_pipeline ||
      !cfg.listen_port) {
    return false;
  }

  g_bearer = cfg.bearer_token;
  g_play = cfg.play_pipeline;
  g_sim_busy_ms = cfg.simulate_busy_ms;

  g_chain = new BearSSL::X509List(cfg.server_cert_pem);
  g_key = new BearSSL::PrivateKey(cfg.server_private_key_pem);
  if (!g_chain || !g_key) {
    return false;
  }

  g_srv = new BearSSL::WiFiServerSecure(cfg.listen_port);
  if (!g_srv) {
    return false;
  }
  g_srv->setRSACert(g_chain, g_key);
  g_srv->begin();

  Serial.print(F("Pete HTTPS server listening on port "));
  Serial.println(cfg.listen_port);
  return true;
}

void httpsPlayPoll() {
  if (!g_srv) {
    return;
  }
  if (g_play_busy) {
    rejectPendingClients409();
    return;
  }

  BearSSL::WiFiClientSecure client = g_srv->accept();
  if (!client || !client.connected()) {
    return;
  }

  handleOneClient(client);
  client.stop();
}

}  // namespace pete
