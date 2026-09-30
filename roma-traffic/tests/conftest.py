import pytest

from services.positions import gates, stato


@pytest.fixture(autouse=True)
def _reset_stato():
    """Ogni test parte da uno stato pulito: niente cache, breaker chiuso, bucket vuoti."""
    stato._stato = stato.Feed.DOWN
    stato._cache = {"vehicles": None, "fetched_at": 0.0}
    stato._breaker_ok()
    stato.notificatori.clear()
    gates._bucket.clear()
    yield
