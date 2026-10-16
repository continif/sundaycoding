"""
S05E03 free — Come taglia le parole italiane un tokenizzatore di Mistral.

Confronta i due tokenizzatori che Mistral distribuisce con la libreria
mistral-common (i file sono dentro il pacchetto, non serve scaricare nulla):

  - v1: SentencePiece, 32.000 pezzi, quello dei primi modelli;
  - Tekken: tiktoken, 131.072 pezzi, addestrato su più di cento lingue,
    in uso da Mistral NeMo (luglio 2024) in poi.

Uso:
    pip install "mistral-common[sentencepiece]"
    python mistral.py ../corpus/specchio.jsonl
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import mistral_common
from mistral_common.tokens.tokenizers.sentencepiece import SentencePieceTokenizer
from mistral_common.tokens.tokenizers.tekken import Tekkenizer

DATI = Path(os.path.dirname(mistral_common.__file__)) / "data"
TEKKEN = Tekkenizer.from_file(str(DATI / "tekken_240911.json"))
V1 = SentencePieceTokenizer(str(DATI / "tokenizer.model.v1"))


def pezzi_tekken(parola: str) -> list[str]:
    # Lo spazio davanti è voluto: nel testo una parola arriva quasi sempre
    # dopo uno spazio, e Tekken ha imparato " però" (con lo spazio) come
    # pezzo a sé. Senza spazio misureremmo un caso che nel libro non c'è.
    ids = TEKKEN.encode(" " + parola, bos=False, eos=False)
    # I pezzi di Tekken sono byte: "ò" sono due byte UTF-8. Li decodifichiamo
    # uno per uno solo per stamparli; errors="replace" mostra "�" quando un
    # pezzo contiene mezza lettera, ed è giusto vederlo.
    return [TEKKEN.id_to_byte_piece(i, "raise").decode("utf-8", "replace").strip()
            for i in ids]


def pezzi_v1(parola: str) -> list[str]:
    ids = V1.encode(parola, bos=False, eos=False)
    return [V1.id_to_piece(i).lstrip("▁") for i in ids if V1.id_to_piece(i) != "▁"]


ESEMPI = ["però", "pero", "papà", "papa", "sì", "si", "così", "cosa",
          "perché", "perchè", "gridò", "gridava", "curiosità",
          "croce", "crocera", "crociera", "crociere", "Giabervocco", "frufrù"]


def main() -> None:
    with Path(sys.argv[1]).open(encoding="utf-8") as f:
        testo = "\n".join(json.loads(r)["testo"] for r in f)
    parole = re.findall(r"\w+", testo)

    print(f"{'parola':12} {'Tekken':28} v1 (SentencePiece)")
    for p in ESEMPI:
        print(f"{p:12} {' · '.join(pezzi_tekken(p)):28} {' · '.join(pezzi_v1(p))}")

    print(f"\nIl libro intero: {len(parole):,} parole")
    for nome, tok in (("Tekken", TEKKEN), ("v1", V1)):
        n = len(tok.encode(testo, bos=False, eos=False))
        print(f"  {nome:7} {n:>7,} token  ({n / len(parole):.2f} token per parola)")

    # Le parole con l'accento in fondo: quante Tekken le tiene intere?
    accentate = sorted({p.casefold() for p in parole if re.search(r"[àèéìòù]$", p.casefold())})
    for nome, f in (("Tekken", pezzi_tekken), ("v1", pezzi_v1)):
        intere = [p for p in accentate if len(f(p)) == 1]
        print(f"  {nome:7} tiene intere {len(intere)} parole accentate su {len(accentate)}")


if __name__ == "__main__":
    main()
