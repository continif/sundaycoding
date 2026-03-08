# Analisi dei Log con Pandas: Identificare e Bloccare i "Cattivi"

Questo repository fa parte della serie [**Sunday Coding**](https://sundaycoding.substack.com/) e si concentra sull'uso avanzato dei Dataframe di Pandas per analizzare i log dei server web al fine di migliorare la sicurezza.

## Funzionalità del Progetto

Lo script permette di trasformare i log grezzi in informazioni azionabili per proteggere il proprio sito web.

### 1. Parsing e Pulizia dei Dati
*   **Lettura Avanzata**: Utilizza espressioni regolari complesse per suddividere correttamente i campi del file `access.log` di Apache tramite la funzione `pd.read_csv`.
*   **Ottimizzazione**: Il codice pulisce i timestamp e converte i campi numerici come `Status` (codici HTTP) e `Size` per massimizzare le prestazioni.
*   **Indicizzazione**: Il timestamp viene impostato come indice del dataframe per facilitare le analisi basate sul tempo.

### 2. Arricchimento con Dati Geografici e di Rete
*   **Integrazione ASN**: Il sistema associa ogni indirizzo IP al relativo **ASN** (Autonomous System Number), ovvero il codice del provider, e alla nazione di origine.
*   **Utilizzo di MaxMind**: Sfrutta la libreria `geoip2` e i database gratuiti di MaxMind per mappare i dati di rete.

### 3. Rilevamento di Attività Malevole
*   **Anomalie Statistiche**: Identifica picchi di traffico insoliti applicando la regola statistica **68-95-99,7** e calcolando lo **Z-Score** per ogni ASN su finestre temporali di 30 minuti.
*   **Caccia agli Impostori**: Individua client malevoli che fingono di essere crawler legittimi (come Googlebot o bingbot) verificando l'incoerenza tra lo User-Agent dichiarato e l'ASN di provenienza.
*   **Identificazione di Scanner**: Filtra gli IP che tentano di accedere a URL sensibili (es. `.env`, `.git`, `wp-admin`) o che presentano un tasso di errore HTTP (4xx/5xx) superiore al 90%.
*   **Monitoraggio Scraper**: Analizza gli ASN che effettuano un numero elevato di richieste mantenendo un basso tasso di errore.

### 4. Risultati Operativi
*   **Regole di Blocco**: Lo script genera automaticamente una configurazione per il file **.htaccess**, pronta per essere copiata e incollata per inibire l'accesso agli IP dannosi.

## Link Utili
*   **Articolo di Approfondimento**: [Sunday Coding - Dataframe: Tutto quello che avresti dovuto sapere - Parte 3](https://sundaycoding.substack.com/p/sunday-coding-dataframe-tutto-quello-d52)
*   **Repository GitHub**: [Codice Sorgente](https://github.com/continif/sundaycoding/tree/main/dataframe-e-log)

---
*Progetto creato da Francesco Contini per Sunday Coding*.
