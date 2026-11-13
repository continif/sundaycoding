"""
S05E06 paid — L'ultimo gradino, facoltativo: un modello di embedding vero.

ATTENZIONE: questo file NON è stato eseguito per scrivere la puntata. Il
modello si scarica da Hugging Face e l'ambiente in cui ho scritto il codice
non ci arriva. Quindi niente numeri: nessuna riga di quella tabella lo
include, e le righe che seguono sono il codice che metterei io, non un
risultato. Misuratelo voi con `valuta.py`, aggiungendo "modello" ai rankers.

Cosa fa: calcola un vettore per ogni paragrafo con un modello multilingue
(una volta, poi su disco) e lo offre al motore come quinto ranker, fuso con
gli altri dall'RRF di ricerca.py.

    pip install sentence-transformers
    python modello_vero.py ../corpus/specchio.jsonl ../vettori/modello.npy
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# Un modello multilingue piccolo (384 dimensioni, include l'italiano). Il
# nome si cambia con quello che preferite: la riga sotto è l'UNICO punto
# in cui il modello è scritto.
MODELLO = "paraphrase-multilingual-MiniLM-L12-v2"


def calcola(corpus: Path, destinazione: Path, nome: str = MODELLO) -> np.ndarray:
    from sentence_transformers import SentenceTransformer     # import qui: chi non lo usa non lo paga
    testi = [json.loads(r)["testo"] for r in corpus.open(encoding="utf-8")]
    modello = SentenceTransformer(nome)
    # normalize_embeddings: vettori di lunghezza 1, così il coseno è un
    # prodotto scalare (E05). Il modello taglia i testi lunghi: i paragrafi
    # più lunghi del libro (518 parole) ne perdono la coda, ed è un motivo
    # in più per guardare i chunk della puntata gratuita.
    v = modello.encode(testi, batch_size=32, normalize_embeddings=True, show_progress_bar=True)
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    np.save(destinazione, v.astype(np.float32))
    return v


def classifica(vettori: np.ndarray, query: str, nome: str = MODELLO, k: int = 100) -> list[int]:
    """Da usare come un ranker qualsiasi: restituisce i numeri di paragrafo
    in ordine. Il modello si carica a ogni chiamata se non lo tenete in
    memoria: in una shell, create il SentenceTransformer una volta sola."""
    from sentence_transformers import SentenceTransformer
    q = SentenceTransformer(nome).encode([query], normalize_embeddings=True)[0]
    s = vettori @ q
    return [int(p) for p in np.argsort(-s)[:k]]


if __name__ == "__main__":
    calcola(Path(sys.argv[1]), Path(sys.argv[2]))
