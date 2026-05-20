#!/usr/bin/env python
"""
run_pipeline.py — Orchestratore della pipeline qaria-milano (S03E06).

Esegue in sequenza i cinque strati, con:
  - singleton-writer: un solo run alla volta (lock file)
  - fail-fast: se uno strato fallisce, i successivi non partono
  - alerting integrato in caso di errore
  - observability finale non-bloccante

Uso:
    python run_pipeline.py

Schedulazione tipica con cron (vedi scripts/crontab.example):
    0 6 * * * cd /percorso/qaria-pipeline && .venv/bin/python run_pipeline.py
"""

import fcntl
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from qaria import ingest, validate, transform, load, health
from qaria import paths

log = logging.getLogger("orchestrator")

# Lock file. Usiamo una posizione scrivibile senza root: dentro data/.
LOCK_FILE = paths.DATA_DIR / ".qaria_pipeline.lock"


@contextmanager
def garantisci_singolo_processo():
    """
    Singleton-writer pattern: prende un lock esclusivo non-bloccante.
    Se un altro processo lo tiene, muore subito.
    (Vedi speciale pubblico 'Python e il mistero dei file scomparsi'.)
    """
    paths.ensure_dirs()
    lock_fd = LOCK_FILE.open("w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        yield
    except IOError:
        raise RuntimeError(
            f"Un'altra istanza della pipeline sta già girando (vedi {LOCK_FILE})."
        )
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()


def _get_alerter():
    try:
        from sundaycoding_alerting import get_chat
        return get_chat()
    except ImportError:
        class _LogOnly:
            def send(self, titolo, messaggio, livello="warning", chiave_dedup=None):
                log.warning(f"[ALERT {livello}] {titolo}: {messaggio}")
        return _LogOnly()


def run() -> int:
    """Esegue la pipeline completa. Ritorna 0 se ok, 1 se fallisce."""
    chat = _get_alerter()
    strati = [
        ("ingest", ingest.run),
        ("validate", validate.run),
        ("transform", transform.run),
        ("load", load.run),
    ]
    inizio = time.time()

    for nome, run_fn in strati:
        log.info(f"--- {nome} ---")
        try:
            risultato = run_fn()
        except Exception as e:
            log.exception(f"Eccezione non gestita in {nome}: {e}")
            chat.send(
                titolo=f"Pipeline qaria: {nome} ha sollevato un'eccezione",
                messaggio=f"Errore: {e}",
                livello="critical",
                chiave_dedup=f"qaria:orchestrator:{nome}:exception",
            )
            return 1

        if risultato.get("status") != "ok":
            kind = risultato.get("kind", "unknown")
            msg = risultato.get("msg", "(nessun dettaglio)")
            log.error(f"{nome} fallito: kind={kind}, msg={msg}")
            chat.send(
                titolo=f"Pipeline qaria: {nome} fallito ({kind})",
                messaggio=f"{msg}\nGli strati successivi NON sono partiti.",
                livello="warning",
                chiave_dedup=f"qaria:orchestrator:{nome}:{kind}",
            )
            return 1

        log.info(f"{nome} ok")

    # Observability finale: sempre eseguita, non-bloccante.
    log.info("--- observe ---")
    try:
        health.osserva_e_alerta()
    except Exception as e:
        log.exception(f"Observability fallita (non-bloccante): {e}")

    log.info(f"Pipeline completata in {time.time() - inizio:.1f}s")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    try:
        with garantisci_singolo_processo():
            sys.exit(run())
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(2)
