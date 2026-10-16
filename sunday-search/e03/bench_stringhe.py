"""
S05E03 paid — I cinque algoritmi di ricerca contro str.find, sul libro.

Uso:
    python bench_stringhe.py ../corpus/specchio.jsonl ../vocabolario/
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import duckdb

from stringhe import AhoCorasick, con_find, forza_bruta, horspool, kmp, rabin_karp


def mediana(f, *args, ripetizioni: int = 7) -> float:
    """Mediana di più misure, in millisecondi: la prima chiamata paga
    cache e allocazioni, e una misura sola mente."""
    tempi = []
    for _ in range(ripetizioni):
        t0 = time.perf_counter()
        f(*args)
        tempi.append(time.perf_counter() - t0)
    return statistics.median(tempi) * 1000


def main() -> None:
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        libro = unicodedata.normalize("NFC", "\n".join(json.loads(r)["testo"] for r in f))
    print(f"il libro: {len(libro):,} caratteri\n")

    algoritmi = [("str.find", con_find), ("forza bruta", forza_bruta), ("KMP", kmp),
                 ("Horspool", horspool), ("Rabin-Karp", rabin_karp)]
    aghi = ["re", "Regina", "crociera", "Giabervocco", "la Regina Rossa disse"]

    print(f"{'':12}" + "".join(f"{a!r:>24}" for a in aghi))
    for nome, f in algoritmi:
        riga = f"{nome:12}"
        for ago in aghi:
            riga += f"{mediana(f, libro, ago):>21.2f} ms"
        print(riga)
    print("occorrenze " + "".join(f"{len(con_find(libro, a)):>24}" for a in aghi))

    # Il testo dieci volte più lungo: chi scala come?
    dieci = libro * 10
    print(f"\nlo stesso testo ripetuto 10 volte ({len(dieci):,} caratteri), ago 'Giabervocco':")
    for nome, f in algoritmi:
        print(f"  {nome:12} {mediana(f, dieci, 'Giabervocco', ripetizioni=3):9.1f} ms")

    # Tanti aghi: tutte le forme di "gridare", dal vocabolario della free.
    forme = [r[0] for r in duckdb.sql(
        f"SELECT forma FROM read_parquet('{Path(sys.argv[2]) / 'forme*.parquet'}') "
        "WHERE lemma = 'gridare' ORDER BY forma").fetchall()]
    print(f"\n{len(forme)} aghi: tutte le forme di 'gridare'")
    ac = AhoCorasick(forme)
    alternativa = re.compile("|".join(map(re.escape, sorted(forme, key=len, reverse=True))))
    print(f"  str.find × {len(forme):<5}  {mediana(lambda: [con_find(libro, a) for a in forme]):9.1f} ms")
    print(f"  re a|b|c...    {mediana(lambda: alternativa.findall(libro)):9.1f} ms")
    print(f"  Aho-Corasick   {mediana(ac.cerca, libro):9.1f} ms"
          f"   (costruzione {mediana(AhoCorasick, forme):.2f} ms)")
    trovate = sorted({a for _, a in ac.cerca(libro)})
    print(f"  trovate: {len(ac.cerca(libro))} occorrenze di {len(trovate)} forme: {', '.join(trovate)}")

    # Aghi senza un prefisso in comune: forme a caso dal vocabolario.
    # Con le forme di "gridare" re vince facile, perché tutte iniziano per
    # "grid" e il motore delle regex cerca prima quel pezzo fisso. Qui no.
    print("\naghi a caso dal vocabolario (almeno 4 lettere):")
    for k in (10, 100, 1000, 10000):
        campione = [r[0] for r in duckdb.sql(
            f"SELECT forma FROM read_parquet('{Path(sys.argv[2]) / 'forme*.parquet'}') "
            "WHERE origine = 'dizionario' AND length(forma) >= 4 "
            f"USING SAMPLE {k} ROWS (reservoir, 1)").fetchall()]
        ac = AhoCorasick(campione)
        alt = re.compile("|".join(map(re.escape, sorted(campione, key=len, reverse=True))))
        r = 3 if k >= 1000 else 5
        print(f"  {k:>6} aghi:  str.find × n {mediana(lambda: [con_find(libro, a) for a in campione], ripetizioni=r):8.1f} ms"
              f"   re {mediana(alt.findall, libro, ripetizioni=r):8.1f} ms"
              f"   Aho-Corasick {mediana(ac.cerca, libro, ripetizioni=r):6.1f} ms"
              f" (+ {mediana(AhoCorasick, campione, ripetizioni=r):.1f} ms per costruirlo)")

    # Il problema delle sottostringhe: "pere" e "Re" dentro altre parole.
    for ago in ("pere", "Re"):
        sotto = len(con_find(libro, ago))
        parole = len(re.findall(rf"(?<![^\W\d_]){ago}(?![^\W\d_])", libro))
        print(f"\n'{ago}': {sotto} occorrenze come sottostringa, {parole} come parola intera")
        esempi = sorted({m.group() for m in re.finditer(rf"[^\W\d_]*{ago}[^\W\d_]*", libro)} - {ago})
        print("  dentro: " + ", ".join(esempi[:12]))


if __name__ == "__main__":
    main()
