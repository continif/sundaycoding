"""Test dello schedario. pytest test_schedario.py"""

from pathlib import Path

import pytest

from schedario import Nodo, bfs, costruisci, dfs_iterativa, dfs_ricorsiva, discendenti, numera

CORPUS = Path(__file__).parent.parent / "corpus" / "specchio.jsonl"


@pytest.fixture(scope="module")
def libro():
    radice = costruisci(CORPUS)
    numera(radice)
    return radice


def test_celko(libro):
    # Il test che non va lasciato all'IA: per OGNI nodo, lo spazio tra lft e
    # rgt deve contenere esattamente due numeri per ogni discendente.
    # Un errore di uno, da qualunque parte, lo fa fallire.
    for nodo, _ in dfs_iterativa(libro):
        assert nodo.rgt - nodo.lft - 1 == 2 * discendenti(nodo), nodo.etichetta


def test_contenimento(libro):
    # Un figlio sta sempre dentro i bordi del padre, e due fratelli non si
    # sovrappongono mai.
    for nodo, _ in dfs_iterativa(libro):
        precedente = nodo.lft
        for figlio in nodo.figli:
            assert nodo.lft < figlio.lft < figlio.rgt < nodo.rgt
            assert figlio.lft > precedente
            precedente = figlio.rgt


def test_ricorsiva_uguale_iterativa(libro):
    a = [(n.etichetta, l) for n, l in dfs_ricorsiva(libro)]
    b = [(n.etichetta, l) for n, l in dfs_iterativa(libro)]
    assert a == b


def test_bfs_per_livelli(libro):
    livelli = [l for _, l in bfs(libro)]
    assert livelli == sorted(livelli)


def test_lft_ordina_come_dfs(libro):
    # Il regalo del nested set: ordinare per lft È la visita in profondità.
    dfs = [n.etichetta for n, _ in dfs_iterativa(libro)]
    per_lft = [n.etichetta for n, _ in sorted(dfs_iterativa(libro), key=lambda c: c[0].lft)]
    assert dfs == per_lft


def test_ricorsione_profonda():
    # Una catena di 5.000 nodi: la ricorsiva si arrende, l'iterativa no.
    radice = nodo = Nodo("x", "0")
    for i in range(1, 5_000):
        nodo = nodo.aggiungi(Nodo("x", str(i)))
    with pytest.raises(RecursionError):
        list(dfs_ricorsiva(radice))
    assert sum(1 for _ in dfs_iterativa(radice)) == 5_000
    assert numera(radice) == 10_000
