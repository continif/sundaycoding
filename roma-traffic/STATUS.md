# STATUS — roma-traffic

Stagione **S04 — Il Microservizio Diffidente**. Fase corrente: **6 / 6 — COMPLETA**.

## Fatto
- [x] Fase 0: scaffolding, permessi deny-first, hook anti-segreti.
- [x] Fase 1: skill gtfs-rt + subagent feed-fetcher.
- [x] Fase 2: `positions` → GET /vehicles (cache 20s, X-Stale/503, 404 sul singolo, ts via HasField).
- [x] Fase 3: catena di gate (solo-lettura, parametri-noti) + stato del feed come macchina a stati.
- [x] Fase 4: gate di sicurezza via `@in_catena` (IP/UA/rate) in cima; `ip_client` con risalita XFF.
- [x] Fase 5: eccezioni di dominio + handler centralizzati; `except` del feed ristretto; breaker.
- [x] Fase 6: alert sul fronte agganciati a `cambia_stato`; long polling nel lifespan; comandi read-only con allowlist.

## Decisioni CHIUSE
- Cache in-memory finché i servizi sono < 5. Niente Redis.
- Il protobuf muore in `feed.py`. Ogni confine parla JSON.
- Feed vuoto/timeout: 200+X-Stale se c'è cache, altrimenti 503+Retry-After. Mai 500.
- I gate vivono in un unico modulo, registrati con `@in_catena`: l'ordine di definizione è l'ordine nella catena.
- Telegram è opzionale: senza token il servizio parte e serve identico.

## Prossima stagione
- Da definire. `positions` è la fonte affidabile da cui partire.
