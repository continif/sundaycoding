"""Test della traduzione protobuf -> dict (E02). Verifica la gestione proto2 (HasField)."""
import pytest
from google.transit import gtfs_realtime_pb2 as pb

from services.positions.feed import _to_vehicle


def _entity(with_ts=True, with_pos=True, route="64"):
    fe = pb.FeedEntity()
    fe.id = "e1"
    vp = fe.vehicle
    if with_pos:
        vp.position.latitude = 41.9
        vp.position.longitude = 12.5
    vp.vehicle.id = "V1"
    if route is not None:
        vp.trip.route_id = route
    if with_ts:
        vp.timestamp = 1700000000
    return fe


def test_entita_completa():
    d = _to_vehicle(_entity())
    assert d["id"] == "V1" and d["linea"] == "64" and d["ts"] == 1700000000
    # lat/lon: il GTFS-RT usa float a 32 bit -> confronto con tolleranza, non ==
    assert d["lat"] == pytest.approx(41.9, abs=1e-4)
    assert d["lon"] == pytest.approx(12.5, abs=1e-4)


def test_timestamp_assente_e_none_non_1970():
    # proto2: assente != 0. HasField distingue "non mandato" da "zero".
    d = _to_vehicle(_entity(with_ts=False))
    assert d["ts"] is None


def test_linea_assente_e_none():
    d = _to_vehicle(_entity(route=None))
    assert d["linea"] is None


def test_senza_posizione_viene_scartato():
    # niente position -> None: non lo piazziamo a lat/lon 0,0 in mezzo all'oceano.
    assert _to_vehicle(_entity(with_pos=False)) is None
