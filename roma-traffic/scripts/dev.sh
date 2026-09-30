#!/usr/bin/env bash
# Avvia positions in sviluppo (ricarica automatica, solo localhost). Uso: ./scripts/dev.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# carica .env se c'è (senza committarlo mai)
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

if [[ -z "${GTFS_RT_URL:-}" ]]; then
  echo "ATTENZIONE: GTFS_RT_URL non impostato: il servizio parte ma il feed risponderà 503." >&2
fi

exec uvicorn services.positions.main:app --reload
