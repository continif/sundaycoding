"""
S05E06 free — Come si taglia un testo prima di darlo ai vettori.

Finora l'unità di ricerca è stata il paragrafo, perché il libro ce l'ha già
tagliato. Ma un paragrafo di dialogo è lungo 19 parole (la mediana), e
"- Non saresti in nessuna parte" da solo non dice niente a nessuno: né a
BM25, né a un vettore. Il taglio è una decisione, e si può misurare.

Il trucco che regge tutto: UN TAGLIO È UNA MATRICE. Se A è la matrice
(paragrafi × chunk) con un 1 dove il paragrafo sta nel chunk, allora

    tf_chunk = tf @ A          i conteggi dei chunk, senza rileggere il testo
    vett_chunk = A^T @ vett    la media dei vettori, senza ricalcolare niente

Cambiare strategia di taglio significa cambiare A. Tutto il resto, indice
compreso, si ricalcola con due moltiplicazioni.

Uso:
    python chunking.py ../indice/ ../vocabolario/
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ricerca import Motore  # noqa: E402
from valutazione_util import carica_query, posizione  # noqa: E402

K1, B = 1.2, 0.75     # gli stessi di E04: cambiare il taglio, non la formula


# ----------------------------------------------------------------------
# Le strategie: ognuna restituisce la lista dei chunk, e ogni chunk è la
# lista dei numeri di paragrafo che contiene.
# ----------------------------------------------------------------------
def per_paragrafo(meta: dict[int, dict]) -> list[list[int]]:
    """Il punto di partenza: un chunk per paragrafo."""
    return [[p] for p in sorted(meta)]


def per_finestra(meta: dict[int, dict], n: int, passo: int) -> list[list[int]]:
    """Finestre di n paragrafi consecutivi, che avanzano di `passo`.
    Mai attraverso un capitolo: l'ultimo paragrafo di un capitolo e il primo
    del successivo non sono vicini, sono solo adiacenti nel file.
    Con passo < n le finestre si sovrappongono: lo stesso paragrafo compare
    in più chunk, e costa più spazio (n/passo volte)."""
    chunk: list[list[int]] = []
    per_cap: dict[int, list[int]] = {}
    for p in sorted(meta):
        per_cap.setdefault(meta[p]["capitolo"], []).append(p)
    for ps in per_cap.values():
        for i in range(0, len(ps), passo):
            chunk.append(ps[i:i + n])
            if i + n >= len(ps):        # l'ultima finestra ha già coperto la coda
                break
    return chunk


def per_parole(meta: dict[int, dict], minimo: int) -> list[list[int]]:
    """Si uniscono paragrafi consecutivi finché il chunk non arriva a
    `minimo` parole. Si taglia SEMPRE tra due paragrafi, mai dentro: un
    chunk che finisce a metà battuta è un chunk che mente. I paragrafi già
    lunghi restano da soli. Il capitolo chiude il chunk."""
    chunk: list[list[int]] = []
    corrente: list[int] = []
    parole = 0
    cap = None
    for p in sorted(meta):
        if corrente and (meta[p]["capitolo"] != cap or parole >= minimo):
            chunk.append(corrente)
            corrente, parole = [], 0
        corrente.append(p)
        parole += meta[p]["parole"]
        cap = meta[p]["capitolo"]
    if corrente:
        chunk.append(corrente)
    return chunk


def per_scena(meta: dict[int, dict], massimo: int = 250) -> list[list[int]]:
    """Come per_parole, ma il taglio segue il TIPO: la prosa chiude una
    scena e si apre un dialogo, il dialogo chiude quando torna la prosa.
    Un dialogo di venti battute resta unito (fino a `massimo` parole);
    la prosa che lo introduce si attacca a lui."""
    chunk: list[list[int]] = []
    corrente: list[int] = []
    parole, cap, tipo_prec = 0, None, None
    for p in sorted(meta):
        tipo = meta[p]["tipo"]
        # Si taglia quando: cambia il capitolo, o si esce da un dialogo
        # verso la prosa, o il chunk è già troppo lungo.
        chiude = corrente and (meta[p]["capitolo"] != cap
                               or (tipo_prec == "dialogo" and tipo != "dialogo")
                               or parole >= massimo)
        if chiude:
            chunk.append(corrente)
            corrente, parole = [], 0
        corrente.append(p)
        parole += meta[p]["parole"]
        cap, tipo_prec = meta[p]["capitolo"], tipo
    if corrente:
        chunk.append(corrente)
    return chunk


def matrice(chunk: list[list[int]], n_par: int) -> sparse.csr_matrix:
    """La matrice di assegnazione A (paragrafi × chunk)."""
    righe = [p for c in chunk for p in c]
    colonne = [j for j, c in enumerate(chunk) for _ in c]
    return sparse.csr_matrix((np.ones(len(righe)), (righe, colonne)), shape=(n_par, len(chunk)))


# ----------------------------------------------------------------------
# L'indice sui chunk, derivato dall'indice sui paragrafi
# ----------------------------------------------------------------------
class IndiceChunk:
    def __init__(self, m: Motore, chunk: list[list[int]]):
        self.m, self.chunk = m, chunk
        n_par = m.reg.n
        self.A = matrice(chunk, n_par)
        # tf_chunk = tf @ A: la somma delle colonne dei paragrafi del chunk.
        self.tf = (m.reg.tf @ self.A).tocsr()
        self.n = len(chunk)
        self.lunghezze = np.asarray(self.tf.sum(axis=0)).ravel()
        self.media = self.lunghezze.mean()
        # Il vettore del chunk: media dei vettori dei suoi paragrafi,
        # pesata per lunghezza (un paragrafo di 200 parole dice più di uno di 5).
        peso = sparse.diags(m.reg.lunghezze) @ self.A
        v = np.asarray(peso.T @ m.par.paragrafi)
        n = np.linalg.norm(v, axis=1, keepdims=True)
        self.vett = np.where(n > 0, v / np.where(n > 0, n, 1), 0.0).astype(np.float32)
        self.parole = np.array([sum(m.meta[p]["parole"] for p in c) for c in chunk])

    def bm25(self, gruppi: list[list[str]]) -> np.ndarray:
        """Lo stesso BM25 a gruppi di E04, sui conteggi del chunk."""
        r = self.m.reg
        tot = np.zeros(self.n)
        for forme in gruppi:
            righe = [r.riga[f] for f in forme if f in r.riga]
            if not righe:
                continue
            tf = np.asarray(self.tf[righe].sum(axis=0)).ravel()
            df = np.count_nonzero(tf)
            if df == 0:
                continue
            idf = np.log(1 + (self.n - df + 0.5) / (df + 0.5))
            den = tf + K1 * (1 - B + B * self.lunghezze / self.media)
            tot += np.where(tf > 0, idf * tf * (K1 + 1) / den, 0.0)
        return tot

    def embedding(self, gruppi: list[list[str]]) -> np.ndarray:
        return self.vett @ self.m.par.query(gruppi)

    def migliori(self, punteggi: np.ndarray, k: int = 5) -> list[int]:
        ordine = np.lexsort((np.arange(len(punteggi)), -punteggi))
        return [int(j) for j in ordine[:k] if punteggi[j] > 0]


def valuta(m: Motore, query: list[dict], chunk: list[list[int]]) -> dict[str, float]:
    ic = IndiceChunk(m, chunk)
    out: dict[str, list] = {"lessicale": [], "parole": []}
    letti: list[int] = []
    for q in query:
        attesi = {m.numero[a] for a in q["attesi"]}
        g = m.gruppi(q["testo"])
        for nome, punti in (("lessicale", ic.bm25(g)), ("parole", ic.embedding(g))):
            cl = ic.migliori(punti, 100)
            # La posizione del primo chunk che CONTIENE un paragrafo atteso.
            out[nome].append(posizione([j for j in cl], {j for j, c in enumerate(chunk) if attesi & set(c)}))
            if nome == "lessicale":
                # Quante parole deve leggere chi guarda i primi 5 risultati.
                letti.append(int(ic.parole[cl[:5]].sum()))
    ris: dict[str, float] = {"chunk": len(chunk), "parole_medie": float(ic.parole.mean()),
                             "parole_lette_top5": float(np.mean(letti))}
    for nome, pos in out.items():
        ris[f"hit5_{nome}"] = sum(1 for p in pos if p and p <= 5)
        ris[f"mrr_{nome}"] = float(np.mean([1 / p if p else 0.0 for p in pos]))
    return ris


def main() -> None:
    cartella_indice, cartella_voc = Path(sys.argv[1]), Path(sys.argv[2])
    m = Motore(cartella_indice, cartella_voc, cartella_indice.parent / "corpus" / "specchio.jsonl")
    query = carica_query()
    strategie = {
        "paragrafo":            per_paragrafo(m.meta),
        "finestra 2, passo 2":  per_finestra(m.meta, 2, 2),
        "finestra 3, passo 3":  per_finestra(m.meta, 3, 3),
        "finestra 3, passo 1":  per_finestra(m.meta, 3, 1),
        "finestra 5, passo 5":  per_finestra(m.meta, 5, 5),
        "almeno 60 parole":     per_parole(m.meta, 60),
        "almeno 120 parole":    per_parole(m.meta, 120),
        "per scena":            per_scena(m.meta),
    }
    print(f"{'strategia':22}{'chunk':>6}{'parole':>8}{'lette':>7}  {'lex hit@5':>9}{'MRR':>7}  {'par hit@5':>9}{'MRR':>7}")
    for nome, ch in strategie.items():
        r = valuta(m, query, ch)
        print(f"{nome:22}{r['chunk']:>6}{r['parole_medie']:>8.0f}{r['parole_lette_top5']:>7.0f}  "
              f"{r['hit5_lessicale']:>6}/15{r['mrr_lessicale']:>7.3f}  {r['hit5_parole']:>6}/15{r['mrr_parole']:>7.3f}")
    print("\nparole = lunghezza media del chunk; lette = parole da leggere nei primi 5 risultati")


if __name__ == "__main__":
    main()
