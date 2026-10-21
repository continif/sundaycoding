"""
S05E04 paid — `cerca --rank`: il motore che ordina.

La query passa dallo stesso tokenizzatore del libro e prende le varianti dal
dizionario (E03); poi BM25 sulla matrice sparsa (E04), i primi k con un heap,
e a richiesta i risultati resi vari con MMR.

Uso:
    python cerca.py "la marmellata ieri e domani" --rank
    python cerca.py regina --rank --vari -k 5
    python cerca.py "regina rossa" --rank --schema coseno

Le cartelle si passano con --indice e --vocabolario (di default ../indice e
../vocabolario, accanto alla cartella e04).
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADICE / "e03"))
from indice import Indice          # noqa: E402
from vocabolario import Vocabolario  # noqa: E402

from registro import Registro


def main() -> None:
    p = argparse.ArgumentParser(description="Cerca nel libro, con o senza ordinamento.")
    p.add_argument("query")
    p.add_argument("--rank", action="store_true", help="ordina per pertinenza (altrimenti: ordine del libro, come in E03)")
    p.add_argument("--schema", default="bm25", choices=["conteggi", "tfidf", "coseno", "bm25"])
    p.add_argument("--vari", action="store_true", help="rende vari i primi risultati (MMR)")
    p.add_argument("-k", type=int, default=10)
    p.add_argument("--indice", type=Path, default=RADICE / "indice")
    p.add_argument("--vocabolario", type=Path, default=RADICE / "vocabolario")
    a = p.parse_args()

    idx = Indice(a.indice, Vocabolario(a.vocabolario))
    reg = Registro(a.indice)
    if not a.rank:
        # Il comportamento di E03: AND tra i termini, nell'ordine del libro.
        for par in idx.cerca(a.query)[: a.k]:
            print(f"{reg.etichette[par]:>8}  {textwrap.shorten(' '.join(reg.testi[par].split()), 98)}")
        return

    # Ogni termine della query con le sue varianti (crociera → crociere,
    # gridare → tutte le forme): un gruppo per termine, che conta come una
    # parola sola. Vedi Registro.punteggi_gruppi.
    gruppi = [sorted(idx.varianti(t)) for t, _ in idx.termini(a.query)]
    punteggi = reg.punteggi_gruppi(gruppi, a.schema)
    risultati = reg.vari_mmr(punteggi, a.k) if a.vari else reg.migliori(punteggi, a.k)
    if not risultati:
        print("nessun paragrafo")
        return
    for par in risultati:
        testo = " ".join(reg.testi[par].split())
        print(f"{reg.etichette[par]:>8}  {punteggi[par]:6.2f}  {textwrap.shorten(testo, 90)}")


if __name__ == "__main__":
    main()
