"""Stato del feed: macchina a stati, cache, circuit breaker (E03 + E05 + E06).

Qui vive l'UNICA autorita' sullo stato del feed. L'endpoint chiede
`aggiorna_stato()` e ottiene un Feed; i guasti senza cache diventano
FeedNonDisponibile (503 via handler centralizzato). Gli alert di E06 partono
solo sul FRONTE (cambio di stato), tramite i notificatori registrati.
"""
import asyncio
import logging
import time
from enum import Enum, auto

import httpx
from google.protobuf.message import DecodeError

from . import feed
from .errori import FeedNonDisponibile

log = logging.getLogger("positions")


# --- Macchina a stati (E03) --------------------------------------------------

class Feed(Enum):
    FRESH = auto()    # dati appena presi
    STALE = auto()    # vecchi ma serviti dalla cache
    DOWN = auto()     # nessun dato: solo all'avvio, finche' non arriva il primo fetch


# La cache in-memory non svanisce: da STALE non si "cade" in DOWN. DOWN e' lo stato d'avvio.
TRANSIZIONI = {
    Feed.FRESH: {Feed.STALE},        # col tempo il fresco invecchia
    Feed.STALE: {Feed.FRESH},        # un refresh riuscito lo riporta fresco (la cache non si perde)
    Feed.DOWN: {Feed.FRESH},         # dallo stato d'avvio si esce solo col primo fetch riuscito
}


def transita(da: Feed, a: Feed) -> Feed:
    if a is not da and a not in TRANSIZIONI[da]:   # restare nello stato corrente e' sempre lecito
        raise ValueError(f"transizione illegale: {da.name} -> {a.name}")
    return a


# --- Stato condiviso del modulo ----------------------------------------------

TTL = 20.0                                          # s: < del refresh del feed, non serviamo dati di >1 giro
_stato: Feed = Feed.DOWN                            # all'avvio non abbiamo ancora dati
_cache: dict = {"vehicles": None, "fetched_at": 0.0}
_lock = asyncio.Lock()                              # un solo refresh alla volta: non mandiamo 10 aiutanti sul feed

# Notificatori registrati da chi vuole reagire ai cambi di stato (es. il bot Telegram, E06).
# Disaccoppiati apposta: stato.py non importa telegram.py (niente dipendenza circolare).
notificatori: list = []


# --- Circuit breaker (E05) ---------------------------------------------------

_falliti = 0
_riprova_dopo = 0.0
SOGLIA, PAUSA = 5, 30.0                              # dopo 5 fallimenti consecutivi, 30s di tregua


def _breaker_aperto() -> bool:
    return _falliti >= SOGLIA and time.monotonic() < _riprova_dopo


def _breaker_ok() -> None:
    global _falliti, _riprova_dopo
    _falliti = 0
    _riprova_dopo = 0.0


def _breaker_ko() -> None:
    global _falliti, _riprova_dopo
    _falliti += 1
    if _falliti >= SOGLIA:                           # superata la soglia: apri e fissa la fine della tregua
        _riprova_dopo = time.monotonic() + PAUSA


# --- Transizione + alert sul fronte (E06) ------------------------------------

async def _notifica(testo: str) -> None:
    for n in notificatori:
        try:
            await n(testo)
        except Exception:                            # un alert perso NON e' un guasto del servizio
            log.warning("notificatore fallito", exc_info=True)


async def cambia_stato(nuovo: Feed) -> Feed:
    """Cambia lo stato passando SEMPRE da transita (unica autorita'), e avvisa solo sul FRONTE."""
    global _stato
    prima = _stato
    _stato = transita(prima, nuovo)
    if _stato is not prima:                          # un messaggio per transizione, non per ogni giro di polling
        if _stato is Feed.DOWN:
            await _notifica("positions: feed non disponibile, nessun dato in cache")
        elif _stato is Feed.STALE:
            await _notifica("positions: feed non si aggiorna, servo dati dalla cache (X-Stale)")
        elif _stato is Feed.FRESH and prima is not Feed.FRESH:
            await _notifica("positions: feed di nuovo aggiornato")
    return _stato


# --- Il cuore: aggiorna_stato ------------------------------------------------

async def aggiorna_stato() -> Feed:
    """Garantisce dati utilizzabili e ritorna lo stato del feed.

    FRESH: cache appena aggiornata. STALE: servo cache vecchia ma valida.
    Se non c'e' nulla da servire, solleva FeedNonDisponibile -> 503 (handler centralizzato).
    Un bug dentro feed.refresh() (KeyError, AttributeError) NON viene catturato qui: risale.
    """
    now = time.monotonic()
    if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
        return await cambia_stato(Feed.FRESH)        # cache ancora fresca: niente fetch

    if _breaker_aperto() and _cache["vehicles"]:
        return await cambia_stato(Feed.STALE)        # sorgente morta di recente: degrado subito, senza sprecare un timeout

    async with _lock:
        now = time.monotonic()
        if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
            return await cambia_stato(Feed.FRESH)    # un aiutante ha gia' aggiornato mentre aspettavamo il lock
        if _breaker_aperto() and _cache["vehicles"]:
            return await cambia_stato(Feed.STALE)

        try:
            vehicles = await feed.refresh()
        except (httpx.HTTPError, DecodeError):       # SOLO i guasti previsti: rete che cade, protobuf illeggibile
            _breaker_ko()
            if _cache["vehicles"]:
                return await cambia_stato(Feed.STALE)   # ho cache -> degrado con dignita'
            await cambia_stato(Feed.DOWN)
            raise FeedNonDisponibile()               # niente cache -> dominio -> handler -> 503

        _breaker_ok()
        if not vehicles:                             # feed valido ma vuoto: non cancello la memoria buona
            if _cache["vehicles"]:
                return await cambia_stato(Feed.STALE)
            await cambia_stato(Feed.DOWN)
            raise FeedNonDisponibile()

        _cache["vehicles"] = vehicles
        _cache["fetched_at"] = time.monotonic()
        return await cambia_stato(Feed.FRESH)


def stato_corrente() -> Feed:
    return _stato
