#include "ir_led_driver.h"

#include <Arduino.h>

namespace pete {

bool IrLedDriver::play(const peter::SignalEnvelope& envelope) {
  if (!irsend_) {
    return false;
  }
  if (envelope.raw_len == 0 || envelope.raw_len > peter::kMaxRawElements) {
    return false;
  }

  Serial.print(F("HTTP 200: pulses="));
  Serial.println(static_cast<unsigned>(envelope.raw_len));

  uint8_t khz = static_cast<uint8_t>(envelope.carrier_hz / 1000);
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
  irsend_->sendRaw(envelope.raw_us, static_cast<uint16_t>(envelope.raw_len), khz);
  Serial.println(F("IR: sendRaw complete"));
  return true;
}

}  // namespace pete
