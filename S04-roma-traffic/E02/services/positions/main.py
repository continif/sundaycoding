"""positions — servizio posizioni mezzi (GTFS-RT).

Traduce il feed protobuf di Roma in JSON pulito. Cache in-memory (niente DB).
GTFS-RT è proto2: i campi optional si leggono con HasField (presence esplicita).
"""
import os
import time
import asyncio

import httpx
from google.transit import gtfs_realtime_pb2
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel

app = FastAPI(title="positions")

FEED_URL = os.environ["GTFS_RT_URL"]   # dalla config, mai hardcoded (deve stare in feeds/allowlist.txt)
TTL = 20.0                             # < del refresh del feed: mai dati più vecchi di un giro

_cache: dict = {"vehicles": None, "fetched_at": 0.0}   # in-memory: niente DB (vincolo del servizio)
_lock = asyncio.Lock()                                  # un solo refresh alla volta


class Vehicle(BaseModel):
    id: str
    linea: str | None
    lat: float
    lon: float
    ts: int | None                     # None = timestamp assente nel feed (verificato con HasField)


def _to_vehicle(entity) -> dict | None:
    v = entity.vehicle                                  # VehiclePosition
    if not v.HasField("position"):                      # senza posizione lo scartiamo (niente lat/lon 0,0)
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
        "ts": v.timestamp if v.HasField("timestamp") else None,   # presence: "assente" != "0"
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


async def _ensure_fresh() -> bool:
    """Garantisce dati utilizzabili. Ritorna True se stiamo servendo dati STALE."""
    now = time.monotonic()
    if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
        return False
    async with _lock:
        now = time.monotonic()
        if _cache["vehicles"] is not None and now - _cache["fetched_at"] < TTL:
            return False
        try:
            vehicles = await _refresh()
        except Exception:                               # NB: largo di proposito; lo stringiamo in E05
            if _cache["vehicles"] is not None:
                return True                             # feed giù ma ho cache -> stale
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="feed GTFS-RT non disponibile",
                headers={"Retry-After": "10"},
            )
        if not vehicles:
            if _cache["vehicles"]:
                return True
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="feed vuoto e nessuna cache",
                headers={"Retry-After": "10"},
            )
        _cache["vehicles"] = vehicles
        _cache["fetched_at"] = time.monotonic()
        return False


@app.get("/vehicles", response_model=list[Vehicle])
async def get_vehicles(response: Response, linea: str | None = None):
    stale = await _ensure_fresh()
    vehicles = _cache["vehicles"] or []
    if linea is not None:
        vehicles = [v for v in vehicles if v["linea"] == linea]
    if stale:
        response.headers["X-Stale"] = "true"
    return vehicles


@app.get("/vehicles/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str, response: Response):
    stale = await _ensure_fresh()
    for v in (_cache["vehicles"] or []):
        if v["id"] == vehicle_id:
            if stale:
                response.headers["X-Stale"] = "true"
            return v
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"mezzo {vehicle_id} non trovato")


@app.get("/health")
def health():
    return {"status": "ok", "service": "positions"}
