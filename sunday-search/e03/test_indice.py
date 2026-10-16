"""I test dell'indice. Quelli sulle intersezioni girano sempre; quelli sul
libro e sulle varianti hanno bisogno del vocabolario e dell'indice generati
(vedi README) e altrimenti vengono saltati."""

import random
from pathlib import Path

import pytest

from indice import Indice, interseca, interseca_bisect

RADICE = Path(__file__).resolve().parent.parent
VOCABOLARIO, INDICE = RADICE / "vocabolario", RADICE / "indice"


def test_intersezioni():
    rnd = random.Random(3)
    for _ in range(500):
        a = sorted(rnd.sample(range(200), rnd.randint(0, 60)))
        b = sorted(rnd.sample(range(200), rnd.randint(0, 60)))
        atteso = sorted(set(a) & set(b))
        assert interseca(a, b) == atteso
        corta, lunga = sorted((a, b), key=len)
        assert interseca_bisect(corta, lunga) == atteso


@pytest.fixture(scope="module")
def idx():
    if not (VOCABOLARIO / "forme.parquet").exists() or not (INDICE / "indice.parquet").exists():
        pytest.skip("servono vocabolario/ e indice/ generati")
    from vocabolario import Vocabolario
    return Indice(INDICE, Vocabolario(VOCABOLARIO))


@pytest.mark.parametrize("parola,attese", [
    ("crociera", {"crociera", "crociere"}),   # mai le croci
    ("croce", {"croce", "croci"}),
    ("casa", {"casa", "case"}),               # mai il caso
    ("caso", {"caso", "casi"}),
    ("però", {"però"}),                       # gli accenti non si toccano
    ("pero", {"pero", "peri"}),
    ("papà", {"papà"}),
    ("testa", {"testa"}),                     # non "testavano"
])
def test_varianti(idx, parola, attese):
    assert idx.varianti(parola) == attese


def test_verbi(idx):
    gridare = idx.varianti("gridare")
    assert {"gridò", "gridava", "griderò", "gridarono"} <= gridare
    assert idx.varianti("gridò") == gridare


def test_grafia_1914(idx):
    # Il libro scrive "perchè", chi cerca oggi scrive "perché": stesso risultato.
    assert idx.cerca("perché") == idx.cerca("perchè") != []


def test_python_e_sql_concordano(idx):
    for q in ["Regina Rossa", "gridò Alice", "casa", "occhio", "Tuidledum"]:
        assert idx.cerca(q) == idx.cerca_sql(q)


def test_frase(idx):
    e = idx.etichette
    assert [e[p] for p in idx.cerca_frase("testa in giù")] == ["VIII.15", "VIII.87", "VIII.89", "VIII.120"]
    assert idx.cerca_frase("Rossa Regina") == []
