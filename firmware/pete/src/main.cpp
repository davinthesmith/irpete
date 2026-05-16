/**
 * Pete Stage 7: Wi-Fi + TLS client to Peter + TLS server on Pete with POST /v1/play,
 * IR output via driver registry (`IrLedDriver` on D2 / GPIO4).
 *
 * Boot: optional one-shot fetch (PETE_TRIGGER_ON_BOOT). Loop: HTTPS /v1/play + Serial ``s``.
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <IRsend.h>
#include <memory>

#include "hardware_driver.h"
#include "ir_led_driver.h"
#include "pete_https_play.h"
#include "peter_tls_client.h"
#include "secrets.h"
#include "stub_hardware_driver.h"

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

/** Fetch envelope from Peter over TLS, then hardware driver play (REFERENCE §5 sequencing). */
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

  pete::HardwareDriver* driver = pete::getDriver("ir");
  if (!driver) {
    Serial.println(F("play: no ir driver"));
    *fr_out = peter::FetchResult::InvalidEnvelope;
    return false;
  }
  if (!driver->play(env)) {
    *fr_out = peter::FetchResult::InvalidEnvelope;
    return false;
  }
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
  Serial.println(F("Pete Stage 7 — HTTPS /v1/play + TLS client + IR driver registry"));
  irsend.begin();

  if (!pete::registerDriver(std::make_unique<pete::IrLedDriver>(&irsend))) {
    Serial.println(F("Halting: IR driver register failed"));
    return;
  }
  if (!pete::registerDriver(std::make_unique<pete::StubHardwareDriver>())) {
    Serial.println(F("Halting: stub driver register failed"));
    return;
  }

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
