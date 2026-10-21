"""
S05E04 paid — PageRank sui personaggi del libro.

Il grafo degli incontri di E02 (due personaggi sono collegati se compaiono
nello stesso paragrafo), questa volta con il peso: quanti paragrafi hanno in
comune. Chi è il personaggio più "centrale"? PageRank lo calcola moltiplicando
una matrice per un vettore finché il vettore smette di cambiare.

Uso:
    python pagerank.py ../corpus/specchio.jsonl
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e02"))
from personaggi import PERSONAGGI, carica, chi_compare  # noqa: E402


def matrice_incontri(paragrafi: list[dict]) -> np.ndarray:
    """A[i][j] = in quanti paragrafi compaiono insieme i e j."""
    pos = {n: i for i, n in enumerate(PERSONAGGI)}
    a = np.zeros((len(PERSONAGGI), len(PERSONAGGI)))
    for p in paragrafi:
        for x, y in combinations(sorted(chi_compare(p["testo"])), 2):
            a[pos[x], pos[y]] += 1
            a[pos[y], pos[x]] += 1
    return a


def transizioni(a: np.ndarray) -> np.ndarray:
    """La matrice del "lettore che salta": dalla colonna j si va alla riga i
    con probabilità proporzionale agli incontri. Ogni colonna somma a 1.
    Chi non incontra nessuno (colonna vuota) salta a caso ovunque: senza
    questa riga la colonna sommerebbe a zero e il calcolo perderebbe peso."""
    somme = a.sum(axis=0)
    m = np.where(somme > 0, a / np.where(somme > 0, somme, 1), 1 / len(a))
    return m


def pagerank(m: np.ndarray, d: float = 0.85, tolleranza: float = 1e-12,
             massimo: int = 1000) -> tuple[np.ndarray, int]:
    """Iterazione delle potenze. d = 0,85 è il valore dell'articolo di Brin
    e Page: l'85% delle volte il lettore segue un incontro, il 15% salta a
    un personaggio qualunque. Il salto rende la matrice "senza vicoli
    ciechi" e garantisce che il calcolo converga."""
    n = len(m)
    v = np.full(n, 1 / n)
    for passo in range(1, massimo + 1):
        nuovo = d * (m @ v) + (1 - d) / n
        if np.abs(nuovo - v).sum() < tolleranza:
            return nuovo, passo
        v = nuovo
    return v, massimo


def con_autovettore(m: np.ndarray, d: float = 0.85) -> np.ndarray:
    """Lo stesso risultato, come autovettore di G = d·M + (1−d)/n:
    l'autovalore più grande vale 1, e il suo autovettore, normalizzato a
    somma 1, è il PageRank."""
    n = len(m)
    g = d * m + (1 - d) / n
    valori, vettori = np.linalg.eig(g)
    v = np.real(vettori[:, np.argmax(np.real(valori))])
    return v / v.sum()


def main() -> None:
    paragrafi = carica(Path(sys.argv[1]))
    a = matrice_incontri(paragrafi)
    m = transizioni(a)
    pr, passi = pagerank(m)
    ev = con_autovettore(m)
    print(f"PageRank in {passi} moltiplicazioni; differenza massima con l'autovettore {np.abs(pr - ev).max():.1e}")
    grado = (a > 0).sum(axis=0)
    incontri = a.sum(axis=0)
    ordine = np.argsort(-pr)
    print(f"\n{'':18} {'PageRank':>9} {'vicini':>7} {'incontri':>9}")
    for i in ordine:
        print(f"{PERSONAGGI[i]:18} {pr[i]:9.3f} {grado[i]:7} {int(incontri[i]):9}")

    # Senza Alice: chi resta al centro?
    senza = np.delete(np.delete(a, 0, 0), 0, 1)
    pr2, _ = pagerank(transizioni(senza))
    nomi = PERSONAGGI[1:]
    print("\nSenza Alice, i primi cinque: " + ", ".join(
        f"{nomi[i]} {pr2[i]:.3f}" for i in np.argsort(-pr2)[:5]))


if __name__ == "__main__":
    main()
