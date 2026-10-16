"""
S05E03 — Il vocabolario italiano, generato una volta sola e salvato in Parquet.

Legge il dizionario e il thesaurus di OpenOffice/LibreOffice (progetto
dict-it, GPL 3) e scrive due file che useremo per tutta la stagione:

  forme.parquet     forma, lemma, origine   (circa 3 milioni di righe)
  sinonimi.parquet  voce, categoria, sinonimo

I file del dizionario NON sono nel repository (GPL 3): si scarica l'estensione
.oxt da https://extensions.openoffice.org/project/dict-it, si apre come uno
zip e si passa la cartella "dictionaries". Neanche i Parquet vanno nel repo:
sono un'opera derivata dal dizionario, con la stessa licenza.

Uso:
    python genera_vocabolario.py PERCORSO/dictionaries ../vocabolario/ [righe per pezzo, 100000]
"""

from __future__ import annotations

import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import duckdb
import pyarrow as pa


# ---------------------------------------------------------------------------
# Le regole del dizionario: .aff
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Regola:
    togli: str
    aggiungi: str
    condizione: re.Pattern
    # "Y" nell'intestazione del blocco: la regola si può combinare con un
    # prefisso. ri- + portare + -ava = riportava.
    incrocia: bool


def leggi_aff(aff: Path) -> tuple[dict[str, list[Regola]], dict[str, list[Regola]]]:
    """Suffissi e prefissi, ciascuno per etichetta.

    "SFX Q a he [gc]a": alle voci con etichetta Q che finiscono in "ca" o
    "ga" togli "a" e aggiungi "he" (giacca → giacche).
    "PFX T 0 dell' [aeiouh]": davanti alle voci con etichetta T che iniziano
    per vocale o h si può mettere "dell'" (albero → dell'albero).
    "PFX J 0 ri .": davanti a qualunque voce con etichetta J si può mettere
    "ri" (portare → riportare).
    """
    suffissi: dict[str, list[Regola]] = defaultdict(list)
    prefissi: dict[str, list[Regola]] = defaultdict(list)
    incrocia: dict[tuple[str, str], bool] = {}
    with aff.open(encoding="utf-8") as f:
        for riga in f:
            campi = riga.split()
            if len(campi) == 4 and campi[0] in ("SFX", "PFX"):
                # Intestazione di blocco: "SFX A Y 81".
                incrocia[campi[0], campi[1]] = campi[2] == "Y"
                continue
            if len(campi) < 5 or campi[0] not in ("SFX", "PFX"):
                continue
            tipo, etichetta, togli, aggiungi, condizione = campi[:5]
            togli = "" if togli == "0" else togli
            aggiungi = "" if aggiungi == "0" else aggiungi.split("/")[0]
            # La condizione è già una piccola regex. Per un suffisso guarda
            # la fine della parola, per un prefisso l'inizio. Compilata una
            # volta sola: le regole sono 3.200, le voci 95.000.
            if tipo == "SFX":
                suffissi[etichetta].append(Regola(togli, aggiungi, re.compile(f"(?:{condizione})$"),
                                                  incrocia[tipo, etichetta]))
            else:
                prefissi[etichetta].append(Regola(togli, aggiungi, re.compile(f"^(?:{condizione})"),
                                                  incrocia[tipo, etichetta]))
    return suffissi, prefissi


# ---------------------------------------------------------------------------
# Le forme
# ---------------------------------------------------------------------------
# Parole che mancano al dizionario, nello stesso formato di it_IT.dic.
# "crocera" (le volte a crocera) è un termine d'architettura e non c'è; con
# l'etichetta Q, come crociera, il dizionario impara anche "crocere".
# "colà" e "micino" mancano anche loro: "micino/o" dà micina, micini, micine.
AGGIUNTE = ["crocera/Q", "colà", "micino/o"]


def genera_forme(cartella: Path, aggiunte: list[str] = AGGIUNTE) -> Iterator[tuple[str, str, str]]:
    """(forma, lemma, origine) per ogni forma che il dizionario sa generare.
    Un generatore: le righe vanno dritte nelle colonne, senza passare da
    un dizionario Python da quasi 400 MB."""
    suffissi, prefissi = leggi_aff(cartella / "it_IT.aff")
    # I prefissi del dizionario sono di tre tipi.
    # - Elisioni (l', dell', quest'...): le salviamo come forme a sé invece
    #   di generare "dell'albero", "nell'albero"... per ogni parola. Il
    #   testo lo tagliamo comunque sull'apostrofo.
    # - Composizione dei numeri (mille-, duemila-...): i numeri sono
    #   infiniti, non si elencano. Se servirà riconoscerne uno scritto in
    #   lettere, lo farà una regola, non un elenco.
    # - Prefissi di parola: ri-, stra-, pre-. Una regola per blocco. Questi
    #   li applichiamo: senza, "riporta" e "riprese" restano fuori.
    veri_prefissi: dict[str, list[Regola]] = defaultdict(list)
    for etichetta, regole in prefissi.items():
        for r in regole:
            if r.aggiungi.endswith("'"):
                yield r.aggiungi, r.aggiungi, "elisione"
        if len(regole) == 1 and regole[0].aggiungi.isalpha():
            veri_prefissi[etichetta] = regole

    def righe_dic() -> Iterator[tuple[str, str]]:
        # Riga per riga, senza caricare il file in una lista.
        with (cartella / "it_IT.dic").open(encoding="utf-8") as f:
            next(f)                               # numero di voci
            for r in f:
                yield r, "dizionario"
        for r in aggiunte:
            yield r, "aggiunta"

    for riga, origine in righe_dic():
        riga = riga.strip()
        if not riga or riga.startswith("/"):
            continue
        lemma, _, etichette = riga.partition("/")
        # Il caso NON si tocca: "Londra" maiuscolo è un nome proprio,
        # "alice" minuscolo è il pesce. Il confronto col testo deciderà.
        # (forma, si può prefissare?) — la voce nuda si può sempre.
        generate = [(lemma, True)]
        for e in etichette:
            for r in suffissi.get(e, ()):
                if r.condizione.search(lemma) and lemma.endswith(r.togli):
                    generate.append((lemma[:len(lemma) - len(r.togli)] + r.aggiungi, r.incrocia))
        for forma, _ in generate:
            yield forma, lemma, origine
        for e in etichette:
            for r in veri_prefissi.get(e, ()):
                if not r.condizione.search(lemma):
                    continue
                # riportava ha come lemma riportare, non portare:
                # chi cerca "riportare" non vuole trovare "portare".
                nuovo_lemma = r.aggiungi + lemma[len(r.togli):]
                for forma, incrocia in generate:
                    if forma == lemma or (incrocia and r.incrocia):
                        yield r.aggiungi + forma[len(r.togli):], nuovo_lemma, origine


def genera_sinonimi(dat: Path) -> Iterator[tuple[str, str, str]]:
    """(voce, categoria, sinonimo) dal thesaurus.
    th_it_IT_v2.dat: "voce|n" seguito da n righe "(categoria)|sin|sin|...".
    È ISO-8859-15, non UTF-8: lo dice la prima riga del file. Aprirlo come
    UTF-8 fallirebbe sulla prima "à"; aprirlo come latin-1 funzionerebbe
    quasi sempre, che è peggio."""
    with dat.open(encoding="iso-8859-15") as f:
        next(f)
        for riga in f:
            voce, _, n = riga.rstrip("\n").partition("|")
            for _ in range(int(n)):
                categoria, *sinonimi = next(f).rstrip("\n").split("|")
                for s in sinonimi:
                    yield voce, categoria.strip("()"), s


# Misurati sul dizionario italiano: con 64 MB e un thread solo DuckDB ordina
# appoggiandosi su disco; con 32 MB non ce la fa (Out of Memory). Ogni
# thread ha i suoi buffer, che stanno FUORI dal tetto: con 4 thread il
# picco del processo sale di 60-70 MB, per due secondi guadagnati.
TETTO = "64MB"
THREADS = 1


def a_pezzi(righe: Iterator[tuple], nomi: list[str], quante: int) -> Iterator[pa.Table]:
    """Da righe a colonne, un pezzo alla volta.

    Parquet e DuckDB ragionano per colonne, quindi le righe vanno girate.
    Ma girarle tutte insieme vuol dire tenere in memoria tre milioni di
    stringhe Python, oltre un GB. A pezzi da `quante` righe, in memoria
    c'è solo il pezzo corrente: il resto è già dentro DuckDB."""
    dati: list[list[str]] = [[] for _ in nomi]
    for riga in righe:
        for colonna, valore in zip(dati, riga):
            colonna.append(valore)
        if len(dati[0]) == quante:
            yield pa.table({n: pa.array(d, pa.string()) for n, d in zip(nomi, dati)})
            dati = [[] for _ in nomi]
    if dati[0]:
        yield pa.table({n: pa.array(d, pa.string()) for n, d in zip(nomi, dati)})


def main() -> None:
    cartella, uscita = Path(sys.argv[1]), Path(sys.argv[2])
    quante = int(sys.argv[3]) if len(sys.argv) > 3 else 100_000
    uscita.mkdir(parents=True, exist_ok=True)

    # Un database DuckDB su file, di appoggio: le righe ci arrivano a pezzi
    # e restano su disco, non in RAM. Lo cancelliamo alla fine.
    appoggio = uscita / "_genera.duckdb"
    appoggio.unlink(missing_ok=True)
    con = duckdb.connect(str(appoggio))
    # Senza tetto DuckDB si prende fino all'80% della RAM, perché può: con
    # un tetto, l'ordinamento e il GROUP BY appoggiano su disco quello che
    # non ci sta. Più lento di poco, e la macchina resta usabile.
    con.execute(f"SET memory_limit = '{TETTO}'")
    con.execute(f"SET temp_directory = '{uscita / '_tmp'}'")
    con.execute(f"SET threads = {THREADS}")
    con.execute("CREATE TABLE forme (forma VARCHAR, lemma VARCHAR, origine VARCHAR)")
    con.execute("CREATE TABLE sinonimi (voce VARCHAR, categoria VARCHAR, sinonimo VARCHAR)")

    t0 = time.perf_counter()
    for tabella, righe, nomi in (
        ("forme", genera_forme(cartella), ["forma", "lemma", "origine"]),
        ("sinonimi", genera_sinonimi(cartella / "th_it_IT_v2.dat"), ["voce", "categoria", "sinonimo"]),
    ):
        for pezzo in a_pezzi(righe, nomi, quante):
            # DuckDB legge la tabella Arrow direttamente dalla variabile
            # Python "pezzo", senza copiarla: si chiama "replacement scan".
            con.execute(f"INSERT INTO {tabella} SELECT * FROM pezzo")
    print(f"generate e caricate a pezzi da {quante:,} righe in {time.perf_counter() - t0:.1f} s")

    t0 = time.perf_counter()
    con.execute(f"""
        COPY (
            WITH diz AS (
                -- La stessa coppia può nascere due volte (una voce ripetuta,
                -- un prefisso che rigenera una forma già vista): una sola.
                SELECT forma, lemma, min(origine) AS origine
                FROM forme GROUP BY forma, lemma
            ),
            th AS (
                -- Le parole singole del thesaurus che il correttore non ha.
                -- Le locuzioni ("viaggio per mare") restano fuori.
                SELECT DISTINCT parola AS forma FROM (
                    SELECT voce AS parola FROM sinonimi
                    UNION SELECT sinonimo FROM sinonimi)
                WHERE parola NOT LIKE '% %'
            )
            SELECT * FROM diz
            UNION ALL
            SELECT forma, forma, 'thesaurus' FROM th
            WHERE forma NOT IN (SELECT forma FROM diz)
            -- Ordinato per forma: Parquet tiene il minimo e il massimo di
            -- ogni gruppo di righe, e con i dati in ordine chi cerca
            -- "crociera" salta subito al gruppo giusto. Lo stesso trucco
            -- dello schedario di E02. L'ordinamento lo fa DuckDB, che se
            -- la memoria non basta appoggia i pezzi su disco.
            ORDER BY forma, lemma
        ) TO '{uscita / "forme.parquet"}' (FORMAT parquet, COMPRESSION zstd)
    """)
    con.execute(f"""
        COPY (SELECT * FROM sinonimi ORDER BY voce)
        TO '{uscita / "sinonimi.parquet"}' (FORMAT parquet, COMPRESSION zstd)
    """)
    print(f"scritti in {time.perf_counter() - t0:.1f} s")
    for nome in ("forme.parquet", "sinonimi.parquet"):
        f = uscita / nome
        righe = con.execute(f"SELECT count(*) FROM '{f}'").fetchone()[0]
        print(f"  {nome:17} {righe:>10,} righe  {f.stat().st_size / 2**20:6.1f} MB")
    con.close()
    appoggio.unlink()


if __name__ == "__main__":
    main()
