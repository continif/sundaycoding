"""
SundayCodingAlerting — Alerting unificato per pipeline.

Supporta Telegram, Google Chat, e un FakeChat di fallback per sviluppo.

Variabili d'ambiente lette dalla factory get_chat():
  TELEGRAM_TOKEN, TELEGRAM_CHAT_ID    -> usa Telegram
  GCHAT_WEBHOOK_URL                    -> usa Google Chat
  (nessuna)                            -> usa FakeChat (scrive su disco)

Documentazione per il setup dei canali:
  Telegram:    https://core.telegram.org/bots/tutorial
  Google Chat: https://developers.google.com/workspace/chat/quickstart/webhooks

Licenza: MIT
Repository: https://github.com/continif/sundaycoding-alerting
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

import requests

log = logging.getLogger("sundaycoding_alerting")

Livello = Literal["info", "warning", "critical"]


class ChatClient(ABC):
    """
    Classe base astratta per un client di alerting.

    Le sottoclassi devono implementare SOLO _invia(testo).
    Tutto il resto (retry, deduplicazione, formattazione) è già qui,
    ereditato gratuitamente.

    Questo è il classico pattern Template Method: il metodo pubblico
    send() definisce l'algoritmo (dedup -> format -> retry -> invia),
    la sottoclasse specializza solo il passo finale.
    """

    # Parametri di default per retry e dedup. Sono attributi di classe,
    # ma se vi servono diversi per uno specifico client basta ridefinirli
    # nella sottoclasse o passarli al costruttore.
    DEDUP_LOG_PATH = Path(".alerts_sent.jsonl")
    FINESTRA_DEDUP_ORE = 6
    TENTATIVI_MAX = 3
    ATTESA_INIZIALE_SEC = 5.0
    FATTORE_BACKOFF = 3.0

    @abstractmethod
    def _invia(self, testo: str) -> None:
        """
        Spedisce effettivamente il messaggio sul canale.
        Lancia un'eccezione (di solito requests.RequestException)
        se la spedizione fallisce.

        Le sottoclassi DEVONO implementare questo metodo.
        """
        ...

    @property
    @abstractmethod
    def nome_canale(self) -> str:
        """Nome leggibile del canale, usato nei log."""
        ...

    def send(
        self,
        titolo: str,
        messaggio: str,
        livello: Livello = "warning",
        chiave_dedup: Optional[str] = None,
    ) -> dict:
        """
        API pubblica: spedisce un alert con retry e dedup.

        chiave_dedup: stringa che identifica univocamente il TIPO di alert.
            Es. 'qaria:validations:threshold_exceeded'.
            Se nelle ultime FINESTRA_DEDUP_ORE è già stato mandato un alert
            con la stessa chiave, questo viene SOPPRESSO.
            Se None, niente deduplicazione.
        """
        # 1. Dedup: controlla se già inviato di recente
        if chiave_dedup and self._gia_inviato_di_recente(chiave_dedup):
            log.info(
                f"[{self.nome_canale}] Alert '{chiave_dedup}' soppresso (dedup)"
            )
            return {"status": "suppressed", "chiave": chiave_dedup}

        # 2. Formattazione: emoji + grassetto per il titolo
        emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}[livello]
        testo_completo = f"{emoji} *{titolo}*\n\n{messaggio}"

        # 3. Invio con retry
        esito = self._invia_con_retry(testo_completo)

        # 4. Se è andato a buon fine, registra la dedup
        if chiave_dedup and esito.get("ok"):
            self._registra_inviato(chiave_dedup)

        return {"status": "sent", "canale": self.nome_canale, **esito}

    def _invia_con_retry(self, testo: str) -> dict:
        """
        Loop di retry con backoff esponenziale.
        Ritenta solo su errori transitori (network o 5xx).
        I 4xx (token sbagliato, ecc.) NON si ritentano: sono strutturali.
        """
        attesa = self.ATTESA_INIZIALE_SEC
        esito_finale = {"ok": False, "errore": "no_attempts"}
        for tentativo in range(1, self.TENTATIVI_MAX + 1):
            try:
                self._invia(testo)
                return {"ok": True, "tentativo": tentativo}
            except requests.exceptions.RequestException as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status and 400 <= status < 500:
                    log.error(
                        f"[{self.nome_canale}] Errore {status} non ritentabile: {e}"
                    )
                    return {"ok": False, "errore": str(e), "status": status}
                esito_finale = {"ok": False, "errore": str(e)}
                if tentativo < self.TENTATIVI_MAX:
                    log.warning(
                        f"[{self.nome_canale}] Tentativo {tentativo} fallito ({e}), "
                        f"riprovo tra {attesa}s"
                    )
                    time.sleep(attesa)
                    attesa *= self.FATTORE_BACKOFF
                else:
                    log.error(f"[{self.nome_canale}] Esauriti i tentativi: {e}")
        return esito_finale

    def _gia_inviato_di_recente(self, chiave: str) -> bool:
        if not self.DEDUP_LOG_PATH.exists():
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.FINESTRA_DEDUP_ORE)
        with self.DEDUP_LOG_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec["chiave"] != chiave:
                        continue
                    ts = datetime.fromisoformat(rec["ts_utc"])
                    if ts >= cutoff:
                        return True
                except (json.JSONDecodeError, KeyError):
                    continue
        return False

    def _registra_inviato(self, chiave: str) -> None:
        record = {
            "chiave": chiave,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "canale": self.nome_canale,
        }
        with self.DEDUP_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class TelegramChat(ChatClient):
    """
    Client Telegram. Spedisce via Bot API.

    Setup del bot e ottenimento del chat_id:
      https://core.telegram.org/bots/tutorial

    Variabili d'ambiente richieste:
      TELEGRAM_TOKEN     (il token che vi dà BotFather)
      TELEGRAM_CHAT_ID   (l'ID della chat di destinazione)
    """

    nome_canale = "telegram"

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def _invia(self, testo: str) -> None:
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": testo,
            "parse_mode": "Markdown",
        }
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()


class GoogleChat(ChatClient):
    """
    Client Google Chat. Spedisce via webhook in arrivo.

    Setup del webhook nello space:
      https://developers.google.com/workspace/chat/quickstart/webhooks

    Variabili d'ambiente richieste:
      GCHAT_WEBHOOK_URL  (URL completo del webhook con key e token)
    """

    nome_canale = "google_chat"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _invia(self, testo: str) -> None:
        payload = {"text": testo}
        r = requests.post(self.webhook_url, json=payload, timeout=10)
        r.raise_for_status()


class FakeChat(ChatClient):
    """
    Client di fallback. Non spedisce niente: scrive l'alert su un file
    locale. Pensato per sviluppo, test, e per chi vuole vedere come
    funziona la libreria senza configurare un canale reale.

    Il file di destinazione di default è 'fake_alerts.log' nella cwd.
    """

    nome_canale = "fake"

    def __init__(self, output_path: Path = Path("fake_alerts.log")):
        self.output_path = output_path

    def _invia(self, testo: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with self.output_path.open("a", encoding="utf-8") as f:
            f.write(f"--- {ts} ---\n{testo}\n\n")
        log.info(f"[fake] Alert scritto su {self.output_path}")


def get_chat() -> ChatClient:
    """
    Factory: ritorna il client di alerting appropriato in base
    alle variabili d'ambiente disponibili.

    Priorità (la prima che matcha vince):
      1. TELEGRAM_TOKEN + TELEGRAM_CHAT_ID -> TelegramChat
      2. GCHAT_WEBHOOK_URL                  -> GoogleChat
      3. nessuna delle precedenti           -> FakeChat

    Perché la priorità a Telegram?
    Perché è il canale personale, e se uno sviluppatore se lo configura
    sulla propria macchina di sviluppo è perché vuole che gli alert
    arrivino A LUI. Google Chat è il canale aziendale di produzione,
    e se sono in dev locale probabilmente NON voglio mandare alert
    nel canale del team. Ordine difensivo, non capriccio.
    """
    telegram_token = os.environ.get("TELEGRAM_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if telegram_token and telegram_chat_id:
        log.info("Alerter: uso TelegramChat (da variabili d'ambiente)")
        return TelegramChat(telegram_token, telegram_chat_id)

    gchat_webhook = os.environ.get("GCHAT_WEBHOOK_URL")
    if gchat_webhook:
        log.info("Alerter: uso GoogleChat (da variabile d'ambiente)")
        return GoogleChat(gchat_webhook)

    log.warning(
        "Alerter: nessun canale configurato, uso FakeChat (scrive su disco)"
    )
    return FakeChat()


__all__ = [
    "ChatClient",
    "TelegramChat",
    "GoogleChat",
    "FakeChat",
    "get_chat",
    "Livello",
]
