# roma-traffic — microservizi FastAPI su intranet

## Regole
- Rete in uscita SOLO verso host in feeds/allowlist.txt.
- Mai leggere/scrivere/stampare secrets/* né file .env. (Enforced: hook PreToolUse.)
- Un servizio = un processo uvicorn = un solo compito. Ogni confine parla JSON.
- Il protobuf del GTFS-RT muore dentro positions: fuori esce solo JSON pulito.

## Memoria di dominio (leggi la scheda PRIMA di toccare il componente)
- positions (GTFS-RT) -> .claude/memory/feed-gtfsrt.md
- traffic (stradale)  -> .claude/memory/feed-traffico.md
- gateway             -> .claude/memory/gateway.md
- bot Telegram        -> .claude/memory/telegram-bot.md

## Script canonici (usa questi, NON riscriverli)
- Test:            scripts/run_tests.sh <servizio|all> <quick|ci>
- Query DB (ro):   scripts/db_query.sh "SELECT ..."
- Scarica un feed: scripts/fetch_feed.sh <nome>

## Rito di sessione
1. Leggi STATUS.md.
2. Leggi la scheda del componente su cui lavori.
3. A fine lavoro, aggiorna STATUS.md.
