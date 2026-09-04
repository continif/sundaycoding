#!/usr/bin/env bash
# Scarica un feed dall'allowlist e lo salva in data/raw/<nome>.bin
set -euo pipefail                     # fail-fast: -e ferma al primo errore, -u becca le var non settate,
                                      # -o pipefail non ingoia gli errori a metà di una pipe.
source "$(dirname "$0")/lib/common.sh"

[[ "${1:-}" =~ ^(-h|--help)$ ]] && { echo "Uso: fetch_feed.sh <nome-feed>" >&2; exit 0; }

feed="${1:?serve il nome del feed}"   # argomento obbligatorio: se manca, muori pulito.
grep -qxF "$feed" feeds/allowlist.txt \
  || die "feed '$feed' non in allowlist" 3   # il PERIMETRO è qui, deterministico: non un buon proposito.

url="$(grep "^$feed=" feeds/urls.txt | cut -d= -f2-)"
[[ -n "$url" ]] || die "nessun URL per '$feed' in feeds/urls.txt" 3
tmp="$(mktemp)"
curl -fsS --max-time 20 "$url" -o "$tmp" || die "download fallito o timeout" 4
[[ -s "$tmp" ]] || die "feed vuoto: NON invento dati" 4   # feed vuoto != successo: fallimento onesto.
mkdir -p data/raw && mv "$tmp" "data/raw/$feed.bin"
log "salvato in data/raw/$feed.bin"
