from functools import cached_property, lru_cache
import atexit
import time

class ProgettoPigro:
    @cached_property
    def operazione_lunga_e_pesante(self):
        """Operazioni lunghissime, tipo connessione+query+lavorazione dei dati per restituire una stringa o un dizionario che non cambierà mai più"""
        ...
        return dati

    @property
    def proprieta_finta(self):
        """Accedere come se fosse una proprietà, ma invece è una funzione!"""
        return self.base*self.altezza

@lru_cache(maxsize=100000)
def calcolo_che_non_voglio_rifare_tutte_le_volte(n):
    """Ad esempio è utile per non mandare la CPU al 100% ad ogni run"""
    if n < 2:
        return n
    return calcolo_che_non_voglio_rifare_tutte_le_volte(n-1) + calcolo_che_non_voglio_rifare_tutte_le_volte(n-2)

@atexit.register
def addio():
    """Chiudo file, chiudo connessioni, mando email, mi ricordo di spegnere le luci e chiudo il gas prima di uscire di casa"""
    self.casa.gas.close()
    self.casa.luci.close()
    self.casa.porta.close()


# logger: il logger logga... qui con delle semplici print, ma potete metterci quello che vi serve
def logger(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"--- [LOG] Chiamata a: {func.__name__} con {args} ---")
        risultato = func(*args, **kwargs)
        print(f"--- [LOG] {func.__name__} ha terminato con successo ---")
        return risultato
    return wrapper

# timing: Cronometra l'esecuzione
def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        inizio = time.perf_counter()
        risultato = func(*args, **kwargs)
        fine = time.perf_counter()
        print(f"--- [TIMER] Tempo impiegato: {fine - inizio:.4f} secondi ---")
        return risultato
    return wrapper

# login_required: Simula un controllo accessi, nel mondo vero ci metti sessioni o token JWT, qui usiamo una varibilona
UTENTE_AUTENTICATO = False 

def login_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not UTENTE_AUTENTICATO:
            print("--- [AUTH] Errore: Devi loggarti per usare questa funzione! ---")
            return None # O lancia un'eccezione PermissionError
        return func(*args, **kwargs)
    return wrapper

# Come si usano?
@login_required
@logger
@timing
def operazione_segreta_e_lenta():
    print("Eseguendo calcoli complessi (molto segreti)...")
    time.sleep(1.5)
    return "Dati Sensibili Recuperati"

# --- TEST ---
print("--- TEST 1: Utente non loggato ---")
operazione_segreta_e_lenta()

print("\n--- TEST 2: Utente loggato ---")
UTENTE_AUTENTICATO = True
operazione_segreta_e_lenta()
