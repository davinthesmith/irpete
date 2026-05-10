/**
 * Pete Stage 5: Wi-Fi + HTTPS GET envelope from Peter + IR sendRaw on D2 (GPIO4).
 *
 * Trigger: optional boot fetch (``PETE_TRIGGER_ON_BOOT``) + Serial ``s`` / newline to repeat.
 */

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <IRsend.h>

#include "peter_tls_client.h"
#include "secrets.h"

#ifndef PETE_TRIGGER_ON_BOOT
#define PETE_TRIGGER_ON_BOOT 1
#endif

#ifndef WIFI_CONNECT_TIMEOUT_MS
#define WIFI_CONNECT_TIMEOUT_MS 60000U
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

bool fetchAndSendIr() {
  peter::FetchConfig cfg = {
      PETER_HOST,
      static_cast<uint16_t>(PETER_PORT),
      PETER_LABEL,
      IRPETE_API_KEY,
      PETER_CA_PEM,
  };
  peter::SignalEnvelope env{};
  peter::FetchResult r = peter::fetchSignalEnvelope(cfg, &env);
  logFetchResult(r);
  if (r != peter::FetchResult::Ok) {
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

  irsend.sendRaw(env.raw_us, static_cast<uint16_t>(env.raw_len), khz);
  Serial.println(F("IR: sendRaw complete"));
  return true;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println(F("Pete Stage 5 — TLS client + IR sendRaw"));
  irsend.begin();

  if (!wifiConnect()) {
    Serial.println(F("Halting: fix Wi-Fi credentials in include/secrets.h"));
    return;
  }

#if PETE_TRIGGER_ON_BOOT
  (void)fetchAndSendIr();
#endif

  Serial.println(F("Serial: press 's' or Enter to fetch + transmit again."));
}

void loop() {
  if (Serial.available() <= 0) {
    return;
  }
  char c = static_cast<char>(Serial.read());
  if (c == 's' || c == 'S' || c == '\n' || c == '\r') {
    while (Serial.available() > 0) {
      (void)Serial.read();
    }
    (void)fetchAndSendIr();
  }
}
