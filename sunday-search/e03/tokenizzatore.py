"""
S05E03 free — Come si fa a pezzi un testo.

Il tokenizzatore della stagione: prima il vocabolario, poi il testo.
Ogni parola del libro viene confrontata con il dizionario italiano di
OpenOffice/LibreOffice (vedi vocabolario.py): quello che il dizionario
riconosce, anche dopo le correzioni di grafia, diventa un token sicuro;
quello che resta si guarda a mano.

Accanto, per confronto, la strada classica: regex, minuscole, stopword e lo
stemmer Snowball, misurati passo per passo sul libro.

Uso:
    python tokenizzatore.py ../corpus/specchio.jsonl ../vocabolario/
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import snowballstemmer

from vocabolario import PAROLA, Vocabolario, riconosci

# ---------------------------------------------------------------------------
# Le stopword
# ---------------------------------------------------------------------------
# Una lista corta e scritta a mano, apposta: articoli, preposizioni semplici e
# articolate, congiunzioni, pronomi atoni, e le loro forme elise (l', dell',
# s', c'). Le liste "complete" che si trovano in giro tolgono anche "non" e
# "più", e in un motore di ricerca "non" conta.
# Gli accenti contano anche qui: "e" è una stopword, "è" no; "se" sì, "sé"
# no; "da" sì, "dà" no; "ne" sì, "né" no.
STOPWORD = set("""
il lo la i gli le un uno una un'
l' d' s' c' m' t' v' n'
di a da in con su per tra fra
del dello della dei degli delle dell'
al allo alla ai agli alle all'
dal dallo dalla dai dagli dalle dall'
nel nello nella nei negli nelle nell'
sul sullo sulla sui sugli sulle sull'
col coi coll' agl'
e ed o od ma che se come anche
mi ti si ci vi ne lo li me te ce ve
""".split())


# ---------------------------------------------------------------------------
# Il tokenizzatore
# ---------------------------------------------------------------------------
def parole_di(testo: str) -> list[str]:
    # NFC una volta sola su tutto il testo, invece che parola per parola:
    # "è" deve essere un carattere solo, come nel dizionario, anche se
    # arriva come "e" + accento combinante (copia-incolla da PDF, vecchi Mac).
    return PAROLA.findall(unicodedata.normalize("NFC", testo).replace("’", "'"))


# Le parole si ripetono: nel libro 26.000 token, 4.800 parole diverse.
# La cache fa lavorare le regole una volta per parola, non per token, e
# resta valida tra un testo e l'altro (un paragrafo e il successivo).
_CACHE: dict[str, list[str]] = {}


def tokenizza_posizioni(testo: str, voc: Vocabolario) -> list[tuple[str, int]]:
    """(token, posizione) dove la posizione è il numero d'ordine della
    parola nel testo, stopword COMPRESE. Le stopword non entrano nell'indice
    ma occupano il loro posto: "a testa in giù" dà testa=1 e giù=3, e la
    ricerca di frasi sa che tra le due c'è una parola."""
    parole = parole_di(testo)
    # Una query sola al Parquet per tutte le parole del testo, prima di
    # cominciare: vedi Vocabolario.prepara.
    voc.prepara(set(parole))
    risultato = []
    for i, p in enumerate(parole):
        if p not in _CACHE:
            _CACHE[p] = tokenizza_parola(p, voc)
        # "pel" → "per il": più token possono stare nella stessa posizione.
        risultato.extend((t, i) for t in _CACHE[p])
    return risultato


def tokenizza(testo: str, voc: Vocabolario) -> list[str]:
    return [t for t, _ in tokenizza_posizioni(testo, voc)]


def tokenizza_parola(p: str, voc: Vocabolario) -> list[str]:
    if p.casefold() in STOPWORD:
        return []
    trovata = riconosci(voc, p)
    if trovata is None and p[0].isupper():
        # Maiuscola d'inizio frase: "Così", "Perchè". La versione minuscola
        # la proviamo solo DOPO quella originale, così "Londra" resta Londra.
        trovata = riconosci(voc, p.lower())
    if trovata is None:
        # Il residuo: nomi propri, invenzioni di Carroll. Restano come sono,
        # solo in minuscolo per l'indice. Nessuno stemmer a indovinare.
        return [p.casefold()]
    # "pel" → "per il": una forma può valere più parole.
    # Restituiamo la FORMA riconosciuta, non il lemma del dizionario: il
    # correttore ortografico scrive "caso/o" e ne ricava casa, case, casi.
    # Per l'ortografia è perfetto, per il significato no (casa non è caso).
    return [f.casefold() for f in trovata[1].split() if f.casefold() not in STOPWORD]


# ---------------------------------------------------------------------------
# La strada classica, per confronto
# ---------------------------------------------------------------------------
REGEX_CLASSICA = re.compile(r"\w+")
STEMMER = snowballstemmer.stemmer("italian")
STOP_CLASSICHE = {s.rstrip("'") for s in STOPWORD}


def main() -> None:
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        testo = "\n".join(json.loads(r)["testo"] for r in f)
    voc = Vocabolario(Path(sys.argv[2]))

    def misura(nome: str, tokens: list[str]) -> None:
        print(f"{nome:32} {len(tokens):>7,} token  {len(set(tokens)):>6,} parole distinte")

    print("La strada classica:")
    misura("  0. split()", testo.split())
    t1 = REGEX_CLASSICA.findall(testo)
    misura("  1. regex \\w+", t1)
    t2 = [unicodedata.normalize("NFC", t).casefold() for t in t1]
    misura("  2. NFC + casefold", t2)
    t3 = [t for t in t2 if t not in STOP_CLASSICHE]
    misura("  3. senza stopword", t3)
    t4 = STEMMER.stemWords(t3)
    misura("  4. Snowball", t4)
    accentate = {t for t in t3 if t[-1] in "àèéìòù"}
    perse = [t for t in accentate if STEMMER.stemWord(t)[-1] not in "àèéìòù"]
    print(f"     Snowball toglie l'accento finale a {len(perse)} parole su {len(accentate)}")

    print("Prima il vocabolario:")
    finale = tokenizza(testo, voc)
    misura("  forme riconosciute", finale)

    print("\nLe parole che si confondono (o no):")
    coppie = ["papa papà", "pero però", "pere però", "giacche giacché",
              "cosa così", "croce crociere", "crociera crociere",
              "crocera crociera", "crocere crociere", "gridare gridò",
              "casa caso", "gamba gambo", "porta portare"]
    voc.prepara({x for c in coppie for x in c.split()})
    for coppia in coppie:
        a, b = coppia.split()
        sa, sb = STEMMER.stemWord(a), STEMMER.stemWord(b)
        print(f"  {a:>8} / {b:<8}  Snowball: {sa:>7} / {sb:<7}  "
              f"lemma del correttore: {'/'.join(voc.lemmi(a))} / {'/'.join(voc.lemmi(b))}")

    print("\nI più frequenti alla fine:")
    print("  " + ", ".join(f"{t} {n}" for t, n in Counter(finale).most_common(15)))


if __name__ == "__main__":
    main()
