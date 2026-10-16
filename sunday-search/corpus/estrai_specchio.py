"""
Estrae capitoli e paragrafi di *Attraverso lo specchio* (Lewis Carroll)
dall'edizione HTML di Liber Liber (1996/1998, CC BY-NC-SA 4.0) e li salva
in JSONL, un paragrafo per riga.

Uso:
    python estrai_specchio.py CARTELLA_HTML  corpus/specchio.jsonl

La cartella è quella che si ottiene scompattando lo zip HTML di Liber Liber:
index.htm + 01.htm ... 12.htm (+ le GIF di Tenniel, che ignoriamo).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Tag

# I file dichiarano charset=iso-8859-1 e sono davvero latin-1: nessun byte
# nell'intervallo 0x80-0x9F, quindi non è cp1252 travestito. Lo diciamo
# esplicitamente invece di lasciar indovinare a BeautifulSoup: un charset
# indovinato male trasforma "perchè" in "perchÃ¨" e nessuno se ne accorge
# finché la ricerca non trova più niente.
CODIFICA = "latin-1"

# Spazi multipli, tab e a capo CRLF del 1998 diventano un solo spazio.
SPAZI = re.compile(r"[ \t\r\n\xa0]+")


@dataclass(slots=True)
class Paragrafo:
    capitolo: int          # 1..12, dal nome del file
    romano: str            # "I".."XII", dall'indice
    titolo: str            # titolo del capitolo, dall'indice
    posizione: int         # 0, 1, 2... dentro il capitolo
    tipo: str              # "prosa", "dialogo" o "poesia"
    testo: str
    parole: int
    caratteri: int


def leggi_html(percorso: Path) -> BeautifulSoup:
    # Leggiamo i byte e decodifichiamo noi: vedi il commento su CODIFICA.
    testo = percorso.read_bytes().decode(CODIFICA)
    # lxml e non html.parser: l'HTML di FrontPage lascia dei <p> aperti,
    # e lxml li chiude secondo le regole HTML invece di annidarli.
    return BeautifulSoup(testo, "lxml")


def pulisci(testo: str) -> str:
    # NFC: "è" come un solo carattere, non "e" + accento combinante.
    # Qui l'origine è latin-1 quindi è già NFC, ma il costo è nullo e ci
    # protegge quando aggiungeremo altri libri con altre storie.
    testo = unicodedata.normalize("NFC", testo)
    return SPAZI.sub(" ", testo).strip()


def testo_poesia(blocco: Tag) -> str:
    # Nelle poesie i versi sono separati da <br>: li teniamo come "\n",
    # perché il verso è un'unità di senso che il tokenizzatore di E03
    # vorrà conoscere.
    for br in blocco.find_all("br"):
        br.replace_with("\n")
    versi = [pulisci(v) for v in blocco.get_text().split("\n")]
    return "\n".join(v for v in versi if v)


def titoli_dall_indice(cartella: Path) -> dict[int, tuple[str, str]]:
    zuppa = leggi_html(cartella / "index.htm")
    titoli: dict[int, tuple[str, str]] = {}
    for riga in zuppa.find_all("tr"):
        link = riga.find_all("a", href=re.compile(r"^\d\d\.htm$"))
        if len(link) == 2:
            numero = int(link[0]["href"][:2])
            titoli[numero] = (pulisci(link[0].get_text()), pulisci(link[1].get_text()))
    return titoli


def classifica(testo: str) -> str:
    # Nel 1914 i dialoghi aprono con "-" oppure con "«" (i pensieri, ma non
    # sempre). Euristica onesta: sbaglia sui paragrafi misti, che però
    # restano testo cercabile, quindi l'errore costa poco.
    return "dialogo" if testo[:1] in "-«" else "prosa"


def blocchi_del_capitolo(zuppa: BeautifulSoup):
    """Restituisce (tipo, testo) per ogni blocco di testo del capitolo."""
    for elemento in zuppa.body.find_all(["p", "blockquote", "td"]):
        # Le poesie: un <blockquote> con dentro uno o più <p> (le strofe).
        # Prendiamo il blockquote intero e saltiamo i <p> al suo interno.
        if elemento.name == "blockquote":
            if elemento.find_parent("blockquote") is None:
                yield "poesia", testo_poesia(elemento)
            continue
        if elemento.find_parent("blockquote") is not None:
            continue

        if elemento.name == "p":
            # align=center: testata, frecce di navigazione, numero e titolo
            # del capitolo. Non è testo del libro.
            if elemento.get("align") == "center":
                continue
            yield None, pulisci(elemento.get_text())

        elif elemento.name == "td" and elemento.get("valign") == "bottom":
            # Capitoli X e XI: il testo sta in una cella accanto
            # all'illustrazione, senza <p> (o con un <p> a metà). Prendiamo
            # solo il testo "diretto" della cella; gli eventuali <p> interni
            # li raccoglie già il ramo sopra.
            diretto = "".join(
                str(figlio) for figlio in elemento.children if not isinstance(figlio, Tag)
            )
            diretto = pulisci(diretto)
            if diretto:
                yield None, diretto


def estrai(cartella: Path) -> list[Paragrafo]:
    titoli = titoli_dall_indice(cartella)
    paragrafi: list[Paragrafo] = []
    for numero in sorted(titoli):
        romano, titolo = titoli[numero]
        zuppa = leggi_html(cartella / f"{numero:02d}.htm")
        posizione = 0
        for tipo, testo in blocchi_del_capitolo(zuppa):
            if not testo:
                continue
            tipo = tipo or classifica(testo)
            paragrafi.append(
                Paragrafo(
                    capitolo=numero,
                    romano=romano,
                    titolo=titolo,
                    posizione=posizione,
                    tipo=tipo,
                    testo=testo,
                    # Conteggio grezzo, "split" sugli spazi: in E03 lo
                    # sostituiremo con un tokenizzatore vero e vedremo
                    # di quanto sbagliava.
                    parole=len(testo.split()),
                    caratteri=len(testo),
                )
            )
            posizione += 1
    return paragrafi


def main() -> None:
    cartella, uscita = Path(sys.argv[1]), Path(sys.argv[2])
    paragrafi = estrai(cartella)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    # Scriviamo su un file temporaneo e poi rinominiamo: se lo script muore
    # a metà, il JSONL vecchio resta intero. (Vedi "Python e il mistero dei
    # file scomparsi".)
    temporaneo = uscita.with_suffix(".tmp")
    with temporaneo.open("w", encoding="utf-8") as f:
        for p in paragrafi:
            # ensure_ascii=False: vogliamo leggere "perchè", non "perchè".
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")
    temporaneo.replace(uscita)
    print(f"{len(paragrafi)} paragrafi scritti in {uscita}", file=sys.stderr)


if __name__ == "__main__":
    main()
