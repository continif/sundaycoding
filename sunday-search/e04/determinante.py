"""
S05E04 free — Determinante e inversa senza paura.

Tutti i numeri dell'articolo, nell'ordine in cui compaiono:
  1. la tavola più grande di Tenniel trasformata da quattro matrici, e
     l'area misurata contro il determinante;
  2. il determinante a mano: 2×2, 3×3, Laplace e Gauss, e quanto costano;
  3. inv contro solve, in tempo e in precisione;
  4. i float che tradiscono: determinanti "quasi zero" e numero di
     condizionamento.

Uso:
    python determinante.py
"""

from __future__ import annotations

import math
import statistics
import time

import numpy as np


# ---------------------------------------------------------------------------
# 1. Il rettangolo e la fotocopiatrice
# ---------------------------------------------------------------------------
def area_con_segno(punti: list[tuple[float, float]]) -> float:
    """Formula dell'allacciatura delle scarpe (shoelace): l'area di un
    poligono dai suoi vertici. Il segno dice il verso: positivo se i vertici
    girano in senso antiorario, negativo se girano in senso orario."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(punti, punti[1:] + punti[:1]):
        s += x1 * y2 - x2 * y1
    return s / 2


def trasforma(m: np.ndarray, punti: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [tuple(m @ np.array(p)) for p in punti]


# ---------------------------------------------------------------------------
# 2. Il determinante a mano
# ---------------------------------------------------------------------------
def det2(m) -> float:
    (a, b), (c, d) = m
    return a * d - b * c


def det3(m) -> float:
    """Sarrus: tre diagonali in giù meno tre diagonali in su. Vale SOLO
    per le 3×3: per le 4×4 non esiste una regola delle diagonali."""
    (a, b, c), (d, e, f), (g, h, i) = m
    return a * e * i + b * f * g + c * d * h - c * e * g - a * f * h - b * d * i


def laplace(m: list[list[float]]) -> float:
    """Sviluppo lungo la prima riga: n determinanti (n-1)×(n-1), ognuno con
    il suo segno a scacchiera. Elegante, e costa n! moltiplicazioni."""
    n = len(m)
    if n == 1:
        return m[0][0]
    if n == 2:
        return det2(m)
    totale = 0.0
    for j in range(n):
        if m[0][j] == 0:
            continue                      # uno zero risparmia un ramo intero
        minore = [riga[:j] + riga[j + 1:] for riga in m[1:]]
        totale += (-1) ** j * m[0][j] * laplace(minore)
    return totale


def gauss(m: list[list[float]]) -> float:
    """Eliminazione di Gauss: si rende la matrice triangolare con
    operazioni che non cambiano il determinante (togliere a una riga un
    multiplo di un'altra) o lo cambiano in modo noto (scambiare due righe
    cambia il segno). Poi il determinante è il prodotto della diagonale.
    Circa n³/3 moltiplicazioni."""
    a = [riga[:] for riga in m]           # copia: non si rovina la matrice di chi chiama
    n, segno, det = len(a), 1.0, 1.0
    for k in range(n):
        # Pivot parziale: si porta su la riga con il numero più grande in
        # colonna k. Dividere per un numero piccolo amplifica gli errori dei
        # float; dividere per il più grande disponibile li tiene a bada.
        p = max(range(k, n), key=lambda r: abs(a[r][k]))
        if a[p][k] == 0:
            return 0.0
        if p != k:
            a[k], a[p] = a[p], a[k]
            segno = -segno
        det *= a[k][k]
        for r in range(k + 1, n):
            f = a[r][k] / a[k][k]
            riga_k, riga_r = a[k], a[r]
            for c in range(k, n):
                riga_r[c] -= f * riga_k[c]
    return segno * det


def tempo(f, *args, ripetizioni: int = 5) -> float:
    t = []
    for _ in range(ripetizioni):
        t0 = time.perf_counter()
        f(*args)
        t.append(time.perf_counter() - t0)
    return statistics.median(t)


def main() -> None:
    rng = np.random.default_rng(1871)

    # --- 1. La tavola di Tenniel -----------------------------------------
    # alice03.gif, capitolo I: 320 × 376 pixel, la più grande del libro.
    base, altezza = 320, 376
    tavola = [(0, 0), (base, 0), (base, altezza), (0, altezza)]
    print(f"1. La tavola di Tenniel: {base}×{altezza}, area {area_con_segno(tavola):,.0f}")
    trasformazioni = {
        "A4 → A3 (141%)": np.array([[math.sqrt(2), 0], [0, math.sqrt(2)]]),
        "riduzione al 50%": np.array([[0.5, 0], [0, 0.5]]),
        "inclinata (taglio)": np.array([[1, 0.6], [0, 1]]),
        "allo specchio": np.array([[-1, 0], [0, 1]]),
        "schiacciata su una riga": np.array([[1, 2], [0.5, 1]]),
    }
    for nome, m in trasformazioni.items():
        nuova = area_con_segno(trasforma(m, tavola))
        print(f"   {nome:26} det {np.linalg.det(m):+8.4f}   area {nuova:+12,.1f}"
              f"   rapporto {nuova / area_con_segno(tavola):+.4f}")

    # --- 2. A mano --------------------------------------------------------
    print("\n2. Il determinante a mano")
    a2 = [[3, 1], [2, 4]]
    a3 = [[2, 0, 1], [1, 3, 2], [1, 1, 2]]
    print(f"   det2 {a2} = {det2(a2)}   numpy {np.linalg.det(a2):.10f}")
    print(f"   det3 {a3} = {det3(a3)}   Laplace {laplace(a3)}   Gauss {gauss(a3):.10f}")

    print("\n   n   Laplace        Gauss (Python)   numpy")
    for n in range(2, 11):
        m = rng.integers(1, 10, (n, n)).astype(float).tolist()
        tl = tempo(laplace, m, ripetizioni=1 if n >= 9 else 3)
        tg = tempo(gauss, m)
        tn = tempo(np.linalg.det, np.array(m), ripetizioni=50)
        controllo = abs(laplace(m) - gauss(m)) / max(1, abs(gauss(m))) if n <= 8 else 0
        print(f"  {n:2}  {tl * 1000:12.3f} ms  {tg * 1e6:10.1f} µs  {tn * 1e6:8.1f} µs"
              f"   (n! = {math.factorial(n):,}, scarto relativo {controllo:.1e})")

    print("\n   n     Gauss (Python)    numpy")
    for n in (50, 100, 200, 400):
        m = rng.standard_normal((n, n))
        tg = tempo(gauss, m.tolist(), ripetizioni=3 if n <= 200 else 1)
        # slogdet e non det: con n = 400 il determinante di una matrice a
        # caso supera il più grande float (vedi il punto 4). Costa uguale.
        tn = tempo(np.linalg.slogdet, m, ripetizioni=20)
        print(f"  {n:4}  {tg * 1000:12.1f} ms  {tn * 1000:9.3f} ms   x{tg / tn:,.0f}")
    for n in (1000, 2000):
        m = rng.standard_normal((n, n))
        print(f"  {n:4}  {'':12}     {tempo(np.linalg.slogdet, m, ripetizioni=3) * 1000:9.1f} ms")

    # --- 3. inv contro solve ---------------------------------------------
    print("\n3. Risolvere A x = b: inv(A) @ b contro solve(A, b)")
    for n in (100, 1000, 2000):
        A = rng.standard_normal((n, n))
        x_vero = rng.standard_normal(n)
        b = A @ x_vero
        ti = tempo(lambda: np.linalg.inv(A) @ b, ripetizioni=5)
        ts = tempo(lambda: np.linalg.solve(A, b), ripetizioni=5)
        ei = np.linalg.norm(np.linalg.inv(A) @ b - x_vero) / np.linalg.norm(x_vero)
        es = np.linalg.norm(np.linalg.solve(A, b) - x_vero) / np.linalg.norm(x_vero)
        print(f"   n={n:5}  inv {ti * 1000:8.2f} ms (errore {ei:.1e})"
              f"   solve {ts * 1000:8.2f} ms (errore {es:.1e})   inv/solve x{ti / ts:.1f}")

    # --- 4. I float che tradiscono ---------------------------------------
    print("\n4. I float che tradiscono")
    for nome, righe in (("interi", [[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
                        ("decimi", [[.1, .2, .3], [.4, .5, .6], [.7, .8, .9]])):
        # Le due matrici sono singolari tutte e due: la terza riga è il
        # doppio della seconda meno la prima. Ma 0,1 in binario non si scrive
        # esattamente, e il determinante "zero" non viene più zero.
        s = np.array(righe, dtype=float)
        try:
            esito = f"il numero più grande dell'inversa è {np.abs(np.linalg.inv(s)).max():.1e}"
        except np.linalg.LinAlgError as e:
            esito = f"inv: LinAlgError ({e})"
        print(f"   {nome}: det {np.linalg.det(s):.2e}, rank {np.linalg.matrix_rank(s)},"
              f" condizionamento {np.linalg.cond(s):.1e}; {esito}")

    r = rng.standard_normal((400, 400))
    with np.errstate(over="ignore"):
        d = np.linalg.det(r)
    segno, logdet = np.linalg.slogdet(r)
    print(f"\n   400×400 a caso: det {d}, slogdet dice 10^{logdet / math.log(10):.1f}"
          f" (il float più grande è {np.finfo(float).max:.1e})")

    i100 = 0.1 * np.eye(100)
    print(f"\n   0,1 × identità 100×100: det {np.linalg.det(i100):.1e}, condizionamento {np.linalg.cond(i100):.1f}")
    i400 = 0.1 * np.eye(400)
    print(f"   0,1 × identità 400×400: det {np.linalg.det(i400):.1e}  (sotto il più piccolo float)")

    print("\n   matrici di Hilbert, H[i][j] = 1/(i+j+1): risolvere H x = b con x tutto 1")
    for n in (4, 8, 12, 16):
        H = np.array([[1 / (i + j + 1) for j in range(n)] for i in range(n)])
        x_vero = np.ones(n)
        b = H @ x_vero
        ei = np.linalg.norm(np.linalg.inv(H) @ b - x_vero) / np.linalg.norm(x_vero)
        es = np.linalg.norm(np.linalg.solve(H, b) - x_vero) / np.linalg.norm(x_vero)
        print(f"   n={n:2}  det {np.linalg.det(H):9.2e}   cond {np.linalg.cond(H):9.2e}"
              f"   errore inv {ei:8.1e}   solve {es:8.1e}")


if __name__ == "__main__":
    main()
