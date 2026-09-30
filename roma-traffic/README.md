# roma-traffic — Il Microservizio Diffidente

Progetto della **Stagione 4** di [Sunday Coding](https://sundaycoding.substack.com/p/s04e01-il-microservizio-diffidente).

`positions` è un microservizio FastAPI che espone la posizione dei mezzi di Roma
leggendo il feed **GTFS-RT** di Roma Servizi per la Mobilità. È costruito per
*diffidere*: fa una cosa sola e dice di no — con lo status giusto — a tutto il resto.

Ogni pezzo del codice nasce in una puntata:

- **E02** — FastAPI + uvicorn, lettura del feed GTFS-RT (proto2), cache con TTL, status onesti (`feed.py`, `modelli.py`).
- **E03** — fa solo quello per cui è programmato: catena di gate, macchina a stati del feed (`stato.py`, `gates.py`).
- **E04** — controllo delle connessioni: IP (con risalita X-Forwarded-For), User-Agent, rate limit (`gates.py`).
- **E05** — gestione errori centralizzata + circuit breaker (`errori.py`, `stato.py`).
- **E06** — interazioni via Telegram: alert sul fronte, comandi read-only (`telegram.py`).

## Avvio

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # poi riempi GTFS_RT_URL (e, se vuoi, i valori Telegram)
# GTFS_RT_URL deve puntare al feed delle POSIZIONI (non trip_updates, non service_alerts):
#   https://romamobilita.it/sites/default/files/rome_rtgtfs_vehicle_positions_feed.pb

# sviluppo (ricarica automatica, solo su localhost, porta 8002)
uvicorn services.positions.main:app --reload --port 8002 --env-file .env
# poi apri http://127.0.0.1:8002/docs  (l'endpoint e' /vehicles, scritto giusto)

# esercizio, dietro reverse proxy (l'IP client arriva da X-Forwarded-For)
uvicorn services.positions.main:app --host 0.0.0.0 --port 8002 --proxy-headers --env-file .env
```

Da sapere, perche' sono i tre inciampi piu' comuni:

- **`.env` e variabili d'ambiente.** `--env-file` NON sovrascrive le variabili gia'
  presenti nella shell: se hai un vecchio `export GTFS_RT_URL=...` (anche in `~/.bashrc`),
  vince quello. Controlla con `echo $GTFS_RT_URL`, e se serve `unset GTFS_RT_URL`.
- **Cambi al `.env`.** `--reload` ricarica solo i file `.py`: dopo aver modificato il
  `.env` riavvia uvicorn a mano (Ctrl+C e rilancio).
- **`403 accesso non consentito` da localhost.** Il gate IP ammette solo le reti in
  `RETI_AMMESSE` (`gates.py`: `10.0.0.0/8`, `172.16.0.0/12`). Per provare in locale serve
  aggiungere `127.0.0.0/8` (attenzione: `127.0.0.1/8` non e' valido, ha bit host impostati);
  non lasciarlo in produzione. Il User-Agent deve inoltre essere quello di un browser:
  `curl` e `python-requests` vengono rifiutati (`403 client non riconosciuto`).

Telegram è **opzionale**: senza `TELEGRAM_BOT_TOKEN` il servizio parte e serve
identico. Con il token, all'avvio parte il long polling (nessuna porta aperta).

## Endpoint

- `GET /vehicles[?linea=<id>]` → lista dei mezzi (`200`; header `X-Stale: true` se dalla cache).
- `GET /vehicles/{id}` → singolo mezzo (`404` se non c'è).
- `GET /health` → stato del servizio.

Feed giù: `200` + `X-Stale` se c'è cache, altrimenti `503` + `Retry-After`. Mai un `500` per un guasto a monte.

## Test

```bash
pip install -r requirements-dev.txt
./scripts/run_tests.sh              # oppure: python3 -m pytest -q
```

I test non toccano la rete: feed e IP sono mockati.

## Sicurezza — l'onestà che vale più del codice

L'allowlist di IP è un **filtro**, non una serratura: su un servizio davvero
esposto la difesa seria è l'autenticazione (token per i client, TLS mutuo tra
servizi). L'IP è il primo strato, non l'ultimo. Stesso principio sul bot: il
`chat_id` in allowlist è ciò che separa un aiuto da una console aperta a chiunque.
