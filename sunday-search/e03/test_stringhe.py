"""Ogni algoritmo deve dare esattamente le posizioni di str.find."""

import random

import pytest

from stringhe import AhoCorasick, con_find, forza_bruta, horspool, kmp, rabin_karp

ALGORITMI = [forza_bruta, kmp, horspool, rabin_karp]

CASI = [
    ("crociera crocera croce crociere", "croc"),
    ("aaaaa", "aa"),                       # sovrapposizioni
    ("abababab", "abab"),
    ("però pero perché perchè", "però"),   # gli accenti sono lettere
    ("però pero perché perchè", "pero"),
    ("perché", "perche"),                  # non deve trovarlo
    ("", "a"),
    ("abc", "abcd"),                       # ago più lungo del testo
    ("Frufrù e Frufru", "Frufr"),
]


@pytest.mark.parametrize("algoritmo", ALGORITMI)
@pytest.mark.parametrize("testo,ago", CASI)
def test_casi(algoritmo, testo, ago):
    assert algoritmo(testo, ago) == con_find(testo, ago)


@pytest.mark.parametrize("algoritmo", ALGORITMI)
def test_casuali(algoritmo):
    # Alfabeto piccolo, con accenti: tante ripetizioni, tante sovrapposizioni,
    # i casi in cui i salti e i ripieghi sbagliano.
    rnd = random.Random(42)
    for _ in range(500):
        testo = "".join(rnd.choice("abàè") for _ in range(rnd.randint(0, 60)))
        ago = "".join(rnd.choice("abàè") for _ in range(rnd.randint(1, 5)))
        assert algoritmo(testo, ago) == con_find(testo, ago), (testo, ago)


def test_aho_corasick():
    rnd = random.Random(7)
    for _ in range(300):
        testo = "".join(rnd.choice("abàè") for _ in range(rnd.randint(0, 60)))
        aghi = list({"".join(rnd.choice("abàè") for _ in range(rnd.randint(1, 4)))
                     for _ in range(rnd.randint(1, 6))})
        atteso = sorted((i, a) for a in aghi for i in con_find(testo, a))
        assert sorted(AhoCorasick(aghi).cerca(testo)) == atteso, (testo, aghi)
