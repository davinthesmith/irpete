#pragma once

#include <Arduino.h>
#include <stdint.h>

#include "peter_tls_client.h"

namespace pete {

/**
 * HTTPS listener + POST /v1/play (REFERENCE.md §5 Stage 6).
 * Caller supplies TLS PEMs and a play pipeline (Peter fetch + IR send).
 */
using PlayPipelineFn = bool (*)(const char* label, peter::FetchResult* fetch_result_out);

struct HttpsPlayConfig {
  uint16_t listen_port;
  /** Fullchain or leaf PEM for Pete TLS server (PROGMEM ok). */
  const char* server_cert_pem;
  const char* server_private_key_pem;
  /** Same model as Peter IRPETE_API_KEY (REFERENCE.md §4). */
  const char* bearer_token;
  /**
   * Before contacting Peter, optionally busy-wait while rejecting extra HTTPS clients with 409.
   * Use for bench overlap testing (see README); 0 in production.
   */
  uint32_t simulate_busy_ms;
  PlayPipelineFn play_pipeline;
};

bool httpsPlayInit(const HttpsPlayConfig& cfg);
/** Call from loop(): accept HTTPS clients and handle POST /v1/play. */
void httpsPlayPoll();

}  // namespace pete
