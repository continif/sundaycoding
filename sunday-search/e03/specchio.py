"""
S05E03 paid — Intermezzo allo specchio.

Tre domande al libro, tutte con la stessa idea: girare le parole.
  1. Il residuo della free contiene parole che, lette al contrario, sono
     parole del libro? (Sì: è la poesia stampata a specchio del capitolo I.)
  2. Quali parole del libro sono palindrome?
  3. Quali parole del libro, girate, diventano un'altra parola italiana?

Uso:
    python specchio.py ../corpus/specchio.jsonl ../vocabolario/
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import duckdb

from tokenizzatore import parole_di
from vocabolario import Vocabolario, confronta


def main() -> None:
    corpus, voc_dir = Path(sys.argv[1]), Path(sys.argv[2])
    with corpus.open(encoding="utf-8") as f:
        paragrafi = [json.loads(r) for r in f]
    testo = "\n".join(p["testo"] for p in paragrafi)
    voc = Vocabolario(voc_dir)

    parole = Counter(p.casefold().rstrip("'") for p in parole_di(testo))
    residuo = {p.casefold() for p in confronta(voc, testo)["residuo"]}

    # 1a. Il residuo allo specchio. Una parola del residuo è "rovesciata"
    #     se, girata, è una parola del libro o una forma del vocabolario.
    #     Le domande al vocabolario vanno tutte insieme, come sempre.
    girate = {w: w[::-1] for w in residuo if len(w) > 1}
    voc.prepara(set(girate.values()))
    specchiate = sorted(w for w, g in girate.items() if g in parole or voc.lemmi(g))
    print(f"1. Parole del residuo che al contrario esistono: {len(specchiate)} su {len(residuo)}")
    print("   " + ", ".join(f"{w} → {girate[w]}" for w in specchiate))

    # 1b. Quale paragrafo è scritto al contrario? Quello in cui il
    #     vocabolario riconosce più parole girate che dritte. Nessuno gli
    #     dice dove guardare: lo trova da solo.
    def riconosciute(ws: list[str]) -> float:
        return sum(1 for w in ws if voc.lemmi(w.casefold())) / max(len(ws), 1)

    tutte = {w.casefold() for p in paragrafi for w in parole_di(p["testo"])}
    voc.prepara(tutte | {w[::-1] for w in tutte})
    print("\n   paragrafi che il vocabolario riconosce meglio al contrario:")
    for p in paragrafi:
        ws = [w.rstrip("'") for w in parole_di(p["testo"])]
        dritto, rovescio = riconosciute(ws), riconosciute([w[::-1] for w in ws])
        if rovescio > dritto:
            etichetta = f"{p['romano']}.{p['posizione']}"
            print(f"   {etichetta}: dritto {dritto:.0%} delle parole, al contrario {rovescio:.0%}")
            print("     com'è stampato:      " + " / ".join(p["testo"].split("\n")[:2]))
            print("     girato riga per riga: " + " / ".join(v[::-1] for v in p["testo"].split("\n")[:2]))

    # 2. I palindromi: parole del libro uguali al contrario, di almeno 3
    #    lettere: sotto le tre, "a" ed "e" sono palindrome per forza.
    palindromi = sorted((p for p in parole if len(p) >= 3 and p == p[::-1]),
                        key=lambda p: (-len(p), p))
    print(f"\n2. Palindromi nel libro: {len(palindromi)}")
    print("   " + ", ".join(f"{p} ({parole[p]})" for p in palindromi))

    # 3. Le parole bifronti: girate, sono un'altra parola italiana. Qui la
    #    domanda la fa DuckDB da solo, con reverse() dentro la JOIN: una
    #    query, tutto il libro contro tre milioni di forme.
    bifronti = duckdb.execute(f"""
        SELECT DISTINCT l.parola, reverse(l.parola) AS girata
        FROM (SELECT unnest(?::VARCHAR[]) AS parola) AS l
        JOIN read_parquet('{voc.forme_parquet}') AS f ON f.forma = reverse(l.parola)
        WHERE length(l.parola) >= 4 AND l.parola <> reverse(l.parola)
        ORDER BY length(l.parola) DESC, l.parola
    """, [sorted(parole)]).fetchall()
    print(f"\n3. Parole del libro che girate sono un'altra parola: {len(bifronti)}")
    print("   " + ", ".join(f"{a}/{b}" for a, b in bifronti[:40]))


if __name__ == "__main__":
    main()
