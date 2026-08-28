import pytest


@pytest.fixture(autouse=True)
def stato_pulito():
    """Pattern di isolamento: azzera lo stato prima e dopo ogni test.

    In E02 qui ripuliremo la cache in-memory di positions. Per ora non c'è
    stato condiviso da resettare: la fixture c'è per fissare il pattern.
    """
    yield
