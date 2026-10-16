"""
S05E03 paid — L'indice analitico del libro, e il primo cerca().

L'indice invertito: per ogni forma, la lista dei paragrafi (e delle
posizioni) in cui compare. Lo costruiamo con il tokenizzatore della free,
lo salviamo in Parquet come il vocabolario, e lo interroghiamo in due modi:
in Python, per vedere come funziona, e con DuckDB, per vedere quanto costa.

Uso:
    python indice.py ../corpus/specchio.jsonl ../vocabolario/ ../indice/
    python indice.py ../corpus/specchio.jsonl ../vocabolario/ ../indice/ "crociera"
"""

from __future__ import annotations

import json
import sys
import time
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

import duckdb
import pyarrow as pa

from tokenizzatore import parole_di, tokenizza_posizioni
from vocabolario import Vocabolario


# ---------------------------------------------------------------------------
# Costruzione
# ---------------------------------------------------------------------------
def costruisci(corpus: Path, voc: Vocabolario, uscita: Path) -> None:
    with corpus.open(encoding="utf-8") as f:
        paragrafi = [json.loads(r) for r in f]

    # Una query sola al vocabolario per tutte le parole del libro, invece
    # di una per paragrafo: 1.097 paragrafi sarebbero 1.097 JOIN.
    voc.prepara({p for par in paragrafi for p in parole_di(par["testo"])})

    forme, numeri, posizioni = [], [], []
    for n, par in enumerate(paragrafi):
        for token, pos in tokenizza_posizioni(par["testo"], voc):
            forme.append(token)
            numeri.append(n)
            posizioni.append(pos)

    uscita.mkdir(parents=True, exist_ok=True)
    indice = pa.table({"forma": pa.array(forme, pa.string()),
                       "paragrafo": pa.array(numeri, pa.int32()),
                       "posizione": pa.array(posizioni, pa.int32())})
    testi = pa.table({"paragrafo": pa.array(range(len(paragrafi)), pa.int32()),
                      "etichetta": [f"{p['romano']}.{p['posizione']}" for p in paragrafi],
                      "testo": [p["testo"] for p in paragrafi]})
    con = duckdb.connect()
    # Ordinato per forma, come il vocabolario: chi cerca "regina" legge solo
    # i gruppi di righe in cui "regina" può stare. E dentro la forma per
    # paragrafo e posizione, così le liste escono già in ordine.
    con.execute(f"""COPY (SELECT * FROM indice ORDER BY forma, paragrafo, posizione)
                    TO '{uscita / "indice.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    con.execute(f"""COPY (SELECT * FROM testi ORDER BY paragrafo)
                    TO '{uscita / "paragrafi.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")


# ---------------------------------------------------------------------------
# Intersezioni di liste ordinate
# ---------------------------------------------------------------------------
def interseca(a: list[int], b: list[int]) -> list[int]:
    """Due dita che scorrono due liste ordinate, come il merge di E01:
    si fa avanzare quella che sta indietro. len(a) + len(b) passi."""
    i = j = 0
    risultato = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            risultato.append(a[i])
            i += 1
            j += 1
        elif a[i] < b[j]:
            i += 1
        else:
            j += 1
    return risultato


def interseca_bisect(corta: list[int], lunga: list[int]) -> list[int]:
    """Quando una lista è molto più corta dell'altra: per ogni elemento
    della corta, bisect nella lunga (E01 di nuovo). len(corta) × log(len(lunga))
    passi, e la lista lunga non si scorre mai tutta."""
    risultato, inizio = [], 0
    for x in corta:
        # Si riparte da dove si era arrivati: la corta è ordinata, quindi
        # il prossimo elemento non può stare prima.
        inizio = bisect_left(lunga, x, inizio)
        if inizio == len(lunga):
            break
        if lunga[inizio] == x:
            risultato.append(x)
    return risultato


# ---------------------------------------------------------------------------
# L'indice in memoria e cerca()
# ---------------------------------------------------------------------------
class Indice:
    def __init__(self, cartella: Path, voc: Vocabolario):
        self.voc = voc
        self.con = duckdb.connect()
        self.indice_parquet = str(cartella / "indice.parquet")
        # forma → {paragrafo: [posizioni]}. Il Parquet è già ordinato per
        # forma, paragrafo e posizione: i dizionari si riempiono in ordine.
        self.posizioni: dict[str, dict[int, list[int]]] = defaultdict(dict)
        for forma, paragrafo, posizioni in self.con.execute(f"""
                SELECT forma, paragrafo, list(posizione ORDER BY posizione)
                FROM '{self.indice_parquet}' GROUP BY forma, paragrafo
                ORDER BY forma, paragrafo""").fetchall():
            self.posizioni[forma][paragrafo] = posizioni
        # forma → paragrafi in ordine: è la lista che si interseca.
        self.paragrafi: dict[str, list[int]] = {f: list(pp) for f, pp in self.posizioni.items()}
        self.etichette = dict(self.con.execute(
            f"SELECT paragrafo, etichetta FROM '{cartella / 'paragrafi.parquet'}'").fetchall())
        self._forme_di: dict[str, tuple[str, ...]] = {}

    # --- il dizionario nell'altro verso ---------------------------------
    def _carica_forme(self, lemmi: set[str]) -> None:
        """Tutte le forme dei lemmi che servono, con una query sola."""
        mancanti = sorted(lemmi - self._forme_di.keys())
        if not mancanti:
            return
        for lemma, forme in self.con.execute("""
                SELECT lemma, list(forma ORDER BY forma) FROM read_parquet(?)
                WHERE lemma IN (SELECT unnest(?::VARCHAR[])) GROUP BY lemma""",
                [self.voc.forme_parquet, mancanti]).fetchall():
            self._forme_di[lemma] = tuple(forme)

    def varianti(self, forma: str) -> set[str]:
        """Le forme da cercare insieme a `forma`. Tre casi, decisi dal
        dizionario e dalla grammatica, mai da una regola sulle lettere.

        - Un verbo, ma solo quando è sicuro che sia un verbo: l'infinito
          ("gridare") o una forma con l'accento in fondo ("gridò", "sarà"),
          perché lì l'accento è la desinenza. Allora tutte le sue forme.
          Non "porta" o "testa": il correttore le conosce solo come voci di
          portare e testare (la porta e la testa per lui non servono, si
          scrivono uguali), e chi cerca la testa non vuole "testavano".
        - Un nome o un aggettivo: singolare e plurale, MAI l'altro genere.
          Il correttore scrive caso/o e ne ricava casa, casi, case: quando
          una voce in -o ha quattro forme, il genere sta nella vocale
          finale, o/i contro a/e, e chi cerca "casa" non vuole "caso".
        - Tutto il resto, comprese le parole tronche che non sono verbi
          (città, però, papà) e quelle fuori dal vocabolario: sé stesse.
        """
        self.voc.prepara({forma})          # niente query se l'ha già chiesta
        lemmi = set(self.voc.lemmi(forma))
        self._carica_forme(lemmi)
        verbi = {l for l in lemmi if self._e_verbo(l)}
        if verbi and verbi == lemmi and (forma in verbi or forma[-1] in "àèéìòù"):
            return {f for l in verbi for f in self._forme_di[l]}
        if forma[-1] in "àèéìòù":
            return {forma}
        maschile = forma[-1] in "oi"
        risultato = {forma}
        for lemma in lemmi - verbi:
            forme = self._forme_di.get(lemma, ())
            if lemma.endswith("o") and len(forme) == 4:
                # Il caso caso/o: quattro forme, due generi. Si tiene solo
                # quello della parola cercata.
                risultato.update(f for f in forme if (f[-1] in "oi") == maschile)
            else:
                # croce/croci, crociera/crociere, papa/papi: un genere solo,
                # singolare e plurale.
                risultato.update(forme)
        return risultato

    def _e_verbo(self, lemma: str) -> bool:
        # Un verbo ha decine di forme (gridare 178), un nome due o quattro.
        # "mare" finisce in -are ma ne ha due: non è un verbo.
        return lemma.endswith(("are", "ere", "ire", "rre")) and len(self._forme_di.get(lemma, ())) > 6

    # --- le ricerche ------------------------------------------------------
    def termini(self, query: str) -> list[tuple[str, int]]:
        """La query passa dallo STESSO tokenizzatore del libro: maiuscole,
        elisioni, grafia, stopword. Due tokenizzatori diversi ai due lati
        sono il modo più sicuro di non trovare mai niente."""
        self.voc.prepara(set(parole_di(query)))
        return tokenizza_posizioni(query, self.voc)

    def cerca(self, query: str, espandi: bool = True) -> list[int]:
        """I paragrafi che contengono TUTTI i termini della query (AND).
        Ogni termine vale come l'OR delle sue varianti."""
        liste = []
        termini = [t for t, _ in self.termini(query)]
        if espandi:
            # Le forme di tutti i lemmi della query in una query sola.
            self._carica_forme({l for t in termini for l in self.voc.lemmi(t)})
        for t in termini:
            forme = self.varianti(t) if espandi else {t}
            paragrafi = sorted({p for f in forme for p in self.paragrafi.get(f, ())})
            liste.append(paragrafi)
        if not liste:
            return []
        # Si parte dalla lista più corta: ogni intersezione può solo
        # accorciare il risultato, e conviene che sia corto da subito.
        liste.sort(key=len)
        risultato = liste[0]
        for altra in liste[1:]:
            risultato = interseca(risultato, altra)
        return risultato

    def cerca_frase(self, frase: str) -> list[int]:
        """Le parole nello stesso ordine e alla stessa distanza della frase.
        Distanze contate con le stopword, che non sono nell'indice ma
        occupano il loro posto: "testa in giù" è testa a +0, giù a +2."""
        termini = self.termini(frase)
        if not termini:
            return []
        primo, base = termini[0]
        candidati = self.cerca(frase, espandi=False)
        risultato = []
        for par in candidati:
            # Le posizioni di ogni termine in questo paragrafo, in un set
            # per controllare "c'è giù in p+2?" in tempo costante.
            pos = {t: set(self.posizioni[t][par]) for t, _ in termini}
            for inizio in pos[primo]:
                if all(inizio + (o - base) in pos[t] for t, o in termini[1:]):
                    risultato.append(par)
                    break
        return risultato

    def cerca_sql(self, query: str) -> list[int]:
        """Lo stesso AND, scritto in SQL sul Parquet: i paragrafi in cui
        compaiono tante forme diverse quanti sono i termini."""
        gruppi = [(i, sorted(self.varianti(t))) for i, (t, _) in enumerate(self.termini(query))]
        righe = [(i, f) for i, forme in gruppi for f in forme]
        return [r[0] for r in self.con.execute(f"""
            SELECT i.paragrafo
            FROM '{self.indice_parquet}' AS i
            JOIN (SELECT unnest(?::INTEGER[]) AS termine, unnest(?::VARCHAR[]) AS forma) AS q
              USING (forma)
            GROUP BY i.paragrafo
            HAVING count(DISTINCT q.termine) = ?
            ORDER BY i.paragrafo""",
            [[r[0] for r in righe], [r[1] for r in righe], len(gruppi)]).fetchall()]


def main() -> None:
    corpus, voc_dir, uscita = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    voc = Vocabolario(voc_dir)
    if not (uscita / "indice.parquet").exists():
        t0 = time.perf_counter()
        costruisci(corpus, voc, uscita)
        print(f"indice costruito in {time.perf_counter() - t0:.2f} s")
    t0 = time.perf_counter()
    indice = Indice(uscita, voc)
    print(f"indice caricato in {time.perf_counter() - t0:.2f} s: {len(indice.posizioni):,} forme")
    for query in sys.argv[4:]:
        trovati = indice.cerca(query)
        print(f"\n{query!r}: {len(trovati)} paragrafi  "
              + " ".join(indice.etichette[p] for p in trovati[:15]))


if __name__ == "__main__":
    main()
