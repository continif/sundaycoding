"""
S05E05 paid — I libri vicini: i vettori dei paragrafi e la ricerca dei vicini
a forza bruta.

Due tipi di vettori, tutti e due dalla matrice di E04:
- TF-IDF: una colonna della matrice termini × paragrafi, 4.366 dimensioni,
  quasi tutte zero. Due paragrafi sono vicini solo se hanno parole in comune.
- LSA: la stessa colonna proiettata sulle prime 100 direzioni della SVD.
  100 dimensioni, tutte piene. Due paragrafi possono essere vicini anche
  senza parole in comune, se le loro parole stanno spesso negli stessi posti.

I vicini a forza bruta sono un prodotto tra matrici: tutti i paragrafi per
la query (o per tutti i paragrafi), poi i migliori k. È E04, con un nome nuovo.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.sparse.linalg import svds

RADICE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RADICE / "e03"), str(RADICE / "e04")]
from registro import Registro  # noqa: E402

DIREZIONI = 100      # come nella free di E04: 100 direzioni tengono il 43% dell'energia


def normalizza(m: np.ndarray) -> np.ndarray:
    """Ogni riga a lunghezza 1. Le righe tutte zero (VI.55 e VIII.46, solo
    parole vuote) restano zero invece di diventare NaN."""
    n = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.where(n > 0, n, 1)


class Vettori:
    def __init__(self, registro: Registro, direzioni: int = DIREZIONI, dtype=np.float32):
        self.r = registro
        w = registro.tfidf                              # termini × paragrafi, sparsa
        # svds parte da un vettore a caso: con v0 fissato i risultati sono
        # gli stessi a ogni esecuzione (anche il segno delle direzioni, che
        # altrimenti può cambiare e far sembrare diversi due calcoli uguali).
        v0 = np.random.default_rng(0).standard_normal(min(w.shape))
        u, s, vt = svds(w, k=direzioni, v0=v0)
        ordine = np.argsort(-s)                         # svds le restituisce in ordine crescente
        self.u, self.s = u[:, ordine], s[ordine]
        # Le coordinate dei paragrafi nello spazio ridotto. U^T · W = Σ · V^T:
        # proiettare la matrice sulle direzioni o prendere Σ·V^T è la stessa
        # cosa, e la query si proietta allo stesso modo (U^T · q).
        lsa = (vt[ordine].T * self.s)
        # float32: per un ordinamento basta e avanza (E04: nessuna classifica
        # cambiata su 500 query), e metà memoria. Chroma salva comunque float32.
        self.lsa = normalizza(lsa).astype(dtype)
        # TF-IDF normalizzata, da usare densa: 1.097 × 4.366 in float32 sono
        # 19 MB. Per un libro si può; per una biblioteca no, e lì si resta sparsi.
        self.tfidf = normalizza(registro.coseno.T.toarray()).astype(dtype)
        self.n = len(self.lsa)

    # ------------------------------------------------------------------
    def query_tfidf(self, gruppi: list[list[str]]) -> np.ndarray:
        """La query come colonna della matrice: per ogni gruppo di varianti
        (E04) il peso idf di ciascuna forma presente nel libro."""
        q = np.zeros(len(self.r.forme), dtype=np.float64)
        for gruppo in gruppi:
            for forma in gruppo:
                if forma in self.r.riga:
                    i = self.r.riga[forma]
                    q[i] = self.r.idf[i]
        return q

    def query_lsa(self, gruppi: list[list[str]]) -> np.ndarray:
        """Stessa colonna, proiettata sulle stesse direzioni dei paragrafi."""
        q = self.u.T @ self.query_tfidf(gruppi)
        return normalizza(q[None, :])[0].astype(self.lsa.dtype)


# ----------------------------------------------------------------------
# I vicini a forza bruta
# ----------------------------------------------------------------------
def migliori_k(punteggi: np.ndarray, k: int) -> np.ndarray:
    """Gli indici dei k punteggi più alti, in ordine, riga per riga.

    argpartition mette i k più grandi in fondo senza ordinare il resto
    (lineare); poi si ordinano solo quei k. È l'heap di E01 fatto da NumPy
    su tutte le righe insieme: con 1.097 colonne è ~3 volte più veloce di
    un argsort completo."""
    if punteggi.ndim == 1:
        return migliori_k(punteggi[None, :], k)[0]
    k = min(k, punteggi.shape[1])
    parte = np.argpartition(-punteggi, k - 1, axis=1)[:, :k]
    righe = np.arange(len(punteggi))[:, None]
    ordine = np.argsort(-punteggi[righe, parte], axis=1)
    return parte[righe, ordine]


def vicini(base: np.ndarray, query: np.ndarray, k: int = 10, escludi_se: bool = False) -> np.ndarray:
    """kNN a forza bruta con il coseno: vettori già normalizzati, quindi il
    coseno è il prodotto scalare e tutte le query insieme sono UNA
    moltiplicazione tra matrici (query × base^T), come le 42 query di E04.

    escludi_se: quando le query sono i paragrafi stessi, il vicino più
    vicino di ognuno è lui, con coseno 1. Si toglie mettendo la diagonale a -inf."""
    sim = query @ base.T
    if escludi_se:
        np.fill_diagonal(sim, -np.inf)
    return migliori_k(sim, k)
