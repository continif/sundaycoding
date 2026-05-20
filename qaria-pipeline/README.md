# qaria-pipeline — La Pipeline Perfetta

Companion code della serie **[La Pipeline Perfetta (S03)](https://sundaycoding.substack.com)** del **Sunday Coding**: una pipeline di ingestion dati completa, funzionante, e che gira interamente **sul tuo computer** senza dipendere da servizi esterni a pagamento.

Il dato di esempio è la **qualità dell'aria di Milano**. La pipeline lo scarica, lo valida, lo trasforma, lo arricchisce con un indice AQI, lo carica in un database, e si auto-monitora.

> 📰 Ogni modulo di questo repository è spiegato passo passo in una puntata della serie. Se vuoi capire **perché** le cose sono fatte così e non in un altro modo, leggi le newsletter. Questo repo è il codice; le newsletter sono il ragionamento.

---

## Cosa serve

Solo **Python 3.10+**. Niente Docker obbligatorio, niente account cloud, niente Airflow da installare. Il database è **DuckDB**, che è in-process: un singolo file, nessun server da avviare.

Le dipendenze (pandas, pandera, duckdb, pyarrow, requests) sono tutte open source e installabili con pip.

---

## Quickstart (tre comandi)

```bash
# 1. Installa il pacchetto e le dipendenze
pip install -e .

# 2. Prepara i dati di riferimento (anagrafica stazioni)
python scripts/bootstrap.py

# 3. Lancia la pipeline completa
python run_pipeline.py
```

Fatto. La pipeline ha scaricato i dati (o generato dati sintetici realistici se il portale non risponde), li ha validati, trasformati, e caricati in `data/qaria.duckdb`.

Per vedere il risultato:

```bash
python scripts/query_db.py
```

Output di esempio:

```
Ultimo giorno disponibile, per stazione (AQI):
  Milano - Marche               2026-05-20 | AQI 4 (Cattiva) - critico: pm25
  Milano - Pascal Città Studi   2026-05-20 | AQI 3 (Moderata) - critico: pm10
  ...
```

---

## I cinque strati (una puntata ciascuno)

La pipeline è una catena di cinque moduli Python, ognuno con una responsabilità precisa. Ogni modulo ha una funzione `run()` ed è lanciabile in autonomia (`python -m qaria.ingest`).

**`qaria/ingest.py` — Ingestion (S03E01).** Scarica i dati grezzi dal portale CKAN di Milano e li salva nel layer `raw/` in modo immutabile e atomico (file `.tmp` + rename + fsync). Se il portale non risponde, genera dati sintetici realistici così la pipeline gira comunque. Naming a catena: `qaria_<timestamp>_<hash8>.raw.csv`.

**`qaria/validate.py` — Validation (S03E02).** Valida lo *schema* (struttura, tipi, formati) con Pandera. Le righe valide vanno in `validated/`, quelle storte in `quarantine/`. Se troppe righe finiscono in quarantena (oltre il 10%), è un segnale di problema sistemico e la pipeline si ferma.

**`qaria/transform.py` — Transformation (S03E03).** Il cuore del dominio applicativo. Converte i tipi, applica le regole semantiche (zeri sentinel della stazione 6, range fisici plausibili, sospensione stagionale), joina con l'anagrafica stazioni via DuckDB, pivota da long a wide, calcola l'AQI. Produce due layer: `cleaned/` (analyst-friendly) e `transformed/` (production, Parquet).

**`qaria/load.py` — Loading (S03E04).** Carica i Parquet in DuckDB con strategia **upsert** (`ON CONFLICT DO UPDATE`), idempotente per chiave `(stazione_id, data)`. Scrive un manifest in `published/` per ogni file caricato.

**`qaria/health.py` — Observability (S03E05).** Legge tutti i metadata JSONL prodotti dagli strati e ne ricava un report di salute. Alerta le anomalie (success rate basso, silenzio prolungato) evitando falsi positivi (calendario di silenzio atteso) e duplicati (deduplicazione temporale).

**`run_pipeline.py` — Orchestration (S03E06).** Mette tutto insieme: singleton-writer (un solo run alla volta), fail-fast (se uno strato fallisce, i successivi non partono), alerting integrato. È quello che cron lancia ogni mattina.

---

## La catena di custodia

Ogni file ha un parente diretto nello stadio precedente, identificabile dal nome. La pipeline si auto-documenta: niente database di stato, solo file e naming.

```
data/
├── raw/           ← S03E01: bytes grezzi immutabili
├── validated/     ← S03E02: schema-clean
├── quarantine/    ← S03E02: righe schema-sporche
├── cleaned/       ← S03E03 fase 1: tipizzato + flaggato
├── transformed/   ← S03E03 fase 2: arricchito (Parquet)
├── published/     ← S03E04: manifest dei dati caricati
├── reference/     ← anagrafica stazioni
├── metadata/      ← audit JSONL di tutti gli strati
└── qaria.duckdb   ← il database finale
```

Dato un file `qaria_2026-05-20T06-00-00_a3f12b8c.transformed.parquet`, risali al validated, al raw, e ai metadata del fetch. Solo guardando il nome.

---

## Idempotenza e backfill

Ogni strato è idempotente: rilanciare la pipeline due volte è sempre sicuro. Questo rende il **backfill** una proprietà emergente. Per rifare un giorno:

```bash
# Cancella il marker del giorno che vuoi rielaborare
rm data/published/qaria_2026-05-20*.published.json
# Rilancia: la pipeline si accorge che manca e lo rifà
python run_pipeline.py
```

Niente strumento dedicato. Solo la conseguenza di scelte di design corrette.

---

## Schedulazione con cron

Per far girare la pipeline ogni giorno automaticamente, vedi `scripts/crontab.example`. In sintesi:

```cron
0 6 * * * cd /percorso/qaria-pipeline && .venv/bin/python run_pipeline.py >> data/qaria.log 2>&1
```

---

## Alerting (opzionale)

La pipeline può notificarti su Telegram o Google Chat quando qualcosa si rompe, tramite la libreria companion [`sundaycoding-alerting`](https://github.com/continif/sundaycoding-alerting):

```bash
pip install -e ".[alerting]"
export TELEGRAM_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

Senza la libreria (o senza variabili d'ambiente), gli alert finiscono semplicemente nei log. La pipeline funziona lo stesso.

---

## Test

```bash
pip install -e ".[dev]"
pytest tests/
```

I test fanno girare la pipeline completa end-to-end sui dati sintetici e verificano ogni strato.

---

## Dati reali vs sintetici

Di default, `ingest.py` tenta di scaricare dal portale CKAN di Milano. Se il portale non risponde (o il `resource_id` è cambiato), genera **dati sintetici realistici** che includono i casi difficili che la pipeline deve saper gestire (zeri sentinel, formato long, più stazioni e inquinanti). Questo garantisce che il lettore possa vedere tutta la pipeline funzionare anche offline o se il dataset reale è cambiato.

---

## Licenza

MIT. Fai quello che vuoi, basta che non lo spacci per tuo.

---

*Por fin, una pipeline che gira da sola, dorme la notte, e sveglia te solo quando serve davvero.*

📬 [Sunday Coding su Substack](https://sundaycoding.substack.com)
