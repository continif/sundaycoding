"""
S05E05 paid — HNSW in miniatura, per capire cosa fa Chroma sotto il cofano.

HNSW (Malkov e Yashunin, 2016) è un grafo a piani:
- al piano 0 ci sono tutti i vettori, ognuno collegato ai suoi vicini;
- ogni piano sopra ne tiene una frazione sempre più piccola (come un
  sorteggio: 1 su M sale di un piano, 1 su M² di due...), con archi più lunghi;
- la ricerca parte dall'alto, dove pochi nodi coprono tutto lo spazio, e
  scende: a ogni piano si cammina verso la query finché ci si avvicina, poi
  si scende e si ricomincia dal punto raggiunto.

È la BFS di E02 con una coda di priorità al posto della deque: si esplora
prima il nodo più vicino alla query, e si smette quando nessun candidato
può più migliorare i risultati. I parametri hanno i nomi che usa Chroma:
max_neighbors (la M dei paper), ef_construction, ef_search.

Scritto per essere letto, non per essere veloce: Chroma usa hnswlib, in C++.
Il contatore `distanze` dice quanto lavoro si è risparmiato rispetto alla
forza bruta, che calcola N distanze per ogni query.
"""

from __future__ import annotations

import heapq
import math

import numpy as np


class HNSW:
    def __init__(self, max_neighbors: int = 16, ef_construction: int = 100, seme: int = 0):
        self.m = max_neighbors
        self.m0 = 2 * max_neighbors        # al piano 0 il doppio degli archi, come in hnswlib
        self.ef_construction = ef_construction
        self.ml = 1 / math.log(max_neighbors)   # regola il sorteggio dei piani
        self.rng = np.random.default_rng(seme)
        self.piani: list[dict[int, list[int]]] = []   # piano → {nodo: vicini}
        self.ingresso: int | None = None
        self.x: np.ndarray | None = None
        self.distanze = 0                  # il contatore, come quello dei confronti in E01

    # ------------------------------------------------------------------
    def _dist(self, q: np.ndarray, nodi: list[int]) -> np.ndarray:
        # Vettori normalizzati: distanza coseno = 1 - prodotto scalare.
        # È la stessa che Chroma usa con space="cosine".
        self.distanze += len(nodi)
        return 1.0 - self.x[nodi] @ q

    def _cerca_piano(self, q: np.ndarray, partenze: list[int], ef: int, piano: int) -> list[tuple[float, int]]:
        """Il cuore dell'algoritmo. Due code:
        - candidati: da esplorare, il più vicino in cima (min-heap);
        - trovati: i migliori ef visti finora, il PEGGIORE in cima (max-heap,
          con il segno cambiato), così si sa subito chi buttare fuori."""
        d = self._dist(q, partenze)
        visti = set(partenze)
        candidati = [(float(di), n) for di, n in zip(d, partenze)]
        heapq.heapify(candidati)
        trovati = [(-di, n) for di, n in candidati]
        heapq.heapify(trovati)
        while candidati:
            dc, c = heapq.heappop(candidati)
            # Il candidato più vicino è già più lontano del peggiore dei
            # trovati: niente di quello che resta può migliorare. Ci si ferma.
            # È qui che HNSW risparmia: non guarda tutto, guarda finché serve.
            if dc > -trovati[0][0]:
                break
            nuovi = [v for v in self.piani[piano][c] if v not in visti]
            if not nuovi:
                continue
            visti.update(nuovi)
            for dv, v in zip(self._dist(q, nuovi), nuovi):
                dv = float(dv)
                if len(trovati) < ef or dv < -trovati[0][0]:
                    heapq.heappush(candidati, (dv, v))
                    heapq.heappush(trovati, (-dv, v))
                    if len(trovati) > ef:
                        heapq.heappop(trovati)
        return sorted((-d, n) for d, n in trovati)

    # ------------------------------------------------------------------
    def costruisci(self, x: np.ndarray) -> "HNSW":
        self.x = x
        for nodo in range(len(x)):
            self._inserisci(nodo)
        return self

    def _inserisci(self, nodo: int) -> None:
        # Il piano più alto del nodo: un sorteggio con probabilità che cala
        # di un fattore M a ogni piano. Con M=16 e 1.097 nodi: ~68 al piano 1,
        # ~4 al piano 2. Nessuno decide chi va su: è il caso a tenere il grafo
        # bilanciato, come nelle skip list.
        livello = int(-math.log(1.0 - self.rng.random()) * self.ml)
        cima = len(self.piani) - 1         # il piano più alto PRIMA di questo nodo
        while len(self.piani) <= livello:
            self.piani.append({})
        for p in range(livello + 1):
            self.piani[p][nodo] = []
        if self.ingresso is None:
            self.ingresso = nodo
            return
        q = self.x[nodo]
        corrente = [self.ingresso]
        # Sopra il suo livello si scende in fretta: ef=1, solo il più vicino.
        for p in range(cima, livello, -1):
            corrente = [self._cerca_piano(q, corrente, 1, p)[0][1]]
        # Dal suo livello in giù: ef_construction candidati, i migliori M
        # diventano i vicini. Più grande ef_construction, migliori i vicini
        # scelti e più lenta la costruzione. Non si cambia dopo: il grafo è fatto.
        for p in range(min(livello, cima), -1, -1):
            trovati = self._cerca_piano(q, corrente, self.ef_construction, p)
            massimo = self.m0 if p == 0 else self.m
            scelti = [n for _, n in trovati[: self.m]]
            self.piani[p][nodo] = scelti
            for v in scelti:
                archi = self.piani[p][v]
                archi.append(nodo)
                if len(archi) > massimo:
                    # Troppi archi: si tengono i più vicini. (hnswlib usa
                    # un'euristica che preferisce archi in direzioni diverse;
                    # qui la versione semplice, che basta per capire.)
                    d = self._dist(self.x[v], archi)
                    self.piani[p][v] = [archi[i] for i in np.argsort(d)[:massimo]]
            corrente = [n for _, n in trovati]
        if livello > cima:
            self.ingresso = nodo

    # ------------------------------------------------------------------
    def cerca(self, q: np.ndarray, k: int = 10, ef_search: int = 100) -> list[int]:
        corrente = [self.ingresso]
        for p in range(len(self.piani) - 1, 0, -1):
            corrente = [self._cerca_piano(q, corrente, 1, p)[0][1]]
        # ef_search si può cambiare a ogni query: è solo quanti candidati
        # tenere in mano al piano 0. Sotto k non ha senso.
        return [n for _, n in self._cerca_piano(q, corrente, max(ef_search, k), 0)[:k]]
