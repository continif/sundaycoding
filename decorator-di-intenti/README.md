# Decorator di Intenti 🎨

Questo repository contiene il codice d'esempio relativo al post di **Sunday Coding**:
👉 [**Decorator d'intenti: rendere il codice espressivo**](https://sundaycoding.substack.com/p/sunday-coding-decorator-dintenti)

## 📌 Introduzione: Dalle "Lingue Morte" ai Decorator

I decorator hanno radici profonde in linguaggi che oggi potremmo definire "lingue morte" (come il latino o il greco antico), in particolare il **Lisp**. Nato tra gli anni '60 e '70 — gli anni del *Sex, Drugs and Rock&Roll* — il Lisp non ci ha regalato solo i Decorator, ma anche le *Lambda function* e il *Tipo di Dati Dinamico*.

### Cos'è un Decorator?

Secondo la definizione classica della **Gang of Four (GoF)**:
> "Il pattern Decorator consente di aggiungere responsabilità o comportamenti a un oggetto individuale, in modo dinamico e trasparente, senza modificare la struttura della classe originale o utilizzare l’ereditarietà."

Ma per dirla in modo più diretto: **il decorator è una scatola prefabbricata dove schiaffi dentro una funzione per farle fare qualcosa in più, senza toccare una singola riga di codice della funzione originale.**

---

## 📏 La Golden Rule
> *"Se devi scrivere la stessa cosa in più di due funzioni, smetti di scrivere e crea un decorator."*

---

## 🗂️ Le 3 Famiglie di Decorator

Per capire quando usarli, è utile dividerli in categorie logiche:

### 1. Decorator Strutturali (L’Interfaccia)
Cambiano il modo in cui l’utente interagisce con la classe per rendere il codice più pulito.
* `@property`: Trasforma un metodo in un attributo virtuale (utile per validazione).
* `@staticmethod` / `@classmethod`: Definiscono il "raggio d'azione" di un metodo.

### 2. Decorator Computazionali (Performance)
Non cambiano *cosa* fa la funzione, ma *come* viene gestita l'esecuzione per risparmiare risorse.
* `@cached_property`: Calcola il valore una volta sola e lo memorizza.
* `@functools.lru_cache`: Mantiene in memoria gli ultimi $N$ risultati basandosi sugli argomenti.

### 3. Decorator di Servizio (Cross-Cutting / Monitoraggio)
Aggiungono funzionalità che servono a noi sviluppatori per controllare cosa succede (i classici decorator "custom").
* `@logger`: Registra input e output per il debugging.
* `@timer`: Misura il tempo delle operazioni.
* `@login_required`: Controlla i permessi prima di eseguire il codice.

---

## 📖 Approfondimento

Il codice presente in questa cartella (`decorator-di-intenti`) mostra l'applicazione pratica di questi concetti per rendere il codice più espressivo e orientato al dominio.

Per l'analisi completa, i consigli di lettura (comprate il libro della GoF!) e il contesto filosofico dietro questo pattern, leggi l'articolo originale:

🔗 **[Sunday Coding - Decorator d'intenti](https://sundaycoding.substack.com/p/sunday-coding-decorator-dintenti)**

---
*Contenuto ispirato dalla newsletter Sunday Coding.*
