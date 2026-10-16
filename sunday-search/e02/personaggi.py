"""
S05E02 — Quando lo schedario smette di essere un albero.

I personaggi di *Attraverso lo specchio* compaiono in più capitoli: una scheda
con più genitori. E chi parla con chi forma una rete con i cicli.

Uso:
    python personaggi.py ../corpus/specchio.jsonl
"""

from __future__ import annotations

import json
import re
import sys
from collections import deque
from itertools import combinations
from pathlib import Path

# Nomi come li ha tradotti l'edizione del 1914. Scelti a mano: l'estrazione
# automatica dei nomi propri è un altro mestiere (e un'altra stagione).
PERSONAGGI = [
    "Alice", "Regina Rossa", "Regina Bianca", "Re Rosso", "Re Bianco",
    "Unto Dunto", "Tuidledum", "Tuidledì", "Leone", "Unicorno",
    "Cavaliere Bianco", "Cavaliere Rosso", "Frufrù", "Nevina", "Dina",
    "Lilla", "Pecora", "Giglio", "Hatta",
]

# \b ai bordi: "Leone" non deve scattare dentro "Leonessa". Le regex si
# compilano una volta sola, non a ogni paragrafo.
REGEX = {nome: re.compile(rf"\b{re.escape(nome)}\b") for nome in PERSONAGGI}


def carica(percorso: Path) -> list[dict]:
    with percorso.open(encoding="utf-8") as f:
        return [json.loads(riga) for riga in f]


def chi_compare(testo: str) -> set[str]:
    return {nome for nome, rx in REGEX.items() if rx.search(testo)}


def presenze(paragrafi: list[dict]) -> dict[str, set[str]]:
    """Personaggio → capitoli in cui compare. Nello schedario sarebbe una
    scheda con più genitori: già qui, non è più un albero."""
    risultato: dict[str, set[str]] = {nome: set() for nome in PERSONAGGI}
    for p in paragrafi:
        for nome in chi_compare(p["testo"]):
            risultato[nome].add(p["romano"])
    return risultato


def grafo_incontri(paragrafi: list[dict]) -> dict[str, set[str]]:
    """Due personaggi sono collegati se compaiono nello stesso paragrafo.
    Un dizionario di set: per ogni nodo, i suoi vicini. È la "adjacency
    list" dei grafi, la stessa idea della colonna genitore, ma senza un
    unico genitore."""
    grafo: dict[str, set[str]] = {nome: set() for nome in PERSONAGGI}
    for p in paragrafi:
        # sorted: combinations su un set darebbe coppie in ordine casuale,
        # e vogliamo un risultato riproducibile da una corsa all'altra.
        for a, b in combinations(sorted(chi_compare(p["testo"])), 2):
            grafo[a].add(b)
            grafo[b].add(a)
    return grafo


def percorso_piu_breve(grafo: dict[str, set[str]], da: str, a: str) -> list[str] | None:
    """BFS: la stessa di schedario.py, con due differenze che sono tutto il
    punto della puntata. Primo: teniamo un insieme dei nodi già visti,
    perché in un grafo si può tornare al punto di partenza. Secondo:
    ricordiamo da dove siamo arrivati a ogni nodo, per ricostruire la strada."""
    visti = {da}
    da_dove: dict[str, str] = {}
    coda = deque([da])
    while coda:
        nodo = coda.popleft()
        if nodo == a:
            strada = [a]
            while strada[-1] != da:
                strada.append(da_dove[strada[-1]])
            return strada[::-1]
        # sorted: a parità di distanza scegliamo sempre lo stesso vicino.
        for vicino in sorted(grafo[nodo]):
            if vicino not in visti:
                visti.add(vicino)
                da_dove[vicino] = nodo
                coda.append(vicino)
    return None


def bfs_senza_visti(grafo: dict[str, set[str]], da: str, limite: int) -> int:
    """La BFS dell'albero applicata al grafo, così com'è. Restituisce quanti
    nodi ha tolto dalla coda prima di arrivare al limite: senza il limite,
    non finirebbe mai."""
    coda = deque([da])
    estratti = 0
    while coda and estratti < limite:
        nodo = coda.popleft()
        estratti += 1
        coda.extend(grafo[nodo])
    return estratti


def main() -> None:
    paragrafi = carica(Path(sys.argv[1]))

    print("Personaggi con più di un capitolo (schede con più genitori):")
    pres = presenze(paragrafi)
    for nome, capitoli in sorted(pres.items(), key=lambda kv: -len(kv[1])):
        if len(capitoli) > 1:
            print(f"  {nome:18} {len(capitoli):>2} capitoli")

    grafo = grafo_incontri(paragrafi)
    archi = sum(len(v) for v in grafo.values()) // 2
    print(f"\nGrafo degli incontri: {len(grafo)} personaggi, {archi} collegamenti")
    for da, a in [("Frufrù", "Hatta"), ("Lilla", "Cavaliere Rosso"), ("Giglio", "Unicorno")]:
        print(f"  {da} → {a}: {' → '.join(percorso_piu_breve(grafo, da, a) or ['nessuna strada'])}")

    print(f"\nBFS senza 'visti', fermata a 1.000.000 di estrazioni: "
          f"{bfs_senza_visti(grafo, 'Frufrù', 1_000_000):,} nodi estratti, e non aveva finito")


if __name__ == "__main__":
    main()
