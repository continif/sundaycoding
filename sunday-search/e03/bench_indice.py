"""
S05E03 paid — Le misure dell'indice: varianti, intersezioni, frasi, SQL.

Uso (dopo aver costruito l'indice con indice.py):
    python bench_indice.py ../vocabolario/ ../indice/
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

from indice import Indice, interseca, interseca_bisect
from vocabolario import Vocabolario


def mediana_us(f, *args, ripetizioni: int = 200) -> float:
    tempi = []
    for _ in range(ripetizioni):
        t0 = time.perf_counter()
        f(*args)
        tempi.append(time.perf_counter() - t0)
    return statistics.median(tempi) * 1e6


def main() -> None:
    voc = Vocabolario(Path(sys.argv[1]))
    idx = Indice(Path(sys.argv[2]), voc)
    e = idx.etichette

    print("Le varianti, cioè il dizionario nell'altro verso:")
    for parola in ["croce", "crociera", "crocere", "casa", "caso", "gatto", "uovo", "testa",
                   "gridò", "porta", "pera", "papà", "regina", "Tuidledum"]:
        [t] = [t for t, _ in idx.termini(parola)] or [parola]
        v = sorted(idx.varianti(t))
        print(f"  {parola:10} → {len(v):3} forme: {', '.join(v[:8])}{' ...' if len(v) > 8 else ''}")

    print("\nCon e senza varianti:")
    for q in ["occhio", "mano", "fiore", "regina", "gridare", "casa", "uovo"]:
        print(f"  {q:10} esatta {len(idx.cerca(q, espandi=False)):3} paragrafi,"
              f" con le varianti {len(idx.cerca(q)):3}")

    print("\nAND tra due liste ordinate di paragrafi:")
    for a, b in [("alice", "regina"), ("alice", "tuidledum"), ("regina", "rossa")]:
        la, lb = idx.paragrafi[a], idx.paragrafi[b]
        corta, lunga = sorted((la, lb), key=len)
        assert interseca(la, lb) == interseca_bisect(corta, lunga) == sorted(set(la) & set(lb))
        sa, sb = set(la), set(lb)
        print(f"  {a} ({len(la)}) AND {b} ({len(lb)}) = {len(interseca(la, lb))}:"
              f"  due dita {mediana_us(interseca, la, lb):6.1f} µs"
              f"   bisect {mediana_us(interseca_bisect, corta, lunga):6.1f} µs"
              f"   set & {mediana_us(lambda: sa & sb):6.1f} µs"
              f"   set da liste {mediana_us(lambda: set(la) & set(lb)):6.1f} µs")

    print("\ncerca() in Python contro la stessa ricerca in SQL sul Parquet:")
    for q in ["Regina Rossa", "gridò Alice", "casa", "occhio"]:
        py, sql = idx.cerca(q), idx.cerca_sql(q)
        assert py == sql, (q, py, sql)
        print(f"  {q!r:15} {len(py):3} paragrafi:  Python {mediana_us(idx.cerca, q, ripetizioni=50):8.0f} µs"
              f"   DuckDB {mediana_us(idx.cerca_sql, q, ripetizioni=50):8.0f} µs")

    print("\nFrasi:")
    for frase in ["testa in giù", "a testa in giù", "Regina Rossa", "Rossa Regina", "la Regina Bianca"]:
        r = idx.cerca_frase(frase)
        print(f"  {frase!r:20} {len(r):3} paragrafi  {' '.join(e[p] for p in r[:8])}"
              f"   ({mediana_us(idx.cerca_frase, frase, ripetizioni=50):.0f} µs)")


if __name__ == "__main__":
    main()
