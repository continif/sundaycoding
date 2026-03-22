# Sunday Coding - Dataframe: Tutto quello che avresti dovuto sapere (Parte 5) 🧹

Benvenuti all'ultimo episodio della serie dedicata alla manipolazione chirurgica dei dati con **Pandas** e **NumPy**. [cite_start]In questa puntata esploriamo come trasformare un log grezzo e disordinato in un dataset cristallino, ottimizzando le performance ed eliminando il rumore[cite: 9, 87].

🔗 **Leggi l'articolo completo su Substack:** [Sunday Coding - Dataframe: Tutto quello che avresti dovuto sapere](https://open.substack.com/pub/sundaycoding/p/sunday-coding-dataframe-tutto-quello-0eb?utm_campaign=post-expanded-share&utm_medium=web)

## 📋 Cosa imparerai in questo modulo
[cite_start]Il focus principale è la **Pipeline di Purificazione**, un insieme di tecniche per gestire i dati mancanti, estrarre informazioni strutturate e "purgare" il dataframe dai record inutili[cite: 25, 26].

### 1. Gestione dei Dati Vuoti (Imputazione)
I log spesso usano caratteri segnaposto come il trattino `-`. [cite_start]Impariamo a normalizzarli in `NaN` per poi assegnare valori di default più descrittivi[cite: 29, 30, 57]:
* [cite_start]Trasformazione globale dei trattini in `pd.NA`[cite: 33, 58].
* [cite_start]Utilizzo di `.fillna()` per settare utenti 'guest' o referer 'Direct'[cite: 36, 38, 61].

### 2. Feature Engineering (Estrazione)
[cite_start]Trasformiamo stringhe complesse in colonne categoriche utilizzando il "coltello svizzero" di Pandas: `.str`[cite: 40, 63].
* [cite_start]Estrazione del metodo HTTP (GET/POST) tramite `.split()` o `.replace()`[cite: 43, 64, 68].
* [cite_start]Estrazione automatica delle estensioni dei file con Regex[cite: 47].

### 3. Cancellazione Strategica: Il "Buttafuori" del Dataframe
Andiamo oltre il semplice `.drop()` degli indici. [cite_start]Scopriamo l'efficacia dell'operatore di negazione bitwise **`~`** per filtrare i dati senza modificare l'originale[cite: 73, 74, 75]:
* [cite_start]Eliminazione rapida di errori di Timeout (408) e file a 0 byte[cite: 50, 51, 77].
* [cite_start]Rimozione del rumore tecnico (favicon.ico, robots.txt) tramite maschere booleane[cite: 54, 55].

## 🚀 Perché usare l'operatore `~`?
[cite_start]Mentre la classica `drop` richiede di recuperare gli indici [cite: 69, 71][cite_start], l'operatore `~` agisce come un filtro istantaneo[cite: 74, 76]:
* [cite_start]**Performance:** Più veloce su dataset di grandi dimensioni[cite: 83].
* [cite_start]**Pulizia:** Evita l'uso di `inplace=True` e `.index`, rendendo il codice più leggibile e Pythonico[cite: 78, 87].

---
[cite_start]*Realizzato da Francesco Contini per Sunday Coding.* [cite: 10, 91]
