#pragma once

#include <Arduino.h>
#include <stdint.h>

#include "catalog_tls_client.h"

namespace emitter {

/**
 * HTTPS listener + POST /v1/play (REFERENCE.md §5).
 * JSON body: required `label`; optional `kind` (default `"ir"`). Caller supplies TLS PEMs and a
 * play pipeline (Catalog TLS fetch + hardware driver dispatch).
 */
using PlayPipelineFn = bool (*)(const char* label, catalog::FetchResult* fetch_result_out);

struct HttpsPlayConfig {
  uint16_t listen_port;
  /** Fullchain or leaf PEM for Emitter TLS server (PROGMEM ok). */
  const char* server_cert_pem;
  const char* server_private_key_pem;
  /** Same model as Catalog IRPETE_API_KEY (REFERENCE.md §4). */
  const char* bearer_token;
  /**
   * Before contacting Catalog, optionally busy-wait while rejecting extra HTTPS clients with 409.
   * Use for bench overlap testing (see README); 0 in production.
   */
  uint32_t simulate_busy_ms;
  PlayPipelineFn play_pipeline;
};

bool httpsPlayInit(const HttpsPlayConfig& cfg);
/** Call from loop(): accept HTTPS clients and handle POST /v1/play. */
void httpsPlayPoll();

}  // namespace emitter
