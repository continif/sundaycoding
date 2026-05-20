"""
load.py — Loading & Destination (S03E04).

Carica i file transformed (Parquet) in DuckDB con strategia UPSERT,
e scrive un manifest in published/ per ogni file caricato.

Pattern chiave:
  - idempotenza via ON CONFLICT DO UPDATE su PRIMARY KEY (stazione_id, data)
  - tutto in transazione: niente stati intermedi visibili
  - layer published/ come marker (non copia) dei dati caricati
  - colonna loaded_at come provenance per il debugging
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from . import paths

log = logging.getLogger("load")

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS qaria_giornaliera (
    stazione_id              INTEGER NOT NULL,
    stazione_nome            VARCHAR,
    stazione_zona            VARCHAR,
    stazione_tipologia       VARCHAR,
    stazione_lat             DOUBLE,
    stazione_lon             DOUBLE,
    data                     DATE NOT NULL,
    benzene                  DOUBLE,
    monossido_carbonio       DOUBLE,
    biossido_azoto           DOUBLE,
    ozono                    DOUBLE,
    pm10                     DOUBLE,
    pm25                     DOUBLE,
    biossido_zolfo           DOUBLE,
    flag_fuori_range         BOOLEAN,
    flag_in_sospensione      BOOLEAN,
    aqi_livello              INTEGER,
    aqi_label                VARCHAR,
    aqi_inquinante_critico   VARCHAR,
    loaded_at                TIMESTAMP NOT NULL,
    PRIMARY KEY (stazione_id, data)
);
"""

# Colonne del transformed, nell'ordine atteso.
COLONNE = [
    "stazione_id", "stazione_nome", "stazione_zona", "stazione_tipologia",
    "stazione_lat", "stazione_lon", "data", "benzene", "monossido_carbonio",
    "biossido_azoto", "ozono", "pm10", "pm25", "biossido_zolfo",
    "flag_fuori_range", "flag_in_sospensione",
    "aqi_livello", "aqi_label", "aqi_inquinante_critico",
]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _connect_db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(paths.DB_PATH))
    con.execute(SCHEMA_DDL)
    return con


def _trova_da_caricare() -> list[Path]:
    """File transformed senza manifest in published/ (= non ancora caricati)."""
    tutti = sorted(paths.TRANSFORMED_DIR.glob("qaria_*.transformed.parquet"))
    da_caricare = []
    for tp in tutti:
        manifest = paths.PUBLISHED_DIR / f"{tp.stem}.published.json"
        if not manifest.exists():
            da_caricare.append(tp)
    log.info(f"File da caricare: {len(da_caricare)}/{len(tutti)}")
    return da_caricare


def _carica_in_db(con, parquet_path: Path, loaded_at: datetime) -> int:
    """Upsert di un singolo Parquet, dentro una transazione."""
    log.info(f"Carico in DB: {parquet_path.name}")

    # Costruisce le clausole di update per tutte le colonne tranne la PK.
    pk = {"stazione_id", "data"}
    update_set = ",\n                ".join(
        f"{c} = EXCLUDED.{c}" for c in COLONNE if c not in pk
    )
    select_cols = ", ".join(f"d.{c}" for c in COLONNE)

    con.execute("BEGIN TRANSACTION")
    try:
        # Contiamo le righe del Parquet PRIMA dell'upsert: DuckDB non
        # restituisce un rowcount affidabile per ON CONFLICT (torna -1),
        # quindi ce lo calcoliamo noi dal file sorgente. È il numero di
        # righe affette (tutte vengono o inserite o aggiornate).
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
        ).fetchone()[0]

        con.execute(f"""
            INSERT INTO qaria_giornaliera ({", ".join(COLONNE)}, loaded_at)
            SELECT {select_cols}, TIMESTAMP '{loaded_at.isoformat()}'
            FROM read_parquet('{parquet_path}') d
            ON CONFLICT (stazione_id, data) DO UPDATE SET
                {update_set},
                loaded_at = EXCLUDED.loaded_at
        """)
        con.execute("COMMIT")
        log.info(f"Caricate {n} righe (insert + update)")
        return n
    except Exception:
        con.execute("ROLLBACK")
        raise


def _scrivi_manifest(parquet_path: Path, n_righe: int, loaded_at: datetime) -> Path:
    """Manifest in published/: marker dei dati caricati (non copia)."""
    manifest_path = paths.PUBLISHED_DIR / f"{parquet_path.stem}.published.json"
    manifest = {
        "pipeline": paths.PIPELINE_NAME,
        "source_transformed": str(parquet_path),
        "loaded_at_utc": loaded_at.isoformat(),
        "rows_affected": n_righe,
        "target_table": "qaria_giornaliera",
        "target_db": str(paths.DB_PATH),
        "source_sha256": _sha256_file(parquet_path),
        "status": "ok",
    }
    # Scrittura atomica.
    tmp = manifest_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    tmp.replace(manifest_path)
    log.info(f"Manifest: {manifest_path.name}")
    return manifest_path


def run() -> dict:
    """Entry point del loading. Carica tutti i transformed non pubblicati."""
    paths.ensure_dirs()
    started_at = datetime.now(timezone.utc)

    da_caricare = _trova_da_caricare()
    if not da_caricare:
        log.info("Niente da caricare, tutti i transformed sono già pubblicati.")
        return {"status": "ok", "files_loaded": 0}

    con = _connect_db()
    risultati, errori = [], []

    for parquet_path in da_caricare:
        loaded_at = datetime.now(timezone.utc)
        try:
            n = _carica_in_db(con, parquet_path, loaded_at)
            _scrivi_manifest(parquet_path, n, loaded_at)
            risultati.append({"file": str(parquet_path), "rows": n})
        except Exception as e:
            log.error(f"Caricamento fallito per {parquet_path.name}: {e}")
            errori.append({"file": str(parquet_path), "error": str(e)})

    con.close()

    record = {
        "pipeline": paths.PIPELINE_NAME,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_db": str(paths.DB_PATH),
        "files_total": len(da_caricare),
        "files_ok": len(risultati),
        "files_failed": len(errori),
        "status": "ok" if not errori else "partial",
    }
    meta_path = paths.META_DIR / "loadings.jsonl"
    with meta_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    # Se TUTTI i file sono falliti, è un errore vero.
    if errori and not risultati:
        return {"status": "error", "kind": "duckdb_error",
                "msg": f"Tutti i {len(errori)} caricamenti falliti"}

    return {"status": "ok", "files_loaded": len(risultati),
            "files_failed": len(errori)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print(json.dumps(run(), indent=2, default=str))
