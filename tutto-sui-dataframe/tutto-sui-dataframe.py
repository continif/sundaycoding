import pandas as pd
from contextlib import contextmanager
import time

@contextmanager
def timer(etichetta):
    """
    Un cronometro svizzero per umiliare il codice lento. 
    Se un'operazione ci mette troppo, qui lo vedremo nero su bianco.
    """
    inizio = time.perf_counter()
    yield
    fine = time.perf_counter()
    print(f"\n[{etichetta}] Tempo: {fine - inizio:.6f} s\n")

# Carichiamo i dati come farebbe chiunque non abbia ancora letto questo articolo
df = pd.read_csv('csv/20241225/list.csv')

# Moltiplichiamo i dati x1000: benvenuti nel mondo reale. 
# Se il tuo codice regge qui, regge ovunque.
df = pd.concat([df] * 1000, ignore_index=True) 

# Verifichiamo il "peso" del nostro neonato. Spoiler: è un ciccione.
memoria_totale = df.memory_usage(deep=True).sum()
print(f"Il DataFrame occupa {memoria_totale / 1024**2:.2f} MB")

# Togliamo la targa ('plate'). 
# Non ci serve e occupa spazio come un SUV in centro città.
# Usiamo 'del' perché siamo pigri e vogliamo che sparisca subito.
del df['plate']

# Vediamo se la dieta ha funzionato
memoria_totale = df.memory_usage(deep=True).sum()
print(f"Il DataFrame senza 'plate' occupa {memoria_totale / 1024**2:.2f} MB")

# Un po' di statistiche per sentirci dei veri Data Scientist
print("Ci sono "+str(df['manufacturer'].nunique()) + " marchi diversi.")
print(df['manufacturer'].value_counts())

print( "QUERY GENERICHE " + ('='*50))
# La tecnica "Brute Force": chiediamo a Pandas di guardare ogni singola riga.
# È come cercare un ago in un pagliaio spostando un filo d'erba alla volta.
with timer("Query su Opel "+(':'*5) ):
    risultato = df.loc[df['manufacturer'] == 'Opel', ['name', 'model']]

# Cerchiamo l'Astra col metodo AND (&). 
# Doppio controllo, doppia fatica per la CPU.
with timer("Query su Opel Astra "+(':'*5) ):
    risultato = df.loc[(df['manufacturer'] == 'Opel') & (df['model'] == 'Astra'), ['name', 'model']]


print( "QUERY TRICK 1 " + ('='*50))
# Puliamo tutto e ripartiamo. Stavolta facciamo i seri.
del df
df = pd.read_csv('csv/20241225/list.csv')
del df['plate']
df = pd.concat([df] * 1000, ignore_index=True) 

# TRUCCO 1: L'Indice.
# Trasformiamo Manufacturer e Model nelle "coordinate" della tabella.
# È come mettere le etichette agli scaffali del magazzino.
df.set_index(['manufacturer', 'model'], inplace=True)

# Fondamentale: se non ordini l'indice, Pandas si arrabbia e rallenta.
# Ordinare è cortesia, ma qui è pure performance.
df.sort_index(inplace=True)

memoria_totale = df.memory_usage(deep=True).sum()
print(f"Con l'indice (senza ancora categorie) il DataFrame occupa {memoria_totale / 1024**2:.2f} MB")

# Cerchiamo Opel usando l'indice. 
# Pandas ora non "cerca", ma "va a colpo sicuro".
with timer("Query su Opel "+(':'*5) ):
    risultato = df.loc[[('Opel')]] 

# Accesso chirurgico alle Opel Astra tramite Tupla. 
# La velocità della luce è vicina.
with timer("Query su Opel Astra "+(':'*5) ):
    risultato = df.loc[[('Opel', 'Astra')]] 


print( "QUERY TRICK 2 " + ('='*50))
# TRUCCO 2: La "Chirurgia Estetica".
# Non carichiamo nemmeno quello che non ci serve. 
# Entriamo in memoria già magri.
del df
colonne_utili = ['manufacturer', 'model', 'name']

with timer("Estrazione dei dati"):
    # Leggiamo solo le colonne utili: risparmio di RAM istantaneo.
    df = pd.read_csv('csv/20241225/list.csv', usecols=colonne_utili)
    df = pd.concat([df] * 1000, ignore_index=True)

# TRUCCO FINALE: Le Categorie.
# Invece di scrivere "Volkswagen" 269.000 volte, usiamo un codice numerico.
# È come usare i gettoni al posto delle banconote: pesano meno.
df['manufacturer'] = df['manufacturer'].astype('category')

# Re-impostiamo l'indice sulla versione "light" del DataFrame
df.set_index(['manufacturer', 'model'], inplace=True)
df.sort_index(inplace=True)

memoria_totale = df.memory_usage(deep=True).sum()
print(f"Ora il DataFrame occupa solo {memoria_totale / 1024**2:.2f} MB. Praticamente invisibile!")

# Ultimo test: la velocità di una gazzella con la memoria di un elefante.
with timer("Query su Opel "+(':'*5) ):
    risultato = df.loc[[('Opel')]]

with timer("Query su Opel Astra "+(':'*5) ):
    risultato = df.loc[[('Opel', 'Astra')]]
