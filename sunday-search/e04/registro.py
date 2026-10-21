"""
S05E04 paid — Il registro di carico: la matrice termini × paragrafi del
libro, i pesi TF-IDF e BM25, il ranking e la diversità dei risultati.

La matrice si costruisce dall'indice di E03 (indice/indice.parquet): righe =
forme, colonne = paragrafi, valori = quante volte la forma compare nel
paragrafo. È lo stesso dato dell'indice, letto come matrice.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
from scipy import sparse

# I due parametri di BM25, ai valori che usano quasi tutti (Lucene compreso).
# k1: quanto conta ripetere una parola (oltre k1 ripetizioni conta poco).
# b:  quanto si punisce la lunghezza del paragrafo (0 = per niente, 1 = tutta).
K1, B = 1.2, 0.75


class Registro:
    def __init__(self, cartella: Path, dtype=np.float64):
        con = duckdb.connect()
        # Una query: forma, paragrafo, quante volte. GROUP BY in DuckDB
        # invece che un Counter in Python: 17.686 righe diventano 16.511.
        righe = con.execute(f"""
            SELECT forma, paragrafo, count(*)::INTEGER AS volte
            FROM '{cartella / "indice.parquet"}'
            GROUP BY forma, paragrafo""").fetchall()
        self.etichette = dict(con.execute(
            f"SELECT paragrafo, etichetta FROM '{cartella / 'paragrafi.parquet'}'").fetchall())
        self.testi = dict(con.execute(
            f"SELECT paragrafo, testo FROM '{cartella / 'paragrafi.parquet'}'").fetchall())
        self.forme = sorted({r[0] for r in righe})
        self.riga = {f: i for i, f in enumerate(self.forme)}
        n_t, n_p = len(self.forme), len(self.etichette)

        # COO → CSR: COO è la tabella di triple (riga, colonna, valore),
        # comoda da costruire; CSR è la stessa cosa compressa per righe,
        # comoda da leggere una riga alla volta. Come l'indice di E03.
        self.tf = sparse.coo_matrix(
            (np.array([r[2] for r in righe], dtype=dtype),
             (np.array([self.riga[r[0]] for r in righe]), np.array([r[1] for r in righe]))),
            shape=(n_t, n_p)).tocsr()
        self.n = n_p
        self.df = np.diff(self.tf.indptr)                  # paragrafi per forma
        self.lunghezze = np.asarray(self.tf.sum(axis=0)).ravel()
        self.media = self.lunghezze.mean()

        # --- TF-IDF -----------------------------------------------------
        self.idf = np.log(n_p / self.df).astype(dtype)
        # diags(idf) @ tf: ogni riga moltiplicata per il suo idf. È una
        # moltiplicazione per una matrice diagonale, ma SciPy non costruisce
        # nessuna matrice piena: scala le righe e basta.
        self.tfidf = (sparse.diags(self.idf) @ self.tf).tocsr()
        norme = np.sqrt(np.asarray(self.tfidf.multiply(self.tfidf).sum(axis=0)).ravel())
        self.norme = np.where(norme > 0, norme, 1).astype(dtype)   # i 2 paragrafi vuoti
        # Le colonne normalizzate: il coseno diventa un prodotto scalare.
        self.coseno = (self.tfidf @ sparse.diags(1 / self.norme)).tocsr()

        # --- BM25 -------------------------------------------------------
        self.idf_bm25 = np.log(1 + (n_p - self.df + 0.5) / (self.df + 0.5)).astype(dtype)
        coo = self.tf.tocoo()
        tf = coo.data
        lung = self.lunghezze[coo.col]
        # Il peso BM25 di ogni casella piena, calcolato una volta sola:
        # satura con le ripetizioni (k1) e corregge per la lunghezza (b).
        pesi = self.idf_bm25[coo.row] * tf * (K1 + 1) / (tf + K1 * (1 - B + B * lung / self.media))
        self.bm25 = sparse.csr_matrix((pesi.astype(dtype), (coo.row, coo.col)), shape=(n_t, n_p))

    # ------------------------------------------------------------------
    # Le versioni "a mano": un ciclo sulle liste dell'indice, come in E03
    # ------------------------------------------------------------------
    def liste(self) -> dict[str, list[tuple[int, int]]]:
        """forma → [(paragrafo, volte)]: l'indice di E03, dalla matrice."""
        out = {}
        for f, i in self.riga.items():
            a, b = self.tf.indptr[i], self.tf.indptr[i + 1]
            out[f] = list(zip(self.tf.indices[a:b].tolist(), self.tf.data[a:b].astype(int).tolist()))
        return out

    def bm25_a_mano(self, liste, termini: list[str]) -> dict[int, float]:
        punteggi: dict[int, float] = defaultdict(float)
        for t in termini:
            if t not in liste:
                continue
            df = len(liste[t])
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for par, tf in liste[t]:
                lung = self.lunghezze[par]
                punteggi[par] += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * lung / self.media))
        return punteggi

    # ------------------------------------------------------------------
    # Le versioni con le matrici
    # ------------------------------------------------------------------
    def vettore(self, termini: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """La query come (righe, pesi): solo le caselle non zero del vettore.
        Una forma ripetuta nella query vale di più, come nelle formule."""
        conta: dict[int, float] = defaultdict(float)
        for t in termini:
            if t in self.riga:
                conta[self.riga[t]] += 1.0
        righe = np.fromiter(conta.keys(), dtype=np.int64)
        return righe, np.fromiter(conta.values(), dtype=np.float64)

    def punteggi(self, termini: list[str], schema: str = "bm25") -> np.ndarray:
        """Matrice × vettore, leggendo solo le righe della query: W[righe]
        in CSR è una fetta, poi la trasposta per il vettore dei pesi."""
        righe, pesi = self.vettore(termini)
        if len(righe) == 0:
            return np.zeros(self.n)
        if schema == "conteggi":
            w = self.tf
        elif schema == "tfidf":
            w = self.tfidf
        elif schema == "coseno":
            w = self.coseno
            pesi = pesi * self.idf[righe]
            pesi = pesi / np.linalg.norm(pesi)
        else:
            w = self.bm25
        return np.asarray(w[righe].T @ pesi).ravel()

    def punteggi_gruppi(self, gruppi: list[list[str]], schema: str = "bm25") -> np.ndarray:
        """Come punteggi(), ma ogni termine della query è un GRUPPO di forme
        (le varianti di E03: regina e regine, gridare e le sue 178 forme).

        Le forme di un gruppo si sommano in una riga sola prima di pesarle.
        Se le pesassimo una per una, ognuna con il suo idf, il plurale raro
        "regine" (14 paragrafi) peserebbe molto più di "regina" (168), e in
        cima finirebbero solo i paragrafi con le Regine al plurale. Per chi
        cerca, regina e regine sono una parola sola, e così deve contare."""
        totale = np.zeros(self.n)
        for forme in gruppi:
            righe = [self.riga[f] for f in forme if f in self.riga]
            if not righe:
                continue
            # La riga del gruppo: somma delle righe delle forme. Densa, ma
            # sono 1.097 numeri: costa meno che tenerla sparsa.
            tf = np.asarray(self.tf[righe].sum(axis=0)).ravel()
            df = np.count_nonzero(tf)
            if schema == "conteggi":
                totale += tf
            elif schema in ("tfidf", "coseno"):
                w = np.log(self.n / df) * tf
                totale += w / self.norme if schema == "coseno" else w
            else:
                idf = np.log(1 + (self.n - df + 0.5) / (df + 0.5))
                denominatore = tf + K1 * (1 - B + B * self.lunghezze / self.media)
                totale += np.where(tf > 0, idf * tf * (K1 + 1) / denominatore, 0.0)
        return totale

    def migliori(self, punteggi: np.ndarray, k: int = 10) -> list[int]:
        """I k migliori con un heap: niente sort di 1.097 numeri. A parità di
        punteggio vince il paragrafo che viene prima nel libro."""
        candidati = np.flatnonzero(punteggi)
        return heapq.nlargest(k, candidati.tolist(), key=lambda p: (punteggi[p], -p))

    # ------------------------------------------------------------------
    # Risultati vari
    # ------------------------------------------------------------------
    def simili(self, paragrafi: list[int]) -> np.ndarray:
        """Matrice dei coseni tra paragrafi: Gram delle colonne normalizzate."""
        v = self.coseno[:, paragrafi].T.tocsr()
        return (v @ v.T).toarray()

    def vari_det(self, punteggi: np.ndarray, k: int = 10, candidati: int = 50) -> list[int]:
        """Greedy alla maniera dei determinantal point process: tra i primi
        `candidati`, si sceglie ogni volta il paragrafo che fa crescere di
        più il log del determinante di L = diag(r) · S · diag(r), dove S sono
        i coseni e r la pertinenza. Pertinenza alta e poca somiglianza con
        quelli già scelti: è la stessa misura che tiene insieme le due cose."""
        pool = self.migliori(punteggi, candidati)
        r = punteggi[pool] / punteggi[pool].max()
        L = np.outer(r, r) * self.simili(pool)
        scelti: list[int] = []
        while len(scelti) < min(k, len(pool)):
            meglio, valore = None, -np.inf
            for i in range(len(pool)):
                if i in scelti:
                    continue
                idx = scelti + [i]
                # slogdet: con dieci paragrafi il determinante diventa
                # piccolo in fretta (vedi la free), il logaritmo no.
                segno, ld = np.linalg.slogdet(L[np.ix_(idx, idx)])
                if segno > 0 and ld > valore:
                    meglio, valore = i, ld
            if meglio is None:         # tutti i rimasti sono doppioni esatti
                break
            scelti.append(meglio)
        return [pool[i] for i in scelti]

    def vari_mmr(self, punteggi: np.ndarray, k: int = 10, candidati: int = 50,
                 lam: float = 0.7) -> list[int]:
        """Maximal Marginal Relevance (Carbonell e Goldstein, 1998): ogni
        volta il paragrafo con lam × pertinenza − (1 − lam) × somiglianza
        massima con quelli già scelti. Più semplice, e il confronto onesto."""
        pool = self.migliori(punteggi, candidati)
        r = punteggi[pool] / punteggi[pool].max()
        S = self.simili(pool)
        scelti: list[int] = []
        while len(scelti) < min(k, len(pool)):
            def valore(i):
                vicino = max((S[i, j] for j in scelti), default=0.0)
                return lam * r[i] - (1 - lam) * vicino
            scelti.append(max((i for i in range(len(pool)) if i not in scelti), key=valore))
        return [pool[i] for i in scelti]

    def doppioni(self, paragrafi: list[int], soglia: float = 0.5) -> int:
        """Quante coppie di risultati si somigliano oltre la soglia."""
        S = self.simili(paragrafi)
        return int((np.triu(S, 1) >= soglia).sum())

    def volume(self, paragrafi: list[int]) -> float:
        segno, ld = np.linalg.slogdet(self.simili(paragrafi))
        return float(segno * math.exp(ld))
