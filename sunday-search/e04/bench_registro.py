"""
S05E04 paid — Le misure della puntata.

Uso:
    python bench_registro.py ../indice/ ../vocabolario/
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "e03"))
from indice import Indice          # noqa: E402
from vocabolario import Vocabolario  # noqa: E402

from registro import Registro


def us(f, *args, ripetizioni: int = 200) -> float:
    t = []
    for _ in range(ripetizioni):
        t0 = time.perf_counter()
        f(*args)
        t.append(time.perf_counter() - t0)
    return statistics.median(t) * 1e6


def byte_csr(m) -> int:
    return m.data.nbytes + m.indices.nbytes + m.indptr.nbytes


def main() -> None:
    cartella_indice, cartella_voc = Path(sys.argv[1]), Path(sys.argv[2])

    # --- 1. Costruzione ----------------------------------------------------
    t0 = time.perf_counter()
    r = Registro(cartella_indice)
    print(f"1. Registro costruito dal Parquet in {time.perf_counter() - t0:.2f} s:"
          f" {r.tf.shape[0]:,} × {r.tf.shape[1]:,}, {r.tf.nnz:,} caselle piene")
    print(f"   CSR in float64: {byte_csr(r.bm25) / 1024:.0f} KB"
          f" (dati {r.bm25.data.nbytes / 1024:.0f}, colonne {r.bm25.indices.nbytes / 1024:.0f},"
          f" inizio righe {r.bm25.indptr.nbytes / 1024:.0f})")

    # --- 2. Righe e colonne in una matrice piena ---------------------------
    print("\n2. La stessa matrice piena, per righe (C) e per colonne (F)")
    piena_c = r.bm25.toarray()                     # row-major: una riga è contigua
    piena_f = np.asfortranarray(piena_c)            # column-major: una colonna è contigua
    print(f"   strides C {piena_c.strides}, F {piena_f.strides}  (byte per scendere di una riga, per spostarsi di una colonna)")
    righe = np.random.default_rng(1).choice(piena_c.shape[0], 200, replace=False)
    colonne = np.random.default_rng(2).choice(piena_c.shape[1], 200, replace=False)
    for nome, a in (("C", piena_c), ("F", piena_f)):
        print(f"   {nome}: somma di una riga {us(lambda: [a[i].sum() for i in righe], ripetizioni=20) / 200:6.2f} µs,"
              f"  di una colonna {us(lambda: [a[:, j].sum() for j in colonne], ripetizioni=20) / 200:6.2f} µs")

    # --- 3. CSR contro CSC -------------------------------------------------
    print("\n3. CSR contro CSC: una parola → i suoi paragrafi, un paragrafo → le sue parole")
    csr = r.bm25
    t0 = time.perf_counter()
    csc = csr.tocsc()
    print(f"   conversione CSR → CSC: {(time.perf_counter() - t0) * 1000:.2f} ms")
    for nome, m in (("CSR", csr), ("CSC", csc)):
        print(f"   {nome}: una riga {us(lambda: [m[i] for i in righe[:50]], ripetizioni=20) / 50:7.1f} µs,"
              f"  una colonna {us(lambda: [m[:, j] for j in colonne[:50]], ripetizioni=20) / 50:7.1f} µs")

    # --- 4. BM25 a mano contro matrice -------------------------------------
    print("\n4. BM25: ciclo sulle liste contro matrice × vettore (stesso risultato)")
    liste = r.liste()
    query = [["regina"], ["regina", "rossa"], ["alice"], ["marmellata", "ieri", "domani", "mai", "oggi"]]
    for q in query:
        a = r.bm25_a_mano(liste, q)
        s = r.punteggi(q)
        assert len(a) == np.count_nonzero(s) and all(abs(s[p] - v) < 1e-9 for p, v in a.items())
        piena = lambda: piena_c.T @ np.isin(np.arange(len(r.forme)), [r.riga[t] for t in q]).astype(float)
        print(f"   {' '.join(q):38} a mano {us(r.bm25_a_mano, liste, q):7.0f} µs"
              f"   CSR {us(r.punteggi, q):5.0f} µs   matrice piena {us(piena, ripetizioni=20):7.0f} µs")
    r32 = Registro(cartella_indice, dtype=np.float32)
    print(f"   float32: CSR {byte_csr(r32.bm25) / 1024:.0f} KB invece di {byte_csr(r.bm25) / 1024:.0f},"
          f" una query {us(r32.punteggi, ['regina', 'rossa']):.0f} µs")

    # --- 5. Il ranking contro le risposte attese ---------------------------
    print("\n5. Dove finisce il paragrafo atteso (posizione nei primi 10)")
    idx = Indice(cartella_indice, Vocabolario(cartella_voc))
    attese = [("la marmellata ieri e domani ma mai oggi", "V.22"),
              ("per quanto si corra si rimane sempre allo stesso punto", "II.89"),
              ("parole con due significati", "VI.89"),
              ("l'uovo seduto sul muro", "VI.2"),
              ("la regina che corre", "II.89")]
    print(f"   {'':58} conteggi  tfidf  coseno  bm25  bm25+varianti")
    for q, atteso in attese:
        t = [x for x, _ in idx.termini(q)]
        posizioni = []
        for schema in ("conteggi", "tfidf", "coseno", "bm25"):
            lab = [r.etichette[p] for p in r.migliori(r.punteggi(t, schema), 10)]
            posizioni.append(str(lab.index(atteso) + 1) if atteso in lab else "-")
        gruppi = [sorted(idx.varianti(x)) for x in t]
        lab = [r.etichette[p] for p in r.migliori(r.punteggi_gruppi(gruppi), 10)]
        posizioni.append(str(lab.index(atteso) + 1) if atteso in lab else "-")
        print(f"   {q + ' → ' + atteso:58} {posizioni[0]:>8} {posizioni[1]:>6} {posizioni[2]:>7}"
              f" {posizioni[3]:>5} {posizioni[4]:>14}")

    # L'errore delle varianti pesate una per una.
    v = sorted(idx.varianti("regina"))
    separate = r.migliori(r.punteggi(v), 10)
    insieme = r.migliori(r.punteggi_gruppi([v]), 10)
    plurali = lambda ps: sum(1 for p in ps if r.tf[r.riga["regine"], p] > 0)
    print(f"\n   'regina' con le varianti {v}: primi 10 con 'regine' al plurale:"
          f" forme pesate una per una {plurali(separate)}, come un gruppo solo {plurali(insieme)}"
          f"  (idf regina {r.idf_bm25[r.riga['regina']]:.2f}, regine {r.idf_bm25[r.riga['regine']]:.2f})")

    # --- 6. Risultati vari -------------------------------------------------
    print("\n6. I primi 10: BM25 puro, greedy col determinante, MMR")
    for q in (["regina"], ["regina", "rossa"], ["alice"], ["re", "bianco"]):
        s = r.punteggi(q)
        base = r.migliori(s, 10)
        for nome, scelti in (("BM25", base), ("determinante", r.vari_det(s)), ("MMR", r.vari_mmr(s))):
            nuovi = len(set(scelti) - set(base))
            print(f"   {' '.join(q):12} {nome:13} volume {r.volume(scelti):.3f}"
                  f"   pertinenza {s[scelti].sum() / s[base].sum():.1%}   cambiati {nuovi}")
        print(f"   {'':12} tempi: determinante {us(r.vari_det, s, ripetizioni=5) / 1000:.1f} ms,"
              f" MMR {us(r.vari_mmr, s, ripetizioni=5) / 1000:.1f} ms")


if __name__ == "__main__":
    main()
