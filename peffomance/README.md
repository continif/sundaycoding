# *[Sunday Coding: Peffommance!](https://sundaycoding.substack.com/p/sunday-coding-peffommance)*



L'ottimizzazione delle performance per il processamento dei dati, passando da un'elaborazione lenta a una soluzione centinaia di volte più veloce.

## 📌 Il Problema
Durante la creazione del modello per Astarte, il primo script progettato per arricchire i log di Apache (aggiungendo informazioni sull'IP) ha impiegato **8 ore per elaborare solo 505.000 record**. 
Dovendo gestire un volume totale di circa **21 milioni di righe**, i tempi di attesa iniziali risultavano inaccettabili per proseguire il lavoro.

## 🧪 Benchmark e Soluzioni
L'analisi si è concentrata sulla ricerca del database più efficiente per effettuare lookup di indirizzi IP (IPv4 e IPv6) trasformandoli in dati confrontabili.

### 1. DuckDB (L'approccio iniziale)
*   **Tecnologia:** Integrazione con CSV e Pandas.
*   **Problema:** Necessità di convertire manualmente gli IP in numeri interi per il confronto (specialmente complesso per IPv6) e gestione della concorrenza tramite VIEW.
*   **Performance:** Ordine dei **decimi di secondo** per query.

### 2. MySQL / MariaDB
*   **Tecnologia:** Utilizzo delle funzioni native `INET6_ATON` e `INET6_NTOA` con campi `VARBINARY`.
*   **Miglioramento:** Eliminando la conversione lato codice Python e affidandosi a funzioni native, le operazioni sono diventate più snelle.
*   **Performance:** Ordine dei **centesimi di secondo** (circa 0.036s - 0.044s).

### 3. ClickHouse (Il Vincitore 🏆)
*   **Tecnologia:** Database colonnare con supporto nativo per i tipi di dato `IPv4` e `IPv6`.
*   **Vantaggio:** Non richiede trasformazioni dei dati durante la query, permettendo caricamenti rapidi e letture quasi istantanee.
*   **Performance:** Ordine dei **millesimi di secondo** (media di 0.008s per query).

## 📈 Risultati Finali
Il passaggio da un database relazionale a uno colonnare come ClickHouse ha permesso di aumentare la velocità di esecuzione di **centinaia di volte** rispetto all'implementazione iniziale con DuckDB.

| Database   | Tempo di Risposta (approx) | Guadagno di Performance |
| :---       | :---                       | :---                    |
| DuckDB     | Decimi di secondo          | Base                    |
| MySQL      | Centesimi di secondo       | 10x                     |
| ClickHouse | Millesimi di secondo       | 100x+                   |

## 💡 Lezioni Apprese
*   Il "romanticismo" di programmare tutto da zero (stile anni '80) è affascinante ma inefficiente per grandi volumi di dati moderni.
*   Il principale collo d'bottiglia sono spesso le **operazioni di conversione dei dati**: è preferibile utilizzare tipi di dato nativi della piattaforma.
*   Per operazioni di sola lettura intensiva su dataset massivi, i **database colonnari** come ClickHouse offrono vantaggi strutturali insuperabili.

---
*Contenuto basato sulla newsletter [Sunday Coding: Peffommance!](https://sundaycoding.substack.com/p/sunday-coding-peffommance) di Francesco Contini.*
---
Questo file è stato creato da NotebookLM, per questo è poco divertente e praticamente rende inutile andare a leggere l'articolo originale, che invece è divertentissimo e ha la barzelletta del programmatore che va al supermercato.
