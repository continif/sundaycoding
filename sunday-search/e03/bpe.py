"""
S05E03 free — Le parole-baule di Unto Dunto, ovvero il BPE in miniatura.

Byte Pair Encoding, nella versione "da lavagna": si parte dalle lettere e si
fondono, una alla volta, le due unità vicine più frequenti nel testo. Dopo
qualche centinaio di fusioni, le parole comuni sono un pezzo solo e quelle
rare (o inventate) restano spezzate in pezzi che il modello già conosce.

Uso:
    python bpe.py ../corpus/specchio.jsonl 500
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

FINE = "_"  # segna la fine della parola: "ra_" in fondo è diverso da "ra" in mezzo


def addestra(parole: Counter, fusioni: int) -> list[tuple[str, str]]:
    # Ogni parola diventa una tupla di simboli: all'inizio, le sue lettere.
    vocabolario = {tuple(p) + (FINE,): n for p, n in parole.items()}
    regole = []
    for _ in range(fusioni):
        coppie: Counter = Counter()
        for simboli, n in vocabolario.items():
            for a, b in zip(simboli, simboli[1:]):
                coppie[a, b] += n          # pesata per la frequenza della parola
        if not coppie:
            break
        (a, b), _ = coppie.most_common(1)[0]
        regole.append((a, b))
        nuovo = {}
        for simboli, n in vocabolario.items():
            fusi, i = [], 0
            while i < len(simboli):
                if i + 1 < len(simboli) and simboli[i] == a and simboli[i + 1] == b:
                    fusi.append(a + b)
                    i += 2
                else:
                    fusi.append(simboli[i])
                    i += 1
            nuovo[tuple(fusi)] = n
        vocabolario = nuovo
    return regole


def spezza(parola: str, regole: list[tuple[str, str]]) -> list[str]:
    # Si applicano le fusioni nello stesso ordine in cui sono state imparate.
    simboli = list(parola) + [FINE]
    for a, b in regole:
        i = 0
        while i < len(simboli) - 1:
            if simboli[i] == a and simboli[i + 1] == b:
                simboli[i:i + 2] = [a + b]
            else:
                i += 1
    return [s.rstrip(FINE) for s in simboli if s != FINE]


def main() -> None:
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        testo = "\n".join(json.loads(r)["testo"] for r in f).casefold()
    parole = Counter(re.findall(r"\w+", testo))
    regole = addestra(parole, int(sys.argv[2]))
    print(f"{len(regole)} fusioni; le prime dieci: {[a + b for a, b in regole[:10]]}")
    for p in ["alice", "regina", "specchio", "crociera", "crocera", "croce",
              "cencinarri", "cincinarri", "cincinnarro", "girtrellavan",
              "suffuggiavan", "giabervocco", "pischetto", "frufru", "frufrù"]:
        print(f"  {p:14} → {' · '.join(spezza(p, regole))}")


if __name__ == "__main__":
    main()
