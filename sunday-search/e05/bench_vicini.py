"""
S05E05 paid — Le misure della puntata.

Uso:
    python bench_vicini.py ../indice/ ../vocabolario/            # il libro
    python bench_vicini.py ../indice/ ../vocabolario/ --scala    # + vettori sintetici fino a 100.000 (qualche minuto)
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import chromadb
import numpy as np

RADICE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RADICE / "e03"), str(RADICE / "e04"), str(RADICE / "e05")]
from hnsw import HNSW                                          # noqa: E402
from indice import Indice                                      # noqa: E402
from registro import Registro                                  # noqa: E402
from vettori import Vettori, migliori_k, normalizza, vicini    # noqa: E402
from vocabolario import Vocabolario                            # noqa: E402


def ms(f, ripetizioni: int = 20) -> float:
    t = []
    for _ in range(ripetizioni):
        t0 = time.perf_counter()
        f()
        t.append(time.perf_counter() - t0)
    return statistics.median(t) * 1000


def recall(trovati, veri) -> float:
    return float(np.mean([len(set(a) & set(b)) / len(b) for a, b in zip(trovati, veri)]))


def collection(client, nome, x, **hnsw):
    col = client.create_collection(nome, configuration={"hnsw": {"space": "cosine", **hnsw}},
                                   embedding_function=None)
    for a in range(0, len(x), 5000):          # add a blocchi: un limite di Chroma per chiamata
        col.add(ids=[str(i) for i in range(a, min(a + 5000, len(x)))], embeddings=x[a:a + 5000])
    return col


def chroma_vicini(col, q, k=10):
    r = col.query(query_embeddings=q, n_results=k, include=[])
    return [list(map(int, ids)) for ids in r["ids"]]


def libro(cartella_indice: Path, cartella_voc: Path) -> None:
    # --- 1. I vettori --------------------------------------------------
    t0 = time.perf_counter()
    r = Registro(cartella_indice)
    t1 = time.perf_counter()
    v = Vettori(r)
    t2 = time.perf_counter()
    energia = (v.s ** 2).sum() / r.tfidf.multiply(r.tfidf).sum()
    print(f"1. Registro {t1 - t0:.2f} s, SVD a 100 direzioni {t2 - t1:.2f} s ({energia:.1%} dell'energia)")
    print(f"   LSA   {v.lsa.shape}  {v.lsa.nbytes / 1024:.0f} KB")
    print(f"   TF-IDF densa {v.tfidf.shape}  {v.tfidf.nbytes / 2**20:.1f} MB"
          f"  (sparsa: {r.coseno.data.nbytes + r.coseno.indices.nbytes + r.coseno.indptr.nbytes:,} byte)")

    # --- 2. Forza bruta: tutti contro tutti è UNA moltiplicazione ---------
    print("\n2. Forza bruta, i 10 vicini di tutti i 1.097 paragrafi")
    for nome, x in (("LSA", v.lsa), ("TF-IDF densa", v.tfidf)):
        print(f"   {nome:13} {ms(lambda: vicini(x, x, 10, True), 5):6.1f} ms")
    sparsa = r.coseno.T.tocsr()
    print(f"   {'TF-IDF sparsa':13} {ms(lambda: migliori_k((sparsa @ sparsa.T).toarray(), 10), 5):6.1f} ms")
    s = v.lsa @ v.lsa.T
    print(f"   solo il top-10: argpartition {ms(lambda: migliori_k(s, 10)):.1f} ms,"
          f" argsort completo {ms(lambda: np.argsort(-s, axis=1)[:, :10]):.1f} ms")
    print(f"   una query sola: {ms(lambda: vicini(v.lsa, v.lsa[:1], 10), 200) * 1000:.0f} µs")

    # --- 3. Coseno, L2, prodotto scalare -------------------------------
    print("\n3. Le tre distanze danno lo stesso ordine? (top-10 di tutti i paragrafi)")
    # Senza i due vettori a zero: in L2 un vettore nullo dista 1 da tutti i
    # vettori di lunghezza 1, e quindi è "più vicino" di ogni paragrafo con
    # coseno sotto 0,5. Col coseno invece è fuori gara (0/0).
    ok = np.linalg.norm(v.lsa, axis=1) > 0
    grezzi = (v.u.T @ r.tfidf.toarray()).T[ok]                     # le coordinate prima di normalizzare
    for nome, x in (("normalizzati", v.lsa[ok].astype(np.float64)), ("non normalizzati", grezzi)):
        cos = normalizza(x) @ normalizza(x).T
        ip = x @ x.T
        n2 = (x ** 2).sum(1)
        l2 = n2[:, None] + n2[None, :] - 2 * ip                    # ||a-b||² senza cicli
        for m in (cos, ip):
            np.fill_diagonal(m, -np.inf)
        np.fill_diagonal(l2, np.inf)
        a, b, c = migliori_k(cos, 10), migliori_k(ip, 10), migliori_k(-l2, 10)
        diversi_ip = sum(set(i) != set(j) for i, j in zip(a, b))
        diversi_l2 = sum(set(i) != set(j) for i, j in zip(a, c))
        print(f"   {nome:17} liste diverse dal coseno: prodotto scalare {diversi_ip:4}, L2 {diversi_l2:4}  su {len(x):,}")
    # Che numeri restituisce Chroma: la distanza, non la somiglianza.
    cl = chromadb.EphemeralClient()
    a, b = v.lsa[0].tolist(), v.lsa[1].tolist()
    cosab = float(v.lsa[0] @ v.lsa[1])
    for space in ("cosine", "l2", "ip"):
        col = cl.create_collection(f"due_{space}", configuration={"hnsw": {"space": space}}, embedding_function=None)
        col.add(ids=["a"], embeddings=[a])
        d = col.query(query_embeddings=[b], n_results=1)["distances"][0][0]
        print(f"   Chroma space={space:6}: distanza {d:.4f}", end="")
        print({"cosine": f"   = 1 - coseno ({1 - cosab:.4f})",
               "l2": f"   = ||a-b||² ({float(((v.lsa[0] - v.lsa[1]) ** 2).sum()):.4f}), al quadrato",
               "ip": f"   = 1 - a·b ({1 - cosab:.4f})"}[space])

    # --- 4. LSA contro TF-IDF sulle query con risposta nota ----------------
    print("\n4. Dove finisce il paragrafo atteso (posizione su 1.097)")
    idx = Indice(cartella_indice, Vocabolario(cartella_voc))
    numero = {e: n for n, e in r.etichette.items()}
    attese = [("la marmellata ieri e domani ma mai oggi", "V.22"),
              ("per quanto si corra si rimane sempre allo stesso punto", "II.89"),
              ("parole con due significati", "VI.89"),
              ("l'uovo seduto sul muro", "VI.2"),
              ("la regina che corre", "II.89"),
              ("la regina che corre senza muoversi", "II.89")]
    print(f"   {'':62} BM25  TF-IDF  LSA")
    for testo, atteso in attese:
        gruppi = [sorted(idx.varianti(t)) for t, _ in idx.termini(testo)]
        pos = []
        for punteggi in (r.punteggi_gruppi(gruppi),
                         v.tfidf @ normalizza(v.query_tfidf(gruppi)[None, :])[0],
                         v.lsa @ v.query_lsa(gruppi)):
            pos.append(int(np.where(np.argsort(-punteggi, kind="stable") == numero[atteso])[0][0]) + 1)
        print(f"   {testo + ' → ' + atteso:62} {pos[0]:4} {pos[1]:7} {pos[2]:4}")

    # --- 5. Vicini senza parole in comune -----------------------------------
    nn = vicini(v.lsa, v.lsa, 5, True)
    comuni = np.take_along_axis(v.tfidf @ v.tfidf.T, nn, 1)
    zero = comuni <= 1e-6
    print(f"\n5. Nei 5 vicini LSA di ogni paragrafo, {zero.sum()} su {zero.size} non hanno"
          f" nessuna parola in comune ({zero.any(1).sum()} paragrafi ne hanno almeno uno)")
    for e in ("II.89", "VI.89"):
        i = numero[e]
        print(f"   {e}: " + ", ".join(f"{r.etichette[j]} (lsa {v.lsa[i] @ v.lsa[j]:.2f}, tfidf {v.tfidf[i] @ v.tfidf[j]:.2f})"
                                    for j in nn[i]))

    # --- 6. HNSW in miniatura ---------------------------------------------
    print("\n6. HNSW in miniatura sul libro: recall@10 e distanze calcolate per query")
    ok = np.where(np.linalg.norm(v.lsa, axis=1) > 0)[0]
    x = v.lsa.astype(np.float64)
    veri = vicini(v.lsa, v.lsa, 10, True)
    for m in (4, 16):
        t0 = time.perf_counter()
        h = HNSW(max_neighbors=m, ef_construction=100).costruisci(x)
        print(f"   max_neighbors={m:2}: costruito in {time.perf_counter() - t0:.2f} s,"
              f" nodi per piano {[len(p) for p in h.piani]}")
        for ef in (10, 20, 50, 100):
            h.distanze = 0
            trovati = [[j for j in h.cerca(x[i], 11, ef) if j != i][:10] for i in ok]
            print(f"      ef_search={ef:3}  recall {recall(trovati, veri[ok]):.3f}"
                  f"   distanze {h.distanze / len(ok):5.0f} (la forza bruta: {len(x)})")

    # --- 7. Chroma sul libro -------------------------------------------------
    print("\n7. Chroma sul libro (HNSW vero, hnswlib)")
    cl = chromadb.EphemeralClient()
    t0 = time.perf_counter()
    col = collection(cl, "libro", v.lsa[ok])
    print(f"   add di {len(ok)} vettori: {(time.perf_counter() - t0) * 1000:.0f} ms")
    trovati = [[int(ok[j]) for j in t if ok[j] != i][:10] for i, t in zip(ok, chroma_vicini(col, v.lsa[ok], 11))]
    print(f"   recall@10 con i default: {recall(trovati, veri[ok]):.3f}")
    print(f"   una query: Chroma {ms(lambda: col.query(query_embeddings=v.lsa[:1], n_results=10, include=[]), 200) * 1000:.0f} µs,"
          f" NumPy {ms(lambda: vicini(v.lsa, v.lsa[:1], 10), 200) * 1000:.0f} µs")


def sintetici(rng, n: int, struttura: bool, a: np.ndarray) -> np.ndarray:
    """Vettori di 100 numeri, normalizzati.
    a caso: ogni numero indipendente. È il caso peggiore: in 100 dimensioni
      punti a caso sono quasi tutti alla stessa distanza da tutti, e "il più
      vicino" è vicino per poco. Nessun dato vero è fatto così.
    con struttura: 10 numeri a caso mescolati in 100 dalla stessa matrice `a`,
      più un po' di rumore. I punti stanno su una "superficie" di poche
      dimensioni, come i vettori veri di testi e immagini."""
    if not struttura:
        return normalizza(rng.standard_normal((n, 100))).astype(np.float32)
    return normalizza(rng.standard_normal((n, 10)) @ a + 0.3 * rng.standard_normal((n, 100))).astype(np.float32)


def scala() -> None:
    print("\n8. Vettori sintetici da 100 numeri: forza bruta in NumPy contro HNSW in Chroma")
    for struttura in (False, True):
        rng = np.random.default_rng(1)
        a = rng.standard_normal((10, 100))
        q = sintetici(rng, 200, struttura, a)
        print(f"\n   {'CON STRUTTURA' if struttura else 'A CASO'}")
        for n in (10_000, 100_000):
            x = sintetici(rng, n, struttura, a)
            veri = vicini(x, q, 10)
            print(f"   N={n:,}  ({x.nbytes / 2**20:.0f} MB)")
            print(f"      NumPy: {ms(lambda: vicini(x, q[:1], 10), 50):.2f} ms a query,"
                  f" {ms(lambda: vicini(x, q, 10), 5) / len(q):.3f} ms a query in blocco da 200")
            cl = chromadb.EphemeralClient()
            for m in (4, 16, 32) if (struttura and n == 100_000) else (16,):
                for ef in (10, 50, 100, 200):
                    # Una collection per ogni ef_search: modify() non vale nel
                    # processo che ha già l'indice in memoria (vedi sezione 9).
                    t0 = time.perf_counter()
                    col = collection(cl, f"s{n}m{m}e{ef}", x, max_neighbors=m, ef_search=ef)
                    costruzione = time.perf_counter() - t0
                    tq = ms(lambda: col.query(query_embeddings=q[:1], n_results=10, include=[]), 50)
                    print(f"      Chroma max_neighbors={m:2} ef_search={ef:3}: recall {recall(chroma_vicini(col, q), veri):.3f},"
                          f" {tq:.2f} ms a query, costruzione {costruzione:.1f} s")
                    cl.delete_collection(col.name)


def trappola_modify() -> None:
    """modify() salva la configurazione, ma nel processo che ha già l'indice
    caricato la ricerca continua con i vecchi valori. Si vede riaprendo la
    cartella da un processo nuovo."""
    print("\n9. modify(ef_search) e modify(max_neighbors): cosa succede davvero")
    cartella = Path(tempfile.mkdtemp())
    codice = f"""
import sys, numpy as np, chromadb
sys.path[:0] = [{str(RADICE / 'e05')!r}]
from vettori import normalizza, vicini
rng = np.random.default_rng(1)
x = normalizza(rng.standard_normal((20000, 100))).astype(np.float32)
q = normalizza(rng.standard_normal((200, 100))).astype(np.float32)
veri = vicini(x, q, 10)
def rec(col):
    r = col.query(query_embeddings=q, n_results=10, include=[])
    return np.mean([len(set(map(int, i)) & set(v)) / 10 for i, v in zip(r["ids"], veri)])
cl = chromadb.PersistentClient({str(cartella)!r})
if sys.argv[1] == "crea":
    col = cl.create_collection("prova", configuration={{"hnsw": {{"space": "cosine", "ef_search": 10, "max_neighbors": 4}}}}, embedding_function=None)
    for a in range(0, 20000, 5000):
        col.add(ids=[str(i) for i in range(a, a + 5000)], embeddings=x[a:a + 5000])
    print(f"   creata con ef_search=10, max_neighbors=4: recall {{rec(col):.3f}}")
    col.modify(configuration={{"hnsw": {{"ef_search": 200}}}})
    print(f"   modify(ef_search=200), stesso processo: recall {{rec(cl.get_collection('prova')):.3f}}")
else:
    col = cl.get_collection("prova")
    print(f"   processo nuovo, ef_search={{col.configuration['hnsw']['ef_search']}}: recall {{rec(col):.3f}}")
    col.modify(configuration={{"hnsw": {{"max_neighbors": 32}}}})
    print(f"   modify(max_neighbors=32): la configurazione dice {{cl.get_collection('prova').configuration['hnsw']['max_neighbors']}}")
"""
    for fase in ("crea", "riapri", "riapri"):
        print(subprocess.run([sys.executable, "-c", codice, fase], capture_output=True, text=True).stdout, end="")
    shutil.rmtree(cartella)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("indice", type=Path)
    p.add_argument("vocabolario", type=Path)
    p.add_argument("--scala", action="store_true")
    a = p.parse_args()
    libro(a.indice, a.vocabolario)
    trappola_modify()
    if a.scala:
        scala()
