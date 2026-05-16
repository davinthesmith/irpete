/**
 * Emitter: Wi-Fi + TLS client to Catalog + TLS server on Emitter with POST /v1/play,
 * IR output via driver registry (`IrLedDriver` on D2 / GPIO4).
 *
 * Boot: optional one-shot fetch (EMITTER_TRIGGER_ON_BOOT). Loop: HTTPS /v1/play + Serial ``s``.
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <IRsend.h>
#include <memory>

#include "hardware_driver.h"
#include "ir_led_driver.h"
#include "emitter_https_play.h"
#include "catalog_tls_client.h"
#include "secrets.h"
#include "stub_hardware_driver.h"

#ifndef EMITTER_TRIGGER_ON_BOOT
#define EMITTER_TRIGGER_ON_BOOT 1
#endif

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 60000U
#endif

#ifndef EMITTER_HTTPS_PORT
#define EMITTER_HTTPS_PORT 8443
#endif

#ifndef EMITTER_SIMULATE_BUSY_MS
#define EMITTER_SIMULATE_BUSY_MS 0
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

void logFetchResult(catalog::FetchResult r) {
  Serial.print(F("Catalog fetch: "));
  Serial.println(catalog::fetchResultMessage(r));
}

/** Fetch envelope from Catalog over TLS, then hardware driver play (REFERENCE §5 sequencing). */
bool playPipeline(const char* label, catalog::FetchResult* fr_out) {
  catalog::FetchConfig cfg = {
      CATALOG_HOST,
      static_cast<uint16_t>(CATALOG_PORT),
      label,
      IRPETE_API_KEY,
      CATALOG_CA_PEM,
  };
  catalog::SignalEnvelope env{};
  *fr_out = catalog::fetchSignalEnvelope(cfg, &env);
  logFetchResult(*fr_out);
  if (*fr_out != catalog::FetchResult::Ok) {
    return false;
  }

  emitter::HardwareDriver* driver = emitter::getDriver("ir");
  if (!driver) {
    Serial.println(F("play: no ir driver"));
    *fr_out = catalog::FetchResult::InvalidEnvelope;
    return false;
  }
  if (!driver->play(env)) {
    *fr_out = catalog::FetchResult::InvalidEnvelope;
    return false;
  }
  return true;
}

bool fetchAndSendIrBoot() {
  Serial.println(F("phase: boot trigger (Catalog TLS + IR)"));
  catalog::FetchResult fr{};
  return playPipeline(CATALOG_LABEL, &fr);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("Emitter — HTTPS /v1/play + TLS client + IR driver registry"));
  irsend.begin();

  if (!emitter::registerDriver(std::make_unique<emitter::IrLedDriver>(&irsend))) {
    Serial.println(F("Halting: IR driver register failed"));
    return;
  }
  if (!emitter::registerDriver(std::make_unique<emitter::StubHardwareDriver>())) {
    Serial.println(F("Halting: stub driver register failed"));
    return;
  }

  if (!wifiConnect()) {
    Serial.println(F("Halting: fix Wi-Fi credentials in include/secrets.h"));
    return;
  }

  emitter::HttpsPlayConfig srv = {
      static_cast<uint16_t>(EMITTER_HTTPS_PORT),
      EMITTER_SERVER_CERT_PEM,
      EMITTER_SERVER_PRIVATE_KEY_PEM,
      IRPETE_API_KEY,
      EMITTER_SIMULATE_BUSY_MS,
      playPipeline,
  };
  if (!emitter::httpsPlayInit(srv)) {
    Serial.println(F("Halting: HTTPS server init failed (cert/key PEM?)"));
    return;
  }

#if EMITTER_TRIGGER_ON_BOOT
  (void)fetchAndSendIrBoot();
#endif

  Serial.print(F("Ready: POST https://<emitter-ip>:"));
  Serial.print(static_cast<int>(EMITTER_HTTPS_PORT));
  Serial.println(F("/v1/play"));
  Serial.println(F("Serial: press 's' or Enter to replay CATALOG_LABEL via Catalog + IR."));
}

void loop() {
  emitter::httpsPlayPoll();

  if (Serial.available() <= 0) {
    return;
  }
  char c = static_cast<char>(Serial.read());
  if (c == 's' || c == 'S' || c == '\n' || c == '\r') {
    while (Serial.available() > 0) {
      (void)Serial.read();
    }
    Serial.println(F("phase: serial trigger (Catalog TLS + IR)"));
    catalog::FetchResult fr{};
    (void)playPipeline(CATALOG_LABEL, &fr);
  }
}
