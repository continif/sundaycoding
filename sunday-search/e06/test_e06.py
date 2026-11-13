"""
Test di E06. Quelli sintetici girano ovunque; quelli sul libro vengono
saltati se manca la cartella indice/ (che non è nel repo: si ricostruisce
con E03).

    pytest test_e06.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from chunking import matrice, per_finestra, per_paragrafo, per_parole, per_scena  # noqa: E402
from grafo import Grafo  # noqa: E402
from ricerca import rrf  # noqa: E402
from valuta import bootstrap  # noqa: E402

RADICE = AQUI.parent


def finto_libro() -> dict[int, dict]:
    """3 capitoli, 20 paragrafi, tipi e lunghezze a rotazione."""
    meta, p = {}, 0
    for cap, n in ((1, 8), (2, 7), (3, 5)):
        for i in range(n):
            meta[p] = {"capitolo": cap, "parole": 10 + 15 * (i % 3), "tipo": ("prosa", "dialogo", "dialogo")[i % 3]}
            p += 1
    return meta


# ---------------------------------------------------------------- RRF
def test_rrf_premia_il_consenso():
    # b è terzo in entrambe, a è primo in una e assente nell'altra
    punti = rrf([["a", "x", "b"], ["y", "z", "b"]])
    assert punti["b"] > punti["a"]


def test_rrf_assente_non_penalizza():
    assert rrf([[1, 2], [3]])[3] == pytest.approx(1 / 61)


# ----------------------------------------------------------- chunking
@pytest.mark.parametrize("chunk", [
    per_paragrafo(finto_libro()), per_finestra(finto_libro(), 3, 3), per_finestra(finto_libro(), 3, 1),
    per_parole(finto_libro(), 40), per_scena(finto_libro(), 60)])
def test_ogni_paragrafo_in_almeno_un_chunk(chunk):
    assert {p for c in chunk for p in c} == set(finto_libro())


@pytest.mark.parametrize("chunk", [per_finestra(finto_libro(), 3, 2), per_parole(finto_libro(), 40), per_scena(finto_libro(), 60)])
def test_nessun_chunk_attraversa_un_capitolo(chunk):
    meta = finto_libro()
    assert all(len({meta[p]["capitolo"] for p in c}) == 1 for c in chunk)


def test_parole_e_scena_non_si_sovrappongono():
    for chunk in (per_parole(finto_libro(), 40), per_scena(finto_libro(), 60)):
        tutti = [p for c in chunk for p in c]
        assert len(tutti) == len(set(tutti))


def test_finestre_sovrapposte_coprono_il_triplo():
    assert sum(len(c) for c in per_finestra(finto_libro(), 3, 1)) > len(finto_libro())


def test_taglio_e_una_matrice():
    """tf @ A deve dare lo stesso risultato che sommare le colonne a mano."""
    from scipy import sparse
    rng = np.random.default_rng(0)
    tf = sparse.csr_matrix(rng.integers(0, 3, (30, 20)).astype(float))
    chunk = per_finestra(finto_libro(), 3, 3)
    ac = (tf @ matrice(chunk, 20)).toarray()
    a_mano = np.stack([tf[:, c].sum(axis=1).A1 for c in chunk], axis=1)
    assert np.allclose(ac, a_mano)


# -------------------------------------------------------------- grafo
def vettori_a_gruppi() -> np.ndarray:
    """Due gruppi ben separati di 5 vettori, più un ponte a metà."""
    rng = np.random.default_rng(1)
    a = np.array([1, 0, 0]) + rng.normal(0, .05, (5, 3))
    b = np.array([0, 1, 0]) + rng.normal(0, .05, (5, 3))
    ponte = np.array([[1, 1, 0]])
    v = np.vstack([a, b, ponte])
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_grafo_percorso_passa_dal_ponte():
    g = Grafo(vettori_a_gruppi(), k=3)
    strada = g.percorso(0, 5)
    assert strada is not None and strada[0] == 0 and strada[-1] == 5


def test_grafo_simmetrico():
    g = Grafo(vettori_a_gruppi(), k=3).g
    assert abs(g - g.T).nnz == 0


def test_grafo_vettore_nullo_isolato():
    v = vettori_a_gruppi()
    v[3] = 0
    g = Grafo(v, k=3)
    assert g.vicini(3) == [] and g.percorso(0, 3) is None


# ---------------------------------------------------------- valutazione
def test_bootstrap_zero_se_uguali():
    d, lo, hi = bootstrap([1, 2, None, 5], [1, 2, None, 5])
    assert d == lo == hi == 0.0


def test_bootstrap_segno():
    d, lo, hi = bootstrap([1, 1, 1, 1], [None, None, None, None])
    assert d == 1.0 and lo > 0


# ----------------------------------------------- sul libro (se c'è)
@pytest.fixture(scope="module")
def cerca(tmp_path_factory):
    if not (RADICE / "indice" / "indice.parquet").exists():
        pytest.skip("manca indice/: si costruisce con E03")
    from motore import Cerca
    return Cerca(RADICE / "indice", RADICE / "vocabolario", RADICE / "corpus" / "specchio.jsonl",
                 tmp_path_factory.mktemp("chroma"))


def test_filtro_capitolo_vale_per_tutti_i_metodi(cerca):
    ammessi = cerca.ammessi("XII", None)
    assert ammessi and all(cerca.m.meta[p]["romano"] == "XII" for p in ammessi)
    for metodo in ("lessicale", "lsa", "parole", "ibrida", "ibrida3"):
        for p, _ in cerca.m.cerca("il gattino e la regina", metodo, 5, ammessi):
            assert p in ammessi, metodo


def test_filtro_due_condizioni(cerca):
    ammessi = cerca.ammessi("II", "dialogo")
    assert all(cerca.m.meta[p]["romano"] == "II" and cerca.m.meta[p]["tipo"] == "dialogo" for p in ammessi)


def test_uovo_sul_muro(cerca):
    top = [cerca.m.etichette[p] for p, _ in cerca.m.cerca("l'uovo seduto sul muro", "ibrida", 3)]
    assert "VI.2" in top


def test_ibrida_e_deterministica(cerca):
    a = cerca.m.cerca("il cavaliere con il nido di api", "ibrida", 5)
    b = cerca.m.cerca("il cavaliere con il nido di api", "ibrida", 5)
    assert a == b


def test_query_vuota_o_sconosciuta(cerca):
    assert cerca.m.cerca("xqzzk", "ibrida", 5) == []


def test_scena_contiene_il_paragrafo(cerca):
    for p in (0, 500, 1096):
        assert p in cerca.scene[cerca.scena_di[p]]


def test_riferimento_sbagliato(cerca):
    with pytest.raises(SystemExit):
        cerca.risolvi("ZZ.9")
