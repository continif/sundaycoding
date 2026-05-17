# Validazione Qualità Aria Milano con Pandera

[![Substack](https://img.shields.io/badge/Substack-Sunday%20Coding-orange?style=for-the-badge&logo=substack)](https://sundaycoding.substack.com/p/sunday-coding-anno-nuovo-coi-bot)

Esempio standalone di validazione di un CSV Open Data con [Pandera](https://pandera.readthedocs.io), applicato al dataset della qualità dell'aria del Comune di Milano.

> 📰 **Questo codice è spiegato passo passo nella newsletter** [Pandera, il braccio destro dei validatori](https://sundaycoding.substack.com/p/pandera-il-braccio-destro-dei-validatori) — speciale di **Sunday Coding** dedicato alla validazione dichiarativa dei DataFrame.
>
> Se vuoi capire **perché** il codice è scritto così e non in un altro modo, leggi prima la newsletter: questo repository è il companion code, non un tutorial autosufficiente.

---

## Cosa fa

Lo script `validazione-qaria-milano.py` mostra come usare Pandera per validare in modo dichiarativo un CSV reale, scaricabile dal portale Open Data del Comune di Milano:

- carica il CSV grezzo come stringhe (`dtype=str`) per evitare type inference indesiderato,
- valida la presenza, l'ordine e il formato delle quattro colonne attese (`stazione_id`, `data`, `inquinante`, `valore`),
- usa la modalità `lazy=True` di Pandera per raccogliere **tutti** gli errori in un colpo solo, non solo il primo,
- separa le righe valide da quelle quarantenate, restituendole come due DataFrame distinti,
- stampa un report sintetico con conteggi e percentuali di quarantena.

È un esempio minimale e leggibile, pensato per essere copiato, eseguito e modificato. Niente boilerplate, niente magia.

---

## Dataset

[Rilevazione qualità aria 2026 — Comune di Milano](https://dati.comune.milano.it/dataset/ds2969-rilevazione-qualita-aria-2026)

Licenza: **CC-BY 4.0**. Il filename del CSV cambia ogni giorno (es. `qaria_datoariagiornostazione_2026-03-26.csv`), quindi sostituisci il path nello script con quello che hai scaricato.

---

## Setup

Requisiti: Python 3.10+

```bash
pip install pandas pandera
```

---

## Uso

1. Scarica il CSV dal portale di Milano (link sopra).
2. Modifica la riga di `pd.read_csv(...)` nello script col path del tuo file.
3. Esegui:

```bash
python validazione-qaria-milano.py
```

Output atteso (su un file pulito):

```
Totale righe lette: 247
  → valide:        247
  → quarantenate:  0
  → quarantena %:  0.0%
```

Per vedere Pandera all'opera, prova a corrompere a mano qualche riga del CSV — cambia un valore in `abc`, inserisci un inquinante inventato tipo `PLUTONIO`, inverti due colonne — e rilancia.

---

## Cosa c'è dentro (in breve)

- **Schema dichiarativo** (`DataFrameSchema`) per le quattro colonne, con check `str_matches` per i formati e `isin` per i set chiusi.
- **`strict=True` + `ordered=True`** per rifiutare colonne extra e ordini inattesi.
- **`lazy=True`** nella validazione per accumulare tutti gli errori invece di sollevare al primo.
- **Estrazione delle righe sporche** da `exc.failure_cases` per costruire la quarantena.

Tutta la teoria — perché `dtype=str`, perché `keep_default_na=False`, perché `lazy=True`, quando Pandera **non** è la risposta giusta — è nella newsletter linkata in cima.

---

## Sunday Coding

Questo repository fa parte del progetto **[Sunday Coding](https://sundaycoding.substack.com)**, la newsletter della domenica sul Data Engineering e dintorni: una domenica mattina, un pezzo di codice commentato senza orpelli e con qualche battuta da nerd.

Lo speciale Pandera è un complemento gratuito alla serie seria in abbonamento **La Pipeline Perfetta**, in particolare alla puntata **S03E02 — Validation & Cleansing**, dove costruiamo intorno a Pandera tutto l'apparato di una pipeline di validazione vera: quarantena, soglie, classificazione errori, audit trail, e confronto motivato tra tre approcci (a mano, Pandera puro, ibrido).

📬 [Iscriviti al Sunday Coding](https://sundaycoding.substack.com)

---

## Licenza

MIT. Fai quello che vuoi, basta che non lo spacci per tuo. Il dato sorgente del Comune di Milano è CC-BY 4.0: se lo riusi, ricordati di citarlo.

