"""traffic — stato del traffico stradale (Città Metropolitana di Roma).

Fase 0: solo scheletro. GET /roads arriva in S04E03.
"""
from fastapi import FastAPI

app = FastAPI(title="traffic")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "traffic"}
