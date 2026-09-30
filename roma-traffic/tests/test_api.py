"""Test di contratto sugli endpoint (E02-E05), via TestClient. Nessuna rete: feed e IP mockati."""
import httpx
import pytest
from fastapi.testclient import TestClient

from services.positions import gates, main

UA = {"user-agent": "Mozilla/5.0"}
CAMPIONE = [{"id": "A", "linea": "64", "lat": 41.9, "lon": 12.5, "ts": None}]


@pytest.fixture
def client(monkeypatch):
    # bypasso il gate IP fingendo un peer interno (il gate lo testiamo a parte).
    monkeypatch.setattr(gates, "ip_client", lambda req: "10.0.0.5")

    async def fake_refresh():
        return list(CAMPIONE)

    monkeypatch.setattr("services.positions.feed.refresh", fake_refresh)
    return TestClient(main.app)


def test_health_ok(client):
    r = client.get("/health", headers=UA)
    assert r.status_code == 200
    assert r.json()["service"] == "positions"


def test_vehicles_200(client):
    r = client.get("/vehicles", headers=UA)
    assert r.status_code == 200
    assert r.json()[0]["id"] == "A"


def test_vehicle_singolo_404(client):
    r = client.get("/vehicles/NON_ESISTE", headers=UA)
    assert r.status_code == 404


def test_post_vietato_405(client):
    r = client.post("/vehicles", headers=UA)
    assert r.status_code == 405


def test_parametro_sconosciuto_400(client):
    r = client.get("/vehicles?admin=1", headers=UA)
    assert r.status_code == 400


def test_linea_non_valida_422(client):
    r = client.get("/vehicles?linea=$$$", headers=UA)
    assert r.status_code == 422


def test_ip_non_ammesso_403():
    # senza monkeypatch dell'IP: il TestClient ha un peer non valido -> 403.
    c = TestClient(main.app)
    r = c.get("/vehicles", headers=UA)
    assert r.status_code == 403


def test_feed_giu_senza_cache_503(monkeypatch):
    monkeypatch.setattr(gates, "ip_client", lambda req: "10.0.0.5")

    async def boom():
        raise httpx.HTTPError("feed giu'")

    monkeypatch.setattr("services.positions.feed.refresh", boom)
    c = TestClient(main.app)
    r = c.get("/vehicles", headers=UA)
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "10"
