# SPEC — positions

Servizio di sola lettura che espone la posizione in tempo reale dei mezzi di Roma.

## Cosa fa
- Legge il feed GTFS-RT (protobuf, proto2), lo traduce in JSON, lo tiene in cache in-memory.
- Espone `/vehicles`, `/vehicles/{id}`, `/health`.

## Invarianti (non negoziabili)
- **Una sola responsabilità**: legge il feed e serve posizioni. Niente DB, niente dipendenze da altri servizi.
- **Il protobuf muore in `feed.py`**: oltre quel confine si parla solo dict/JSON.
- **Diffidenza di default**: metodi diversi da GET → 405; parametri sconosciuti → 400; IP fuori allowlist → 403.
- **Onestà sugli stati**: dato fresco → 200; dato vecchio ma valido → 200 + `X-Stale`; nulla da servire → 503 + `Retry-After`. Mai 500 per un guasto a monte.
- **Errori vs bug**: i guasti previsti del feed (rete, protobuf illeggibile) si gestiscono; i bug risalgono all'handler di ultima istanza (500 sobrio, stack trace solo nei log).

## Config (da ambiente)
- `GTFS_RT_URL` — URL del feed (in allowlist). Obbligatorio per servire dati.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWLIST` — opzionali (E06). Assenti → nessun canale, servizio identico.

## Parametri noti
- `linea` (query, opzionale): filtra per `route_id`. Alfanumerico, altrimenti 422.
