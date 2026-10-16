"""
S05E03 — Prima il vocabolario, poi il testo.

Il vocabolario italiano (dizionario e thesaurus di OpenOffice/LibreOffice)
è già stato generato una volta per tutte da genera_vocabolario.py in due
file Parquet. Qui lo interroghiamo con DuckDB: si confronta ogni parola del
libro con le forme del vocabolario e si guarda solo quello che avanza, pochi
nomi propri, qualche grafia del 1914, qualche refuso, le invenzioni di
Carroll. Un residuo così piccolo si legge a mano.

Uso:
    python vocabolario.py ../vocabolario/ ../corpus/specchio.jsonl
"""

from __future__ import annotations

import json
import re
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import duckdb


# ---------------------------------------------------------------------------
# Il vocabolario, su Parquet
# ---------------------------------------------------------------------------
class Vocabolario:
    """Le forme italiane, lette da forme.parquet con DuckDB.

    In memoria non teniamo i 3 milioni di forme: teniamo solo quelle che
    servono al testo che stiamo leggendo. Prima si raccolgono tutte le
    parole che le regole potrebbero voler controllare, poi si chiede a
    DuckDB in UNA query quali esistono. Una domanda per parola sarebbe il
    problema delle N+1 query dello schedario di E02, in un altro vestito.
    """

    def __init__(self, cartella: Path):
        # Il glob prende forme.parquet e gli eventuali file affiancati
        # (forme_aggiunte.parquet...): un Parquet non si modifica, si affianca.
        self.forme_parquet = str(cartella / "forme*.parquet")
        self.sinonimi_parquet = str(cartella / "sinonimi.parquet")
        self.con = duckdb.connect()
        # Le elisioni sono 58: queste sì, in memoria subito.
        self.elisioni = {r[0] for r in self.con.execute(
            "SELECT forma FROM read_parquet(?) WHERE origine = 'elisione'",
            [self.forme_parquet]).fetchall()}
        self._lemmi: dict[str, tuple[str, ...]] = {}
        # Tutto quello che abbiamo già chiesto al Parquet, trovato o no:
        # le parole che non esistono non vanno richieste a ogni paragrafo.
        self._chieste: set[str] = set()
        self._registro: set[str] | None = None

    def conosce(self, parola: str) -> bool:
        if self._registro is not None:
            # Modalità "registra": annotiamo la domanda e rispondiamo no.
            # Rispondendo sempre no, riconosci() prova TUTTE le sue regole,
            # e alla fine nel registro c'è ogni parola che potrebbe servirle.
            self._registro.add(parola)
            return False
        return parola in self._lemmi

    def lemmi(self, parola: str) -> tuple[str, ...]:
        return self._lemmi.get(parola, ())

    def prepara(self, parole: set[str]) -> None:
        """Carica dal Parquet tutte le forme che servono per queste parole."""
        self._registro = set()
        for p in parole:
            riconosci(self, p)
            if p[:1].isupper():
                riconosci(self, p.lower())
        chieste, self._registro = self._registro, None
        chieste -= self._chieste
        if not chieste:
            return
        self._chieste |= chieste
        # La lista delle parole entra in DuckDB come una tabella di una
        # colonna, e la JOIN con il Parquet fa il resto.
        righe = self.con.execute("""
            SELECT f.forma, list(f.lemma ORDER BY f.lemma)
            FROM read_parquet(?) AS f
            JOIN (SELECT unnest(?::VARCHAR[]) AS forma) AS c USING (forma)
            GROUP BY f.forma
        """, [self.forme_parquet, sorted(chieste)]).fetchall()
        self._lemmi.update((forma, tuple(lemmi)) for forma, lemmi in righe)

    def sinonimi(self, parola: str) -> list[str]:
        return [r[0] for r in self.con.execute(
            "SELECT sinonimo FROM read_parquet(?) WHERE voce = ?",
            [self.sinonimi_parquet, parola]).fetchall()]


# ---------------------------------------------------------------------------
# Il confronto col testo
# ---------------------------------------------------------------------------
# Una parola: lettere (non "_", che \w includerebbe), con l'apostrofo finale
# se c'è, così "dell'albero" dà "dell'" e "albero". Il libro usa l'apostrofo
# dritto 731 volte e quello tipografico una: li prendiamo tutti e due.
PAROLA = re.compile(r"[^\W\d_]+['’]?")


# Decise a mano, leggendo il residuo: sono i casi in cui le regole sbagliano
# o non arrivano. Il valore può essere più parole (pel → per il).
A_MANO = {
    # forme antiche che una regola tradurrebbe male
    "pel": "per il", "cor": "cuore", "stan": "stanno", "ei": "egli",
    "vo": "vado", "fo'": "faccio", "fe'": "fece", "di'": "dì", "to'": "toh",
    "meco": "con me", "veggo": "vedo", "vegga": "veda", "lagrime": "lacrime",
    "cittade": "città", "ubbriaca": "ubriaca", "bodino": "budino",
    "scotendo": "scuotendo", "sonare": "suonare", "sonava": "suonava",
    "sonerò": "suonerò", "gridâro": "gridarono", "batteami": "mi batteva",
    # refusi dell'edizione: l'occhio umano li corregge, il computer no
    "all": "all'", "aI": "al", "i'": "l'", "vedi'": "vedi",
    "lietamente'": "lietamente", "finche": "finché", "diffìcile": "difficile",
    "dàlle": "dalle", "sonnetto": "sonetto",
    # restano come sono: la regola del troncamento le "correggerebbe" male
    "spron": "spron",   # lo Spron di Cavaliere, un fiore (sprono → sbagliato)
    "len": "len",       # "nel" al contrario, dalla poesia allo specchio
}


def riconosci(voc: Vocabolario, p: str) -> tuple[str, str] | None:
    """(come, forma del dizionario), oppure None se la parola resta fuori.

    Ogni regola propone una forma; a decidere è sempre il dizionario. Non
    trasformiamo mai una parola in qualcosa che il vocabolario non conosce.
    """
    if voc.conosce(p):
        return "nota", p
    if p in A_MANO:
        return "a mano", A_MANO[p]
    if p.endswith("'"):
        # anch' → anche, quand' → quando, quest' → questa: la vocale caduta
        # si rimette provando le quattro possibili. Quando ne vanno bene due
        # (tutt' → tutte o tutto?) non importa: il lemma è lo stesso.
        for v in "eoia":
            if voc.conosce(p[:-1] + v):
                return "elisione", p[:-1] + v
        if p in voc.elisioni:
            return "elisione", p
        return None
    if p.endswith("è") and voc.conosce(p[:-1] + "é"):
        # Grafia del 1914: perchè, sè, potè. Oggi perché, sé, poté. La regola
        # NON è "è diventa é": è "se la versione con l'acuto è una parola
        # italiana, era quella". "è" da sola, verbo essere, resta com'è.
        return "grafia 1914", p[:-1] + "é"
    if p.endswith("ea") and voc.conosce(p[:-2] + "eva"):
        # Imperfetto poetico: avea, dicea, sedea, volea → aveva, diceva...
        return "forma antica", p[:-2] + "eva"
    if "uo" in p and voc.conosce(p.replace("uo", "o")):
        # Dittongo mobile: giuoco → gioco, legnaiuolo → legnaiolo. Il 1914
        # lo scrive ovunque, l'italiano di oggi quasi mai.
        return "forma antica", p.replace("uo", "o")
    if p[-1] in "lmnr":
        # Troncamento: andavan, eran, fuor, facil. In italiano la vocale
        # finale cade solo dopo l, m, n, r: per questo la regola guarda
        # solo lì, e non trasforma "tump" in "tumpo". Ma il dizionario,
        # come giudice, a volte si sbaglia: vedi A_MANO.
        for v in "oeia":
            if voc.conosce(p + v):
                return "troncamento", p + v
    return None


def confronta(voc: Vocabolario, testo: str) -> dict[str, Counter]:
    """Divide le parole del libro per come sono state riconosciute."""
    parole = [m.group().replace("’", "'") for m in PAROLA.finditer(testo)]
    voc.prepara(set(parole))
    esito: dict[str, Counter] = defaultdict(Counter)
    for p in parole:
        trovata = riconosci(voc, p)
        if trovata is None and p[0].isupper():
            # Maiuscola a inizio frase o di riguardo: "Così", "Perchè".
            trovata = riconosci(voc, p.lower())
        esito[trovata[0] if trovata else "residuo"][p] += 1
    return esito


def main() -> None:
    cartella, corpus = Path(sys.argv[1]), Path(sys.argv[2])
    voc = Vocabolario(cartella)
    with corpus.open(encoding="utf-8") as f:
        testo = "\n".join(json.loads(r)["testo"] for r in f)
    t0 = time.perf_counter()
    esito = confronta(voc, testo)
    # ru_maxrss: il picco di memoria del processo, in KB su Linux.
    picco = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"confronto col libro in {time.perf_counter() - t0:.2f} s, "
          f"{len(voc._lemmi):,} forme lette dal Parquet, picco {picco:,.0f} MB")

    totale = sum(c.total() for c in esito.values())
    for nome in ("nota", "elisione", "grafia 1914", "forma antica", "troncamento",
                 "a mano", "residuo"):
        c = esito[nome]
        print(f"{nome:12} {c.total():>7,} token ({c.total() / totale:6.2%})  {len(c):>5,} distinte")
        if nome in ("grafia 1914", "forma antica", "troncamento"):
            print("               " + ", ".join(f"{p}→{riconosci(voc, p.lower())[1]}" for p in sorted(c)))

    # Il residuo, diviso in due: quello che nel libro compare SEMPRE con la
    # maiuscola (nomi propri, quasi certamente) e tutto il resto.
    residuo = esito["residuo"]
    minuscole = {p.lower() for p in residuo if not p[0].isupper()}
    nomi = {p: n for p, n in residuo.items() if p[0].isupper() and p.lower() not in minuscole}
    resto = {p: n for p, n in residuo.items() if p not in nomi}
    print(f"\nsempre con la maiuscola ({len(nomi)}, {sum(nomi.values())} token):")
    print("  " + ", ".join(f"{p} {n}" for p, n in sorted(nomi.items(), key=lambda x: -x[1])))
    print(f"\nil resto ({len(resto)}, {sum(resto.values())} token):")
    print("  " + ", ".join(f"{p} {n}" for p, n in sorted(resto.items(), key=lambda x: (-x[1], x[0]))))


if __name__ == "__main__":
    main()
