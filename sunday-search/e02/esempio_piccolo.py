"""L'albero piccolo della free E02: adjacency list e nested set nella stessa tabella, in DuckDB."""
import duckdb

# (id, nome, genitore)
NODI = [
    (1, "Biblioteca", None),
    (2, "Narrativa", 1),
    (3, "Italiana", 2),
    (4, "Calvino", 3),
    (5, "Morante", 3),
    (6, "Inglese", 2),
    (7, "Carroll", 6),
    (8, "Saggistica", 1),
    (9, "Informatica", 8),
    (10, "Storia", 8),
]

def numera(nodi):
    figli = {}
    for i, _, g in nodi:
        figli.setdefault(g, []).append(i)
    lft, rgt = {}, {}
    contatore = 1
    def visita(n):
        nonlocal contatore
        lft[n] = contatore; contatore += 1
        for f in figli.get(n, []):
            visita(f)
        rgt[n] = contatore; contatore += 1
    visita(1)
    return lft, rgt

lft, rgt = numera(NODI)
con = duckdb.connect()
con.execute("CREATE TABLE catalogo (id INT, nome TEXT, genitore INT, lft INT, rgt INT)")
con.executemany("INSERT INTO catalogo VALUES (?,?,?,?,?)",
                [(i, n, g, lft[i], rgt[i]) for i, n, g in NODI])
print(con.sql("SELECT id, nome, genitore, lft, rgt FROM catalogo ORDER BY lft"))

print("adjacency: sotto Narrativa")
print(con.sql("""
WITH RECURSIVE sotto(id, nome, livello) AS (
    SELECT id, nome, 0 FROM catalogo WHERE nome = 'Narrativa'
    UNION ALL
    SELECT c.id, c.nome, s.livello + 1
    FROM catalogo c JOIN sotto s ON c.genitore = s.id
)
SELECT nome, livello FROM sotto ORDER BY livello, nome"""))

print("nested set: sotto Narrativa")
print(con.sql("""
SELECT figlio.nome
FROM catalogo AS padre, catalogo AS figlio
WHERE padre.nome = 'Narrativa'
  AND figlio.lft BETWEEN padre.lft AND padre.rgt
ORDER BY figlio.lft"""))

print("nested set: antenati di Carroll")
print(con.sql("""
SELECT antenato.nome
FROM catalogo AS antenato, catalogo AS nodo
WHERE nodo.nome = 'Carroll'
  AND nodo.lft BETWEEN antenato.lft AND antenato.rgt
ORDER BY antenato.lft"""))

print("nested set: foglie e numero di discendenti")
print(con.sql("""
SELECT nome, (rgt - lft - 1) // 2 AS discendenti, rgt = lft + 1 AS foglia
FROM catalogo ORDER BY lft"""))

print("insert Ginzburg sotto Italiana: righe toccate dal nested set")
print(con.sql("""
SELECT count(*) FILTER (WHERE rgt >= (SELECT rgt FROM catalogo WHERE nome='Italiana')) AS rgt_spostati,
       count(*) FILTER (WHERE lft >  (SELECT rgt FROM catalogo WHERE nome='Italiana')) AS lft_spostati,
       count(*) AS totale
FROM catalogo"""))

