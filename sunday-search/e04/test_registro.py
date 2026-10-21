"""I test di E04. Hanno bisogno dell'indice generato in E03 (cartella indice/)
e, per PageRank, del corpus; altrimenti vengono saltati."""

from pathlib import Path

import numpy as np
import pytest

RADICE = Path(__file__).resolve().parent.parent
INDICE, CORPUS = RADICE / "indice", RADICE / "corpus" / "specchio.jsonl"


@pytest.fixture(scope="module")
def reg():
    if not (INDICE / "indice.parquet").exists():
        pytest.skip("serve indice/ generato da e03/indice.py")
    from registro import Registro
    return Registro(INDICE)


QUERY = [["regina"], ["regina", "rossa"], ["alice"], ["marmellata", "ieri", "domani"], ["giabervocco"]]


@pytest.mark.parametrize("q", QUERY)
def test_bm25_a_mano_uguale_alla_matrice(reg, q):
    a = reg.bm25_a_mano(reg.liste(), q)
    s = reg.punteggi(q)
    assert len(a) == np.count_nonzero(s)
    assert all(abs(s[p] - v) < 1e-9 for p, v in a.items())


@pytest.mark.parametrize("q", QUERY)
def test_gruppi_di_una_forma_uguali_a_punteggi(reg, q):
    for schema in ("conteggi", "tfidf", "bm25"):
        assert np.allclose(reg.punteggi(q, schema), reg.punteggi_gruppi([[t] for t in q], schema))


def test_matrice_uguale_all_indice(reg):
    # La riga di "regina" è la lista di E03: stessi paragrafi.
    liste = reg.liste()
    assert [p for p, _ in liste["regina"]] == sorted(p for p, _ in liste["regina"])
    assert len(liste["regina"]) == reg.df[reg.riga["regina"]] == 168


def test_coseno_tra_zero_e_uno(reg):
    s = reg.punteggi(["regina", "rossa"], "coseno")
    assert s.min() >= 0 and s.max() <= 1 + 1e-12


def test_migliori_ordinati(reg):
    s = reg.punteggi(["regina"])
    top = reg.migliori(s, 10)
    assert [s[p] for p in top] == sorted((s[p] for p in top), reverse=True)


@pytest.mark.parametrize("metodo", ["vari_det", "vari_mmr"])
def test_vari(reg, metodo):
    s = reg.punteggi(["regina"])
    scelti = getattr(reg, metodo)(s, 10)
    assert len(scelti) == len(set(scelti)) == 10
    assert scelti[0] == reg.migliori(s, 1)[0]          # il migliore resta primo
    assert reg.volume(scelti) >= reg.volume(reg.migliori(s, 10)) - 1e-9


def test_pagerank():
    if not CORPUS.exists():
        pytest.skip("serve corpus/specchio.jsonl")
    from pagerank import carica, con_autovettore, matrice_incontri, pagerank, transizioni
    m = transizioni(matrice_incontri(carica(CORPUS)))
    assert np.allclose(m.sum(axis=0), 1)
    pr, _ = pagerank(m)
    assert abs(pr.sum() - 1) < 1e-9
    assert np.allclose(pr, con_autovettore(m), atol=1e-10)
