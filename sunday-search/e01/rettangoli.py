"""
S05E01 — Rettangoli in fila.

Quattro modi di insegnare a un rettangolo a mettersi in fila per area,
ognuno con un contatore che dice quante volte l'area viene calcolata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key, total_ordering


class Contatore:
    """Un contatore globale, azzerabile. Lo usiamo per contare i calcoli
    dell'area senza toccare la logica dei confronti."""

    def __init__(self) -> None:
        self.n = 0

    def azzera(self) -> None:
        self.n = 0


CALCOLI_AREA = Contatore()


def calcola_area(base: float, altezza: float) -> float:
    # Il punto unico in cui si calcola un'area: contarlo qui vuol dire
    # contarlo per tutte e quattro le classi allo stesso modo.
    CALCOLI_AREA.n += 1
    return base * altezza


# ---------------------------------------------------------------------------
# Modo 1: __lt__ + @total_ordering
# ---------------------------------------------------------------------------
@total_ordering
@dataclass(slots=True, eq=False)
class RettangoloLt:
    base: float
    altezza: float

    @property
    def area(self) -> float:
        return calcola_area(self.base, self.altezza)

    # sorted() usa SOLO __lt__. total_ordering serve a chi scrive a <= b
    # o a > b altrove nel codice: genera gli altri tre a partire da questi.
    def __lt__(self, altro: RettangoloLt) -> bool:
        # Due aree calcolate a ogni confronto: una per lato.
        return self.area < altro.area

    def __eq__(self, altro: object) -> bool:
        if not isinstance(altro, RettangoloLt):
            return NotImplemented
        return self.area == altro.area


# ---------------------------------------------------------------------------
# Modo 2: nessun confronto nella classe, key= da fuori
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class Rettangolo:
    base: float
    altezza: float

    @property
    def area(self) -> float:
        return calcola_area(self.base, self.altezza)


# ---------------------------------------------------------------------------
# Modo 3: @dataclass(order=True) con l'area come primo campo
# ---------------------------------------------------------------------------
# frozen=True non è un vezzo: l'area è calcolata una volta sola in
# __post_init__. Se la base potesse cambiare dopo, l'area resterebbe
# quella vecchia e l'ordinamento mentirebbe senza dare errori.
@dataclass(slots=True, frozen=True, order=True)
class RettangoloOrdinato:
    # Il primo campo è quello che decide l'ordine: order=True confronta i
    # campi nell'ordine in cui sono dichiarati, come una tupla.
    area: float = field(init=False)
    # compare=False: base e altezza non partecipano al confronto. Senza,
    # a parità di area deciderebbe la base, e due rettangoli 2×3 e 3×2
    # risulterebbero diversi.
    base: float = field(compare=False)
    altezza: float = field(compare=False)

    def __post_init__(self) -> None:
        # Con frozen=True l'assegnazione normale è vietata: si passa da
        # object.__setattr__, che è esattamente quello che fa dataclass
        # stessa dietro le quinte.
        object.__setattr__(self, "area", calcola_area(self.base, self.altezza))


# ---------------------------------------------------------------------------
# Modo 4: funzione di confronto stile C + cmp_to_key
# ---------------------------------------------------------------------------
def confronta_aree(a: Rettangolo, b: Rettangolo) -> int:
    area_a, area_b = a.area, b.area
    # Il trucco classico (area_a > area_b) - (area_a < area_b) restituisce
    # -1, 0 o 1 senza if, e funziona con qualunque tipo confrontabile.
    # "area_a - area_b" va bene solo con i numeri: con le stringhe dà
    # TypeError, con le date restituisce un timedelta.
    return (area_a > area_b) - (area_a < area_b)


chiave_cmp = cmp_to_key(confronta_aree)
