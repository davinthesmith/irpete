#pragma once

#include <IRsend.h>

#include "hardware_driver.h"

namespace pete {

/** Driver `id` `"ir"`: envelope → IRremoteESP8266 `sendRaw` on the configured GPIO. */
class IrLedDriver final : public HardwareDriver {
 public:
  explicit IrLedDriver(IRsend* irsend) : irsend_(irsend) {}

  const char* id() const override { return "ir"; }
  bool play(const peter::SignalEnvelope& envelope) override;

 private:
  IRsend* irsend_;
};

}  // namespace pete
