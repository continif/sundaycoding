"""positions — servizio posizioni mezzi (GTFS-RT).

Traduce il feed protobuf di Roma in JSON pulito. Cache in-memory (niente DB).
E03: il servizio fa SOLO quello per cui è nato — guardia all'ingresso, catena di
gate (Chain of Responsibility via middleware) e stato del feed come macchina a stati.
"""
import os
import time
import asyncio
from enum import Enum, auto
from typing import Callable

import httpx
from google.transit import gtfs_realtime_pb2
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="positions")

FEED_URL = os.environ["GTFS_RT_URL"]   # dalla config, mai hardcoded (deve stare in feeds/allowlist.txt)
TTL = 20.0                             # < del refresh del feed: mai dati più vecchi di un giro

_cache: dict = {"vehicles": None, "fetched_at": 0.0}
_lock = asyncio.Lock()


# --- stato del feed: macchina a stati (fedele al servizio) ------------------
class Feed(Enum):
    FRESH = auto()    # dati appena presi
    STALE = auto()    # vecchi ma serviti dalla cache
    DOWN  = auto()    # nessun dato: solo all'avvio, finché non arriva il primo fetch


TRANSIZIONI = {
    Feed.FRESH: {Feed.STALE},        # col tempo il fresco invecchia
    Feed.STALE: {Feed.FRESH},        # un refresh riuscito lo riporta fresco (la cache non si perde)
    Feed.DOWN:  {Feed.FRESH},        # dallo stato d'avvio si esce solo col primo fetch riuscito
}


def transita(da: Feed, a: Feed) -> Feed:
    if a is not da and a not in TRANSIZIONI[da]:   # restare nello stato corrente è sempre lecito
        raise ValueError(f"transizione illegale: {da.name} -> {a.name}")
    return a


# dispatch table: lo stato -> (status HTTP, header)
RISPOSTA = {
    Feed.FRESH: (200, {}),
    Feed.STALE: (200, {"X-Stale": "true"}),
    Feed.DOWN:  (503, {"Retry-After": "10"}),
}

_stato = Feed.DOWN   # stato d'avvio: nessun dato


# --- catena di gate: Chain of Responsibility ---------------------------------
Gate = Callable[[Request], Response | None]   # None = passa oltre, Response = blocca qui


def gate_solo_lettura(req: Request) -> Response | None:
    if req.method != "GET":
        return JSONResponse({"detail": "servizio di sola lettura"}, status_code=405)
    return None


PARAMETRI_NOTI = {"linea"}                     # tutto ciò che il servizio sa interpretare


def gate_parametri_noti(req: Request) -> Response | None:
    ignoti = set(req.query_params) - PARAMETRI_NOTI
    if ignoti:
        return JSONResponse({"detail": f"parametri non ammessi: {sorted(ignoti)}"}, status_code=400)
    return None


CATENA: list[Gate] = [gate_solo_lettura, gate_parametri_noti]
# NB: in E04 in cima -> [gate_ip, gate_user_agent, gate_rate_limit, ...]


@app.middleware("http")
async def applica_catena(req: Request, call_next):
    # il middleware http gira PRIMA del routing: i gate valgono per ogni richiesta
    for gate in CATENA:
        if (blocco := gate(req)) is not None:   # il primo anello che ferma, vince
            return blocco
    return await call_next(req)


# --- validazione input -------------------------------------------------------
def valida_linea(raw: str | None) -> str | None:
    match raw:
        case None:
            return None                        # assente è lecito: /vehicles senza filtro
        case str(s) if s.isalnum():
            return s
        case _:
            raise HTTPException(422, "parametro 'linea' non valido")


# --- modello di uscita -------------------------------------------------------
class Vehicle(BaseModel):
    id: str
    linea: str | None
    lat: float
    lon: float
    ts: int | None                     # None = timestamp assente nel feed (verificato con HasField)


# --- parsing GTFS-RT (proto2: presence esplicita con HasField) ---------------
def _to_vehicle(entity) -> dict | None:
    v = entity.vehicle
    if not v.HasField("position"):                      # senza posizione lo scartiamo (niente 0,0)
        return None
    if v.HasField("vehicle") and v.vehicle.HasField("id"):
        vid = v.vehicle.id
    else:
        vid = entity.id
    linea = None
    if v.HasField("trip") and v.trip.HasField("route_id"):
        linea = v.trip.route_id
    return {
        "id": vid,
        "linea": linea,
        "lat": v.position.latitude,
        "lon": v.position.longitude,
        "ts": v.timestamp if v.HasField("timestamp") else None,
    }


async def _refresh() -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(FEED_URL)
        r.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)                     # oltre qui: solo JSON, mai protobuf
    vehicles = []
    for e in feed.entity:
        if not e.HasField("vehicle"):
            continue
        dv = _to_vehicle(e)
        if dv is not None:
            vehicles.append(dv)
    return vehicles


async def aggiorna_stato() -> Feed:
    """Aggiorna la cache e ritorna il nuovo stato del feed, validato da transita()."""
    global _stato
    now = time.monotonic()
    if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
        return _stato                                   # cache fresca: restiamo FRESH
    async with _lock:
        now = time.monotonic()
        if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
            return _stato
        try:
            vehicles = await _refresh()
            if not vehicles:                            # feed valido ma vuoto: come un fallimento
                raise ValueError("feed vuoto")
        except Exception:                               # NB: largo di proposito; lo stringiamo in E05
            nuovo = Feed.STALE if _cache["vehicles"] else Feed.DOWN
            _stato = transita(_stato, nuovo)
            return _stato
        _cache["vehicles"] = vehicles
        _cache["fetched_at"] = time.monotonic()
        _stato = transita(_stato, Feed.FRESH)
        return _stato


def _applica_stato(stato: Feed, response: Response) -> None:
    """La dispatch table decide status e header. 503 -> eccezione; altrimenti setta gli header."""
    status_code, headers = RISPOSTA[stato]
    if status_code == 503:
        raise HTTPException(503, "feed non disponibile", headers=headers)
    for k, v in headers.items():
        response.headers[k] = v


# --- endpoint ----------------------------------------------------------------
@app.get("/vehicles", response_model=list[Vehicle])
async def get_vehicles(response: Response, linea: str | None = None):
    linea = valida_linea(linea)
    stato = await aggiorna_stato()
    _applica_stato(stato, response)
    vehicles = _cache["vehicles"] or []
    if linea is not None:
        vehicles = [v for v in vehicles if v["linea"] == linea]
    return vehicles


@app.get("/vehicles/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str, response: Response):
    stato = await aggiorna_stato()
    _applica_stato(stato, response)
    for v in (_cache["vehicles"] or []):
        if v["id"] == vehicle_id:
            return v
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"mezzo {vehicle_id} non trovato")


@app.get("/health")
def health():
    return {"status": "ok", "service": "positions"}
