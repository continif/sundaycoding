"""Tutti i numeri della paid S05E01. python bench_paid.py"""

import platform
import random
import sys
import timeit
from operator import attrgetter

from ordinamenti import ALGORITMI, Conti, quick_sort
from rettangoli import (CALCOLI_AREA, Rettangolo, RettangoloLt,
                        RettangoloOrdinato, chiave_cmp)

print("Python", sys.version.split()[0], platform.machine())


def migliore(funzione, ripetizioni=5):
    return min(timeit.repeat(funzione, number=1, repeat=ripetizioni))


# --- 1. I quattro modi: calcoli dell'area e tempo -----------------------
N = 100_000
rng = random.Random(42)
misure = [(rng.uniform(1, 100), rng.uniform(1, 100)) for _ in range(N)]

lt = [RettangoloLt(b, h) for b, h in misure]
semplici = [Rettangolo(b, h) for b, h in misure]
CALCOLI_AREA.azzera()
ordinati = [RettangoloOrdinato(b, h) for b, h in misure]
calcoli_costruzione = CALCOLI_AREA.n

casi = {
    "__lt__ + total_ordering": lambda: sorted(lt),
    "key=attrgetter('area')": lambda: sorted(semplici, key=attrgetter("area")),
    "dataclass(order=True)": lambda: sorted(ordinati),
    "cmp_to_key": lambda: sorted(semplici, key=chiave_cmp),
}
print(f"\n1) {N:,} rettangoli casuali")
print(f"   order=True: {calcoli_costruzione:,} aree calcolate alla costruzione")
for nome, f in casi.items():
    CALCOLI_AREA.azzera()
    f()
    calcoli = CALCOLI_AREA.n
    t = migliore(f)
    print(f"   {nome:26} aree calcolate={calcoli:>10,}  tempo={t*1000:7.1f} ms")

# Confronti fatti da Timsort sulla stessa lista: calcoli_lt / 2
CALCOLI_AREA.azzera(); sorted(lt)
print(f"   confronti di Timsort ≈ {CALCOLI_AREA.n // 2:,}")

# Costo di total_ordering: a >= b generato contro scritto a mano
a, b = lt[0], lt[1]
t_lt = min(timeit.repeat(lambda: a < b, number=200_000, repeat=5)) / 200_000
t_ge = min(timeit.repeat(lambda: a >= b, number=200_000, repeat=5)) / 200_000
print(f"   a < b {t_lt*1e9:.0f} ns   a >= b (generato da total_ordering) {t_ge*1e9:.0f} ns")

# Variante "cache": key= con lambda che calcola al volo
t_lambda = migliore(lambda: sorted(semplici, key=lambda r: r.base * r.altezza))
print(f"   key=lambda r: r.base*r.altezza (senza property) tempo={t_lambda*1000:.1f} ms")

# --- 2. Algoritmi a mano: confronti, scritture, tempo -------------------
print()
for n in (1_000, 5_000):
    dati = [rng.uniform(1, 100) * rng.uniform(1, 100) for _ in range(n)]
    print(f"2) {n:,} aree casuali")
    for nome, algo in ALGORITMI.items():
        c = Conti()
        algo(dati, conti=c)
        t = migliore(lambda: algo(dati), ripetizioni=3)
        print(f"   {nome:10} confronti={c.confronti:>11,}  scritture={c.scritture:>11,}  tempo={t*1000:9.1f} ms")
    t = migliore(lambda: sorted(dati))
    print(f"   {'sorted()':10} tempo={t*1000:.3f} ms")

# --- 3. Già ordinata: chi se ne accorge -----------------------------------
n = 5_000
dati = sorted(rng.uniform(1, 10_000) for _ in range(n))
print(f"\n3) {n:,} aree GIÀ ORDINATE")
for nome, algo in ALGORITMI.items():
    c = Conti()
    algo(dati, conti=c)
    t = migliore(lambda: algo(dati), ripetizioni=3)
    print(f"   {nome:10} confronti={c.confronti:>11,}  tempo={t*1000:9.1f} ms")
c = Conti()
quick_sort(dati, conti=c, pivot="ultimo")
t = migliore(lambda: quick_sort(dati, pivot="ultimo"), ripetizioni=3)
print(f"   {'quick/ultimo':10} confronti={c.confronti:>11,}  tempo={t*1000:9.1f} ms")
t = migliore(lambda: sorted(dati))
print(f"   {'sorted()':10} tempo={t*1000:.3f} ms")

# --- 4. Stabilità: chi rimescola gli uguali --------------------------------
print("\n4) stabilità su 200 rettangoli con 6 aree possibili")
r = random.Random(7)
rett = [(r.choice([6, 12, 24, 36, 48, 60]), i) for i in range(200)]
atteso = sorted(rett, key=lambda x: x[0])
for nome, algo in ALGORITMI.items():
    ok = algo(rett, key=lambda x: x[0]) == atteso
    print(f"   {nome:10} {'stabile' if ok else 'NON stabile'}")

# --- 5. Il caso ricorsivo da manuale --------------------------------------
def quick_ricorsivo(a):
    if len(a) <= 1:
        return a
    p = a[-1]
    return quick_ricorsivo([x for x in a[:-1] if x < p]) + [p] + quick_ricorsivo([x for x in a[:-1] if x >= p])

print("\n5) quicksort ricorsivo da manuale (pivot = ultimo)")
for n in (500, 1_000, 2_000):
    try:
        quick_ricorsivo(list(range(n)))
        print(f"   {n:,} già ordinati: ok")
    except RecursionError as e:
        print(f"   {n:,} già ordinati: RecursionError ({e})")
