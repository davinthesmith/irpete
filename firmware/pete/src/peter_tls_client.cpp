#include "peter_tls_client.h"

#include <ESP8266HTTPClient.h>
#include <WiFiClientSecureBearSSL.h>
#include <ArduinoJson.h>
#include <memory>

namespace peter {

namespace {

constexpr uint32_t kTlsTimeoutMs = 20000;
constexpr int kCarrierMinHz = 30000;
constexpr int kCarrierMaxHz = 60000;

bool copyRawUs(JsonArrayConst arr, SignalEnvelope* out) {
  size_t n = arr.size();
  if (n == 0 || n > kMaxRawElements) {
    return false;
  }
  size_t i = 0;
  for (JsonVariantConst v : arr) {
    if (!v.is<int>()) {
      return false;
    }
    int x = v.as<int>();
    if (x < 1 || x > 65535) {
      return false;
    }
    out->raw_us[i++] = static_cast<uint16_t>(x);
  }
  out->raw_len = n;
  return true;
}

}  // namespace

const char* fetchResultMessage(FetchResult r) {
  switch (r) {
    case FetchResult::Ok:
      return "ok";
    case FetchResult::HttpError:
      return "http transport error";
    case FetchResult::Unauthorized:
      return "HTTP 401 unauthorized";
    case FetchResult::NotFound:
      return "HTTP 404 unknown label";
    case FetchResult::ServerError:
      return "HTTP 5xx server error";
    case FetchResult::TlsError:
      return "TLS connect or trust failure";
    case FetchResult::JsonError:
      return "JSON parse failure";
    case FetchResult::InvalidEnvelope:
      return "envelope fields invalid";
    default:
      return "unknown";
  }
}

FetchResult fetchSignalEnvelope(const FetchConfig& cfg, SignalEnvelope* out) {
  if (!out || !cfg.host || !cfg.label || !cfg.bearer_token || !cfg.ca_pem_progmem) {
    return FetchResult::InvalidEnvelope;
  }

  std::unique_ptr<BearSSL::WiFiClientSecure> client(new BearSSL::WiFiClientSecure());
  BearSSL::X509List cert(cfg.ca_pem_progmem);
  client->setTrustAnchors(&cert);
  client->setTimeout(kTlsTimeoutMs / 1000);

  HTTPClient https;
  String path = String("/v1/signals/") + cfg.label;
  if (!https.begin(*client, cfg.host, cfg.port, path, true)) {
    return FetchResult::TlsError;
  }

  https.addHeader(F("Authorization"), String(F("Bearer ")) + cfg.bearer_token);
  https.setTimeout(kTlsTimeoutMs);
  https.setReuse(false);

  int code = https.GET();
  if (code < 0) {
    https.end();
    return FetchResult::HttpError;
  }
  if (code == 401) {
    https.end();
    return FetchResult::Unauthorized;
  }
  if (code == 404) {
    https.end();
    return FetchResult::NotFound;
  }
  if (code >= 500) {
    https.end();
    return FetchResult::ServerError;
  }
  if (code != 200) {
    https.end();
    return FetchResult::HttpError;
  }

  String payload = https.getString();
  https.end();

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    return FetchResult::JsonError;
  }

  if (!doc["schema_version"].is<int>() || !doc["carrier_hz"].is<int>() ||
      !doc["raw_us"].is<JsonArrayConst>()) {
    return FetchResult::InvalidEnvelope;
  }

  int schema = doc["schema_version"].as<int>();
  if (schema != 1) {
    return FetchResult::InvalidEnvelope;
  }

  int carrier = doc["carrier_hz"].as<int>();
  if (carrier < kCarrierMinHz || carrier > kCarrierMaxHz) {
    return FetchResult::InvalidEnvelope;
  }

  JsonArrayConst rawArr = doc["raw_us"].as<JsonArrayConst>();
  SignalEnvelope tmp{};
  if (!copyRawUs(rawArr, &tmp)) {
    return FetchResult::InvalidEnvelope;
  }

  tmp.carrier_hz = static_cast<uint16_t>(carrier);
  *out = tmp;
  return FetchResult::Ok;
}

}  // namespace peter
