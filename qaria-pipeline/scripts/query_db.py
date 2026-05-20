#!/usr/bin/env python
"""
query_db.py — Esplora i dati caricati nel database DuckDB.

Mostra alcuni esempi di query sul risultato finale della pipeline.
Utile per verificare che tutto abbia funzionato.

Uso:
    python scripts/query_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from qaria import paths


def main():
    if not paths.DB_PATH.exists():
        print(f"Database non trovato: {paths.DB_PATH}")
        print("Lancia prima: python run_pipeline.py")
        return

    con = duckdb.connect(str(paths.DB_PATH), read_only=True)

    print("=" * 60)
    print("Conteggio righe totali nella tabella qaria_giornaliera:")
    n = con.execute("SELECT COUNT(*) FROM qaria_giornaliera").fetchone()[0]
    print(f"  {n} righe")

    print("=" * 60)
    print("Ultimo giorno disponibile, per stazione (AQI):")
    rows = con.execute("""
        SELECT stazione_nome, data, aqi_livello, aqi_label, aqi_inquinante_critico
        FROM qaria_giornaliera
        WHERE data = (SELECT MAX(data) FROM qaria_giornaliera)
        ORDER BY aqi_livello DESC
    """).fetchall()
    for r in rows:
        nome = r[0] or "(senza nome)"
        print(f"  {nome:35s} {r[1]} | AQI {r[2]} ({r[3]}) - critico: {r[4]}")

    print("=" * 60)
    print("Distribuzione dei livelli AQI su tutto lo storico:")
    rows = con.execute("""
        SELECT aqi_label, COUNT(*) AS n
        FROM qaria_giornaliera
        WHERE aqi_label IS NOT NULL
        GROUP BY aqi_label
        ORDER BY n DESC
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:12s} {r[1]} righe")

    con.close()
    print("=" * 60)


if __name__ == "__main__":
    main()
