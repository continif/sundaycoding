"""
S05E06 paid — Il grafo di somiglianza: i paragrafi vicini diventano strade.

Ogni paragrafo è collegato ai suoi K più simili (K=6). Il risultato è un
GRAFO DI SOMIGLIANZA: nodi = paragrafi, archi = "questi due si assomigliano",
peso = distanza (1 - coseno). Non è un grafo di conoscenza: non sa che
"Alice" è un personaggio e "Tweedledum" un altro, non sa chi fa cosa a chi.
Sa solo chi somiglia a chi. Il grafo di conoscenza è la stagione 6.

Con il grafo si fanno due cose che la ricerca non fa:

    simili(p)        le scene vicine a una scena, senza una query
    percorso(a, b)   la strada più corta (in somiglianza) tra due scene:
                     "da dove arrivo a lì, passando per cosa?"

Le distanze si calcolano con scipy.sparse.csgraph (Dijkstra in C): il ciclo
con la coda di priorità, in Python, per 1.097 nodi andrebbe benissimo
lo stesso, ma qui il ciclo non è la parte interessante.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components, dijkstra


class Grafo:
    def __init__(self, vettori: np.ndarray, k: int = 6):
        """`vettori`: una riga normalizzata per paragrafo (coseno = prodotto scalare)."""
        n = len(vettori)
        s = vettori @ vettori.T                  # 1.097 × 1.097: 1,2 milioni di coseni, una moltiplicazione
        np.fill_diagonal(s, -np.inf)             # un paragrafo non è vicino a sé stesso
        vuoti = np.linalg.norm(vettori, axis=1) == 0
        s[:, vuoti] = -np.inf                    # i vettori nulli non hanno vicini...
        s[vuoti, :] = -np.inf                    # ...e non sono vicini di nessuno
        # I K migliori per riga: argpartition evita di ordinare tutte le 1.097.
        idx = np.argpartition(-s, k, axis=1)[:, :k]
        righe = np.repeat(np.arange(n), k)
        colonne = idx.ravel()
        coseni = s[righe, colonne]
        ok = np.isfinite(coseni)
        # Il peso è una DISTANZA: Dijkstra cerca il minimo, e "più simile"
        # deve voler dire "più vicino". Il max(.., 1e-6) perché un arco con
        # peso zero, in una matrice sparsa, sparisce (zero = nessun arco).
        pesi = np.maximum(1.0 - coseni[ok], 1e-6)
        g = sparse.csr_matrix((pesi, (righe[ok], colonne[ok])), shape=(n, n))
        # Non orientato: se A ha B tra i vicini, la strada si può fare anche
        # da B ad A. Dove l'arco esiste in entrambe le direzioni, vale il minimo.
        self.g = _simmetrico(g)
        self.k = k
        self.componenti, self.etichetta_comp = connected_components(self.g, directed=False)

    def vicini(self, p: int) -> list[tuple[int, float]]:
        riga = self.g[p]
        return sorted(((int(j), float(1 - d)) for j, d in zip(riga.indices, riga.data)), key=lambda x: -x[1])

    def percorso(self, a: int, b: int) -> list[int] | None:
        """La strada più corta da a a b, o None se stanno in componenti diverse."""
        dist, pred = dijkstra(self.g, directed=False, indices=a, return_predecessors=True)
        if not np.isfinite(dist[b]):
            return None
        strada = [b]
        while strada[-1] != a:
            strada.append(int(pred[strada[-1]]))
        return strada[::-1]


def _simmetrico(g: sparse.csr_matrix) -> sparse.csr_matrix:
    """Un arco c'è se c'è in almeno una delle due direzioni, e vale il minimo
    dei due pesi. (g + g.T raddoppierebbe gli archi reciproci: tutte le
    distanze tra buoni amici verrebbero doppie.)"""
    t = g.T.tocsr()
    # Dove un lato è zero (arco assente) vince l'altro; dove ci sono
    # entrambi vince il minore.
    a, b = g.tocoo(), t.tocoo()
    d: dict[tuple[int, int], float] = {}
    for r, c, v in zip(np.concatenate([a.row, b.row]), np.concatenate([a.col, b.col]),
                       np.concatenate([a.data, b.data])):
        key = (int(r), int(c))
        d[key] = min(v, d.get(key, np.inf))
    righe, colonne = zip(*d) if d else ((), ())
    return sparse.csr_matrix((list(d.values()), (righe, colonne)), shape=g.shape)
