"""
S05E06 paid — Le parole in casa: embedding di parole addestrati sul libro.

Nessun modello scaricato. Si parte dai token che il NOSTRO tokenizzatore
(E03) ha già messo nell'indice, si contano le parole che stanno vicine, e
con tre passaggi di algebra (che nella puntata di E04 abbiamo già fatto) si
ottiene per ogni parola un vettore di 100 numeri:

    1. co-occorrenze: quante volte la parola i sta a meno di 5 parole dalla j;
    2. PPMI: si tiene solo quello che succede PIÙ spesso del caso;
    3. SVD: si comprime la matrice a 100 direzioni.

È la ricetta di Levy e Goldberg (2014), che hanno mostrato che word2vec
(skip-gram con negative sampling) sta facendo, senza dirlo, la
fattorizzazione di questa matrice. Qui la facciamo apertamente.

Il limite va detto subito: il libro ha 27.000 parole. word2vec vero impara
da miliardi. Questi vettori sanno dove stanno le parole in QUESTO libro, e
poco altro.

Uso:
    python parole.py ../indice/
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import duckdb
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import svds

RADICE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RADICE / "e03"), str(RADICE / "e04")]
from registro import Registro  # noqa: E402


def sequenze(cartella_indice: Path) -> list[tuple[str, list[str]]]:
    """Per ogni paragrafo, nell'ordine del libro: (capitolo, forme nell'ordine
    del testo). L'indice di E03 le ha già: forma, paragrafo, posizione."""
    con = duckdb.connect()
    etichette = dict(con.execute(
        f"SELECT paragrafo, etichetta FROM '{cartella_indice / 'paragrafi.parquet'}'").fetchall())
    per_par: dict[int, list[str]] = defaultdict(list)
    # ORDER BY posizione: l'indice è ordinato per forma, il testo no.
    for p, forma in con.execute(
            f"SELECT paragrafo, forma FROM '{cartella_indice / 'indice.parquet'}' "
            "ORDER BY paragrafo, posizione").fetchall():
        per_par[p].append(forma)
    return [(etichette[p].split(".")[0], per_par.get(p, [])) for p in sorted(etichette)]


class Parole:
    def __init__(self, registro: Registro, cartella_indice: Path, dimensioni: int = 100,
                 finestra: int = 5, oltre_il_paragrafo: bool = True, min_volte: int = 2,
                 alfa: float = 0.75, esponente: float = 0.5):
        self.r = registro
        v = len(registro.forme)

        # --- 1. Co-occorrenze -------------------------------------------
        seq = sequenze(cartella_indice)
        if oltre_il_paragrafo:
            # I dialoghi del libro sono battute di dieci parole: "- Non
            # saresti in nessuna parte" da solo non dice niente. La finestra
            # attraversa i paragrafi, ma non i capitoli (un capitolo finisce,
            # il successivo è un'altra storia).
            flussi, corrente, cap = [], [], None
            for capitolo, forme in seq:
                if capitolo != cap and corrente:
                    flussi.append(corrente)
                    corrente = []
                cap = capitolo
                corrente += forme
            flussi.append(corrente)
        else:
            flussi = [forme for _, forme in seq]

        righe, colonne, pesi = [], [], []
        volte = np.zeros(v)
        for flusso in flussi:
            ids = np.array([registro.riga[f] for f in flusso], dtype=np.int64)
            np.add.at(volte, ids, 1)
            for d in range(1, finestra + 1):
                if len(ids) <= d:
                    break
                # Il peso è 1/d: la parola accanto conta più di quella a
                # cinque posti. word2vec fa lo stesso con la "finestra
                # dinamica", a caso; qui è un peso e basta.
                righe.append(ids[:-d]); colonne.append(ids[d:]); pesi.append(np.full(len(ids) - d, 1.0 / d))
        r_, c_, w_ = np.concatenate(righe), np.concatenate(colonne), np.concatenate(pesi)
        # Simmetrica: se i sta vicino a j, j sta vicino a i.
        C = sparse.coo_matrix((np.concatenate([w_, w_]),
                               (np.concatenate([r_, c_]), np.concatenate([c_, r_]))), shape=(v, v)).tocsr()

        # --- 2. PPMI ------------------------------------------------------
        # Le parole viste una volta sola hanno contesti irripetibili: ogni
        # loro coppia è "rarissima", quindi PMI altissimo, e riempiono la
        # matrice di rumore. Si tengono le parole con almeno min_volte
        # occorrenze; le altre restano a zero (e il lessicale le trova lo stesso).
        ammesse = volte >= min_volte
        C = sparse.diags(ammesse.astype(float)) @ C @ sparse.diags(ammesse.astype(float))
        C = C.tocoo()
        riga_tot = np.asarray(C.sum(axis=1)).ravel()
        # Smoothing del contesto (alfa=0,75): elevando i totali delle colonne
        # a 0,75 si tolgono punti alle parole frequentissime come contesto,
        # e si evita che le rarissime abbiano PMI esagerato.
        col_alfa = np.asarray(C.sum(axis=0)).ravel() ** alfa
        totale = C.sum()
        pmi = np.log(C.data * col_alfa.sum() / (riga_tot[C.row] * col_alfa[C.col]))
        # Solo i positivi: "più spesso del caso" ha informazione, "meno
        # spesso" in 27.000 parole è per lo più assenza di dati.
        tieni = pmi > 0
        ppmi = sparse.csr_matrix((pmi[tieni], (C.row[tieni], C.col[tieni])), shape=(v, v))
        self.densita = ppmi.nnz / (v * v)

        # --- 3. SVD -------------------------------------------------------
        v0 = np.random.default_rng(0).standard_normal(v)          # risultati ripetibili
        u, s, _ = svds(ppmi, k=dimensioni, v0=v0)
        ordine = np.argsort(-s)
        # u · sigma^0,5: Levy e Goldberg trovano che pesare per la radice
        # dei valori singolari dà vettori migliori di u da solo (troppo
        # peso alle direzioni piccole) e di u · sigma (troppo alle grandi).
        vett = u[:, ordine] * s[ordine] ** esponente
        n = np.linalg.norm(vett, axis=1, keepdims=True)
        self.vett = np.where(n > 0, vett / np.where(n > 0, n, 1), 0.0).astype(np.float32)
        self.ammesse = ammesse
        self.volte = volte

        # --- Dalle parole ai paragrafi: una moltiplicazione ---------------
        # Il vettore di un paragrafo è la media delle sue parole pesata per
        # tf-idf: tfidf^T (paragrafi × parole) · vett (parole × 100). La media
        # che in Python sarebbe un ciclo su ogni parola di ogni paragrafo è
        # UNA moltiplicazione sparsa × densa.
        w = registro.tfidf.T.tocsr() @ sparse.diags(ammesse.astype(float))
        paragrafi = np.asarray(w @ self.vett)
        n = np.linalg.norm(paragrafi, axis=1, keepdims=True)
        self.paragrafi = np.where(n > 0, paragrafi / np.where(n > 0, n, 1), 0.0).astype(np.float32)

    # ------------------------------------------------------------------
    def vicine(self, parola: str, k: int = 8) -> list[tuple[str, float]]:
        """Le parole più vicine: il coseno è un prodotto scalare."""
        i = self.r.riga[parola]
        s = self.vett @ self.vett[i]
        s[i] = -np.inf
        s[~self.ammesse] = -np.inf
        return [(self.r.forme[j], float(s[j])) for j in np.argsort(-s)[:k]]

    def query(self, gruppi: list[list[str]]) -> np.ndarray:
        """La query nello stesso spazio. Per ogni termine (gruppo di varianti,
        come in E04) il centroide delle sue forme, pesato per quanto sono
        frequenti, moltiplicato per l'idf del gruppo."""
        q = np.zeros(self.vett.shape[1])
        for forme in gruppi:
            idx = [self.r.riga[f] for f in forme if f in self.r.riga and self.ammesse[self.r.riga[f]]]
            if not idx:
                continue
            df = np.count_nonzero(np.asarray(self.r.tf[idx].sum(axis=0)).ravel())
            idf = np.log(self.r.n / df)
            peso = self.volte[idx]
            q += idf * (peso[:, None] * self.vett[idx]).sum(axis=0) / peso.sum()
        n = np.linalg.norm(q)
        return (q / n).astype(np.float32) if n > 0 else q.astype(np.float32)


if __name__ == "__main__":
    import time
    t0 = time.perf_counter()
    reg = Registro(Path(sys.argv[1]))
    p = Parole(reg, Path(sys.argv[1]))
    print(f"addestrate in {time.perf_counter() - t0:.2f} s; parole con vettore: {int(p.ammesse.sum())} su {len(reg.forme)}")
    for parola in ("regina", "correre", "sogno", "uovo", "torta", "re", "bosco"):
        if parola in reg.riga:
            print(f"{parola:10}", ", ".join(f"{f} {s:.2f}" for f, s in p.vicine(parola, 6)))
