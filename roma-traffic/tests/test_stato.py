"""Test della macchina a stati, del breaker e di aggiorna_stato (E03/E05/E06). Nessuna rete."""
import asyncio

import httpx
import pytest

from services.positions import stato
from services.positions.errori import FeedNonDisponibile
from services.positions.stato import Feed


def test_alert_solo_sul_fronte():
    # E06: un messaggio PER TRANSIZIONE, non per ogni giro di polling.
    inviati = []

    async def n(t):
        inviati.append(t)

    stato.notificatori[:] = [n]

    async def run():
        for s in [Feed.FRESH, Feed.FRESH, Feed.STALE, Feed.STALE, Feed.FRESH]:
            await stato.cambia_stato(s)

    asyncio.run(run())
    assert inviati == [
        "positions: feed di nuovo aggiornato",                                  # DOWN -> FRESH
        "positions: feed non si aggiorna, servo dati dalla cache (X-Stale)",    # FRESH -> STALE
        "positions: feed di nuovo aggiornato",                                  # STALE -> FRESH
    ]


def test_transizione_illegale_e_un_bug():
    # STALE -> DOWN non esiste nel grafo: deve esplodere (e' un bug, non un errore atteso).
    with pytest.raises(ValueError):
        stato.transita(Feed.STALE, Feed.DOWN)


def test_breaker_apre_dopo_soglia():
    stato._breaker_ok()
    for _ in range(stato.SOGLIA):
        assert not stato._breaker_aperto()   # finche' non tocca la soglia, resta chiuso
        stato._breaker_ko()
    assert stato._breaker_aperto()           # alla soglia: apre


def test_aggiorna_stato_successo(monkeypatch):
    async def fake():
        return [{"id": "A", "linea": "64", "lat": 1.0, "lon": 2.0, "ts": None}]

    monkeypatch.setattr("services.positions.feed.refresh", fake)
    st = asyncio.run(stato.aggiorna_stato())
    assert st is Feed.FRESH
    assert stato._cache["vehicles"][0]["id"] == "A"


def test_guasto_con_cache_degrada_a_stale(monkeypatch):
    # scenario reale: prima avevamo dati (FRESH), poi il feed cade. Con cache -> STALE.
    stato._stato = Feed.FRESH
    stato._cache = {"vehicles": [{"id": "A", "linea": "64", "lat": 1.0, "lon": 2.0, "ts": None}],
                    "fetched_at": 0.0}     # cache vecchia (oltre TTL) -> si tenta il refresh

    async def boom():
        raise httpx.HTTPError("feed giu'")

    monkeypatch.setattr("services.positions.feed.refresh", boom)
    st = asyncio.run(stato.aggiorna_stato())
    assert st is Feed.STALE                 # ho cache -> degrado con dignita', niente eccezione


def test_guasto_senza_cache_e_feed_non_disponibile(monkeypatch):
    async def boom():
        raise httpx.HTTPError("feed giu'")

    monkeypatch.setattr("services.positions.feed.refresh", boom)
    with pytest.raises(FeedNonDisponibile):
        asyncio.run(stato.aggiorna_stato())
    assert stato.stato_corrente() is Feed.DOWN


def test_bug_nel_refresh_non_viene_ingoiato(monkeypatch):
    # E05: un KeyError e' un BUG, NON e' (httpx.HTTPError, DecodeError): deve risalire.
    async def bug():
        raise KeyError("campo che credevo ci fosse")

    monkeypatch.setattr("services.positions.feed.refresh", bug)
    with pytest.raises(KeyError):
        asyncio.run(stato.aggiorna_stato())
