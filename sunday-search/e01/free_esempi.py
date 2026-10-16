"""S05E01 free — Salutame a sort!

Gli esempi del pezzo sullo scaffale di prova: sort() che ritorna None,
le due passate stabili, cmp_to_key, nlargest, bisect con key=.

    python free_esempi.py
"""
from dataclasses import dataclass
from operator import attrgetter
from functools import cmp_to_key
import bisect, heapq

@dataclass(slots=True)
class Libro:
    titolo: str
    autore: str
    anno: int
    pagine: int

scaffale = [
    Libro("Il nome della rosa", "Eco", 1980, 503),
    Libro("Il pendolo di Foucault", "Eco", 1988, 509),
    Libro("Se una notte d'inverno un viaggiatore", "Calvino", 1979, 263),
    Libro("Le città invisibili", "Calvino", 1972, 164),
    Libro("Il barone rampante", "Calvino", 1957, 283),
    Libro("La storia", "Morante", 1974, 661),
]
r = scaffale.sort(key=attrgetter("anno"))
print("sort ritorna:", r)
# stabilità, due passate
per_anno_desc = sorted(scaffale, key=attrgetter("anno"), reverse=True)
risultato = sorted(per_anno_desc, key=attrgetter("autore"))
for l in risultato: print(l.autore, l.anno, l.titolo)
print([ (l.autore,l.anno) for l in sorted(scaffale, key=lambda l: (l.autore, -l.anno))])
# reverse con stabilità
print([l.titolo for l in sorted(scaffale, key=attrgetter("autore"), reverse=True)])

def chi_va_prima(a, b):
    if a + b > b + a: return -1
    if a + b < b + a: return 1
    return 0
print("".join(sorted(["3","30","34","5","9"], key=cmp_to_key(chi_va_prima))))

print([l.titolo for l in heapq.nlargest(2, scaffale, key=attrgetter("pagine"))])

per_anno = sorted(scaffale, key=attrgetter("anno"))
nuovo = Libro("Lessico famigliare", "Ginzburg", 1963, 230)
bisect.insort(per_anno, nuovo, key=attrgetter("anno"))
print([ (l.anno) for l in per_anno])
i = bisect.bisect_left(per_anno, 1975, key=attrgetter("anno"))
print("primo dal 1975:", per_anno[i].titolo)
try:
    bisect.bisect_left(per_anno, nuovo, key=attrgetter("anno"))
except Exception as e: print("errore:", type(e).__name__, e)
