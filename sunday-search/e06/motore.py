"""
S05E06 paid — `cerca`: il mini motore di ricerca a linea di comando.

    python motore.py cerca "la regina che corre"              # ibrida, primi 5
    python motore.py cerca "il leone e l'unicorno" --spiega   # chi ha votato cosa
    python motore.py cerca "sogno" --capitolo XII --tipo prosa
    python motore.py cerca "uovo sul muro" --metodo lessicale -k 3
    python motore.py cerca "uovo sul muro" --scena            # mostra la scena intera
    python motore.py simili II.89                             # le scene vicine
    python motore.py percorso V.22 VI.89                      # la strada tra due scene
    python motore.py shell                                    # carica una volta, chiedi quante vuoi

Il motore è lo stesso di valuta.py (ricerca.py): cambia solo la porta
d'ingresso. I filtri (--capitolo, --tipo) passano da Chroma, che tiene i
metadati, e valgono per TUTTI i ranker: filtrare dopo la fusione
lascerebbe fuori scena dei buoni risultati già scartati dalle singole
classifiche.
"""

from __future__ import annotations

import argparse
import shlex
import sys
import textwrap
import time
from pathlib import Path

import chromadb
import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from chunking import per_scena          # noqa: E402
from grafo import Grafo                 # noqa: E402
from ricerca import COMPONENTI, METODI, Motore  # noqa: E402

RADICE = AQUI.parent
NOME_COLLECTION = "specchio_filtri"
LARGHEZZA = 96


class Cerca:
    """Il motore più tutto quello che serve alla riga di comando: i filtri
    di Chroma, le scene, il grafo."""

    def __init__(self, indice: Path, vocabolario: Path, corpus: Path, cartella_chroma: Path):
        self.m = Motore(indice, vocabolario, corpus)
        self.col = self._apri(cartella_chroma)
        self.scene = per_scena(self.m.meta)
        self.scena_di = {p: j for j, c in enumerate(self.scene) for p in c}
        self._grafo: Grafo | None = None

    def _apri(self, cartella: Path):
        client = chromadb.PersistentClient(path=str(cartella))
        if NOME_COLLECTION in [c.name for c in client.list_collections()]:
            return client.get_collection(NOME_COLLECTION)
        col = client.create_collection(NOME_COLLECTION, configuration={"hnsw": {"space": "cosine"}},
                                       embedding_function=None)
        m = self.m
        # Qui Chroma fa da archivio dei METADATI. I vettori ci sono perché
        # una collection li vuole, ma il filtro (where) non li guarda.
        ok = [p for p in sorted(m.meta) if np.linalg.norm(m.par.paragrafi[p]) > 0]
        col.add(ids=[m.etichette[p] for p in ok],
                embeddings=m.par.paragrafi[ok],
                metadatas=[{"capitolo": m.meta[p]["romano"], "tipo": m.meta[p]["tipo"],
                            "parole": m.meta[p]["parole"]} for p in ok])
        return col

    @property
    def grafo(self) -> Grafo:
        # Costa 20 ms, ma si costruisce solo se serve: chi cerca e basta non lo paga.
        if self._grafo is None:
            self._grafo = Grafo(self.m.vet.lsa)
        return self._grafo

    # ------------------------------------------------------------------
    def ammessi(self, capitolo: str | None, tipo: str | None) -> set[int] | None:
        filtri = [{"capitolo": capitolo}] if capitolo else []
        filtri += [{"tipo": tipo}] if tipo else []
        if not filtri:
            return None
        # $and vuole almeno due condizioni: con una sola si passa quella.
        where = filtri[0] if len(filtri) == 1 else {"$and": filtri}
        ids = self.col.get(where=where, include=[])["ids"]
        return {self.m.numero[i] for i in ids}

    def posizioni(self, query: str, p: int) -> dict[str, int | None]:
        """Per --spiega: in che posizione ha messo il paragrafo p ogni ranker."""
        out = {}
        for r in ("lessicale", "tesauro", "lsa", "parole"):
            cl = self.m.classifica(self.m.punteggi(r, query))
            out[r] = cl.index(p) + 1 if p in cl else None
        return out

    def risolvi(self, rif: str) -> int:
        try:
            return self.m.numero[rif.upper().replace("..", ".")]
        except KeyError:
            raise SystemExit(f"'{rif}' non è un riferimento del libro (es. II.89)") from None


def stampa(p: int, c: Cerca, riga_testa: str, scena: bool = False) -> None:
    d = c.m.meta[p]
    print(f"{c.m.etichette[p]:>8}  {riga_testa}  [{d['tipo']}, cap. {d['romano']}: {d['titolo']}]")
    ps = c.scene[c.scena_di[p]] if scena else [p]
    for q in ps:
        marca = ">" if (scena and q == p) else " "
        testo = " ".join(c.m.meta[q]["testo"].split())
        for i, r in enumerate(textwrap.wrap(testo, LARGHEZZA - 12) or [""]):
            print(f"{'':8} {marca if i == 0 else ' '} {r}")
    print()


def cmd_cerca(c: Cerca, a: argparse.Namespace) -> None:
    query = " ".join(a.query)
    ammessi = c.ammessi(a.capitolo, a.tipo)
    if ammessi is not None and not ammessi:
        print("nessun paragrafo con questi filtri")
        return
    t0 = time.perf_counter()
    risultati = c.m.cerca(query, a.metodo, a.k, ammessi)
    ms = (time.perf_counter() - t0) * 1000
    if not risultati:
        print(f"nessun risultato per «{query}» ({a.metodo}). Il lessicale non trova parole che il libro non ha: "
              "prova --metodo parole, che ragiona per vicinanza.")
        return
    print(f"«{query}» — {a.metodo}, {len(risultati)} risultati in {ms:.0f} ms\n")
    for p, punti in risultati:
        testa = f"{punti:.4f}"
        if a.spiega:
            pos = c.posizioni(query, p)
            testa += "  " + " ".join(f"{r[:3]}={pos[r] if pos[r] else '-'}" for r in pos)
        stampa(p, c, testa, a.scena)


def cmd_simili(c: Cerca, a: argparse.Namespace) -> None:
    p = c.risolvi(a.paragrafo)
    ammessi = c.ammessi(a.capitolo, a.tipo)
    print(f"simili a {a.paragrafo}: {' '.join(c.m.meta[p]['testo'].split())[:LARGHEZZA - 20]}\n")
    n = 0
    for j, coseno in c.grafo.vicini(p):
        if ammessi is not None and j not in ammessi:
            continue
        stampa(j, c, f"{coseno:.2f}")
        n += 1
        if n >= a.k:
            break
    if n == 0:
        print("nessun vicino (con questi filtri).")


def cmd_percorso(c: Cerca, a: argparse.Namespace) -> None:
    da, a_ = c.risolvi(a.da), c.risolvi(a.a)
    strada = c.grafo.percorso(da, a_)
    if strada is None:
        print("nessuna strada: i due paragrafi stanno in parti scollegate del grafo.")
        return
    print(f"da {a.da} a {a.a}: {len(strada) - 1} salti\n")
    for p in strada:
        stampa(p, c, "")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cerca", description="Mini motore di ricerca su «Attraverso lo specchio».")
    p.add_argument("--indice", type=Path, default=RADICE / "indice")
    p.add_argument("--vocabolario", type=Path, default=RADICE / "vocabolario")
    p.add_argument("--corpus", type=Path, default=RADICE / "corpus" / "specchio.jsonl")
    p.add_argument("--chroma", type=Path, default=RADICE / "vettori")
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("cerca", help="cerca con parole")
    s.add_argument("query", nargs="+")
    s.add_argument("--metodo", choices=METODI, default="ibrida")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--capitolo", help="I, II, ... XII")
    s.add_argument("--tipo", choices=["dialogo", "prosa", "poesia"])
    s.add_argument("--spiega", action="store_true", help="la posizione data da ogni ranker")
    s.add_argument("--scena", action="store_true", help="mostra tutta la scena attorno al risultato")
    s.set_defaults(fn=cmd_cerca)

    s = sub.add_parser("simili", help="le scene vicine a una scena")
    s.add_argument("paragrafo")
    s.add_argument("-k", type=int, default=5)
    s.add_argument("--capitolo")
    s.add_argument("--tipo", choices=["dialogo", "prosa", "poesia"])
    s.set_defaults(fn=cmd_simili)

    s = sub.add_parser("percorso", help="la strada tra due scene")
    s.add_argument("da")
    s.add_argument("a")
    s.set_defaults(fn=cmd_percorso)

    sub.add_parser("shell", help="carica una volta, chiedi quante volte vuoi")
    return p


def main(argv: list[str] | None = None) -> None:
    p = parser()
    a = p.parse_args(argv)
    t0 = time.perf_counter()
    c = Cerca(a.indice, a.vocabolario, a.corpus, a.chroma)
    if a.comando != "shell":
        a.fn(c, a)
        return
    print(f"pronto in {time.perf_counter() - t0:.1f} s. Scrivi un comando (cerca/simili/percorso) o 'esci'.")
    while True:
        try:
            riga = input("cerca> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if riga in ("esci", "exit", "q"):
            break
        if not riga:
            continue
        try:
            # Una riga senza comando è una ricerca: il caso più frequente.
            args = shlex.split(riga)
            if args[0] not in ("cerca", "simili", "percorso"):
                args = ["cerca"] + args
            b = p.parse_args(args)
            b.fn(c, b)
        except SystemExit:
            pass                      # argparse ha già stampato l'errore: la shell resta viva


if __name__ == "__main__":
    main()
