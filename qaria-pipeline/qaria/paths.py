"""
paths.py — Costanti condivise della pipeline qaria.

Raccoglie in un solo posto tutti i path delle cartelle e la naming
convention. Modificando qui, modifichi ovunque. È la "tabella di dominio"
strutturale della pipeline.
"""

from pathlib import Path

# Radice del progetto: due livelli sopra questo file (qaria/paths.py -> root).
ROOT = Path(__file__).resolve().parent.parent

# La catena di custodia: ogni cartella è uno stadio della pipeline.
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"                # S03E01: bytes grezzi immutabili
VALIDATED_DIR = DATA_DIR / "validated"    # S03E02: schema-clean
QUARANTINE_DIR = DATA_DIR / "quarantine"  # S03E02: righe schema-sporche
CLEANED_DIR = DATA_DIR / "cleaned"        # S03E03 fase 1: tipizzato + filtrato
TRANSFORMED_DIR = DATA_DIR / "transformed"  # S03E03 fase 2: arricchito
PUBLISHED_DIR = DATA_DIR / "published"    # S03E04: manifest dei dati caricati
REFERENCE_DIR = DATA_DIR / "reference"    # anagrafica stazioni
META_DIR = DATA_DIR / "metadata"          # audit JSONL di tutti gli strati

# Database di destinazione (S03E04). DuckDB è in-process: un singolo file.
DB_PATH = DATA_DIR / "qaria.duckdb"

# Anagrafica delle stazioni (scaricata a parte, vedi scripts/bootstrap.py)
ANAGRAFICA_PATH = REFERENCE_DIR / "stazioni_milano.csv"

# Nome della pipeline, usato in tutti i record di metadata.
PIPELINE_NAME = "qaria-milano"


def ensure_dirs() -> None:
    """Crea tutte le cartelle della catena di custodia se non esistono."""
    for d in (
        RAW_DIR, VALIDATED_DIR, QUARANTINE_DIR, CLEANED_DIR,
        TRANSFORMED_DIR, PUBLISHED_DIR, REFERENCE_DIR, META_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)
