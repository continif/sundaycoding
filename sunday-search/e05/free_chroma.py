"""
S05E05 free — ChromaDB in dieci minuti (e cosa fare nell'undicesimo).

Il magazzino dove gli scaffali stanno per somiglianza: ogni articolo ha un
vettore a tre numeri (quanto è dolce, quanto è salato, quanto è croccante),
scritto a mano. Niente modello di embedding, così si vede che Chroma non ha
bisogno di "capire" niente: gli bastano i numeri. Il modello serve solo a
trasformare il testo in numeri, e quello lo vediamo in fondo.

Uso:
    python free_chroma.py
"""

from __future__ import annotations

import shutil
import tempfile
import warnings
from pathlib import Path

import chromadb

#                         dolce salato croccante
ARTICOLI = {
    "biscotti al burro":   ([0.8, 0.1, 0.7], {"reparto": "colazione", "prezzo": 2.10}),
    "fette biscottate":    ([0.3, 0.1, 0.9], {"reparto": "colazione", "prezzo": 1.60}),
    "cioccolato fondente": ([0.7, 0.0, 0.3], {"reparto": "dolci", "prezzo": 2.90}),
    "torrone":             ([0.9, 0.0, 0.8], {"reparto": "dolci", "prezzo": 6.50}),
    "marmellata":          ([1.0, 0.0, 0.0], {"reparto": "colazione", "prezzo": 3.20}),
    "patatine":            ([0.0, 0.9, 0.9], {"reparto": "aperitivo", "prezzo": 1.90}),
    "taralli":             ([0.0, 0.6, 0.8], {"reparto": "aperitivo", "prezzo": 2.40}),
    "olive":               ([0.0, 0.9, 0.1], {"reparto": "aperitivo", "prezzo": 3.80}),
    "cracker":             ([0.1, 0.5, 0.9], {"reparto": "aperitivo", "prezzo": 1.50}),
    "acciughe":            ([0.0, 1.0, 0.0], {"reparto": "conserve", "prezzo": 4.10}),
}


def stampa(titolo: str, risultato: dict) -> None:
    print(f"\n{titolo}")
    # query() restituisce liste di liste: una lista per ogni query mandata.
    for i, d in zip(risultato["ids"][0], risultato["distances"][0]):
        print(f"   {d:.3f}  {i}")


def main() -> None:
    # --- 1. Il client --------------------------------------------------
    # EphemeralClient: tutto in memoria, sparisce a fine programma. Per i test.
    # PersistentClient: su disco, in una cartella. Per un progetto.
    # HttpClient: un server Chroma a parte (`chroma run`), per più processi.
    cartella = Path(tempfile.mkdtemp())
    client = chromadb.PersistentClient(path=str(cartella))

    # --- 2. La collection: la distanza si sceglie QUI e mai più --------
    try:
        client.create_collection("ab")
    except Exception as e:                       # nomi da 3 a 512 caratteri
        print(f"nome di due lettere: {type(e).__name__}")

    magazzino = client.create_collection(
        "magazzino",
        # Il default è l2 (la distanza al quadrato). Per il testo si usa il
        # coseno: conta la direzione del vettore, non la sua lunghezza.
        configuration={"hnsw": {"space": "cosine"}},
        # None: i vettori li diamo noi. Senza questa riga Chroma prepara il
        # suo modello di default e lo scarica alla prima add con documenti.
        embedding_function=None,
    )
    print("configurazione:", magazzino.configuration["hnsw"])

    # --- 3. add ----------------------------------------------------------
    nomi = list(ARTICOLI)
    magazzino.add(
        ids=nomi,                                    # obbligatori, stringhe, unici
        embeddings=[ARTICOLI[n][0] for n in nomi],
        metadatas=[ARTICOLI[n][1] for n in nomi],
        documents=nomi,                              # il testo, facoltativo
    )
    print("articoli:", magazzino.count())

    # Lo stesso id due volte: niente errore, la seconda add viene ignorata.
    magazzino.add(ids=["olive"], embeddings=[[1.0, 0.0, 0.0]], metadatas=[{"reparto": "dolci", "prezzo": 0.0}])
    print("olive dopo la seconda add:", magazzino.get(ids=["olive"], include=["metadatas"])["metadatas"][0])

    # --- 4. query: i vicini ----------------------------------------------
    voglio = [0.9, 0.0, 0.9]                         # dolce e croccante
    stampa("dolce e croccante:", magazzino.query(query_embeddings=[voglio], n_results=4))

    # where: prima si filtra sui metadati, poi si cercano i vicini tra chi resta.
    stampa("dolce e croccante, sotto i 3 euro:",
           magazzino.query(query_embeddings=[voglio], n_results=4, where={"prezzo": {"$lt": 3}}))
    stampa("salato, reparto aperitivo o conserve, sotto i 4 euro:",
           magazzino.query(query_embeddings=[[0.0, 1.0, 0.2]], n_results=3,
                           where={"$and": [{"reparto": {"$in": ["aperitivo", "conserve"]}},
                                           {"prezzo": {"$lt": 4}}]}))
    # where_document: un filtro sul testo, non sul significato.
    stampa("con 'bis' nel nome:",
           magazzino.query(query_embeddings=[voglio], n_results=3, where_document={"$contains": "bis"}))

    # --- 5. get: per id o per filtro, senza vicini ------------------------
    r = magazzino.get(where={"reparto": "dolci"}, include=["metadatas"])
    print("\nreparto dolci:", r["ids"])

    # --- 6. update, upsert, delete --------------------------------------
    magazzino.update(ids=["torrone"], metadatas=[{"reparto": "dolci", "prezzo": 4.90}])
    magazzino.upsert(ids=["grissini"], embeddings=[[0.0, 0.4, 1.0]],
                     metadatas=[{"reparto": "aperitivo", "prezzo": 1.20}], documents=["grissini"])
    magazzino.delete(where={"reparto": "conserve"})
    print("dopo update, upsert e delete:", magazzino.count(), "articoli")

    # --- 7. L'undicesimo minuto: le trappole -----------------------------
    print("\nLe trappole")
    # a) La sintassi vecchia della distanza (metadata={"hnsw:space": ...}),
    #    quella che trovate in mezzo web e che l'IA vi suggerirà.
    with warnings.catch_warnings(record=True) as avvisi:
        warnings.simplefilter("always")
        vecchia = client.create_collection("vecchia", metadata={"hnsw:space": "cosine"}, embedding_function=None)
    print(f"   sintassi vecchia: space={vecchia.configuration['hnsw']['space']}, avvisi: {len(avvisi)}")
    # b) Tutte e due insieme, in disaccordo: vince configuration, in silenzio,
    #    e i metadati continuano a dire un'altra cosa.
    doppia = client.create_collection("doppia", metadata={"hnsw:space": "ip"},
                                      configuration={"hnsw": {"space": "cosine"}}, embedding_function=None)
    print(f"   tutte e due: space={doppia.configuration['hnsw']['space']}, metadata={doppia.metadata}")
    # c) La distanza non si cambia dopo.
    try:
        magazzino.modify(configuration={"hnsw": {"space": "l2"}})
    except Exception as e:
        print(f"   cambiare space dopo: {type(e).__name__}")
    # d) max_neighbors invece si "cambia": la configurazione dice 32, il
    #    grafo resta quello costruito con 16. Vedi la paid.
    #    (L'oggetto in mano continua a dire 16: bisogna rileggere la collection.)
    magazzino.modify(configuration={"hnsw": {"max_neighbors": 32}})
    riletta = client.get_collection("magazzino")
    print(f"   max_neighbors dopo modify: {riletta.configuration['hnsw']['max_neighbors']} (ma il grafo non cambia)")

    # --- 8. Riaprire: la cartella è il database ----------------------------
    del client, magazzino
    riaperto = chromadb.PersistentClient(path=str(cartella)).get_collection("magazzino")
    print(f"\nriaperto: {riaperto.count()} articoli, space={riaperto.configuration['hnsw']['space']}")
    print("file su disco:", sorted(p.name for p in cartella.iterdir()))
    shutil.rmtree(cartella)


if __name__ == "__main__":
    main()
