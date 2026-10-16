"""
S05E01 — Le illustrazioni di Tenniel sono rettangoli veri.

Ogni <img> dell'edizione HTML di Liber Liber ha WIDTH e HEIGHT: li leggiamo
e mettiamo in fila le illustrazioni per area.

Uso:
    python tenniel.py CARTELLA_HTML
"""

from __future__ import annotations

import heapq
import re
import sys
from dataclasses import dataclass
from operator import attrgetter
from pathlib import Path

from bs4 import BeautifulSoup


@dataclass(slots=True, frozen=True)
class Illustrazione:
    file: str
    capitolo: int
    base: int
    altezza: int

    @property
    def area(self) -> int:
        return self.base * self.altezza

    @property
    def verticale(self) -> bool:
        return self.altezza > self.base


def leggi_illustrazioni(cartella: Path) -> list[Illustrazione]:
    trovate = []
    for pagina in sorted(cartella.glob("[0-9][0-9].htm")):
        zuppa = BeautifulSoup(pagina.read_bytes().decode("latin-1"), "lxml")
        # Solo le tavole di Tenniel (aliceNN.gif): le frecce di navigazione
        # sono immagini anche loro, ma non fanno parte del libro.
        for img in zuppa.find_all("img", src=re.compile(r"^alice\d+\.gif$")):
            # FrontPage scriveva gli attributi in maiuscolo, lxml li porta in
            # minuscolo: "WIDTH" diventa "width". Un'immagine senza misure
            # la saltiamo invece di inventarci un default.
            if not (img.get("width") and img.get("height")):
                continue
            trovate.append(
                Illustrazione(img["src"], int(pagina.stem), int(img["width"]), int(img["height"]))
            )
    return trovate


def main() -> None:
    tavole = leggi_illustrazioni(Path(sys.argv[1]))
    print(f"{len(tavole)} illustrazioni\n")

    print("Le cinque più grandi:")
    for t in heapq.nlargest(5, tavole, key=attrgetter("area")):
        print(f"  {t.file:12} cap. {t.capitolo:>2}  {t.base}×{t.altezza} = {t.area:,} px²")

    print("\nLe cinque più piccole:")
    for t in heapq.nsmallest(5, tavole, key=attrgetter("area")):
        print(f"  {t.file:12} cap. {t.capitolo:>2}  {t.base}×{t.altezza} = {t.area:,} px²")

    # Due passate stabili: prima per area decrescente, poi "verticali prima".
    # reverse=True sulla seconda: True (verticale) viene prima di False.
    per_area = sorted(tavole, key=attrgetter("area"), reverse=True)
    per_forma = sorted(per_area, key=attrgetter("verticale"), reverse=True)
    verticali = sum(t.verticale for t in tavole)
    print(f"\n{verticali} verticali, {len(tavole) - verticali} orizzontali o quadrate")
    print(f"la verticale più grande:    {per_forma[0].file} {per_forma[0].base}×{per_forma[0].altezza}")
    print(f"l'orizzontale più grande:   {per_forma[verticali].file} {per_forma[verticali].base}×{per_forma[verticali].altezza}")


if __name__ == "__main__":
    main()
