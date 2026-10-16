"""Test: ogni algoritmo deve dare lo stesso risultato di sorted(), e quelli
stabili devono conservare l'ordine degli uguali. Si lancia con pytest."""

import random

import pytest

from ordinamenti import ALGORITMI, quick_sort
from rettangoli import Rettangolo, RettangoloLt, RettangoloOrdinato, chiave_cmp

STABILI = {"insertion", "merge"}


@pytest.mark.parametrize("nome", ALGORITMI)
@pytest.mark.parametrize("caso", ["vuota", "uno", "casuale", "ordinata", "rovescia", "uguali"])
def test_come_sorted(nome, caso):
    rng = random.Random(1)
    dati = {
        "vuota": [],
        "uno": [42],
        "casuale": [rng.randint(0, 50) for _ in range(300)],
        "ordinata": list(range(300)),
        "rovescia": list(range(300, 0, -1)),
        "uguali": [7] * 50,
    }[caso]
    assert ALGORITMI[nome](dati) == sorted(dati)


@pytest.mark.parametrize("nome", sorted(STABILI))
def test_stabilita(nome):
    # Coppie (chiave, etichetta): a parità di chiave l'etichetta deve restare
    # nell'ordine d'ingresso. sorted() è il riferimento.
    rng = random.Random(2)
    dati = [(rng.randint(0, 5), i) for i in range(200)]
    assert ALGORITMI[nome](dati, key=lambda c: c[0]) == sorted(dati, key=lambda c: c[0])


def test_quick_pivot_ultimo_ordinata():
    assert quick_sort(list(range(500)), pivot="ultimo") == list(range(500))


def test_quattro_modi_stesso_ordine():
    rng = random.Random(3)
    misure = [(rng.randint(1, 20), rng.randint(1, 20)) for _ in range(500)]
    atteso = sorted(b * h for b, h in misure)
    assert [r.area for r in sorted(RettangoloLt(b, h) for b, h in misure)] == atteso
    assert [r.area for r in sorted((Rettangolo(b, h) for b, h in misure), key=lambda r: r.area)] == atteso
    assert [r.area for r in sorted(RettangoloOrdinato(b, h) for b, h in misure)] == atteso
    assert [r.area for r in sorted((Rettangolo(b, h) for b, h in misure), key=chiave_cmp)] == atteso


def test_ordinato_ignora_base_a_parita_di_area():
    assert RettangoloOrdinato(2, 3) == RettangoloOrdinato(3, 2)
