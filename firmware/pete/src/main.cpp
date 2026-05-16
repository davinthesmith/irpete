/**
 * Pete Stage 6: Wi-Fi + TLS client to Peter + TLS server on Pete with POST /v1/play,
 * plus IR sendRaw on D2 (GPIO4).
 *
 * Boot: optional one-shot fetch (PETE_TRIGGER_ON_BOOT). Loop: HTTPS /v1/play + Serial ``s``.
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <IRsend.h>

#include "pete_https_play.h"
#include "peter_tls_client.h"
#include "secrets.h"

#ifndef PETE_TRIGGER_ON_BOOT
#define PETE_TRIGGER_ON_BOOT 1
#endif

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 60000U
#endif

#ifndef PETE_HTTPS_PORT
#define PETE_HTTPS_PORT 8443
#endif

#ifndef PETE_SIMULATE_BUSY_MS
#define PETE_SIMULATE_BUSY_MS 0
#endif

// IRremoteESP8266: GPIO number (D2 on Wemos D1 mini == GPIO4).
constexpr uint8_t kIrLedGpio = 4;
IRsend irsend(kIrLedGpio);

namespace {

bool wifiConnect() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    if (millis() - start > WIFI_CONNECT_TIMEOUT_MS) {
      Serial.println(F("Wi-Fi: connection timed out"));
      return false;
    }
    delay(250);
    Serial.print('.');
  }
  Serial.println();
  Serial.print(F("Wi-Fi: connected, ip "));
  Serial.println(WiFi.localIP());
  return true;
}

void logFetchResult(peter::FetchResult r) {
  Serial.print(F("Peter fetch: "));
  Serial.println(peter::fetchResultMessage(r));
}

/** Fetch envelope from Peter over TLS, then IR sendRaw (REFERENCE §5 sequencing). */
bool playPipeline(const char* label, peter::FetchResult* fr_out) {
  peter::FetchConfig cfg = {
      PETER_HOST,
      static_cast<uint16_t>(PETER_PORT),
      label,
      IRPETE_API_KEY,
      PETER_CA_PEM,
  };
  peter::SignalEnvelope env{};
  *fr_out = peter::fetchSignalEnvelope(cfg, &env);
  logFetchResult(*fr_out);
  if (*fr_out != peter::FetchResult::Ok) {
    return false;
  }

  Serial.print(F("HTTP 200: pulses="));
  Serial.println(static_cast<unsigned>(env.raw_len));

  uint8_t khz = static_cast<uint8_t>(env.carrier_hz / 1000);
  if (khz < 30 || khz > 60) {
    Serial.println(F("IR: carrier kHz out of range; clamping"));
    if (khz < 30) {
      khz = 30;
    }
    if (khz > 60) {
      khz = 60;
    }
  }

  Serial.println(F("phase: IR sendRaw"));
  irsend.sendRaw(env.raw_us, static_cast<uint16_t>(env.raw_len), khz);
  Serial.println(F("IR: sendRaw complete"));
  return true;
}

bool fetchAndSendIrBoot() {
  Serial.println(F("phase: boot trigger (Peter TLS + IR)"));
  peter::FetchResult fr{};
  return playPipeline(PETER_LABEL, &fr);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("Pete Stage 6 — HTTPS /v1/play + TLS client + IR sendRaw"));
  irsend.begin();

  if (!wifiConnect()) {
    Serial.println(F("Halting: fix Wi-Fi credentials in include/secrets.h"));
    return;
  }

  pete::HttpsPlayConfig srv = {
      static_cast<uint16_t>(PETE_HTTPS_PORT),
      PETE_SERVER_CERT_PEM,
      PETE_SERVER_PRIVATE_KEY_PEM,
      IRPETE_API_KEY,
      PETE_SIMULATE_BUSY_MS,
      playPipeline,
  };
  if (!pete::httpsPlayInit(srv)) {
    Serial.println(F("Halting: HTTPS server init failed (cert/key PEM?)"));
    return;
  }

#if PETE_TRIGGER_ON_BOOT
  (void)fetchAndSendIrBoot();
#endif

  Serial.print(F("Ready: POST https://<pete-ip>:"));
  Serial.print(static_cast<int>(PETE_HTTPS_PORT));
  Serial.println(F("/v1/play"));
  Serial.println(F("Serial: press 's' or Enter to replay PETER_LABEL via Peter + IR."));
}

void loop() {
  pete::httpsPlayPoll();

  if (Serial.available() <= 0) {
    return;
  }
  char c = static_cast<char>(Serial.read());
  if (c == 's' || c == 'S' || c == '\n' || c == '\r') {
    while (Serial.available() > 0) {
      (void)Serial.read();
    }
    Serial.println(F("phase: serial trigger (Peter TLS + IR)"));
    peter::FetchResult fr{};
    (void)playPipeline(PETER_LABEL, &fr);
  }
}
