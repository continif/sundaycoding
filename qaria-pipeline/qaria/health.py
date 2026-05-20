"""
health.py — Observability (S03E05).

Legge i metadata JSONL prodotti dagli strati precedenti e ne ricava
un report di salute. Alerta se qualcosa è anomalo, evitando falsi
positivi (silenzio atteso) e duplicati.

Pattern chiave:
  - metriche da JSONL: filesystem come fonte di verità, niente TSDB
  - resilienza ai dati corrotti: una riga rotta non azzera la visibilità
  - calendario di silenzio atteso: weekend, festività, sospensione stagionale
  - alerting via SundayCodingAlerting (FakeChat di default, no setup richiesto)
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pandas as pd

from . import paths

log = logging.getLogger("health")

# Soglie di anomalia (il "contratto di salute" della pipeline).
SUCCESS_RATE_MINIMO = 0.90
ORE_MAX_SENZA_OK = 36

# Mappa strato -> nome colonna timestamp (ogni strato ha la sua convenzione).
TS_COL = {
    "fetches": "fetch_ts_utc",
    "validations": "validation_ts_utc",
    "transformations": "transformation_ts_utc",
    "loadings": "started_at_utc",
}


def _carica_jsonl(nome: str) -> pd.DataFrame:
    """Carica un JSONL come DataFrame, tollerando righe corrotte."""
    path = paths.META_DIR / f"{nome}.jsonl"
    if not path.exists():
        return pd.DataFrame()
    records = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.error(f"{path.name}:{n} riga corrotta saltata: {e}")
    return pd.DataFrame(records)


def _metriche_strato(nome: str, giorni: int = 7) -> dict[str, Any]:
    df = _carica_jsonl(nome)
    if df.empty:
        return {"strato": nome, "presente": False}

    ts_col = TS_COL[nome]
    df[ts_col] = pd.to_datetime(df[ts_col], format="ISO8601", utc=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=giorni)
    recenti = df[df[ts_col] >= cutoff]

    n_tot = len(recenti)
    n_ok = int((recenti["status"] == "ok").sum())
    success_rate = n_ok / n_tot if n_tot else 0.0
    ok_rows = recenti[recenti["status"] == "ok"]
    last_ok = ok_rows[ts_col].max() if not ok_rows.empty else None

    return {
        "strato": nome,
        "presente": True,
        "n_run_totali": n_tot,
        "n_run_ok": n_ok,
        "success_rate": round(success_rate, 3),
        "ultimo_run_ok_utc": last_ok.isoformat() if last_ok is not None else None,
    }


def _giorno_silenzio_atteso(d: date) -> bool:
    """True se in questa data NON ci si aspetta dati (no alert su assenza)."""
    if d.weekday() >= 5:  # weekend
        return True
    if (4, 1) <= (d.month, d.day) <= (9, 30):  # sospensione stagionale
        return True
    festivita = {
        (1, 1), (1, 6), (4, 25), (5, 1), (6, 2),
        (8, 15), (11, 1), (12, 8), (12, 25), (12, 26),
    }
    return (d.month, d.day) in festivita


def health_report() -> dict[str, Any]:
    """Riepilogo di salute di tutti gli strati."""
    return {
        "pipeline": paths.PIPELINE_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strati": [_metriche_strato(s) for s in TS_COL.keys()],
    }


# --- Deduplicazione degli alert ---
ALERTS_LOG = paths.META_DIR / "alerts_sent.jsonl"


def _alert_gia_inviato(chiave: str, finestra_ore: int = 6) -> bool:
    if not ALERTS_LOG.exists():
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=finestra_ore)
    with ALERTS_LOG.open(encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec["chiave"] != chiave:
                    continue
                if datetime.fromisoformat(rec["ts_utc"]) >= cutoff:
                    return True
            except (json.JSONDecodeError, KeyError):
                continue
    return False


def _registra_alert(chiave: str) -> None:
    rec = {"chiave": chiave, "ts_utc": datetime.now(timezone.utc).isoformat()}
    with ALERTS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _get_alerter():
    """
    Ritorna un alerter. Usa SundayCodingAlerting se installato,
    altrimenti un fallback minimale che logga soltanto.
    """
    try:
        from sundaycoding_alerting import get_chat
        return get_chat()
    except ImportError:
        log.info("SundayCodingAlerting non installato, alert solo nei log.")

        class _LogOnlyAlerter:
            def send(self, titolo, messaggio, livello="warning", chiave_dedup=None):
                log.warning(f"[ALERT {livello}] {titolo}: {messaggio}")
                return {"status": "logged"}

        return _LogOnlyAlerter()


def osserva_e_alerta() -> dict:
    """Entry point dell'observability. Legge le metriche, alerta le anomalie."""
    paths.ensure_dirs()
    report = health_report()
    chat = _get_alerter()
    alert_inviati = []

    oggi = datetime.now(timezone.utc).date()
    silenzio_atteso = _giorno_silenzio_atteso(oggi)

    for info in report["strati"]:
        if not info.get("presente"):
            continue
        strato = info["strato"]

        # Check 1: success rate basso
        if info["success_rate"] < SUCCESS_RATE_MINIMO:
            chiave = f"{strato}:success_rate_low"
            if not _alert_gia_inviato(chiave):
                chat.send(
                    titolo=f"Strato {strato}: success rate basso",
                    messaggio=f"Success rate {info['success_rate']:.0%} "
                              f"(soglia {SUCCESS_RATE_MINIMO:.0%}). "
                              f"Run ok: {info['n_run_ok']}/{info['n_run_totali']}.",
                    livello="warning",
                    chiave_dedup=chiave,
                )
                _registra_alert(chiave)
                alert_inviati.append(chiave)

        # Check 2: silenzio prolungato (solo se NON è silenzio atteso)
        if not silenzio_atteso and info["ultimo_run_ok_utc"]:
            last_ok = datetime.fromisoformat(info["ultimo_run_ok_utc"])
            ore = (datetime.now(timezone.utc) - last_ok).total_seconds() / 3600
            if ore > ORE_MAX_SENZA_OK:
                chiave = f"{strato}:silent_too_long"
                if not _alert_gia_inviato(chiave):
                    chat.send(
                        titolo=f"Strato {strato}: silenzio prolungato",
                        messaggio=f"Nessun run ok da {ore:.1f} ore "
                                  f"(soglia {ORE_MAX_SENZA_OK}h).",
                        livello="critical",
                        chiave_dedup=chiave,
                    )
                    _registra_alert(chiave)
                    alert_inviati.append(chiave)

    # Audit
    record = {
        "pipeline": paths.PIPELINE_NAME,
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "silenzio_atteso_oggi": silenzio_atteso,
        "alert_inviati": alert_inviati,
        "report": report,
    }
    meta_path = paths.META_DIR / "observability_runs.jsonl"
    with meta_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    return record


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print(json.dumps(osserva_e_alerta(), indent=2, default=str))
