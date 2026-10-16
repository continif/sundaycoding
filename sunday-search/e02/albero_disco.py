#!/usr/bin/env python3
"""
S05E02 — Una directory del disco dentro due database, uno per modello.

Carica nomi di sottodirectory e file di DIR in due file SQLite:
    adjacency.sqlite   (id, genitore)               "sto dentro a..."
    nested.sqlite      (lft, rgt)                   i numeri di Celko

e con --print ristampa l'albero da ciascuno, misurando tempo e query.

Esempi:
    python albero_disco.py /usr/lib/python3.13 --db alberi/
    python albero_disco.py --db alberi/ --print > /dev/null
    python albero_disco.py --db alberi/ --print --modello nested --da json
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MODELLI = ("adjacency", "nested")



# ---------------------------------------------------------------------------
# Misure: tempo e numero di query
# ---------------------------------------------------------------------------
@dataclass
class Misura:
    query: int = 0
    secondi: float = 0.0


LATENZA = 0.0  # secondi aggiunti a ogni query, impostata da --latenza


def apri(percorso: Path, misura: Misura) -> sqlite3.Connection:
    con = sqlite3.connect(percorso)
    # set_trace_callback viene chiamato per ogni istruzione SQL eseguita:
    # è il contatore più onesto che abbiamo, perché conta quello che arriva
    # davvero al database, non quello che crediamo di avergli chiesto.
    def conta(_sql: str) -> None:
        misura.query += 1
        # SQLite vive nel nostro processo: una query costa microsecondi.
        # Un PostgreSQL o un MySQL in rete costano un viaggio di andata e
        # ritorno ciascuna. --latenza simula quel viaggio.
        if LATENZA:
            time.sleep(LATENZA)
    con.set_trace_callback(conta)
    return con


# ---------------------------------------------------------------------------
# Lettura della directory
# ---------------------------------------------------------------------------
@dataclass
class Nodo:
    nome: str
    relativo: str          # percorso relativo alla radice, solo per --da
    cartella: bool
    figli: list["Nodo"]


def leggi_directory(radice: Path) -> Nodo:
    def visita(cartella: Path, relativo: str) -> Nodo:
        nodo = Nodo(cartella.name or str(cartella), relativo, True, [])
        try:
            # Ordiniamo le voci per nome: è l'ordine in cui le vuole vedere
            # chi legge, e lo fissiamo UNA volta al caricamento. I modelli
            # che lo conservano (il nested set) non dovranno più ordinare
            # per nome in lettura.
            voci = sorted(os.scandir(cartella), key=lambda v: v.name)
        except PermissionError:
            return nodo
        for v in voci:
            figlio_rel = f"{relativo}/{v.name}" if relativo else v.name
            # follow_symlinks=False: un link a una cartella superiore
            # trasformerebbe l'albero in un ciclo, e la visita non finirebbe.
            if v.is_dir(follow_symlinks=False):
                nodo.figli.append(visita(Path(v.path), figlio_rel))
            else:
                nodo.figli.append(Nodo(v.name, figlio_rel, False, []))
        return nodo

    return visita(radice, "")


def in_profondita(radice: Nodo):
    """Visita iterativa: restituisce (nodo, genitore, posizione tra i fratelli).
    Iterativa e non ricorsiva perché un albero di cartelle può essere più
    profondo dei 1000 livelli di ricorsione di Python."""
    pila = [(radice, None, 0)]
    while pila:
        nodo, genitore, posizione = pila.pop()
        yield nodo, genitore, posizione
        for i in range(len(nodo.figli) - 1, -1, -1):
            pila.append((nodo.figli[i], nodo, i))


# ---------------------------------------------------------------------------
# Caricamento: un file SQLite per modello
# ---------------------------------------------------------------------------
def carica_adjacency(radice: Nodo, con: sqlite3.Connection) -> int:
    con.execute("""CREATE TABLE nodo (
        id INTEGER PRIMARY KEY, genitore INTEGER, nome TEXT,
        cartella INTEGER, relativo TEXT)""")
    ids: dict[int, int] = {}
    righe = []
    for nodo, genitore, _ in in_profondita(radice):
        ids[id(nodo)] = len(ids) + 1
        righe.append((ids[id(nodo)], ids[id(genitore)] if genitore else None,
                      nodo.nome, nodo.cartella, nodo.relativo))
    con.executemany("INSERT INTO nodo VALUES (?,?,?,?,?)", righe)
    # L'indice sul genitore è quello che rende veloce "dammi i figli di X".
    con.execute("CREATE INDEX i_genitore ON nodo(genitore)")
    con.execute("CREATE INDEX i_relativo ON nodo(relativo)")
    return len(righe)


def carica_nested(radice: Nodo, con: sqlite3.Connection) -> int:
    # lft NON è la chiave primaria: inserendo un nodo i lft si spostano di 2,
    # e una chiave che cambia a metà UPDATE fa scattare i vincoli di unicità.
    con.execute("""CREATE TABLE nodo (
        id INTEGER PRIMARY KEY, lft INTEGER, rgt INTEGER, nome TEXT,
        cartella INTEGER, relativo TEXT)""")
    righe = []
    contatore = 1
    # Visita con entrata e uscita: lft all'entrata, rgt all'uscita.
    pila: list[tuple[Nodo, bool]] = [(radice, False)]
    lft: dict[int, int] = {}
    while pila:
        nodo, uscita = pila.pop()
        if uscita:
            righe.append((len(righe) + 1, lft[id(nodo)], contatore, nodo.nome, nodo.cartella, nodo.relativo))
            contatore += 1
            continue
        lft[id(nodo)] = contatore
        contatore += 1
        pila.append((nodo, True))
        for figlio in reversed(nodo.figli):
            pila.append((figlio, False))
    con.executemany("INSERT INTO nodo VALUES (?,?,?,?,?,?)", righe)
    con.execute("CREATE INDEX i_lft ON nodo(lft)")
    con.execute("CREATE INDEX i_rgt ON nodo(rgt)")
    con.execute("CREATE INDEX i_relativo ON nodo(relativo)")
    return len(righe)


CARICATORI = {"adjacency": carica_adjacency, "nested": carica_nested}


# ---------------------------------------------------------------------------
# Stampa: quattro modi di rileggere l'albero
# ---------------------------------------------------------------------------
def riga(nome: str, cartella: int, livello: int) -> str:
    return "  " * livello + nome + ("/" if cartella else "")


def stampa_adjacency_ingenua(con, da: str) -> list[str]:
    """Il modo che si scrive di getto: una query per ogni cartella aperta.
    È il famoso problema "N+1": N cartelle, N query."""
    (radice, nome, cartella), = con.execute(
        "SELECT id, nome, cartella FROM nodo WHERE relativo = ?", (da,)).fetchall()
    righe = [riga(nome, cartella, 0)]

    def scendi(padre: int, livello: int) -> None:
        # Una query per ogni cartella: "chi sta dentro a te?". Ai file non
        # chiediamo niente, sappiamo già che sono vuoti.
        for fid, fnome, fcartella in con.execute(
                "SELECT id, nome, cartella FROM nodo WHERE genitore = ? ORDER BY nome",
                (padre,)).fetchall():
            righe.append(riga(fnome, fcartella, livello))
            if fcartella:
                scendi(fid, livello + 1)

    # La ricorsione scende quanto è profondo l'albero delle cartelle: di
    # solito una decina di livelli, ben sotto il limite di 1000 di Python.
    scendi(radice, 1)
    return righe


def stampa_adjacency_cte(con, da: str) -> list[str]:
    """Una sola query: la CTE ricorsiva scende l'albero dentro il database.
    Per avere le righe in ordine di visita costruiamo una chiave d'ordine
    con i nomi separati da char(1), il carattere più piccolo che c'è: così
    "a" + figli viene sempre prima di "a.txt"."""
    righe = con.execute("""
        WITH RECURSIVE sotto(id, nome, cartella, livello, chiave) AS (
            SELECT id, nome, cartella, 0, nome FROM nodo WHERE relativo = ?
            UNION ALL
            SELECT n.id, n.nome, n.cartella, s.livello + 1,
                   s.chiave || char(1) || n.nome
            FROM nodo n JOIN sotto s ON n.genitore = s.id
        )
        SELECT nome, cartella, livello FROM sotto ORDER BY chiave""", (da,)).fetchall()
    return [riga(n, c, l) for n, c, l in righe]


def stampa_nested(con, da: str) -> list[str]:
    """Due query: una per trovare i bordi della scatola di partenza, una per
    leggere tutto quello che sta in mezzo, già in ordine."""
    (lft, rgt), = con.execute("SELECT lft, rgt FROM nodo WHERE relativo = ?", (da,)).fetchall()
    righe = []
    # Il livello non è scritto da nessuna parte, ma si ricava gratis: teniamo
    # una pila dei rgt delle scatole aperte. Quando arriva un nodo con lft
    # oltre il rgt in cima alla pila, quella scatola si è chiusa.
    aperte: list[int] = []
    for n_lft, n_rgt, nome, cartella in con.execute(
            "SELECT lft, rgt, nome, cartella FROM nodo WHERE lft BETWEEN ? AND ? ORDER BY lft",
            (lft, rgt)):
        while aperte and aperte[-1] < n_lft:
            aperte.pop()
        righe.append(riga(nome, cartella, len(aperte)))
        aperte.append(n_rgt)
    return righe


STAMPATORI = {
    "adjacency (una query per cartella)": ("adjacency", stampa_adjacency_ingenua),
    "adjacency (CTE ricorsiva)": ("adjacency", stampa_adjacency_cte),
    "nested set": ("nested", stampa_nested),
}


# ---------------------------------------------------------------------------
# Aggiungere un file, al suo posto in ordine alfabetico
# ---------------------------------------------------------------------------
def aggiungi_adjacency(con, cartella: str, nome: str, relativo: str) -> None:
    # Una riga e basta: l'ordine alfabetico lo ricostruisce la lettura
    # con ORDER BY nome, quindi non c'è niente da spostare.
    (padre,), = con.execute("SELECT id FROM nodo WHERE relativo = ? AND cartella", (cartella,)).fetchall()
    con.execute("INSERT INTO nodo (genitore, nome, cartella, relativo) VALUES (?, ?, 0, ?)",
                (padre, nome, relativo))


def aggiungi_nested(con, cartella: str, nome: str, relativo: str) -> None:
    (p_lft, p_rgt), = con.execute(
        "SELECT lft, rgt FROM nodo WHERE relativo = ? AND cartella", (cartella,)).fetchall()
    # Il nested set non sa chi sono i figli DIRETTI di una cartella: sa solo
    # chi le sta dentro, a qualunque profondità. Per trovare il posto giusto
    # tra i fratelli leggiamo il sottoalbero e saltiamo i nipoti: un figlio
    # diretto è un nodo che comincia dopo la fine del figlio precedente.
    punto = p_rgt  # se il nuovo nome è l'ultimo, va in fondo alla cartella
    fine_precedente = p_lft
    for lft, rgt, figlio in con.execute(
            "SELECT lft, rgt, nome FROM nodo WHERE lft > ? AND lft < ? ORDER BY lft", (p_lft, p_rgt)):
        if lft < fine_precedente:
            continue  # è un nipote, sta dentro il figlio precedente
        if figlio > nome:
            punto = lft
            break
        fine_precedente = rgt
    # La ricetta di Celko: si apre un buco di 2 nel punto, spostando tutto
    # ciò che sta a destra. ">=" su entrambi perché il punto può essere il
    # lft di un fratello (che deve spostarsi) o il rgt del padre (idem).
    con.execute("UPDATE nodo SET rgt = rgt + 2 WHERE rgt >= ?", (punto,))
    con.execute("UPDATE nodo SET lft = lft + 2 WHERE lft >= ?", (punto,))
    con.execute("INSERT INTO nodo (lft, rgt, nome, cartella, relativo) VALUES (?, ?, ?, 0, ?)",
                (punto, punto + 1, nome, relativo))


AGGIUNTORI = {"adjacency": aggiungi_adjacency, "nested": aggiungi_nested}


# ---------------------------------------------------------------------------
# Riga di comando
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("directory", nargs="?", type=Path, help="directory da caricare (se omessa, si usano i db esistenti)")
    ap.add_argument("--db", type=Path, required=True, help="cartella dove stanno i file .sqlite")
    ap.add_argument("--print", dest="stampa", action="store_true", help="ristampa l'albero da ogni modello")
    ap.add_argument("--modello", choices=MODELLI, help="limita la stampa a un modello")
    ap.add_argument("--da", default="", help="percorso relativo da cui partire (default: la radice)")
    ap.add_argument("--aggiungi", metavar="PERCORSO",
                    help="aggiunge un file (es. doc/nuovo.txt) in entrambi i db, al suo posto alfabetico")
    ap.add_argument("--latenza", type=float, default=0.0, metavar="MS",
                    help="millisecondi aggiunti a ogni query, per simulare un database in rete")
    args = ap.parse_args()
    global LATENZA
    LATENZA = args.latenza / 1000

    # Le misure vanno su stderr, l'albero su stdout: così si può fare
    # "--print > /dev/null" e leggere solo i numeri.
    def log(*parti):
        print(*parti, file=sys.stderr)

    if args.directory:
        args.db.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        radice = leggi_directory(args.directory.resolve())
        log(f"lettura del disco: {(time.perf_counter() - t0) * 1000:.0f} ms")
        for modello in MODELLI:
            file = args.db / f"{modello}.sqlite"
            file.unlink(missing_ok=True)
            misura = Misura()
            con = apri(file, misura)
            t0 = time.perf_counter()
            with con:  # una sola transazione: commit alla fine, rollback se fallisce
                nodi = CARICATORI[modello](radice, con)
            misura.secondi = time.perf_counter() - t0
            con.close()
            log(f"caricato {modello:10} {nodi:>8,} nodi  {misura.query:>8,} query  "
                f"{misura.secondi * 1000:8.1f} ms  {file.stat().st_size / 1024:8.0f} KB")

    if args.aggiungi:
        cartella, _, nome = args.aggiungi.rpartition("/")
        for modello in MODELLI:
            misura = Misura()
            con = apri(args.db / f"{modello}.sqlite", misura)
            if con.execute("SELECT 1 FROM nodo WHERE relativo = ?", (args.aggiungi,)).fetchone():
                log(f"{args.aggiungi} esiste già in {modello}.sqlite")
                con.close()
                continue
            misura.query = 0
            prima = con.total_changes
            t0 = time.perf_counter()
            with con:  # tutto o niente: un nested set a metà è un albero rotto
                AGGIUNTORI[modello](con, cartella, nome, args.aggiungi)
            misura.secondi = time.perf_counter() - t0
            # total_changes somma le righe inserite, aggiornate o cancellate da
            # ogni istruzione: è la misura di quanto albero abbiamo dovuto
            # toccare. Nel nested set una riga spostata da entrambe le UPDATE
            # (rgt e lft) conta due volte, ed è giusto così: è lavoro doppio.
            toccate = con.total_changes - prima
            con.close()
            log(f"aggiunto in {modello:10} {toccate:>8,} aggiornamenti di riga  {misura.query:>6,} query  "
                f"{misura.secondi * 1000:8.1f} ms")

    if args.stampa:
        for etichetta, (modello, stampatore) in STAMPATORI.items():
            if args.modello and args.modello != modello:
                continue
            misura = Misura()
            con = apri(args.db / f"{modello}.sqlite", misura)
            t0 = time.perf_counter()
            # Misuriamo lettura e formattazione, non la scrittura sul
            # terminale: quella dipende da dove finisce l'output.
            righe = stampatore(con, args.da)
            misura.secondi = time.perf_counter() - t0
            con.close()
            print(f"### {etichetta}")
            print("\n".join(righe))
            log(f"stampa {etichetta:36} {len(righe):>8,} righe  {misura.query:>8,} query  "
                f"{misura.secondi * 1000:8.1f} ms")


if __name__ == "__main__":
    main()
