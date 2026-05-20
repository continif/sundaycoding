"""
test_pipeline.py — Test end-to-end della pipeline qaria.

Verifica che ogni strato funzioni e che la catena completa giri
senza errori, usando i dati sintetici generati dall'ingestion.

Lancia con: pytest tests/
"""

import sys
from pathlib import Path

# Aggiunge la root al path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from qaria import ingest, validate, transform, load, health, paths


@pytest.fixture(scope="module", autouse=True)
def setup_anagrafica():
    """Crea l'anagrafica stazioni prima dei test (serve a transform)."""
    paths.ensure_dirs()
    # Riusa lo script di bootstrap.
    from scripts.bootstrap import ANAGRAFICA
    paths.ANAGRAFICA_PATH.write_text(ANAGRAFICA, encoding="utf-8")
    yield


def test_01_ingest():
    """L'ingestion deve produrre un raw (sintetico se il CKAN non risponde)."""
    r = ingest.run()
    assert r["status"] == "ok"
    # Deve esserci almeno un file raw.
    raw_files = list(paths.RAW_DIR.glob("qaria_*.raw.csv"))
    assert len(raw_files) >= 1


def test_02_validate():
    """La validazione deve produrre un validated."""
    r = validate.run()
    assert r["status"] == "ok"
    assert r["rows_valid"] > 0
    validated = list(paths.VALIDATED_DIR.glob("qaria_*.validated.csv"))
    assert len(validated) >= 1


def test_03_transform():
    """La transformation deve produrre cleaned + transformed."""
    r = transform.run()
    assert r["status"] == "ok"
    assert r["rows_wide"] > 0
    transformed = list(paths.TRANSFORMED_DIR.glob("qaria_*.transformed.parquet"))
    assert len(transformed) >= 1


def test_04_load():
    """Il loading deve caricare in DuckDB e creare un manifest."""
    r = load.run()
    assert r["status"] == "ok"
    assert paths.DB_PATH.exists()
    manifest = list(paths.PUBLISHED_DIR.glob("*.published.json"))
    assert len(manifest) >= 1


def test_05_load_idempotente():
    """Rilanciare il load NON deve duplicare: i file sono già pubblicati."""
    r = load.run()
    assert r["status"] == "ok"
    assert r["files_loaded"] == 0  # niente da caricare, già fatto


def test_06_health():
    """L'observability deve girare e produrre un report."""
    r = health.osserva_e_alerta()
    assert "report" in r
    assert r["report"]["pipeline"] == "qaria-milano"
    # Deve aver visto almeno lo strato fetches.
    strati_presenti = [s for s in r["report"]["strati"] if s.get("presente")]
    assert len(strati_presenti) >= 1


def test_07_db_contiene_dati():
    """Il database finale deve contenere righe con AQI calcolato."""
    import duckdb
    con = duckdb.connect(str(paths.DB_PATH), read_only=True)
    n = con.execute("SELECT COUNT(*) FROM qaria_giornaliera").fetchone()[0]
    n_aqi = con.execute(
        "SELECT COUNT(*) FROM qaria_giornaliera WHERE aqi_livello IS NOT NULL"
    ).fetchone()[0]
    con.close()
    assert n > 0
    assert n_aqi > 0
