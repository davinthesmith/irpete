#pragma once

#include "hardware_driver.h"

namespace emitter {

/** Reserved `id` for future drivers; v1 play never selects this path. */
class StubHardwareDriver final : public HardwareDriver {
 public:
  const char* id() const override { return "stub"; }
  bool play(const catalog::SignalEnvelope&) override { return true; }
};

}  // namespace emitter
