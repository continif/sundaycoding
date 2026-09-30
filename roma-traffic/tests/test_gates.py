"""Test dei gate e della lettura dell'IP (E03/E04). Nessuna rete: uso una request finta."""
import pytest
from fastapi import HTTPException

from services.positions import gates
from services.positions.gates import TokenBucket, ip_client, valida_linea


class FakeReq:
    """Solo gli attributi che i gate leggono davvero."""

    def __init__(self, method="GET", client_host="10.0.0.5", headers=None, query=None):
        self.method = method
        self.client = type("C", (), {"host": client_host})() if client_host else None
        self.headers = headers or {}
        self.query_params = query or {}


# --- ip_client ---------------------------------------------------------------

def test_ip_peer_non_fidato_ignora_xff():
    # 10.0.0.5 non e' un proxy fidato: l'X-Forwarded-For non lo guardiamo nemmeno.
    req = FakeReq(client_host="10.0.0.5", headers={"x-forwarded-for": "1.2.3.4"})
    assert ip_client(req) == "10.0.0.5"


def test_ip_multi_proxy_risale_da_destra():
    # peer fidato (10.0.0.1), catena "9.9.9.9, 10.0.0.2": scarto 10.0.0.2 (fidato), prendo 9.9.9.9.
    req = FakeReq(client_host="10.0.0.1", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.2"})
    assert ip_client(req) == "9.9.9.9"


def test_ip_token_spazzatura_non_ci_si_fida():
    req = FakeReq(client_host="10.0.0.1", headers={"x-forwarded-for": "non-un-ip"})
    assert ip_client(req) is None


def test_ip_proxy_fidati_vuoto_torna_sempre_il_peer(monkeypatch):
    monkeypatch.setattr(gates, "PROXY_FIDATI", [])   # servizio esposto: nessun header di cui fidarsi
    req = FakeReq(client_host="10.0.0.1", headers={"x-forwarded-for": "9.9.9.9"})
    assert ip_client(req) == "10.0.0.1"


# --- TokenBucket -------------------------------------------------------------

def test_token_bucket_si_esaurisce():
    b = TokenBucket(capacita=3, ricarica=0.0)   # ricarica 0: una volta finiti, restano finiti
    assert [b.consenti() for _ in range(4)] == [True, True, True, False]


# --- Gate --------------------------------------------------------------------

def test_gate_ip_fuori_reti_ammesse():
    assert gates.gate_ip(FakeReq(client_host="9.9.9.9")).status_code == 403
    assert gates.gate_ip(FakeReq(client_host="10.0.0.5")) is None   # dentro 10.0.0.0/8: passa


def test_gate_user_agent():
    assert gates.gate_user_agent(FakeReq(headers={"user-agent": "python-requests/2"})).status_code == 403
    assert gates.gate_user_agent(FakeReq(headers={})).status_code == 403          # assente: fuori
    assert gates.gate_user_agent(FakeReq(headers={"user-agent": "Mozilla/5.0"})) is None


def test_gate_solo_lettura():
    assert gates.gate_solo_lettura(FakeReq(method="POST")).status_code == 405
    assert gates.gate_solo_lettura(FakeReq(method="GET")) is None


def test_gate_parametri_noti():
    assert gates.gate_parametri_noti(FakeReq(query={"admin": "1"})).status_code == 400
    assert gates.gate_parametri_noti(FakeReq(query={"linea": "64"})) is None


def test_ordine_catena():
    nomi = [g.__name__ for g in gates.CATENA]
    assert nomi == ["gate_ip", "gate_user_agent", "gate_rate_limit",
                    "gate_solo_lettura", "gate_parametri_noti"]   # sicurezza prima, applicativi dopo


# --- valida_linea ------------------------------------------------------------

def test_valida_linea():
    assert valida_linea(None) is None
    assert valida_linea("64") == "64"
    with pytest.raises(HTTPException):
        valida_linea("?!")
