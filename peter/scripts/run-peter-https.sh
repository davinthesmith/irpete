#!/usr/bin/env bash
# Run Peter with Uvicorn TLS. Requires IRPETE_TLS_CERTFILE + IRPETE_TLS_KEYFILE + IRPETE_API_KEY.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -z "${IRPETE_TLS_CERTFILE:-}" || -z "${IRPETE_TLS_KEYFILE:-}" ]]; then
  echo "run-peter-https.sh: set IRPETE_TLS_CERTFILE and IRPETE_TLS_KEYFILE (fullchain + private key PEM paths)." >&2
  exit 1
fi
export IRPETE_HOST="${IRPETE_HOST:-0.0.0.0}"
export IRPETE_PORT="${IRPETE_PORT:-8443}"
exec python -m irpete.main
