# [Sunday Coding] Dataframe: Tutto quello che avresti dovuto sapere (e non hai mai chiesto)

Benvenuti in questo appuntamento di **Sunday Coding**. In questo modulo esploriamo come ottimizzare la gestione di grandi moli di dati in Pandas, passando da un approccio "brute force" a tecniche professionali di gestione della memoria e della velocità di esecuzione.

## 📖 Articolo Completo
Per una spiegazione dettagliata della filosofia dietro questo codice e dei trade-off ingegneristici, leggi il post originale:
👉 **[Sunday Coding su Substack](https://sundaycoding.substack.com/p/sunday-coding-dataframe-tutto-quello)**

## 🚀 Panoramica delle Ottimizzazioni
L'obiettivo è trasformare un "bradipo digitale che mangia RAM" in un software scalabile e leggero. Nei test effettuati su un dataset di **3 milioni di record**, abbiamo ottenuto i seguenti risultati:

| Metodo | Occupazione RAM | Tempo Query (Opel Astra) | Verdetto |
| :--- | :--- | :--- | :--- |
| **Principiante (Brute Force)** | ~6 GB | 0.257 s | Inefficiente e rischioso |
| **Trick 1 (MultiIndex)** | ~5.7 GB | 0.035 s | Rapido ma ancora "obeso" |
| **Trick 2 (Pro Optimization)** | **256 MB** | **0.018 s** | **Rapido e leggero** |



### 🛠 Tecniche Utilizzate

1. **Indicizzazione Gerarchica (MultiIndex):** Invece di scansionare ogni riga, abbiamo creato una gerarchia (dei "cassetti") per accedere direttamente ai dati.
2. **Caricamento Selettivo (`usecols`):** Abbiamo caricato in memoria solo le colonne strettamente necessarie ("ce ripigliamm solo chell che ce sirv").
3. **Ottimizzazione dei Tipi (`category`):** Trasformazione dei nomi ripetitivi in codici numerici per abbattere drasticamente l'uso della RAM.



## 💻 Requisiti
* Python 3.x
* Pandas

## 📝 Conclusione
> "È la differenza tra un pensare ad un software che scala o pensare ad uno che implode non appena il business decide di aggiungere qualche riga in più al database o se hai più di 1 accesso concorrente."

---
© 2026 Francesco Contini - Sunday Coding
