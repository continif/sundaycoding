# STATUS — roma-traffic

Fase corrente: **1 / 6 — Ingestion feed GTFS-RT**

## Fatto
- [x] Fase 0: scaffolding, permessi deny-first, hook anti-segreti, script canonici

## In corso
- [ ] Fase 1: skill gtfs-rt (protobuf -> JSON) + subagent feed-fetcher a privilegi minimi

## Prossime fasi
- [ ] Fase 2: servizio positions -> GET /vehicles, cache 20s
- [ ] Fase 3: servizio traffic (monitoraggio stradale, refresh 10 min)
- [ ] Fase 4: gateway + controllo connessioni (IP / User-Agent / rate limit)
- [ ] Fase 5: gestione errori centralizzata
- [ ] Fase 6: bot Telegram

## Decisioni CHIUSE (non riaprire senza motivo scritto qui)
- Cache in-memory finché i servizi sono < 5. Niente Redis.
- Il protobuf muore dentro positions. Ogni confine parla JSON.
- I segreti si bloccano con hook, non con .gitignore o buone intenzioni.
