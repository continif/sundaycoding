"""
S05E05 paid — `simili`: i paragrafi vicini, da un paragrafo o da una frase.

I vettori sono quelli LSA di vettori.py (100 direzioni dalla SVD della matrice
TF-IDF), salvati in una collection Chroma su disco con i metadati del
paragrafo. La prima volta la collection si costruisce, poi si riapre.

Uso:
    python simili.py II.89
    python simili.py VI.89 --capitolo VI
    python simili.py --testo "parole con due significati"
    python simili.py II.89 --tipo dialogo -k 5
    python simili.py II.89 --forza-bruta          # stesso risultato, senza Chroma

Le cartelle si passano con --indice, --vocabolario e --vettori (di default
accanto alla cartella e05). I vettori contengono il testo del libro: la
cartella vettori/ è nel .gitignore, come indice/.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

import chromadb
import numpy as np

RADICE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RADICE / "e03"), str(RADICE / "e04"), str(RADICE / "e05")]
from indice import Indice                 # noqa: E402
from registro import Registro             # noqa: E402
from vettori import Vettori, vicini       # noqa: E402
from vocabolario import Vocabolario       # noqa: E402

NOME = "specchio_lsa100"


def costruisci(collection, vettori: Vettori, corpus: Path) -> None:
    with corpus.open(encoding="utf-8") as f:
        paragrafi = [json.loads(r) for r in f]
    r = vettori.r
    ok = np.linalg.norm(vettori.lsa, axis=1) > 0
    # I due paragrafi con il vettore tutto zero (solo parole vuote) restano
    # fuori: col coseno la distanza da zero non è definita.
    idx = [i for i in range(vettori.n) if ok[i]]
    collection.add(
        ids=[r.etichette[i] for i in idx],          # "II.89": l'id è il riferimento del libro
        embeddings=vettori.lsa[idx],
        documents=[r.testi[i] for i in idx],
        # I metadati sono quelli su cui si filtra con where. Solo tipi
        # semplici: stringhe, numeri, booleani (niente liste annidate).
        metadatas=[{"capitolo": paragrafi[i]["romano"], "numero": paragrafi[i]["capitolo"],
                    "posizione": paragrafi[i]["posizione"], "tipo": paragrafi[i]["tipo"],
                    "parole": paragrafi[i]["parole"]} for i in idx],
    )


def apri(cartella: Path, vettori: Vettori | None = None, corpus: Path | None = None):
    client = chromadb.PersistentClient(path=str(cartella))
    if NOME in [c.name for c in client.list_collections()]:
        return client.get_collection(NOME)
    col = client.create_collection(
        NOME,
        # Il coseno, deciso adesso e per sempre (non si cambia dopo).
        # max_neighbors ed ef_construction restano ai default (16 e 100):
        # su 1.095 vettori la recall è già 1 con ef_search=100, vedi bench.
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,
    )
    costruisci(col, vettori, corpus)
    return col


def main() -> None:
    p = argparse.ArgumentParser(description="I paragrafi più simili.")
    p.add_argument("paragrafo", nargs="?", help="un riferimento come II.89")
    p.add_argument("--testo", help="una frase invece di un paragrafo")
    p.add_argument("--capitolo", help="solo in questo capitolo (I, II, ... XII)")
    p.add_argument("--tipo", choices=["dialogo", "prosa", "poesia"])
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--forza-bruta", action="store_true", help="NumPy invece di Chroma")
    p.add_argument("--indice", type=Path, default=RADICE / "indice")
    p.add_argument("--vocabolario", type=Path, default=RADICE / "vocabolario")
    p.add_argument("--vettori", type=Path, default=RADICE / "vettori")
    p.add_argument("--corpus", type=Path, default=RADICE / "corpus" / "specchio.jsonl")
    a = p.parse_args()
    if not (a.paragrafo or a.testo):
        p.error("serve un paragrafo o --testo")

    reg = Registro(a.indice)
    vet = Vettori(reg)
    etichetta_a_numero = {e: n for n, e in reg.etichette.items()}

    if a.testo:
        idx = Indice(a.indice, Vocabolario(a.vocabolario))
        # Stessa dogana del libro (E03), stesse varianti (E04), poi la
        # proiezione sulle 100 direzioni.
        gruppi = [sorted(idx.varianti(t)) for t, _ in idx.termini(a.testo)]
        q = vet.query_lsa(gruppi)
        stesso = None
    else:
        stesso = etichetta_a_numero[a.paragrafo]
        q = vet.lsa[stesso]
        print(f"{a.paragrafo:>8}  {textwrap.shorten(' '.join(reg.testi[stesso].split()), 98)}\n")

    if a.forza_bruta:
        # Il prodotto matrice × vettore di E04, su tutti i paragrafi; i filtri
        # non ci sono: per quelli Chroma serve davvero.
        candidati = vicini(vet.lsa, q[None, :], a.k + 1)[0]
        for n in [c for c in candidati if c != stesso][: a.k]:
            print(f"{reg.etichette[n]:>8}  {1 - float(vet.lsa[n] @ q):.3f}  "
                  f"{textwrap.shorten(' '.join(reg.testi[n].split()), 88)}")
        return

    col = apri(a.vettori, vet, a.corpus)
    filtri = [{"capitolo": a.capitolo}] if a.capitolo else []
    filtri += [{"tipo": a.tipo}] if a.tipo else []
    # $and vuole almeno due condizioni: con una sola si passa quella.
    where = None if not filtri else (filtri[0] if len(filtri) == 1 else {"$and": filtri})
    # Il paragrafo stesso è il primo vicino di sé (distanza 0): se ne chiede
    # uno in più e lo si scarta. Con un filtro che lo esclude già, non c'è.
    r = col.query(query_embeddings=[q], n_results=a.k + (1 if stesso is not None else 0),
                  where=where, include=["documents", "distances"])
    righe = [(i, d, t) for i, d, t in zip(r["ids"][0], r["distances"][0], r["documents"][0])
             if i != a.paragrafo][: a.k]
    if not righe:
        print("nessun paragrafo")
    for i, d, t in righe:
        print(f"{i:>8}  {d:.3f}  {textwrap.shorten(' '.join(t.split()), 88)}")


if __name__ == "__main__":
    main()
