#!/usr/bin/env bash
# Lancia la suite di test. Uso: ./scripts/run_tests.sh [percorso-o-marker]
set -euo pipefail          # esci al primo errore, variabili non definite = errore, fallimenti in pipe contano

cd "$(dirname "$0")/.."    # sempre dalla radice del repo, da qualunque cwd venga lanciato

echo ">> pytest" >&2        # log su stderr: lo stdout resta pulito per l'output dei test
exec python3 -m pytest -q "$@"
