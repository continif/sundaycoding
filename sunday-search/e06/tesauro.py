"""
S05E06 paid — Il tesauro: i sinonimi fatti a mano da qualcuno prima di noi.

Il thesaurus di OpenOffice/LibreOffice (E03: `sinonimi.parquet`, 25.851
voci e 143.581 coppie) è un grafo di sinonimi scritto da persone. Non sa
niente del nostro libro, e proprio per questo copre quello che i vettori
addestrati su 27.000 parole non possono sapere.

Lo usiamo per allargare la query: per ogni parola cercata, i suoi sinonimi
che stanno davvero nel libro. I sinonimi contano meno dell'originale (peso
ESPANSIONE), perché un thesaurus non sa quale accezione intendeva chi cerca:
"corre" ha tra i sinonimi "fluire", "passare", "trascorrere", e nella
Regina Rossa nessuno dei tre c'entra.
"""

from __future__ import annotations

from collections import defaultdict


def espandi(indice, termini: list[str], limite: int = 40) -> list[list[str]]:
    """Per ogni termine della query, il gruppo di forme dei suoi sinonimi che
    esistono nel libro. Un gruppo per termine (non per sinonimo): come per
    le varianti di E04, l'insieme conta come una parola sola, altrimenti un
    termine con 30 sinonimi peserebbe 30 volte uno con uno.

    Si parte dai lemmi del termine (il vocabolario di E03), si chiedono i
    sinonimi al thesaurus, e ogni sinonimo si apre nelle sue forme con le
    stesse varianti della ricerca lessicale: un verbo come infinito dà tutte
    le sue forme, un nome singolare e plurale."""
    voc = indice.voc
    gruppi: list[list[str]] = []
    for t in termini:
        sinonimi: dict[str, None] = {}
        for lemma in voc.lemmi(t) or (t,):
            # La stessa parola non è un sinonimo di sé stessa.
            for s in voc.sinonimi(lemma):
                if s != lemma and " " not in s:         # niente locuzioni: "dare fuori"
                    sinonimi[s] = None
        if not sinonimi:
            gruppi.append([])
            continue
        voc.prepara(set(sinonimi))
        forme: set[str] = set()
        for s in list(sinonimi)[:limite]:
            forme |= {f for f in indice.varianti(s) if f in indice.paragrafi}
        forme -= set(indice.varianti(t))           # quello che già cerchiamo non si conta due volte
        gruppi.append(sorted(forme))
    return gruppi
