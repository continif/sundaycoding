"""
S05E01 — Cinque algoritmi di ordinamento scritti a mano, con contatori.

Tutti accettano una lista e una funzione key, come sorted(), e restituiscono
una NUOVA lista. Contano i confronti e le scritture (spostamenti o scambi):
sono i due costi che la teoria chiama in causa, e misurarli ci dice se la
teoria regge sui dati veri.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Conti:
    confronti: int = 0
    scritture: int = 0


def _prepara(lista, key):
    # Decorate: calcoliamo la chiave UNA volta per elemento, come fa sorted().
    # Gli algoritmi lavorano su coppie (chiave, indice originale, elemento).
    # L'indice serve a due cose: rende la tupla sempre confrontabile anche se
    # gli elementi non lo sono, e ci permette di verificare la stabilità.
    return [(key(x), i, x) for i, x in enumerate(lista)]


def _minore(a, b, conti: Conti) -> bool:
    # Un solo punto in cui si confronta: contiamo qui. Confrontiamo SOLO le
    # chiavi, non l'indice: se confrontassimo anche l'indice, ogni algoritmo
    # diventerebbe "stabile per finta".
    conti.confronti += 1
    return a[0] < b[0]


# ---------------------------------------------------------------------------
# Insertion sort: le carte in mano
# ---------------------------------------------------------------------------
def insertion_sort(lista, key=lambda x: x, conti: Conti | None = None):
    conti = conti if conti is not None else Conti()
    a = _prepara(lista, key)
    for i in range(1, len(a)):
        corrente = a[i]
        j = i - 1
        # Spostiamo a destra tutto ciò che è più grande, poi inseriamo.
        # "Più grande" stretto: a parità di chiave ci fermiamo, ed è questo
        # che rende insertion sort stabile.
        while j >= 0 and _minore(corrente, a[j], conti):
            a[j + 1] = a[j]
            conti.scritture += 1
            j -= 1
        a[j + 1] = corrente
        conti.scritture += 1
    return [x for _, _, x in a]


# ---------------------------------------------------------------------------
# Selection sort: cerco il più piccolo e lo metto in testa
# ---------------------------------------------------------------------------
def selection_sort(lista, key=lambda x: x, conti: Conti | None = None):
    conti = conti if conti is not None else Conti()
    a = _prepara(lista, key)
    n = len(a)
    for i in range(n - 1):
        minimo = i
        for j in range(i + 1, n):
            if _minore(a[j], a[minimo], conti):
                minimo = j
        if minimo != i:
            # Lo scambio a lunga distanza è quello che rompe la stabilità:
            # a[i] salta oltre elementi uguali a lui.
            a[i], a[minimo] = a[minimo], a[i]
            conti.scritture += 2
    return [x for _, _, x in a]


# ---------------------------------------------------------------------------
# Merge sort: due mazzetti ordinati diventano uno
# ---------------------------------------------------------------------------
def merge_sort(lista, key=lambda x: x, conti: Conti | None = None):
    conti = conti if conti is not None else Conti()

    def fondi(sinistra, destra):
        risultato = []
        i = j = 0
        while i < len(sinistra) and j < len(destra):
            # "Destra strettamente minore": a parità prende da sinistra,
            # quindi gli uguali restano nell'ordine originale. Stabile.
            if _minore(destra[j], sinistra[i], conti):
                risultato.append(destra[j])
                j += 1
            else:
                risultato.append(sinistra[i])
                i += 1
            conti.scritture += 1
        resto = sinistra[i:] + destra[j:]
        conti.scritture += len(resto)
        risultato.extend(resto)
        return risultato

    def ordina(a):
        if len(a) <= 1:
            return a
        meta = len(a) // 2
        return fondi(ordina(a[:meta]), ordina(a[meta:]))

    return [x for _, _, x in ordina(_prepara(lista, key))]


# ---------------------------------------------------------------------------
# Quicksort: scegli un pivot, dividi, ricomincia
# ---------------------------------------------------------------------------
def quick_sort(lista, key=lambda x: x, conti: Conti | None = None,
               pivot: str = "casuale", rng: random.Random | None = None):
    """pivot="ultimo" è la versione da manuale (Lomuto); "casuale" quella
    che si usa davvero. La differenza la misuriamo sui dati già ordinati."""
    conti = conti if conti is not None else Conti()
    rng = rng or random.Random(0)
    a = _prepara(lista, key)

    def partiziona(basso, alto):
        if pivot == "casuale":
            k = rng.randint(basso, alto)
            a[k], a[alto] = a[alto], a[k]
            conti.scritture += 2
        p = a[alto]
        i = basso
        for j in range(basso, alto):
            if _minore(a[j], p, conti):
                a[i], a[j] = a[j], a[i]
                conti.scritture += 2
                i += 1
        a[i], a[alto] = a[alto], a[i]
        conti.scritture += 2
        return i

    # Iterativo, con una pila esplicita. La versione ricorsiva da manuale
    # su una lista già ordinata scende di n livelli e Python si ferma a
    # 1000 (RecursionError). Con la pila esplicita il caso peggiore resta
    # lento, ma almeno non esplode: possiamo misurarlo.
    pila = [(0, len(a) - 1)]
    while pila:
        basso, alto = pila.pop()
        if basso < alto:
            m = partiziona(basso, alto)
            pila.append((basso, m - 1))
            pila.append((m + 1, alto))
    return [x for _, _, x in a]


# ---------------------------------------------------------------------------
# Heap sort: il torneo
# ---------------------------------------------------------------------------
def heap_sort(lista, key=lambda x: x, conti: Conti | None = None):
    conti = conti if conti is not None else Conti()
    a = _prepara(lista, key)
    n = len(a)

    def affonda(radice, fine):
        # Il genitore scende finché è più grande di un figlio: alla fine il
        # massimo è in cima. È lo stesso meccanismo di heapq, ma con il
        # massimo invece del minimo.
        while True:
            figlio = 2 * radice + 1
            if figlio >= fine:
                return
            if figlio + 1 < fine and _minore(a[figlio], a[figlio + 1], conti):
                figlio += 1
            if _minore(a[radice], a[figlio], conti):
                a[radice], a[figlio] = a[figlio], a[radice]
                conti.scritture += 2
                radice = figlio
            else:
                return

    for i in range(n // 2 - 1, -1, -1):
        affonda(i, n)
    for fine in range(n - 1, 0, -1):
        a[0], a[fine] = a[fine], a[0]
        conti.scritture += 2
        affonda(0, fine)
    return [x for _, _, x in a]


ALGORITMI: dict[str, Callable[..., list[Any]]] = {
    "insertion": insertion_sort,
    "selection": selection_sort,
    "merge": merge_sort,
    "quick": quick_sort,
    "heap": heap_sort,
}
