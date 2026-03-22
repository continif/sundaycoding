# Sunday Coding - Dataframe: Tutto quello che avresti dovuto sapere (Parte 5) 🧹

Benvenuti all'ultimo episodio della serie dedicata alla manipolazione chirurgica dei dati con **Pandas** e **NumPy**. In questa puntata esploriamo come trasformare un log grezzo e disordinato in un dataset cristallino, ottimizzando le performance ed eliminando il rumore.

🔗 **Leggi l'articolo completo su Substack:** [Sunday Coding - Dataframe: Tutto quello che avresti dovuto sapere (Parte 5)](https://open.substack.com/pub/sundaycoding/p/sunday-coding-dataframe-tutto-quello-0eb?utm_campaign=post-expanded-share&utm_medium=web)

## 📋 Cosa imparerai in questo modulo
Il focus principale è la **Pipeline di Purificazione**, un insieme di tecniche per gestire i dati mancanti, estrarre informazioni strutturate e "purgare" il dataframe dai record inutili.

### 1. Gestione dei Dati Vuoti (Imputazione)
I log spesso usano caratteri segnaposto come il trattino `-`. Impariamo a normalizzarli in `NaN` per poi assegnare valori di default più descrittivi:
* Trasformazione globale dei trattini in `pd.NA`.
* Utilizzo di `.fillna()` per settare utenti 'guest' o referer 'Direct'.

### 2. Feature Engineering (Estrazione)
Trasformiamo stringhe complesse in colonne categoriche utilizzando il "coltello svizzero" di Pandas: `.str`.
* Estrazione del metodo HTTP (GET/POST) tramite `.split()` o `.replace()`.
* Estrazione automatica delle estensioni dei file con Regex.

### 3. Cancellazione Strategica: Il "Buttafuori" del Dataframe
Andiamo oltre il semplice `.drop()` degli indici. Scopriamo l'efficacia dell'operatore di negazione bitwise **`~`** per filtrare i dati senza modificare l'originale:
* Eliminazione rapida di errori di Timeout (408) e file a 0 byte.
* Rimozione del rumore tecnico (favicon.ico, robots.txt) tramite maschere booleane.

## 🚀 Perché usare l'operatore `~`?
Mentre la classica `drop` richiede di recuperare gli indici , l'operatore `~` agisce come un filtro istantaneo:
* **Performance:** Più veloce su dataset di grandi dimensioni.
* **Pulizia:** Evita l'uso di `inplace=True` e `.index`, rendendo il codice più leggibile e Pythonico.

---
*Realizzato da Francesco Contini per Sunday Coding.* 
PS: ovviamente io non uso parole come Pythonico. Questa è stata un'idea di Gemini, e non ho capito perché dopo tutto questo tempo ancora non ha capito che queste cose io non le faccio.
Pythonico... mah... 
