# TESTS — cosa lanciare e quando

Regola zero: NON scrivere test al volo. Usa il dispatcher canonico.

- Dopo ogni modifica a un servizio:  scripts/run_tests.sh <servizio> quick
- Prima di chiudere una fase:        scripts/run_tests.sh all ci

## positions
- unit:        ts assente (HasField=false) -> None; route_id assente -> None; entity senza position scartata.
- contract:    GET /vehicles rispetta lo schema {id, linea, lat, lon, ts}.
- integration: feed in timeout con cache piena -> 200 + X-Stale; senza cache -> 503 + Retry-After.

Golden file in tests/fixtures/ (feed reali congelati). NON rigenerarli senza annotarlo in STATUS.md.
