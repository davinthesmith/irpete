#pragma once

#include <memory>

#include "peter_tls_client.h"

namespace pete {

/**
 * Pluggable output path for fetched envelopes (Stage 7 — REFERENCE §5).
 * v1 `/v1/play` resolves `kind` to driver `id()`; wire JSON is parsed in `peter_tls_client`.
 */
class HardwareDriver {
 public:
  virtual ~HardwareDriver() = default;
  virtual const char* id() const = 0;
  virtual bool play(const peter::SignalEnvelope& envelope) = 0;
};

bool registerDriver(std::unique_ptr<HardwareDriver> d);
HardwareDriver* getDriver(const char* id);

}  // namespace pete
