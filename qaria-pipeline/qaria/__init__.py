"""
qaria — Pipeline qualità aria Milano (Sunday Coding, stagione S03 "La Pipeline Perfetta").

Pacchetto che implementa una pipeline di ingestion completa e funzionante,
costruita puntata dopo puntata nella serie. Tutti i moduli girano in locale,
senza servizi esterni a pagamento: Python, DuckDB in-process, cron.

Moduli (uno per puntata):
    ingest      — S03E01: scarica i dati grezzi dal portale CKAN di Milano
    validate    — S03E02: validazione schema + quarantena
    transform   — S03E03: tipizzazione, regole semantiche, join, pivot, AQI
    load        — S03E04: caricamento idempotente in DuckDB con upsert
    health      — S03E05: observability, metriche, alerting
    paths       — costanti condivise (cartelle, naming)
"""

__version__ = "1.0.0"
