# Il manuale segreto del 'Data Wrangling' elegante. #4

[![Substack](https://img.shields.io/badge/Substack-Sunday%20Coding-orange?style=for-the-badge&logo=substack)](https://sundaycoding.substack.com/p/il-manuale-segreto-del-data-wrangling-4)

Questo repository contiene un dataset di circa **300.000 righe uniche** estratte da log di elaborazione veicoli datati 2025. Per ottimizzare la distribuzione, il file CSV è stato compresso e suddiviso in 99 segmenti.

## 📦 Struttura dei File
I file sono stati generati tramite una procedura di splitting binario. Troverai 99 archivi numerati:
- `data-wrangling-01.zip`
- `data-wrangling-02.zip`
- ...
- `data-wrangling-99.zip`

**Nota bene:** I file singolarmente non possono essere aperti come normali archivi ZIP. Devono prima essere riuniti nel file originale.

---

## 🛠 Istruzioni per la Ricostruzione

Segui questi passaggi dal terminale (Linux, macOS o WSL su Windows).

### 1. Unire i frammenti
Posizionati nella cartella contenente i file e utilizza il comando `cat` per concatenare i segmenti in un unico archivio:

```bash
cat data-wrangling-*.zip > dataset_completo.zip
```

### 2. Estrarre il file CSV
Una volta creato l'archivio unico, scompatta il contenuto per ottenere il CSV finale:

```bash
unzip dataset_completo.zip
```

### 3. (Opzionale) Pulizia rapida
Per unire, estrarre e pulire i file temporanei in un colpo solo, puoi usare:
```bash
cat data-wrangling-*.zip > full.zip && unzip full.zip && rm full.zip
```

---

## 📊 Dettagli del Dataset
Il file finale `filtered_unique.csv` è stato pulito rimuovendo dati ridondanti (url, source, plate) e mantenendo le seguenti 24 colonne:

| Nome Colonna | Descrizione |
| :--- | :--- |
| `name` | Titolo identificativo dell'annuncio |
| `manufacturer` | Produttore del veicolo |
| `brand` | Marca |
| `model` | Modello specifico |
| `description` | Descrizione testuale |
| `doors` / `seats` | Numero porte e posti a sedere |
| `color` / `interior_color` | Colori esterni ed interni |
| `registration` | Anno/Mese di immatricolazione |
| `engineSize` / `power` | Cilindrata e potenza (CV/kW) |
| `fuel` / `engineType` | Tipo di alimentazione e motore |
| `mileage` | Chilometri percorsi |
| `price` / `currency` | Prezzo di vendita e valuta |
| `status` | Stato del veicolo (usato, nuovo, km0) |
| `optionals` | Elenco degli accessori inclusi |

---

## ⚠️ Troubleshooting
- **File mancanti:** Verifica che il numero totale dei file sia esattamente 99 con il comando:  
  `ls data-wrangling-*.zip | wc -l`
- **Errore Unzip:** Se ricevi un errore di tipo "End-of-central-directory signature not found", significa che uno dei segmenti non è stato scaricato completamente o l'unione tramite `cat` è fallita.
