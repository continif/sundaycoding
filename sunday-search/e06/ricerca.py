"""
S05E06 paid — Il motore: i rankers della stagione e come si fondono.

Ogni ranker risponde alla stessa domanda, "quanto questo paragrafo c'entra
con la query?", con un punteggio per ognuno dei 1.097 paragrafi:

    lessicale   BM25 sulle parole e le loro varianti          (E03 + E04)
    tesauro     BM25 allargato ai sinonimi del thesaurus       (E06)
    lsa         il paragrafo come 100 direzioni della SVD      (E05)
    parole      la media delle parole, addestrate sul libro    (E06)

e la ricerca ibrida li fonde con il Reciprocal Rank Fusion (RRF), che non
guarda i punteggi ma solo le POSIZIONI: BM25 dà numeri tra 0 e 30, un
coseno tra 0 e 1, e sommarli sarebbe sommare metri e secondi.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RADICE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RADICE / d) for d in ("e03", "e04", "e05", "e06")]
from indice import Indice               # noqa: E402
from parole import Parole               # noqa: E402
from registro import Registro           # noqa: E402
from tesauro import espandi             # noqa: E402
from vettori import Vettori             # noqa: E402
from vocabolario import Vocabolario     # noqa: E402

# Quanto contano i sinonimi rispetto alla parola cercata. 0,3: un
# sinonimo che compare nel paragrafo vale meno di un terzo della parola
# stessa. Scelto prima di misurare, e non toccato dopo.
ESPANSIONE = 0.3

# La costante dell'RRF: ammorbidisce il vantaggio dei primissimi posti.
# 60 è il valore del paper originale (Cormack, Clarke e Büttcher, 2009).
K_RRF = 60

# "ibrida" è la fusione dei 4 rankers, decisa PRIMA di misurare. "ibrida3" toglie
# il lessicale (già dentro il tesauro, che lo contiene): nata DOPO aver visto i
# numeri di valuta.py, e dichiarata tale nella puntata.
COMPONENTI = {
    "ibrida":  ("lessicale", "tesauro", "lsa", "parole"),
    "ibrida3": ("tesauro", "lsa", "parole"),
}
METODI = ("lessicale", "tesauro", "lsa", "parole") + tuple(COMPONENTI)


def rrf(rankings: list[list[int]], k: int = K_RRF) -> dict[int, float]:
    """Reciprocal Rank Fusion: ogni paragrafo prende 1/(k + posizione) da
    ogni classifica in cui compare, e si sommano. Un paragrafo al terzo
    posto in due classifiche batte uno al primo posto in una sola, e un
    paragrafo che una classifica non vede non perde niente: prende zero."""
    punti: dict[int, float] = {}
    for classifica in rankings:
        for posizione, p in enumerate(classifica, start=1):
            punti[p] = punti.get(p, 0.0) + 1.0 / (k + posizione)
    return punti


class Motore:
    def __init__(self, cartella_indice: Path, cartella_voc: Path, corpus: Path | None = None):
        self.voc = Vocabolario(cartella_voc)
        self.indice = Indice(cartella_indice, self.voc)
        self.reg = Registro(cartella_indice)
        self.vet = Vettori(self.reg)                       # E05: LSA a 100 direzioni
        self.par = Parole(self.reg, cartella_indice)       # E06: le parole in casa
        self.etichette = self.reg.etichette
        self.numero = {e: n for n, e in self.etichette.items()}
        self.meta: dict[int, dict] = {}
        if corpus and corpus.exists():
            with corpus.open(encoding="utf-8") as f:
                for riga in f:
                    d = json.loads(riga)
                    self.meta[self.numero[f"{d['romano']}.{d['posizione']}"]] = d

    # ------------------------------------------------------------------
    def termini(self, query: str) -> list[str]:
        return [t for t, _ in self.indice.termini(query)]

    def gruppi(self, query: str) -> list[list[str]]:
        """Ogni termine con le sue varianti: la stessa dogana per tutti i ranker."""
        return [sorted(self.indice.varianti(t)) for t in self.termini(query)]

    def punteggi(self, metodo: str, query: str) -> np.ndarray:
        g = self.gruppi(query)
        if metodo == "lessicale":
            return self.reg.punteggi_gruppi(g)
        if metodo == "tesauro":
            # La parola cercata più i suoi sinonimi, questi a peso ridotto.
            # Si sommano i due BM25: lo schema è lineare nei termini.
            base = self.reg.punteggi_gruppi(g)
            sin = [x for x in espandi(self.indice, self.termini(query)) if x]
            return base + ESPANSIONE * self.reg.punteggi_gruppi(sin) if sin else base
        if metodo == "lsa":
            return self.vet.lsa @ self.vet.query_lsa(g)
        if metodo == "parole":
            return self.par.paragrafi @ self.par.query(g)
        raise ValueError(metodo)

    def classifica(self, punteggi: np.ndarray, k: int = 100) -> list[int]:
        """I paragrafi in ordine di punteggio, escludendo chi ha zero (nel
        lessicale: chi non contiene nessuna parola della query)."""
        ordine = np.lexsort((np.arange(len(punteggi)), -punteggi))   # a parità, prima nel libro
        return [int(p) for p in ordine[:k] if punteggi[p] > 0]

    def ibrida(self, query: str, componenti: tuple[str, ...] = ("lessicale", "tesauro", "lsa", "parole")) -> dict[int, float]:
        return rrf([self.classifica(self.punteggi(m, query)) for m in componenti])

    def cerca(self, query: str, metodo: str = "ibrida", k: int = 5, ammessi: set[int] | None = None) -> list[tuple[int, float]]:
        if metodo in COMPONENTI:
            punti = self.ibrida(query, COMPONENTI[metodo])
            if ammessi is not None:
                punti = {p: s for p, s in punti.items() if p in ammessi}
            ordine = sorted(punti, key=lambda p: (-punti[p], p))[:k]
            return [(p, punti[p]) for p in ordine]
        s = self.punteggi(metodo, query)
        if ammessi is not None:
            s = np.where(np.isin(np.arange(len(s)), list(ammessi)), s, 0)
        return [(p, float(s[p])) for p in self.classifica(s, k)]
