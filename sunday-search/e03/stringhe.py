"""
S05E03 paid — Cercare una parola dentro un testo, cinque modi.

Tutte le funzioni restituiscono la lista delle posizioni in cui `parola`
compare in `testo`, sovrapposizioni comprese, esattamente come farebbe
un ciclo su str.find. È quello che controllano i test.

Lavorano su caratteri Unicode, non su byte: "però" e "pero" sono stringhe
diverse e restano diverse. Ma il testo e la parola cercata devono essere nella stessa
forma (NFC), altrimenti "perché" non trova "perché": vedi la free.
"""

from __future__ import annotations

from collections import deque


# ---------------------------------------------------------------------------
# 0. Il riferimento: str.find in un ciclo
# ---------------------------------------------------------------------------
def con_find(testo: str, parola: str) -> list[int]:
    posizioni, i = [], testo.find(parola)
    while i != -1:
        posizioni.append(i)
        # +1 e non +len(parola): vogliamo anche le sovrapposizioni
        # ("aa" dentro "aaa" compare due volte, in 0 e in 1).
        i = testo.find(parola, i + 1)
    return posizioni


# ---------------------------------------------------------------------------
# 1. Forza bruta
# ---------------------------------------------------------------------------
def forza_bruta(testo: str, parola: str) -> list[int]:
    """Si appoggia la parola in ogni posizione e si confronta lettera per
    lettera. Nel caso peggiore n × m confronti."""
    n, m = len(testo), len(parola)
    posizioni = []
    for i in range(n - m + 1):
        j = 0
        while j < m and testo[i + j] == parola[j]:
            j += 1
        if j == m:
            posizioni.append(i)
    return posizioni


# ---------------------------------------------------------------------------
# 2. Knuth-Morris-Pratt
# ---------------------------------------------------------------------------
def tabella_kmp(parola: str) -> list[int]:
    """bordo[j] = lunghezza del più lungo prefisso di parola[:j+1] che ne è
    anche suffisso. Dice di quanto si può ripartire senza tornare indietro
    nel testo dopo un errore."""
    bordo = [0] * len(parola)
    k = 0
    for j in range(1, len(parola)):
        while k and parola[j] != parola[k]:
            k = bordo[k - 1]
        if parola[j] == parola[k]:
            k += 1
        bordo[j] = k
    return bordo


def kmp(testo: str, parola: str) -> list[int]:
    """Il testo si legge una volta sola, senza mai tornare indietro:
    al massimo 2n confronti. Utile quando il testo arriva a pezzi (uno
    stream) e non si può rileggere."""
    bordo, m = tabella_kmp(parola), len(parola)
    posizioni, k = [], 0
    for i, c in enumerate(testo):
        while k and c != parola[k]:
            k = bordo[k - 1]
        if c == parola[k]:
            k += 1
            if k == m:
                posizioni.append(i - m + 1)
                k = bordo[k - 1]
    return posizioni


# ---------------------------------------------------------------------------
# 3. Boyer-Moore-Horspool
# ---------------------------------------------------------------------------
def horspool(testo: str, parola: str) -> list[int]:
    """Si confronta da destra, e quando non va si salta: di quanto, lo
    dice l'ultima lettera della finestra. Se non compare nella parola, si salta
    la parola intera. Più la parola è lunga, più i salti sono lunghi: è l'unico
    dei cinque che va più veloce con parole più lunghe."""
    n, m = len(testo), len(parola)
    if m == 0 or m > n:
        return []
    # Un dizionario e non un array di 256: l'alfabeto è Unicode, e le
    # lettere che non sono nella parola valgono "salta tutto" con .get().
    salto = {c: m - 1 - j for j, c in enumerate(parola[:-1])}
    posizioni, i = [], 0
    while i <= n - m:
        j = m - 1
        while j >= 0 and testo[i + j] == parola[j]:
            j -= 1
        if j < 0:
            posizioni.append(i)
        i += salto.get(testo[i + m - 1], m)
    return posizioni


# ---------------------------------------------------------------------------
# 4. Rabin-Karp
# ---------------------------------------------------------------------------
BASE = 1_114_112          # quanti sono i code point Unicode: ogni carattere è una cifra
MODULO = (1 << 61) - 1    # un primo di Mersenne: poche collisioni, e Python non va mai in overflow


def rabin_karp(testo: str, parola: str) -> list[int]:
    """Si confrontano impronte (hash) invece di stringhe. L'impronta della
    finestra si aggiorna in tempo costante quando la finestra scorre di uno:
    togli la lettera che esce, aggiungi quella che entra. Quando le impronte
    coincidono si controlla davvero, perché due stringhe diverse possono
    avere la stessa impronta."""
    n, m = len(testo), len(parola)
    if m == 0 or m > n:
        return []
    alta = pow(BASE, m - 1, MODULO)      # il peso della lettera che esce
    h_ago = h = 0
    for i in range(m):
        h_ago = (h_ago * BASE + ord(parola[i])) % MODULO
        h = (h * BASE + ord(testo[i])) % MODULO
    posizioni = []
    for i in range(n - m + 1):
        if h == h_ago and testo[i:i + m] == parola:
            posizioni.append(i)
        if i < n - m:
            h = ((h - ord(testo[i]) * alta) * BASE + ord(testo[i + m])) % MODULO
    return posizioni


# ---------------------------------------------------------------------------
# 5. Aho-Corasick: tante parole in una passata sola
# ---------------------------------------------------------------------------
class AhoCorasick:
    """Un albero di prefissi (trie) di tutte le parole, più un collegamento di
    ripiego per ogni nodo: dove andare quando la lettera successiva non c'è.
    È KMP generalizzato a tante parole insieme. Il testo si legge una volta,
    qualunque sia il numero delle parole."""

    def __init__(self, parole: list[str]):
        # Ogni nodo è un intero; figli[nodo] è un dizionario lettera → nodo.
        self.figli: list[dict[str, int]] = [{}]
        self.ripiego: list[int] = [0]
        self.uscite: list[list[str]] = [[]]
        for parola in parole:
            nodo = 0
            for c in parola:
                if c not in self.figli[nodo]:
                    self.figli.append({})
                    self.ripiego.append(0)
                    self.uscite.append([])
                    self.figli[nodo][c] = len(self.figli) - 1
                nodo = self.figli[nodo][c]
            self.uscite[nodo].append(parola)
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
                # Se il ripiego è la fine di una parola, anche questo nodo lo è:
                # "crociere" contiene "ere".
                self.uscite[figlio] += self.uscite[self.ripiego[figlio]]

    def cerca(self, testo: str) -> list[tuple[int, str]]:
        """(posizione, parola) per ogni occorrenza di ogni parola."""
        trovati, nodo = [], 0
        # Variabili locali invece di self.figli: dentro un ciclo da 156.000
        # giri ogni self.qualcosa è una ricerca in più. Sul libro con 1.000
        # parole: 34 ms invece di 38. Poco, ma gratis.
        figli, ripiego, uscite = self.figli, self.ripiego, self.uscite
        for i, c in enumerate(testo):
            while nodo and c not in figli[nodo]:
                nodo = ripiego[nodo]
            nodo = figli[nodo].get(c, 0)
            for parola in uscite[nodo]:
                trovati.append((i - len(parola) + 1, parola))
        return trovati
