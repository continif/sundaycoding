"""Lettura del feed GTFS-RT di Roma e traduzione protobuf -> dict (E02).

Il confine col protobuf vive QUI: oltre questo modulo si parla solo JSON/dict.
GTFS-RT e' proto2 -> i campi optional hanno presence esplicita: si controlla
sempre HasField(...) PRIMA di leggere, invece di fidarsi del default (0 o "").
"""
import os

import httpx
from google.transit import gtfs_realtime_pb2   # binding ufficiali del GTFS-RT (protobuf)

# L'URL arriva dalla config, MAI hardcoded: deve stare nell'allowlist delle fonti.
FEED_URL = os.environ.get("GTFS_RT_URL", "")


def _to_vehicle(entity) -> dict | None:
    """Traduce una FeedEntity in un dict, o None se non e' un dato di posizione usabile."""
    v = entity.vehicle                                   # VehiclePosition

    if not v.HasField("position"):                       # senza posizione non e' un dato di posizione:
        return None                                      # lo scartiamo (altrimenti finirebbe a lat/lon 0,0)

    if v.HasField("vehicle") and v.vehicle.HasField("id"):
        vid = v.vehicle.id                               # id del mezzo, se c'e'...
    else:
        vid = entity.id                                  # ...altrimenti ripiega sull'id dell'entity

    linea = None
    if v.HasField("trip") and v.trip.HasField("route_id"):   # route_id vive dentro trip: presence a ogni livello
        linea = v.trip.route_id

    return {
        "id": vid,
        "linea": linea,
        "lat": v.position.latitude,                      # 'position' c'e' (controllato sopra)
        "lon": v.position.longitude,
        # presence: distingue "assente" (None) da "0" (che sarebbe il 1970), non li confonde
        "ts": v.timestamp if v.HasField("timestamp") else None,
    }


async def refresh() -> list[dict]:
    """Scarica il feed, lo traduce e restituisce la lista dei mezzi con posizione.

    Solleva httpx.HTTPError (rete/HTTP) o google.protobuf...DecodeError (bytes illeggibili):
    entrambi GUASTI previsti, gestiti a monte. Un KeyError/AttributeError qui sarebbe un BUG,
    e deve risalire fino all'handler di ultima istanza (E05), non essere ingoiato.
    """
    if not FEED_URL:
        # config mancante: lo trattiamo come guasto della sorgente, non come crash
        raise httpx.HTTPError("GTFS_RT_URL non configurato")

    async with httpx.AsyncClient(timeout=10) as client:  # timeout stretto: una fonte lenta e' peggio di una morta
        r = await client.get(FEED_URL)
        r.raise_for_status()                             # un 4xx/5xx del feed diventa eccezione, non dati finti

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(r.content)                      # QUI il protobuf viene tradotto; oltre, solo dict

    vehicles: list[dict] = []
    for e in feed.entity:
        if not e.HasField("vehicle"):                    # ci interessano solo le entity con posizione mezzo
            continue
        dv = _to_vehicle(e)
        if dv is not None:                               # _to_vehicle scarta i mezzi senza position
            vehicles.append(dv)
    return vehicles
