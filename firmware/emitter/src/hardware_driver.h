#pragma once

#include <memory>

#include "catalog_tls_client.h"

namespace emitter {

/**
 * Pluggable output path for fetched envelopes (REFERENCE §5).
 * v1 `/v1/play` resolves `kind` to driver `id()`; wire JSON is parsed in `catalog_tls_client`.
 */
class HardwareDriver {
 public:
  virtual ~HardwareDriver() = default;
  virtual const char* id() const = 0;
  virtual bool play(const catalog::SignalEnvelope& envelope) = 0;
};

bool registerDriver(std::unique_ptr<HardwareDriver> d);
HardwareDriver* getDriver(const char* id);

}  // namespace emitter
