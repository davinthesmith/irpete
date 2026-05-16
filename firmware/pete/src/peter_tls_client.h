#pragma once

#include <Arduino.h>
#include <stddef.h>
#include <stdint.h>

/**
 * HTTPS client for GET /v1/signals/{label} (REFERENCE.md §5–6).
 * Keep TLS setup localized here so Stage 6 can call fetch from an HTTPS server handler.
 */
namespace peter {

static constexpr size_t kMaxRawElements = 512;

struct SignalEnvelope {
  uint16_t carrier_hz;
  size_t raw_len;
  uint16_t raw_us[kMaxRawElements];
};

enum class FetchResult {
  Ok,
  HttpError,
  Unauthorized,
  NotFound,
  ServerError,
  TlsError,
  JsonError,
  InvalidEnvelope,
};

struct FetchConfig {
  const char* host;
  uint16_t port;
  const char* label;
  const char* bearer_token;
  /** PEM trust anchor (same bytes as ``secrets.h`` ``PETER_CA_PEM``); PROGMEM string. */
  const char* ca_pem_progmem;
};

/** Single HTTPS GET + JSON parse; no overlapping calls until this returns (Stage 5 sequencing). */
FetchResult fetchSignalEnvelope(const FetchConfig& cfg, SignalEnvelope* out);

const char* fetchResultMessage(FetchResult r);

}  // namespace peter
