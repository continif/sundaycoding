"""
S05E01 — Il catalogo: i paragrafi di *Attraverso lo specchio* messi in fila.

Uso:
    python catalogo.py ../corpus/specchio.jsonl
"""

from __future__ import annotations

import heapq
import json
import sys
from collections import Counter
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path


@dataclass(slots=True, frozen=True)
class Paragrafo:
    capitolo: int
    romano: str
    titolo: str
    posizione: int
    tipo: str
    testo: str
    parole: int
    caratteri: int

    @property
    def rif(self) -> str:
        # "VI.89": capitolo in romano e posizione. È il "segnalibro" che
        # useremo in tutta la stagione per dire dove sta un risultato.
        return f"{self.romano}.{self.posizione}"


def carica(percorso: Path) -> list[Paragrafo]:
    with percorso.open(encoding="utf-8") as f:
        return [Paragrafo(**json.loads(riga)) for riga in f]


def anteprima(p: Paragrafo, larghezza: int = 70) -> str:
    # Le poesie hanno gli a capo: per l'anteprima li appiattiamo.
    testo = p.testo.replace("\n", " / ")
    return testo if len(testo) <= larghezza else testo[: larghezza - 1] + "…"


def main() -> None:
    paragrafi = carica(Path(sys.argv[1]))

    # 1. Ordine di lettura: capitolo, poi posizione. Chiave a tupla con
    #    attrgetter: due campi, entrambi necessari, quindi la tupla si paga
    #    volentieri.
    in_ordine = sorted(paragrafi, key=attrgetter("capitolo", "posizione"))
    print(f"{len(in_ordine)} paragrafi, {sum(p.parole for p in in_ordine):,} parole")
    print(f"primo:  {in_ordine[0].rif}  {anteprima(in_ordine[0])}")
    print(f"ultimo: {in_ordine[-1].rif}  {anteprima(in_ordine[-1])}")

    # 2. I dieci paragrafi più lunghi. nlargest e non sorted()[:10]:
    #    vogliamo 10 elementi su un migliaio, il caso per cui heapq è nato.
    print("\nI dieci paragrafi più lunghi:")
    for p in heapq.nlargest(10, paragrafi, key=attrgetter("parole")):
        print(f"  {p.rif:>8}  {p.parole:>4} parole  {p.tipo:<8} {anteprima(p, 50)}")

    # 3. Due passate stabili: per tipo (A→Z) e, dentro ogni tipo, dal più
    #    lungo al più corto. Prima il criterio secondario, poi il principale.
    per_lunghezza = sorted(paragrafi, key=attrgetter("parole"), reverse=True)
    per_tipo = sorted(per_lunghezza, key=attrgetter("tipo"))
    print("\nIl più lungo per ogni tipo (due passate stabili):")
    visti: set[str] = set()
    for p in per_tipo:
        if p.tipo not in visti:
            visti.add(p.tipo)
            print(f"  {p.tipo:<8} {p.rif:>8}  {p.parole:>4} parole  {anteprima(p, 45)}")

    # 4. Quante parole per capitolo, in ordine decrescente. Counter fa la
    #    somma, most_common l'ordinamento (e usa heapq quando gli chiedi n).
    parole_per_capitolo: Counter[str] = Counter()
    for p in paragrafi:
        parole_per_capitolo[f"{p.romano} {p.titolo}"] += p.parole
    print("\nCapitoli dal più lungo al più corto:")
    for capitolo, parole in parole_per_capitolo.most_common():
        print(f"  {parole:>5}  {capitolo}")


if __name__ == "__main__":
    main()
