"""Le due cose che valuta.py e chunking.py condividono: le query e la posizione."""

from __future__ import annotations

import json
from pathlib import Path

FILE = Path(__file__).resolve().parent / "valutazione.json"


def carica_query() -> list[dict]:
    return json.loads(FILE.read_text(encoding="utf-8"))["query"]


def posizione(classifica: list[int], attesi: set[int]) -> int | None:
    """La posizione (da 1) del primo elemento atteso, o None se non c'è."""
    for i, p in enumerate(classifica, start=1):
        if p in attesi:
            return i
    return None
