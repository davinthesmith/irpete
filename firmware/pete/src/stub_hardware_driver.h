#pragma once

#include "hardware_driver.h"

namespace pete {

/** Reserved `id` for future drivers; v1 play never selects this path. */
class StubHardwareDriver final : public HardwareDriver {
 public:
  const char* id() const override { return "stub"; }
  bool play(const peter::SignalEnvelope&) override { return true; }
};

}  // namespace pete
