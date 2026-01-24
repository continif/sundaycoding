# Vatti a fidare dell'IA 🤖

Benvenuti in questa sezione del progetto **Sunday Coding**. In questa directory troverete il codice e i dati relativi all'esperimento descritto nell'articolo: 
👉 [**Sunday Coding: Modello bello che non balla**](https://sundaycoding.substack.com/p/sunday-coding-modello-bello-che-non?utm_campaign=post&utm_medium=github)

## Di cosa si tratta?

In questa puntata di Sunday Coding, dopo i problemi di potenza di calcolo riscontrati in precedenza (PC che si spegne sul più bello!), ho esplorato alternative più leggere per analizzare il traffico di rete.

L'incipit dell'esperimento:
> "Allora, vi ricordate la puntata precedente? Quella in cui mi si spegneva il pc durante l’esecuzione dello script? I giorni successivi ho studiato un po’ di alternative. Ne ho trovate un paio che non hanno bisogno di tanta potenza di calcolo e tra queste ci sono i tanti algoritmi per la rilevazione di anomalie. L’idea è che se gli passo tutti le chiamate fatte da bot e malware una chiamata buona dovrebbe identificarmela come anomalia, e anche sapere il grado di anomalia! Tra gli algoritmi che si occupano di anomaly detection quello che consuma meno macchina è l’Isolation Forest di Scikit-Learn, e allora che non lo vai a provare?"

## Contenuto della Directory

- **Codice**: Script Python per l'implementazione dell'algoritmo **Isolation Forest** (Scikit-Learn).
- **Dati**: I dataset utilizzati per addestrare il modello e testare la rilevazione delle anomalie tra traffico malevolo e chiamate "buone".

## Obiettivo

Testare se un modello di Anomaly Detection, solitamente usato per trovare l'intruso in un ambiente sicuro, possa funzionare al contrario: identificare una chiamata legittima come "anomalia" all'interno di un mare di traffico generato da bot e malware.

---
*Segui il blog su [Sunday Coding Substack](https://sundaycoding.substack.com/)*
