"""
validate.py — Validazione schema + quarantena (S03E02).

Legge l'ultimo raw, valida lo SCHEMA (struttura, tipi, formati) con
Pandera, e separa le righe schema-valide (-> validated/) da quelle
schema-sporche (-> quarantine/).

Pattern chiave:
  - validazione schema-level, NON semantica (quella è in transform, S03E03)
  - quarantena invece di scarto: le righe storte si conservano
  - soglia di quarantena: se troppe righe sono sporche, è un problema sistemico
  - metadata JSONL: validations.jsonl
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pandera.pandas as pa
from pandera.pandas import Column, DataFrameSchema, Check

from . import paths

log = logging.getLogger("validate")

# Soglia: se più del 10% delle righe finisce in quarantena, è un segnale
# che qualcosa è cambiato a monte (sorgente, formato). Fail esplicito.
QUARANTINE_THRESHOLD_PCT = 10.0

# Inquinanti attesi nel dataset.
INQUINANTI_VALIDI = {"C6H6", "CO_8h", "NO2", "O3", "PM10", "PM25", "SO2"}

# Schema Pandera: descrive come DEVE essere una riga valida.
# lazy=True fa raccogliere TUTTI gli errori invece di fermarsi al primo.
SCHEMA = DataFrameSchema(
    {
        # stazione_id: stringa di sole cifre (la converto a int in transform)
        "stazione_id": Column(
            str,
            checks=Check.str_matches(r"^\d+$"),
            nullable=False,
        ),
        # data: formato ISO YYYY-MM-DD
        "data": Column(
            str,
            checks=Check.str_matches(r"^\d{4}-\d{2}-\d{2}$"),
            nullable=False,
        ),
        # inquinante: deve essere uno dei valori noti
        "inquinante": Column(
            str,
            checks=Check.isin(INQUINANTI_VALIDI),
            nullable=False,
        ),
        # valore: stringa che rappresenta un float (o stringa vuota = missing)
        "valore": Column(
            str,
            checks=Check(
                lambda s: s.str.match(r"^-?\d*\.?\d*$"),
                element_wise=False,
            ),
            nullable=True,
        ),
    },
    strict=True,  # rifiuta colonne extra non dichiarate
    coerce=False,  # NON convertire i tipi: lo facciamo noi in transform
)


def _carica_raw_piu_recente() -> tuple[pd.DataFrame, Path]:
    """Carica il raw più recente per nome (lessicografico = cronologico)."""
    files = sorted(paths.RAW_DIR.glob("qaria_*.raw.csv"))
    if not files:
        raise FileNotFoundError(f"Nessun file raw in {paths.RAW_DIR}")
    latest = files[-1]
    log.info(f"Carico raw: {latest.name}")
    # dtype=str: leggiamo tutto come stringa, le conversioni in transform.
    df = pd.read_csv(latest, sep=";", dtype=str, keep_default_na=False)
    return df, latest


def _valida_riga_per_riga(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Valida ogni riga contro lo schema. Ritorna (valide, sporche).

    Strategia: uso Pandera in modalità lazy per raccogliere gli indici
    delle righe che falliscono, poi splitto il DataFrame.
    """
    try:
        SCHEMA.validate(df, lazy=True)
        # Nessun errore: tutte valide.
        return df.copy(), df.iloc[0:0].copy()
    except pa.errors.SchemaErrors as err:
        # err.failure_cases contiene gli indici delle righe fallite.
        indici_sporchi = set(err.failure_cases["index"].dropna().astype(int))
        mask_sporche = df.index.isin(indici_sporchi)
        valide = df[~mask_sporche].copy()
        sporche = df[mask_sporche].copy()
        return valide, sporche


def run() -> dict:
    """Entry point della validazione."""
    paths.ensure_dirs()
    ts = datetime.now(timezone.utc)

    try:
        df, raw_path = _carica_raw_piu_recente()
        n_totali = len(df)

        valide, sporche = _valida_riga_per_riga(df)
        n_sporche = len(sporche)
        pct_sporche = (n_sporche / n_totali * 100) if n_totali else 0.0

        # Naming a catena: eredito lo stem del raw.
        stem = raw_path.stem.replace(".raw", "")

        # Salva le valide.
        validated_path = paths.VALIDATED_DIR / f"{stem}.validated.csv"
        valide.to_csv(validated_path, sep=";", index=False)
        log.info(f"Validated: {validated_path.name} ({len(valide)} righe)")

        # Salva le sporche in quarantena (se ce ne sono).
        if n_sporche > 0:
            quarantine_path = paths.QUARANTINE_DIR / f"{stem}.quarantine.csv"
            sporche.to_csv(quarantine_path, sep=";", index=False)
            log.warning(f"Quarantena: {n_sporche} righe ({pct_sporche:.1f}%)")

        # Audit JSONL
        record = {
            "pipeline": paths.PIPELINE_NAME,
            "validation_ts_utc": ts.isoformat(),
            "input_raw": str(raw_path),
            "validated_path": str(validated_path),
            "rows_total": n_totali,
            "rows_valid": len(valide),
            "rows_quarantine": n_sporche,
            "quarantine_pct": round(pct_sporche, 2),
            "status": "ok",
        }
        meta_path = paths.META_DIR / "validations.jsonl"
        with meta_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # Soglia: troppe righe sporche = problema sistemico.
        if pct_sporche > QUARANTINE_THRESHOLD_PCT:
            log.error(f"Troppi dati in quarantena: {pct_sporche:.1f}%")
            return {
                "status": "error",
                "kind": "quarantine_threshold",
                "msg": f"{pct_sporche:.1f}% di righe in quarantena "
                       f"(soglia {QUARANTINE_THRESHOLD_PCT}%)",
            }

        return {
            "status": "ok",
            "validated_path": str(validated_path),
            "rows_valid": len(valide),
            "rows_quarantine": n_sporche,
        }

    except FileNotFoundError as e:
        log.error(f"Input mancante: {e}")
        return {"status": "error", "kind": "no_input", "msg": str(e)}
    except Exception as e:
        log.exception(f"Errore imprevisto in validazione: {e}")
        return {"status": "error", "kind": "unknown", "msg": str(e)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print(json.dumps(run(), indent=2, default=str))
