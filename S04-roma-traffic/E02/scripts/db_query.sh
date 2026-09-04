#!/usr/bin/env bash
# Query READ-ONLY al DB di staging. Prima linea di difesa; la barriera VERA è l'utente DB read-only.
set -euo pipefail
sql="${*:-}"; [[ -z "$sql" ]] && { echo 'Uso: db_query.sh "SELECT ..."' >&2; exit 1; }
# Il filtro keyword è un avviso, non una prigione (commenti/statement multipli lo aggirano).
# La prigione vera è la credenziale: $DATABASE_URL_RO punta a un utente senza privilegi di scrittura.
if grep -qiE '\b(insert|update|delete|drop|alter|truncate|create|grant)\b' <<<"$sql"; then
  echo "BLOCCATO: canale di sola lettura." >&2; exit 2
fi
: "${DATABASE_URL_RO:?imposta DATABASE_URL_RO (utente read-only, mai il superuser)}"
psql "$DATABASE_URL_RO" -c "$sql"
