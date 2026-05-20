# SundayCodingAlerting

Una piccola libreria Python per spedire alert da una pipeline di dati su **Telegram** (canale personale), **Google Chat** (canale aziendale), o un **FakeChat** locale (sviluppo). Retry automatico con backoff esponenziale, deduplicazione temporale degli alert, factory che sceglie il canale giusto in base alle variabili d'ambiente.

> 📰 **Questa libreria è spiegata passo passo nella newsletter** [Chi sveglia chi: alerting con Telegram e Google Chat](https://sundaycoding.substack.com) — speciale gratuito del **Sunday Coding** che fa da gemella della puntata a pagamento [S03E05 — Observability](https://sundaycoding.substack.com).
>
> Se vuoi capire **perché** la libreria è strutturata così e non in un altro modo, leggi prima la newsletter: questo repository è il companion code, non un tutorial autosufficiente.

---

## Cosa fa

- Ti permette di scrivere `chat.send(titolo, messaggio)` una volta sola nel codice, e fa arrivare l'alert sul canale giusto in base a come è configurato l'ambiente.
- **Telegram** (canale personale, ideale per progetti individuali e freelance) — push notification sul telefono via Bot API.
- **Google Chat** (canale aziendale, ideale per team che usano Google Workspace) — webhook in arrivo nello space del team.
- **FakeChat** (fallback per sviluppo) — scrive gli alert su un file locale, così la pipeline funziona anche senza configurare nessun canale reale.
- **Retry automatico** con backoff esponenziale (10s, 30s, 90s) solo per errori transitori (network glitch, 5xx). Gli errori 4xx (token sbagliato, chat_id non valido) falliscono subito.
- **Deduplicazione temporale**: lo stesso alert non viene spedito due volte entro una finestra configurabile (default 6 ore).

---

## Installazione

```bash
git clone https://github.com/continif/sundaycoding-alerting.git
cd sundaycoding-alerting
pip install -e .
```

Oppure, se preferisci il bricolage, copia il singolo file `sundaycoding_alerting/__init__.py` nel tuo progetto. La libreria è volutamente piccola e autosufficiente.

---

## Uso rapido

```python
from sundaycoding_alerting import get_chat

# La factory sceglie il canale giusto in base alle variabili d'ambiente.
chat = get_chat()

# Da qui in poi non ti importa più quale canale sia: l'API è la stessa.
chat.send(
    titolo="Pipeline qaria-milano",
    messaggio="Strato validations: success rate sotto soglia (62% < 90%).",
    livello="warning",                              # 'info', 'warning', 'critical'
    chiave_dedup="qaria:validations:low_success",   # dedup per 6 ore
)
```

### Configurazione via variabili d'ambiente

**Per usare Telegram** (canale personale):

```bash
export TELEGRAM_TOKEN="8472639481:AAH-..."
export TELEGRAM_CHAT_ID="123456789"
python my_pipeline.py
```

Setup del bot e chat_id: [core.telegram.org/bots/tutorial](https://core.telegram.org/bots/tutorial).

**Per usare Google Chat** (canale aziendale, richiede Google Workspace):

```bash
export GCHAT_WEBHOOK_URL="https://chat.googleapis.com/v1/spaces/AAAA.../messages?key=...&token=..."
python my_pipeline.py
```

Setup del webhook nello space: [developers.google.com/workspace/chat/quickstart/webhooks](https://developers.google.com/workspace/chat/quickstart/webhooks).

**Per usare FakeChat** (sviluppo locale, default automatico):

```bash
# Niente da configurare. La libreria scrive su 'fake_alerts.log' nella cwd.
python my_pipeline.py
cat fake_alerts.log
```

---

## Architettura

Cinque componenti:

| Classe | Tipo | Ruolo |
|---|---|---|
| `ChatClient` | Abstract Base Class | Definisce il contratto e tutta la logica condivisa (retry, dedup, formattazione) |
| `TelegramChat` | Client concreto | Implementa `_invia()` via Telegram Bot API |
| `GoogleChat` | Client concreto | Implementa `_invia()` via webhook Google Chat |
| `FakeChat` | Client concreto | Implementa `_invia()` scrivendo su file locale |
| `get_chat()` | Factory function | Sceglie il client giusto in base alle env vars |

Pattern usati:

- **Abstract Base Class** con `@abstractmethod` (Python ti impedisce di istanziare la base).
- **Template Method**: la classe base ha l'algoritmo, le sottoclassi specializzano solo `_invia()`.
- **Factory function**: `get_chat()` torna l'oggetto giusto senza che il chiamante debba decidere.

---

## Estendere con altri canali

Aggiungere Slack, Discord, WhatsApp Business o un client SMTP per email è una manciata di righe. Esempio per Slack:

```python
from sundaycoding_alerting import ChatClient
import requests

class SlackChat(ChatClient):
    nome_canale = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _invia(self, testo: str) -> None:
        r = requests.post(self.webhook_url, json={"text": testo}, timeout=10)
        r.raise_for_status()
```

Aggiungi il check nella factory `get_chat()` per `SLACK_WEBHOOK_URL` e hai un terzo canale supportato. **Pull request benvenute.**

---

## Test

```bash
pip install -e ".[dev]"
pytest tests/
```

---

## Sunday Coding

Questo repository fa parte del progetto **[Sunday Coding](https://sundaycoding.substack.com)**, la newsletter della domenica sul Data Engineering e dintorni: ogni domenica mattina un pezzo di codice commentato, una metafora da impianto idraulico, qualche bestemmia in romanesco.

La libreria nasce come complemento alla puntata **S03E05 — Observability** della serie *La Pipeline Perfetta*. La S03E05 è a pagamento (ti spiega *cosa* misurare, *quando* allertare, e come distinguere falsi positivi da problemi veri). Lo speciale pubblico gemello (gratuito) ti spiega *come* configurare Telegram e Google Chat passo passo, e ti consegna questa libreria pronta all'uso.

📬 [Iscriviti al Sunday Coding](https://sundaycoding.substack.com)

---

## Licenza

MIT. Fai quello che vuoi, basta che non lo spacci per tuo.

---

*Por fin, pipeline che ti svegliano solo quando serve.*
