"""
transform.py — Transformation & Processing (S03E03).

Legge l'ultimo validated, applica:
  - conversione tipi (stringa -> int/date/float)
  - validazione semantica (zeri sentinel, range fisici, calendario)
  - salva il cleaned (formato long, tipizzato, flaggato)
  - join con anagrafica stazioni via DuckDB
  - pivot long -> wide
  - calcolo AQI semplificato (EAQI)
  - salva il transformed in Parquet

Pattern chiave:
  - due layer: cleaned/ (analyst-friendly) e transformed/ (production)
  - tabella di dominio: numeri di business in costanti, non hardcoded
  - flaggare invece di cancellare: conserva l'informazione
  - DuckDB per il join: SQL leggibile su file
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from . import paths

log = logging.getLogger("transform")

# --- Tabella di dominio: range fisici plausibili (NON soglie di legge) ---
RANGE_PLAUSIBILI = {
    "C6H6": (0.0, 50.0),
    "CO_8h": (0.0, 30.0),
    "NO2": (0.0, 500.0),
    "O3": (0.0, 400.0),
    "PM10": (0.0, 1000.0),
    "PM25": (0.0, 800.0),
    "SO2": (0.0, 300.0),
}

# Inquinanti per cui 0 è SENTINEL (sensore rotto), non misura reale.
ZERO_E_SENTINEL = {"C6H6", "CO_8h", "NO2", "SO2", "O3"}

# Sospensione stagionale del monitoraggio del Comune di Milano.
SOSPENSIONE_INIZIO = (4, 1)   # 1 aprile
SOSPENSIONE_FINE = (9, 30)    # 30 settembre

# Soglie AQI semplificato (livelli 1-5), fonte EAQI europeo.
SOGLIE_AQI = {
    "pm10": [(20, 1), (40, 2), (50, 3), (100, 4), (float("inf"), 5)],
    "pm25": [(10, 1), (20, 2), (25, 3), (50, 4), (float("inf"), 5)],
    "biossido_azoto": [(40, 1), (90, 2), (120, 3), (230, 4), (float("inf"), 5)],
    "ozono": [(50, 1), (100, 2), (130, 3), (240, 4), (float("inf"), 5)],
    "biossido_zolfo": [(100, 1), (200, 2), (350, 3), (500, 4), (float("inf"), 5)],
}

LIVELLO_LABEL = {1: "Buona", 2: "Discreta", 3: "Moderata", 4: "Cattiva", 5: "Pessima"}

RINOMINA_INQUINANTI = {
    "C6H6": "benzene",
    "CO_8h": "monossido_carbonio",
    "NO2": "biossido_azoto",
    "O3": "ozono",
    "PM10": "pm10",
    "PM25": "pm25",
    "SO2": "biossido_zolfo",
}


def _in_sospensione_stagionale(data: pd.Timestamp) -> bool:
    """True se la data cade nel periodo di sospensione (mese, giorno)."""
    return SOSPENSIONE_INIZIO <= (data.month, data.day) <= SOSPENSIONE_FINE


def _carica_validated_piu_recente() -> tuple[pd.DataFrame, Path]:
    files = sorted(paths.VALIDATED_DIR.glob("qaria_*.validated.csv"))
    if not files:
        raise FileNotFoundError(f"Nessun file validated in {paths.VALIDATED_DIR}")
    latest = files[-1]
    log.info(f"Carico validated: {latest.name}")
    df = pd.read_csv(latest, sep=";", dtype=str, keep_default_na=False)
    return df, latest


def _converti_tipi(df: pd.DataFrame) -> pd.DataFrame:
    """Converte le stringhe nei tipi finali. errors='coerce' + assert."""
    df = df.copy()
    df["stazione_id"] = df["stazione_id"].astype(int)
    df["data"] = pd.to_datetime(df["data"], format="%Y-%m-%d", errors="coerce")
    df["valore"] = pd.to_numeric(df["valore"], errors="coerce")
    assert df["data"].notna().all(), "Bug: date NaT post-conversione"
    return df


def _applica_regole_semantiche(df: pd.DataFrame) -> pd.DataFrame:
    """Tre regole di dominio: zeri sentinel, range fisici, sospensione."""
    df = df.copy()

    # Regola 1: zeri sentinel -> NaN
    mask_zero = df["inquinante"].isin(ZERO_E_SENTINEL) & (df["valore"] == 0.0)
    df.loc[mask_zero, "valore"] = pd.NA
    log.info(f"Zeri sentinel convertiti a NA: {int(mask_zero.sum())}")

    # Regola 2: flag fuori_range
    fuori = pd.Series(False, index=df.index)
    for inq, (vmin, vmax) in RANGE_PLAUSIBILI.items():
        m = df["inquinante"] == inq
        fuori |= m & ((df["valore"] < vmin) | (df["valore"] > vmax))
    df["flag_fuori_range"] = fuori
    log.info(f"Valori fuori range flaggati: {int(fuori.sum())}")

    # Regola 3: flag sospensione stagionale
    df["flag_in_sospensione"] = df["data"].apply(_in_sospensione_stagionale)

    return df


def _salva_cleaned(df: pd.DataFrame, input_path: Path) -> Path:
    stem = input_path.stem.replace(".validated", "")
    out = paths.CLEANED_DIR / f"{stem}.cleaned.csv"
    df.to_csv(out, sep=";", index=False)
    log.info(f"Cleaned: {out.name} ({len(df)} righe)")
    return out


def _join_con_anagrafica(cleaned_path: Path) -> pd.DataFrame:
    """Join del cleaned con l'anagrafica stazioni via DuckDB (in-memory)."""
    if not paths.ANAGRAFICA_PATH.exists():
        raise FileNotFoundError(
            f"Anagrafica mancante: {paths.ANAGRAFICA_PATH}. "
            f"Lancia prima: python scripts/bootstrap.py"
        )
    con = duckdb.connect(":memory:")
    query = f"""
        SELECT
            d.stazione_id,
            a.nome AS stazione_nome,
            a.zona AS stazione_zona,
            a.tipologia AS stazione_tipologia,
            a.latitudine AS stazione_lat,
            a.longitudine AS stazione_lon,
            d.data, d.inquinante, d.valore,
            d.flag_fuori_range, d.flag_in_sospensione
        FROM read_csv_auto('{cleaned_path}', delim=';', header=true) d
        LEFT JOIN read_csv_auto('{paths.ANAGRAFICA_PATH}', delim=';', header=true) a
            ON d.stazione_id = a.stazione_id
        ORDER BY d.data, d.stazione_id, d.inquinante
    """
    df = con.execute(query).df()
    con.close()
    unmatched = df["stazione_nome"].isna().sum()
    if unmatched > 0:
        mancanti = df[df["stazione_nome"].isna()]["stazione_id"].unique().tolist()
        log.warning(f"{unmatched} righe senza match in anagrafica. Stazioni: {mancanti}")
    log.info(f"Join completato: {len(df)} righe")
    return df


def _pivot_long_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Da long (una misura per riga) a wide (una riga per stazione/giorno)."""
    index_cols = [
        "stazione_id", "stazione_nome", "stazione_zona",
        "stazione_tipologia", "stazione_lat", "stazione_lon", "data",
    ]
    df_wide = df.pivot_table(
        index=index_cols, columns="inquinante", values="valore", aggfunc="first",
    ).reset_index()

    flags = df.groupby(index_cols).agg(
        {"flag_fuori_range": "any", "flag_in_sospensione": "any"}
    ).reset_index()
    df_wide = df_wide.merge(flags, on=index_cols, how="left")
    df_wide = df_wide.rename(columns=RINOMINA_INQUINANTI)
    log.info(f"Pivot completato: {len(df_wide)} righe wide")
    return df_wide


def _livello_inquinante(valore, soglie) -> int | None:
    if pd.isna(valore):
        return None
    for soglia, livello in soglie:
        if valore <= soglia:
            return livello
    return 5


def _calcola_aqi(df_wide: pd.DataFrame) -> pd.DataFrame:
    """AQI = MAX dei sub-indici dei singoli inquinanti misurati."""
    df_wide = df_wide.copy()
    sub = pd.DataFrame(index=df_wide.index)
    for inq, soglie in SOGLIE_AQI.items():
        if inq in df_wide.columns:
            sub[inq] = df_wide[inq].apply(lambda v: _livello_inquinante(v, soglie))

    df_wide["aqi_livello"] = sub.max(axis=1, skipna=True)
    df_wide["aqi_label"] = df_wide["aqi_livello"].map(LIVELLO_LABEL)
    # In caso di parità tra inquinanti, idxmax prende il primo per colonna.
    df_wide["aqi_inquinante_critico"] = sub.idxmax(axis=1)
    return df_wide


def _salva_transformed(df_wide: pd.DataFrame, input_path: Path) -> Path:
    stem = input_path.stem.replace(".validated", "").replace(".cleaned", "")
    out = paths.TRANSFORMED_DIR / f"{stem}.transformed.parquet"
    df_wide.to_parquet(out, engine="pyarrow", compression="snappy")
    log.info(f"Transformed: {out.name} ({len(df_wide)} righe)")
    return out


def run() -> dict:
    """Entry point della transformation."""
    paths.ensure_dirs()
    ts = datetime.now(timezone.utc)

    try:
        df, validated_path = _carica_validated_piu_recente()

        # Fase 1: cleaned (tipi + semantica)
        df = _converti_tipi(df)
        df = _applica_regole_semantiche(df)
        cleaned_path = _salva_cleaned(df, validated_path)

        # Fase 2: transformed (join + pivot + AQI)
        df_joined = _join_con_anagrafica(cleaned_path)
        df_wide = _pivot_long_to_wide(df_joined)
        df_wide = _calcola_aqi(df_wide)
        transformed_path = _salva_transformed(df_wide, validated_path)

        record = {
            "pipeline": paths.PIPELINE_NAME,
            "transformation_ts_utc": ts.isoformat(),
            "input_validated": str(validated_path),
            "cleaned_path": str(cleaned_path),
            "transformed_path": str(transformed_path),
            "rows_input": len(df),
            "rows_wide": len(df_wide),
            "rows_flagged_fuori_range": int(df["flag_fuori_range"].sum()),
            "rows_in_sospensione": int(df["flag_in_sospensione"].sum()),
            "status": "ok",
        }
        meta_path = paths.META_DIR / "transformations.jsonl"
        with meta_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

        return {
            "status": "ok",
            "cleaned_path": str(cleaned_path),
            "transformed_path": str(transformed_path),
            "rows_wide": len(df_wide),
        }

    except FileNotFoundError as e:
        log.error(f"Input mancante: {e}")
        return {"status": "error", "kind": "no_input", "msg": str(e)}
    except duckdb.Error as e:
        log.exception(f"Errore DuckDB: {e}")
        return {"status": "error", "kind": "duckdb_error", "msg": str(e)}
    except AssertionError as e:
        log.exception(f"Assertion fallita: {e}")
        return {"status": "error", "kind": "consistency_bug", "msg": str(e)}
    except Exception as e:
        log.exception(f"Errore imprevisto: {e}")
        return {"status": "error", "kind": "unknown", "msg": str(e)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print(json.dumps(run(), indent=2, default=str))
