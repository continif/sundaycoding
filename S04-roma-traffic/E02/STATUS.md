# STATUS — roma-traffic

Fase corrente: **3 / 6 — Deve fare solo quello per cui è programmato**

## Fatto
- [x] Fase 0: scaffolding, permessi deny-first, hook anti-segreti, script canonici
- [x] Fase 1: skill gtfs-rt + subagent feed-fetcher a privilegi minimi
- [x] Fase 2: positions -> GET /vehicles (cache 20s, X-Stale/503, 404 sul singolo, HasField)

## Prossime fasi
- [ ] Fase 3: restringere positions al suo scopo (guard clause, catena di gate, macchina a stati)
- [ ] Fase 4: gateway + controllo connessioni (IP / User-Agent / rate limit)
- [ ] Fase 5: gestione errori centralizzata
- [ ] Fase 6: bot Telegram

## Decisioni CHIUSE (non riaprire senza motivo scritto qui)
- Cache in-memory finché i servizi sono < 5. Niente Redis.
- Il protobuf muore dentro positions. Ogni confine parla JSON.
- Feed vuoto/timeout: 200+X-Stale se c'è cache, altrimenti 503+Retry-After. Mai 500.
- Campi optional del GTFS-RT letti con HasField (proto2): "assente" != "0".
