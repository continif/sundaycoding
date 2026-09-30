"""Modelli di output del servizio positions (E02).

Il modello Pydantic serve a FastAPI per due cose gratis: la validazione
in uscita e la conversione a JSON pulito. Dietro le quinte arriva protobuf;
da qui in poi si parla solo questo.
"""
from pydantic import BaseModel


class Vehicle(BaseModel):
    id: str
    linea: str | None          # route_id del GTFS-RT: puo' mancare (proto2, presence esplicita)
    lat: float
    lon: float
    ts: int | None             # timestamp: None quando il feed non lo manda (verificato con HasField)
