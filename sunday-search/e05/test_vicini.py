"""I test di E05. Quelli sul libro hanno bisogno di indice/ (E03); gli altri
girano su vettori a caso."""

from pathlib import Path

import chromadb
import numpy as np
import pytest

from hnsw import HNSW
from vettori import migliori_k, normalizza, vicini

RADICE = Path(__file__).resolve().parent.parent
INDICE = RADICE / "indice"


@pytest.fixture(scope="module")
def casuali():
    rng = np.random.default_rng(7)
    return normalizza(rng.standard_normal((500, 20)))


@pytest.fixture(scope="module")
def vet():
    if not (INDICE / "indice.parquet").exists():
        pytest.skip("serve indice/ generato da e03/indice.py")
    from vettori import Registro, Vettori
    return Vettori(Registro(INDICE))


def test_migliori_k_come_argsort(casuali):
    s = casuali @ casuali.T
    assert np.array_equal(migliori_k(s, 7), np.argsort(-s, axis=1, kind="stable")[:, :7])


def test_normalizza_lascia_gli_zeri():
    m = normalizza(np.array([[3.0, 4.0], [0.0, 0.0]]))
    assert np.allclose(m, [[0.6, 0.8], [0.0, 0.0]])


def test_coseno_l2_stesso_ordine(casuali):
    # Vettori normalizzati: ||a-b||² = 2 - 2·cos, quindi stesso ordine.
    q = casuali[:20]
    l2 = ((q[:, None, :] - casuali[None, :, :]) ** 2).sum(-1)
    assert np.array_equal(vicini(casuali, q, 10), np.argsort(l2, axis=1, kind="stable")[:, :10])


def test_hnsw_esatto_con_ef_grande(casuali):
    # Con ef_search pari a tutti i nodi la ricerca guarda tutto: è la forza bruta.
    h = HNSW(max_neighbors=8, ef_construction=50).costruisci(casuali)
    veri = vicini(casuali, casuali[:30], 10)
    for q, v in zip(casuali[:30], veri):
        assert h.cerca(q, 10, ef_search=len(casuali)) == list(v)


def test_hnsw_risparmia_distanze(casuali):
    h = HNSW(max_neighbors=8, ef_construction=50).costruisci(casuali)
    h.distanze = 0
    h.cerca(casuali[0], 10, ef_search=10)
    assert h.distanze < len(casuali)


def test_chroma_coseno_e_distanza(casuali):
    col = chromadb.EphemeralClient().create_collection(
        "test_coseno", configuration={"hnsw": {"space": "cosine"}}, embedding_function=None)
    col.add(ids=[str(i) for i in range(len(casuali))], embeddings=casuali.astype(np.float32))
    r = col.query(query_embeddings=casuali[:5].astype(np.float32), n_results=10)
    for q, ids, dist in zip(casuali[:5], r["ids"], r["distances"]):
        assert np.allclose(dist, 1 - casuali[list(map(int, ids))] @ q, atol=1e-5)
    # Pochi vettori, default di Chroma: stessi vicini della forza bruta.
    assert [list(map(int, i)) for i in r["ids"]] == [list(v) for v in vicini(casuali, casuali[:5], 10)]


def test_lsa_normalizzati(vet):
    norme = np.linalg.norm(vet.lsa, axis=1)
    assert vet.lsa.shape == (1097, 100)
    assert np.allclose(norme[norme > 0], 1, atol=1e-5) and (norme == 0).sum() == 2


def test_lsa_marmellata(vet):
    numero = {e: n for n, e in vet.r.etichette.items()}
    q = vet.query_lsa([["marmellata"], ["ieri"], ["domani"], ["oggi"]])
    # V.22 e V.24 sono la stessa battuta della Regina: tutte e due in testa.
    assert set(vicini(vet.lsa, q[None, :], 2)[0]) == {numero["V.22"], numero["V.24"]}


def test_hnsw_sul_libro(vet):
    ok = np.where(np.linalg.norm(vet.lsa, axis=1) > 0)[0]
    x = vet.lsa.astype(np.float64)
    h = HNSW(16, 100).costruisci(x)
    veri = vicini(vet.lsa, vet.lsa[ok[:200]], 10)
    rec = np.mean([len(set(h.cerca(x[i], 10, 50)) & set(v)) / 10 for i, v in zip(ok[:200], veri)])
    assert rec > 0.98
