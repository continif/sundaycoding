"""Placeholder della suite. I test veri arrivano dalle puntate successive.

Servono a far girare il dispatcher (`run_tests.sh`) fin dalla Fase 0.
"""
import pytest


@pytest.mark.unit
def test_placeholder_unit():
    # In E02: parser GTFS-RT, timestamp 0 -> "sconosciuto".
    assert 1 + 1 == 2


@pytest.mark.contract
def test_placeholder_contract():
    # In E02: il confine positions -> gateway resta {id, linea, lat, lon, ts}.
    payload = {"id": "1", "linea": "64", "lat": 41.9, "lon": 12.5, "ts": None}
    assert set(payload) == {"id", "linea", "lat", "lon", "ts"}
