#!/usr/bin/env bash
# Dispatcher canonico dei test. Un solo ingresso, dietro la piramide (unit/integration/contract/e2e).
set -euo pipefail
target="${1:-all}"; level="${2:-quick}"; shift 2 2>/dev/null || true

case "$level" in
  quick) sel='-m "unit or contract" -p no:randomly' ;;   # loop stretto: veloce e deterministico
  ci)    sel='--randomly-seed=random -n auto' ;;          # prova del fuoco: casuale + parallelo, stana gli incroci
  *)     sel="-m $level" ;;                               # un piano singolo, quando vuoi mirare
esac
path="."; [[ "$target" != "all" ]] && path="services/$target"
eval pytest -q "$sel" "$path" "$@"
