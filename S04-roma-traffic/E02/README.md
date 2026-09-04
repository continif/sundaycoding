# roma-traffic

Microservizi **FastAPI + uvicorn** che servono gli open data del traffico e del trasporto
pubblico di Roma su una intranet locale, costruiti con **Claude Code** configurato in modo
"diffidente": ogni servizio fa solo ciò per cui è nato, e non un byte di più.

Parte della serie **Sunday Coding — S04 "Il Microservizio Diffidente"**.
- Teoria (free): *Montiamo Claude Code come si deve!*
- Setup del progetto (paid): *S04E01 — Il Microservizio Diffidente. Montiamo l'officina*

## Struttura
- `.claude/` — configurazione di Claude Code: `settings.json` (permessi deny-first + hook
  anti-segreti), `memory/` (contratti dei componenti), `commands/`, `agents/`, `skills/`, `hooks/`.
- `scripts/` — script canonici e deterministici (test, query DB read-only, fetch feed).
- `services/` — i microservizi. Un servizio = un processo uvicorn = un solo compito.
- `tests/` — suite a piramide (unit / integration / contract / e2e).
- `feeds/allowlist.txt` — la lista chiusa degli host consentiti in uscita.

## Avvio rapido
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp CLAUDE.local.md.example CLAUDE.local.md    # note personali, restano fuori da git
./scripts/run_tests.sh all ci
```

## Sicurezza
I segreti vanno in `secrets/` (ignorata da git). L'hook `.claude/hooks/no-secrets.sh` impedisce
a Claude Code di leggerli anche via Bash. La query al DB usa un utente **read-only**
(`$DATABASE_URL_RO`), mai il superuser.

## Nota
Stato: **fine E02** — `positions` espone `GET /vehicles`, `GET /vehicles/{id}`, `GET /health`
(cache in-memory, gestione feed vuoto/timeout, parsing GTFS-RT con HasField). Serve la variabile
`GTFS_RT_URL`. Scegli una licenza prima di pubblicare.
