"""
S05E02 — Lo schedario: *Attraverso lo specchio* come albero.

    libro → capitoli → paragrafi → versi (solo per le poesie)

Visite in profondità (ricorsiva e iterativa) e in larghezza, numeri di Celko
calcolati in Python e salvati in DuckDB, con il test che li verifica.

Uso:
    python schedario.py ../corpus/specchio.jsonl schedario.duckdb
"""

from __future__ import annotations

import json
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Il nodo
# ---------------------------------------------------------------------------
@dataclass(slots=True, eq=False)
class Nodo:
    # eq=False: un nodo è uguale solo a sé stesso. Con l'uguaglianza per
    # valore la dataclass diventa non hashable (niente set, niente chiavi
    # di dizionario) e confrontare due nodi confronterebbe i sottoalberi.
    tipo: str                   # "libro", "capitolo", "paragrafo", "verso"
    etichetta: str              # "VI", "VI.89", "VI.86.3"...
    testo: str = ""
    figli: list["Nodo"] = field(default_factory=list)
    # I numeri di Celko: li riempie numera(), finché non la chiami valgono 0.
    lft: int = 0
    rgt: int = 0

    def aggiungi(self, figlio: "Nodo") -> "Nodo":
        self.figli.append(figlio)
        return figlio


def costruisci(percorso: Path) -> Nodo:
    libro = Nodo("libro", "Attraverso lo specchio")
    capitoli: dict[int, Nodo] = {}
    with percorso.open(encoding="utf-8") as f:
        # Il JSONL è già in ordine di lettura: capitolo, poi posizione.
        # Lo abbiamo ordinato noi in E01, e qui ce lo godiamo.
        for riga in f:
            p = json.loads(riga)
            if p["capitolo"] not in capitoli:
                capitoli[p["capitolo"]] = libro.aggiungi(
                    Nodo("capitolo", p["romano"], p["titolo"]))
            par = capitoli[p["capitolo"]].aggiungi(
                Nodo("paragrafo", f"{p['romano']}.{p['posizione']}", p["testo"]))
            if p["tipo"] == "poesia":
                # Le poesie hanno i versi separati da "\n" (li abbiamo tenuti
                # apposta in E01): ogni verso diventa un figlio del paragrafo.
                for i, verso in enumerate(p["testo"].split("\n")):
                    par.aggiungi(Nodo("verso", f"{par.etichetta}.{i}", verso))
    return libro


# ---------------------------------------------------------------------------
# Visite
# ---------------------------------------------------------------------------
def dfs_ricorsiva(nodo: Nodo, livello: int = 0) -> Iterator[tuple[Nodo, int]]:
    """In profondità, nel modo in cui la si scrive alla lavagna.
    Ogni livello dell'albero è una chiamata in più sullo stack di Python."""
    yield nodo, livello
    for figlio in nodo.figli:
        yield from dfs_ricorsiva(figlio, livello + 1)


def dfs_iterativa(radice: Nodo) -> Iterator[tuple[Nodo, int]]:
    """In profondità, con una pila nostra al posto dello stack di Python.
    Stesso ordine della ricorsiva, nessun limite di profondità."""
    pila = [(radice, 0)]
    while pila:
        nodo, livello = pila.pop()
        yield nodo, livello
        # I figli vanno sulla pila al contrario: l'ultimo messo è il primo
        # tolto, e vogliamo che il primo figlio sia visitato per primo.
        for figlio in reversed(nodo.figli):
            pila.append((figlio, livello + 1))


def bfs(radice: Nodo) -> Iterator[tuple[Nodo, int]]:
    """In larghezza: prima tutti i capitoli, poi tutti i paragrafi, poi i
    versi. La deque toglie dalla testa in O(1); una lista con pop(0) dovrebbe
    spostare ogni volta tutti gli elementi che restano."""
    coda = deque([(radice, 0)])
    while coda:
        nodo, livello = coda.popleft()
        yield nodo, livello
        for figlio in nodo.figli:
            coda.append((figlio, livello + 1))


# ---------------------------------------------------------------------------
# I numeri di Celko
# ---------------------------------------------------------------------------
def numera(radice: Nodo) -> int:
    """lft all'entrata, rgt all'uscita, un solo contatore per tutti.
    Iterativa per lo stesso motivo di dfs_iterativa. Restituisce l'ultimo
    numero usato, che deve valere 2 × numero di nodi."""
    contatore = 0
    # Ogni elemento della pila è (nodo, uscita): False la prima volta che lo
    # incontriamo (stiamo entrando), True quando torniamo a chiuderlo.
    pila: list[tuple[Nodo, bool]] = [(radice, False)]
    while pila:
        nodo, uscita = pila.pop()
        contatore += 1
        if uscita:
            nodo.rgt = contatore
            continue
        nodo.lft = contatore
        # Prima rimettiamo il nodo stesso, segnato come "da chiudere", poi i
        # figli sopra di lui: verrà richiuso solo dopo che sono usciti tutti.
        pila.append((nodo, True))
        for figlio in reversed(nodo.figli):
            pila.append((figlio, False))
    return contatore


def discendenti(nodo: Nodo) -> int:
    return sum(1 for _ in dfs_iterativa(nodo)) - 1


# ---------------------------------------------------------------------------
# DuckDB
# ---------------------------------------------------------------------------
def salva(radice: Nodo, percorso: Path) -> None:
    import duckdb

    righe = [(n.lft, n.rgt, livello, n.tipo, n.etichetta, n.testo)
             for n, livello in dfs_iterativa(radice)]
    percorso.unlink(missing_ok=True)
    con = duckdb.connect(str(percorso))
    con.execute("""CREATE TABLE schedario (
        lft INTEGER PRIMARY KEY, rgt INTEGER, livello INTEGER,
        tipo TEXT, etichetta TEXT, testo TEXT)""")
    # Inseriamo in ordine di lft: DuckDB tiene le statistiche min/max per
    # blocchi di righe, e con i dati già ordinati un BETWEEN su lft salta
    # direttamente ai blocchi giusti.
    con.executemany("INSERT INTO schedario VALUES (?, ?, ?, ?, ?, ?)", righe)
    con.close()


def main() -> None:
    libro = costruisci(Path(sys.argv[1]))
    ultimo = numera(libro)
    nodi = sum(1 for _ in dfs_iterativa(libro))
    print(f"{nodi:,} nodi, ultimo numero {ultimo:,} (deve essere {2 * nodi:,})")
    salva(libro, Path(sys.argv[2]))
    print(f"salvato in {sys.argv[2]}")


if __name__ == "__main__":
    main()
