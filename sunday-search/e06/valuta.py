"""
S05E06 paid — La valutazione: 15 query con la scena attesa.

Per ogni metodo e ogni query, in che posizione arriva il PRIMO paragrafo
atteso. Due numeri riassumono:

    hit@5   in quante query un paragrafo atteso è nei primi 5
    MRR     la media di 1/posizione del primo atteso (1 se è primo, 0,5 se
            secondo, 0 se non c'è nei primi 100): premia anche i quasi-primi

Con 15 query, un punto di hit@5 è UNA query. Differenze di una query sono
rumore, non classifica: si leggono le righe, non solo la media.

Uso:
    python valuta.py ../indice/ ../vocabolario/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ricerca import Motore, rrf  # noqa: E402

FILE = Path(__file__).resolve().parent / "valutazione.json"

# Metodo → rankers che lo compongono. Quelli a un solo ranker sono sé stessi.
# "tutti e 4" è l'ibrida come l'avevo decisa PRIMA di misurare. Le due a tre
# sono nate DOPO aver visto i numeri (vedi la puntata): leggetele come tali.
COMPOSTI = {
    "lex+lsa":       ("lessicale", "lsa"),
    "lex+parole":    ("lessicale", "parole"),
    "lex+lsa+par":   ("lessicale", "lsa", "parole"),
    "tes+lsa+par":   ("tesauro", "lsa", "parole"),
    "tutti e 4":     ("lessicale", "tesauro", "lsa", "parole"),
}
SEMPLICI = ("lessicale", "tesauro", "lsa", "parole")


def posizione(classifica: list[int], attesi: set[int]) -> int | None:
    for i, p in enumerate(classifica, start=1):
        if p in attesi:
            return i
    return None


def valuta(m: Motore, query: list[dict], metodi: dict[str, tuple[str, ...]]) -> dict[str, list[int | None]]:
    # Le classifiche dei ranker semplici si calcolano una volta per query.
    base = {q["id"]: {r: m.classifica(m.punteggi(r, q["testo"])) for r in SEMPLICI} for q in query}
    risultati: dict[str, list[int | None]] = {}
    for nome, rankers in metodi.items():
        pos = []
        for q in query:
            attesi = {m.numero[a] for a in q["attesi"]}
            if len(rankers) == 1:
                cl = base[q["id"]][rankers[0]]
            else:
                punti = rrf([base[q["id"]][r] for r in rankers])
                cl = sorted(punti, key=lambda p: (-punti[p], p))[:100]
            pos.append(posizione(cl, attesi))
        risultati[nome] = pos
    return risultati


def riassunto(pos: list[int | None], k: int = 5) -> tuple[int, float]:
    hit = sum(1 for p in pos if p is not None and p <= k)
    mrr = float(np.mean([1 / p if p else 0.0 for p in pos]))
    return hit, mrr


def bootstrap(a: list[int | None], b: list[int | None], n: int = 10_000, seme: int = 0) -> tuple[float, float, float]:
    """Differenza di MRR tra due metodi, con l'intervallo al 95%: si
    ripescano a caso le 15 query (con reinserimento) diecimila volte e si
    guarda quanto balla la differenza. Se l'intervallo contiene lo zero, con
    queste query non possiamo dire che uno dei due sia meglio dell'altro."""
    rr = lambda x: np.array([1 / p if p else 0.0 for p in x])
    d = rr(a) - rr(b)
    rng = np.random.default_rng(seme)
    medie = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(medie, 2.5)), float(np.percentile(medie, 97.5))


def main() -> None:
    cartella_indice, cartella_voc = Path(sys.argv[1]), Path(sys.argv[2])
    corpus = cartella_indice.parent / "corpus" / "specchio.jsonl"
    m = Motore(cartella_indice, cartella_voc, corpus)
    query = json.loads(FILE.read_text(encoding="utf-8"))["query"]
    metodi = {r: (r,) for r in SEMPLICI} | COMPOSTI
    ris = valuta(m, query, metodi)
    nomi = list(metodi)

    print("Posizione del primo paragrafo atteso (- = non nei primi 100)\n")
    print(f"{'':4} {'query':44}" + "".join(f"{n[:11]:>12}" for n in nomi))
    for i, q in enumerate(query):
        riga = "".join(f"{(str(ris[n][i]) if ris[n][i] else "-"):>12}" for n in nomi)
        print(f"{q['id']}{'*' if q['gia_vista'] else ' '} {q['testo'][:44]:44}{riga}")
    print("\n* = già vista in E04 e E05\n")

    nuove = [i for i, q in enumerate(query) if not q["gia_vista"]]
    print(f"{'':14} {'hit@5':>6} {'MRR':>7} {'hit@5 nuove':>12} {'MRR nuove':>10}")
    for n in nomi:
        h, mr = riassunto(ris[n])
        h2, mr2 = riassunto([ris[n][i] for i in nuove])
        print(f"{n:14} {h:>6}/15 {mr:>6.3f} {h2:>9}/10 {mr2:>10.3f}")

    print("\nQuante query risolve almeno un ranker (hit@5), e quanti la risolvono da soli:")
    for i, q in enumerate(query):
        chi = [r for r in SEMPLICI if ris[r][i] and ris[r][i] <= 5]
        if len(chi) < 4:
            print(f"   {q['id']}: {', '.join(chi) if chi else 'nessuno'}")
    unione = sum(1 for i in range(len(query)) if any(ris[r][i] and ris[r][i] <= 5 for r in SEMPLICI))
    print(f"   almeno uno dei 4: {unione}/15")

    print("\nDifferenza di MRR e intervallo al 95% (bootstrap sulle 15 query):")
    for a, b in (("tutti e 4", "lessicale"), ("tes+lsa+par", "lessicale"), ("tes+lsa+par", "tutti e 4"),
                 ("parole", "lessicale"), ("lsa", "lessicale")):
        d, lo, hi = bootstrap(ris[a], ris[b])
        print(f"   {a:12} meno {b:10}: {d:+.3f}   [{lo:+.3f}, {hi:+.3f}]")

    print("\nIl peso dei sinonimi (scelto a 0,3 prima di misurare; qui solo per vedere quanto conta):")
    import ricerca
    for w in (0.0, 0.1, 0.3, 0.5, 1.0):
        ricerca.ESPANSIONE = w
        r = valuta(m, query, {"tesauro": ("tesauro",)})["tesauro"]
        h, mr = riassunto(r)
        print(f"   peso {w:.1f}: hit@5 {h}/15, MRR {mr:.3f}")
    ricerca.ESPANSIONE = 0.3


if __name__ == "__main__":
    main()
