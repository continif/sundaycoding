"""positions — servizio posizioni mezzi (GTFS-RT).

Fase 0: solo scheletro. GET /vehicles arriva in S04E02.
Vincolo (vedi CLAUDE.md nested): questo servizio NON accede al database.
"""
from fastapi import FastAPI

app = FastAPI(title="positions")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "positions"}
