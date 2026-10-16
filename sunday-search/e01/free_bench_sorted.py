"""S05E01 free — Salutame a sort!

sorted() contro list.sort(), lambda contro attrgetter, chiavi a tupla,
cmp_to_key e heapq.nlargest su un milione di elementi.

    python free_bench_sorted.py
"""
import random, timeit, heapq, bisect, sys
from dataclasses import dataclass
from operator import attrgetter, itemgetter
from functools import cmp_to_key

random.seed(42)
N = 1_000_000

@dataclass(slots=True)
class Libro:
    titolo: str
    autore: str
    anno: int
    pagine: int

def best(stmt, number=1, repeat=5, g=None):
    return min(timeit.repeat(stmt, number=number, repeat=repeat, globals=g)) / number

nums = [random.random() for _ in range(N)]
libri = [Libro(f"t{i}", f"a{random.randrange(5000)}", random.randrange(1900, 2027), random.randrange(50, 1500)) for i in range(N)]
g = dict(globals())

print("python", sys.version.split()[0])
# 1. top-10
print("sorted()[:10] nums     ", best("sorted(nums, reverse=True)[:10]", g=g))
print("nlargest(10) nums      ", best("heapq.nlargest(10, nums)", g=g))
print("sorted key [:10] libri ", best("sorted(libri, key=attrgetter('pagine'), reverse=True)[:10]", g=g))
print("nlargest key libri     ", best("heapq.nlargest(10, libri, key=attrgetter('pagine'))", g=g))
print("nlargest(1000) nums    ", best("heapq.nlargest(1000, nums)", g=g))
print("nlargest(100000) nums  ", best("heapq.nlargest(100000, nums)", g=g))
print("max nums               ", best("max(nums)", g=g))

# 2. lambda vs attrgetter
print("key lambda             ", best("sorted(libri, key=lambda l: l.pagine)", g=g))
print("key attrgetter         ", best("sorted(libri, key=attrgetter('pagine'))", g=g))
print("key lambda tupla       ", best("sorted(libri, key=lambda l: (l.anno, l.pagine))", g=g))
print("key attrgetter 2       ", best("sorted(libri, key=attrgetter('anno','pagine'))", g=g))

# 3. cmp_to_key
def cmp(a, b): return a.pagine - b.pagine
g['cmp'] = cmp
print("cmp_to_key             ", best("sorted(libri, key=cmp_to_key(cmp))", g=g, repeat=3))

# 4. sort in place vs sorted
print("sorted nums            ", best("sorted(nums)", g=g))
print("list.sort copy         ", best("x=nums.copy(); x.sort()", g=g))
print("copy only              ", best("x=nums.copy()", g=g))
