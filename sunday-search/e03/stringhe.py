"""
S05E03 paid — Cercare una parola dentro un testo, cinque modi.

Tutte le funzioni restituiscono la lista delle posizioni in cui `ago`
compare in `pagliaio`, sovrapposizioni comprese, esattamente come farebbe
un ciclo su str.find. È quello che controllano i test.

Lavorano su caratteri Unicode, non su byte: "però" e "pero" sono stringhe
diverse e restano diverse. Ma il testo e l'ago devono essere nella stessa
forma (NFC), altrimenti "perché" non trova "perché": vedi la free.
"""

from __future__ import annotations

from collections import deque


# ---------------------------------------------------------------------------
# 0. Il riferimento: str.find in un ciclo
# ---------------------------------------------------------------------------
def con_find(pagliaio: str, ago: str) -> list[int]:
    posizioni, i = [], pagliaio.find(ago)
    while i != -1:
        posizioni.append(i)
        # +1 e non +len(ago): vogliamo anche le sovrapposizioni
        # ("aa" dentro "aaa" compare due volte, in 0 e in 1).
        i = pagliaio.find(ago, i + 1)
    return posizioni


# ---------------------------------------------------------------------------
# 1. Forza bruta
# ---------------------------------------------------------------------------
def forza_bruta(pagliaio: str, ago: str) -> list[int]:
    """Si appoggia l'ago in ogni posizione e si confronta lettera per
    lettera. Nel caso peggiore n × m confronti."""
    n, m = len(pagliaio), len(ago)
    posizioni = []
    for i in range(n - m + 1):
        j = 0
        while j < m and pagliaio[i + j] == ago[j]:
            j += 1
        if j == m:
            posizioni.append(i)
    return posizioni


# ---------------------------------------------------------------------------
# 2. Knuth-Morris-Pratt
# ---------------------------------------------------------------------------
def tabella_kmp(ago: str) -> list[int]:
    """bordo[j] = lunghezza del più lungo prefisso di ago[:j+1] che ne è
    anche suffisso. Dice di quanto si può ripartire senza tornare indietro
    nel testo dopo un errore."""
    bordo = [0] * len(ago)
    k = 0
    for j in range(1, len(ago)):
        while k and ago[j] != ago[k]:
            k = bordo[k - 1]
        if ago[j] == ago[k]:
            k += 1
        bordo[j] = k
    return bordo


def kmp(pagliaio: str, ago: str) -> list[int]:
    """Il testo si legge una volta sola, senza mai tornare indietro:
    al massimo 2n confronti. Utile quando il testo arriva a pezzi (uno
    stream) e non si può rileggere."""
    bordo, m = tabella_kmp(ago), len(ago)
    posizioni, k = [], 0
    for i, c in enumerate(pagliaio):
        while k and c != ago[k]:
            k = bordo[k - 1]
        if c == ago[k]:
            k += 1
            if k == m:
                posizioni.append(i - m + 1)
                k = bordo[k - 1]
    return posizioni


# ---------------------------------------------------------------------------
# 3. Boyer-Moore-Horspool
# ---------------------------------------------------------------------------
def horspool(pagliaio: str, ago: str) -> list[int]:
    """Si confronta da destra, e quando non va si salta: di quanto, lo
    dice l'ultima lettera della finestra. Se non compare nell'ago, si salta
    l'ago intero. Più l'ago è lungo, più i salti sono lunghi: è l'unico
    dei cinque che va più veloce con aghi più lunghi."""
    n, m = len(pagliaio), len(ago)
    if m == 0 or m > n:
        return []
    # Un dizionario e non un array di 256: l'alfabeto è Unicode, e le
    # lettere che non sono nell'ago valgono "salta tutto" con .get().
    salto = {c: m - 1 - j for j, c in enumerate(ago[:-1])}
    posizioni, i = [], 0
    while i <= n - m:
        j = m - 1
        while j >= 0 and pagliaio[i + j] == ago[j]:
            j -= 1
        if j < 0:
            posizioni.append(i)
        i += salto.get(pagliaio[i + m - 1], m)
    return posizioni


# ---------------------------------------------------------------------------
# 4. Rabin-Karp
# ---------------------------------------------------------------------------
BASE = 1_114_112          # quanti sono i code point Unicode: ogni carattere è una cifra
MODULO = (1 << 61) - 1    # un primo di Mersenne: poche collisioni, e Python non va mai in overflow


def rabin_karp(pagliaio: str, ago: str) -> list[int]:
    """Si confrontano impronte (hash) invece di stringhe. L'impronta della
    finestra si aggiorna in tempo costante quando la finestra scorre di uno:
    togli la lettera che esce, aggiungi quella che entra. Quando le impronte
    coincidono si controlla davvero, perché due stringhe diverse possono
    avere la stessa impronta."""
    n, m = len(pagliaio), len(ago)
    if m == 0 or m > n:
        return []
    alta = pow(BASE, m - 1, MODULO)      # il peso della lettera che esce
    h_ago = h = 0
    for i in range(m):
        h_ago = (h_ago * BASE + ord(ago[i])) % MODULO
        h = (h * BASE + ord(pagliaio[i])) % MODULO
    posizioni = []
    for i in range(n - m + 1):
        if h == h_ago and pagliaio[i:i + m] == ago:
            posizioni.append(i)
        if i < n - m:
            h = ((h - ord(pagliaio[i]) * alta) * BASE + ord(pagliaio[i + m])) % MODULO
    return posizioni


# ---------------------------------------------------------------------------
# 5. Aho-Corasick: tanti aghi in una passata sola
# ---------------------------------------------------------------------------
class AhoCorasick:
    """Un albero di prefissi (trie) di tutti gli aghi, più un collegamento di
    ripiego per ogni nodo: dove andare quando la lettera successiva non c'è.
    È KMP generalizzato a tanti aghi insieme. Il testo si legge una volta,
    qualunque sia il numero degli aghi."""

    def __init__(self, aghi: list[str]):
        # Ogni nodo è un intero; figli[nodo] è un dizionario lettera → nodo.
        self.figli: list[dict[str, int]] = [{}]
        self.ripiego: list[int] = [0]
        self.uscite: list[list[str]] = [[]]
        for ago in aghi:
            nodo = 0
            for c in ago:
                if c not in self.figli[nodo]:
                    self.figli.append({})
                    self.ripiego.append(0)
                    self.uscite.append([])
                    self.figli[nodo][c] = len(self.figli) - 1
                nodo = self.figli[nodo][c]
            self.uscite[nodo].append(ago)
        # I ripieghi si calcolano in larghezza (la BFS di E02): il ripiego
        # di un nodo dipende da quello di suo padre, che sta un livello sopra.
        coda = deque(self.figli[0].values())
        while coda:
            nodo = coda.popleft()
            for c, figlio in self.figli[nodo].items():
                coda.append(figlio)
                r = self.ripiego[nodo]
                while r and c not in self.figli[r]:
                    r = self.ripiego[r]
                self.ripiego[figlio] = self.figli[r].get(c, 0)
                # Se il ripiego è la fine di un ago, anche questo nodo lo è:
                # "crociere" contiene "ere".
                self.uscite[figlio] += self.uscite[self.ripiego[figlio]]

    def cerca(self, pagliaio: str) -> list[tuple[int, str]]:
        """(posizione, ago) per ogni occorrenza di ogni ago."""
        trovati, nodo = [], 0
        # Variabili locali invece di self.figli: dentro un ciclo da 156.000
        # giri ogni self.qualcosa è una ricerca in più. Sul libro con 1.000
        # aghi: 34 ms invece di 38. Poco, ma gratis.
        figli, ripiego, uscite = self.figli, self.ripiego, self.uscite
        for i, c in enumerate(pagliaio):
            while nodo and c not in figli[nodo]:
                nodo = ripiego[nodo]
            nodo = figli[nodo].get(c, 0)
            for ago in uscite[nodo]:
                trovati.append((i - len(ago) + 1, ago))
        return trovati
