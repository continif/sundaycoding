"""
S05E04 free — Cercare è moltiplicare.

I numeri della puntata, misurati sulla matrice termini × paragrafi del libro
costruita dall'indice di E03 (indice/indice.parquet):
  1. dimensioni e sparsità;
  2. i pesi: in quanti paragrafi sta una parola, e quanto pesa;
  3. una ricerca come matrice × vettore, con e senza pesi e coseno;
  4. ridondanza: righe quasi parallele, e i valori singolari;
  5. il determinante come area tra paragrafi;
  6. float32 contro float64, dove il determinante si rompe.

Uso:
    python matrice.py ../indice/
"""

from __future__ import annotations

import heapq
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
from scipy import sparse


def carica(cartella: Path):
    con = duckdb.connect()
    righe = con.execute(f"""
        SELECT forma, paragrafo, count(*) AS volte
        FROM '{cartella / "indice.parquet"}' GROUP BY forma, paragrafo""").fetchall()
    etichette = dict(con.execute(
        f"SELECT paragrafo, etichetta FROM '{cartella / 'paragrafi.parquet'}'").fetchall())
    forme = sorted({r[0] for r in righe})
    riga_di = {f: i for i, f in enumerate(forme)}
    n_par = len(etichette)
    # coo_matrix: (valore, (riga, colonna)) per ogni casella non vuota.
    # È il modo naturale di costruirla da una tabella di triple.
    m = sparse.coo_matrix(
        ([r[2] for r in righe], ([riga_di[r[0]] for r in righe], [r[1] for r in righe])),
        shape=(len(forme), n_par), dtype=np.float64).tocsr()
    return m, forme, riga_di, etichette


def main() -> None:
    m, forme, riga_di, etichette = carica(Path(sys.argv[1]))
    n_t, n_p = m.shape

    # --- 1. Dimensioni e sparsità ----------------------------------------
    print(f"1. {n_t:,} forme × {n_p:,} paragrafi = {n_t * n_p:,} caselle")
    print(f"   piene: {m.nnz:,} ({m.nnz / (n_t * n_p):.2%})")
    denso64 = n_t * n_p * 8
    sparso = m.data.nbytes + m.indices.nbytes + m.indptr.nbytes
    print(f"   memoria: piena in float64 {denso64 / 2**20:.1f} MB, sparsa {sparso / 2**10:.0f} KB"
          f" (×{denso64 / sparso:.0f})")
    par_per_forma = np.diff(m.indptr)
    print(f"   forme presenti in un solo paragrafo: {(par_per_forma == 1).sum():,}"
          f" ({(par_per_forma == 1).mean():.0%})")

    # --- 2. I pesi ---------------------------------------------------------
    df = par_per_forma
    idf = np.log(n_p / df)
    print("\n2. In quanti paragrafi sta una parola, e quanto pesa (idf = log(N / df))")
    for f in ["alice", "disse", "non", "regina", "rossa", "tuidledum", "uovo", "marmellata", "giabervocco"]:
        if f in riga_di:
            i = riga_di[f]
            print(f"   {f:12} {df[i]:5} paragrafi   idf {idf[i]:5.2f}")
    lunghezze = np.asarray(m.sum(axis=0)).ravel()
    print(f"   lunghezza dei paragrafi (token indicizzati): mediana {np.median(lunghezze):.0f},"
          f" minimo {lunghezze.min():.0f}, massimo {lunghezze.max():.0f}")

    # --- 3. Una ricerca come matrice × vettore ---------------------------
    pesata = sparse.diags(idf) @ m                       # ogni riga per il suo idf
    norme = np.sqrt(np.asarray(pesata.multiply(pesata).sum(axis=0)).ravel())
    print("\n3. 'regina rossa' come vettore, e il punteggio come matrice × vettore")
    q = np.zeros(n_t)
    for f in ("regina", "rossa"):
        q[riga_di[f]] = 1.0
    for nome, punteggi in [
        ("conteggi", m.T @ q),
        ("conteggi × idf", pesata.T @ q),
        ("coseno", (pesata.T @ (q * idf)) / (norme * np.linalg.norm(q * idf) + 1e-12)),
    ]:
        migliori = heapq.nlargest(5, range(n_p), key=punteggi.__getitem__)
        print(f"   {nome:15} " + "  ".join(f"{etichette[p]} ({punteggi[p]:.2f})" for p in migliori))
    toccate = sum(par_per_forma[riga_di[f]] for f in ("regina", "rossa"))
    print(f"   caselle lette davvero: {toccate} su {m.nnz:,} piene ({toccate / m.nnz:.1%})")

    t = time.perf_counter()
    for _ in range(1000):
        pesata.T @ q
    singola = (time.perf_counter() - t) / 1000
    Q = np.zeros((n_t, 100))
    rng = np.random.default_rng(1871)
    candidate = np.where(df >= 3)[0]
    for c in range(100):
        Q[rng.choice(candidate, 2, replace=False), c] = 1.0
    t = time.perf_counter()
    for _ in range(100):
        pesata.T @ Q
    cento = (time.perf_counter() - t) / 100
    print(f"   una ricerca, matrice sparsa × vettore: {singola * 1e6:.1f} µs")
    print(f"   cento ricerche insieme, matrice × matrice: {cento * 1e6:.0f} µs,"
          f" cioè {cento / 100 * 1e6:.1f} µs a ricerca")

    # --- 4. Ridondanza -----------------------------------------------------
    print("\n4. Righe quasi parallele: parole che compaiono sempre insieme")
    norme_righe = np.sqrt(np.asarray(pesata.multiply(pesata).sum(axis=1)).ravel())
    righe_norm = sparse.diags(1 / norme_righe) @ pesata
    for a, b in [("unto", "dunto"), ("mille", "lire"), ("legnaiolo", "tricheco"),
                 ("regina", "rossa"), ("tuidledum", "tuidledì"), ("alice", "regina")]:
        c = (righe_norm[riga_di[a]] @ righe_norm[riga_di[b]].T).toarray()[0, 0]
        print(f"   {a:10} / {b:10} coseno {c:.3f}   (in {df[riga_di[a]]} e {df[riga_di[b]]} paragrafi)")
    # I valori singolari della matrice pesata: quanta "energia" tengono le
    # prime k direzioni. Matrice piccola: la SVD piena in NumPy va benissimo.
    piena = pesata.toarray()
    s = np.linalg.svd(piena, compute_uv=False)
    energia = np.cumsum(s**2) / np.sum(s**2)
    for k in (10, 50, 100, 300):
        print(f"   prime {k:3} direzioni su {len(s)}: {energia[k - 1]:.0%} dell'energia")
    vuoti = int((lunghezze == 0).sum())
    print(f"   rango numerico: {np.linalg.matrix_rank(piena)} su {min(n_t, n_p)}"
          f" ({vuoti} paragrafi fatti solo di stopword: colonne vuote)")

    # --- 5. Il determinante come area tra paragrafi -----------------------
    print("\n5. L'area tra due paragrafi: det della matrice di Gram dei vettori normalizzati")
    norme_ok = np.where(norme > 0, norme, 1)
    colonne = (pesata @ sparse.diags(1 / norme_ok)).T.tocsr()   # una riga per paragrafo
    simili = (colonne @ colonne.T).toarray()
    np.fill_diagonal(simili, 0)
    i, j = np.unravel_index(np.argmax(simili), simili.shape)

    def gram(idx):
        v = colonne[idx].toarray()
        return v @ v.T

    for nome, coppia in [("i due più simili", [i, j]), ("due a caso", [100, 700])]:
        g = gram(coppia)
        print(f"   {nome:16} {etichette[coppia[0]]} / {etichette[coppia[1]]}:"
              f" coseno {g[0, 1]:.4f}, area (det) {np.linalg.det(g):.4f}")
    u, d = righe_norm[riga_di["unto"]].toarray(), righe_norm[riga_di["dunto"]].toarray()
    gu = np.vstack([u, d]) @ np.vstack([u, d]).T
    print(f"   le righe di unto e dunto: area {np.linalg.det(gu):.1e}")

    qr = np.zeros(n_t)
    qr[riga_di["regina"]] = 1.0
    coseni = colonne @ qr
    ordine = np.argsort(-coseni, kind="stable")
    caso = rng.choice(np.where(lunghezze > 0)[0], 10, replace=False).tolist()
    print(f"   volume dei primi 10 di 'regina': {np.linalg.det(gram(ordine[:10].tolist())):.3f}"
          f"   di 10 paragrafi a caso: {np.linalg.det(gram(caso)):.3f}")
    for k in (30, 100, 160):
        segno, logdet = np.linalg.slogdet(gram(ordine[:k].tolist()))
        print(f"   volume dei primi {k:3}: 10^{logdet / np.log(10):.1f}")

    # --- 6. float32 contro float64 ----------------------------------------
    print("\n6. float32 contro float64 sul ranking")
    c64 = colonne
    c32 = colonne.astype(np.float32)
    cambiate, scarto = 0, 0.0
    for _ in range(500):
        qq = np.zeros(n_t)
        qq[rng.choice(candidate, 2, replace=False)] = 1.0
        s64 = c64 @ qq
        s32 = (c32 @ qq.astype(np.float32)).astype(np.float64)
        cambiate += list(np.argsort(-s64, kind="stable")[:10]) != list(np.argsort(-s32, kind="stable")[:10])
        scarto = max(scarto, float(np.abs(s64 - s32).max()))
    print(f"   500 query a caso: classifiche dei primi 10 cambiate {cambiate}, scarto massimo {scarto:.1e}")
    print(f"   memoria della matrice piena: float64 {denso64 / 2**20:.1f} MB, float32 {denso64 / 2**21:.1f} MB")


if __name__ == "__main__":
    main()
