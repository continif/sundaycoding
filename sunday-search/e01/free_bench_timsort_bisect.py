"""S05E01 free — Salutame a sort!

Quanti confronti fa Timsort su liste casuali, ordinate, rovesciate e quasi
ordinate; bisect.insort contro append+sort; la stabilità in due passate.

    python free_bench_timsort_bisect.py
"""
import random, timeit, bisect, math
random.seed(42)
N = 100_000

class Conta:
    __slots__ = ("v",)
    n = 0
    def __init__(self, v): self.v = v
    def __lt__(self, o):
        Conta.n += 1
        return self.v < o.v

def confronti(valori):
    Conta.n = 0
    sorted([Conta(v) for v in valori])
    return Conta.n

casuale = [random.random() for _ in range(N)]
ordinato = sorted(casuale)
rovescio = ordinato[::-1]
quasi = ordinato.copy()
for _ in range(100):  # 100 scambi a caso
    i, j = random.randrange(N), random.randrange(N)
    quasi[i], quasi[j] = quasi[j], quasi[i]
appesi = ordinato + sorted(random.random() for _ in range(1000))  # lista ordinata + 1000 nuovi in coda, ordinati
print("n log2 n           ", round(N*math.log2(N)))
for nome, v in [("casuale", casuale), ("ordinato", ordinato), ("rovescio", rovescio), ("quasi (100 scambi)", quasi), ("ordinato+1000 in coda", appesi)]:
    t = min(timeit.repeat(lambda: sorted(v), number=10, repeat=5))/10
    print(f"{nome:22} confronti={confronti(v):>9,}  tempo={t*1000:.2f} ms")

# bisect vs append+sort, inserimento uno alla volta di 10_000 elementi in lista da 100_000
nuovi = [random.random() for _ in range(10_000)]
def con_insort():
    l = ordinato.copy()
    for x in nuovi: bisect.insort(l, x)
def con_sort_ogni_volta():
    l = ordinato.copy()
    for x in nuovi[:1000]:
        l.append(x); l.sort()
def con_sort_alla_fine():
    l = ordinato.copy(); l.extend(nuovi); l.sort()
print("insort 10k          ", min(timeit.repeat(con_insort, number=1, repeat=3)))
print("append+sort 1k (!)  ", min(timeit.repeat(con_sort_ogni_volta, number=1, repeat=3)))
print("extend+sort 10k     ", min(timeit.repeat(con_sort_alla_fine, number=1, repeat=3)))

# stabilità
libri = [("Il nome della rosa","Eco",1980),("Il pendolo di Foucault","Eco",1988),("Se una notte d'inverno un viaggiatore","Calvino",1979),("Le città invisibili","Calvino",1972),("Il barone rampante","Calvino",1957),("La storia","Morante",1974)]
from operator import itemgetter
s = sorted(libri, key=itemgetter(2))
s = sorted(s, key=itemgetter(1))
for l in s: print(l)
print(sorted(libri, key=lambda l: (l[1], -l[2])))
