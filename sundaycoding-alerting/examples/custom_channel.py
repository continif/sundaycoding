"""
custom_channel.py — Esempio di come aggiungere un canale custom.

Mostra come scrivere una nuova classe che eredita da ChatClient
per supportare Slack (o qualunque altro servizio con webhook simile).

Sintassi del webhook Slack:
    https://api.slack.com/messaging/webhooks
"""

import logging
import os

import requests

from sundaycoding_alerting import ChatClient

logging.basicConfig(level=logging.INFO)


class SlackChat(ChatClient):
    """
    Client Slack via Incoming Webhook.

    Setup del webhook:
      https://api.slack.com/messaging/webhooks

    Variabile d'ambiente:
      SLACK_WEBHOOK_URL
    """

    nome_canale = "slack"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _invia(self, testo: str) -> None:
        # Slack accetta lo stesso payload base {"text": ...} di Google Chat.
        # Per messaggi ricchi si usa "blocks", ma qui ci basta il testo.
        r = requests.post(self.webhook_url, json={"text": testo}, timeout=10)
        r.raise_for_status()


def main():
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL non configurato. Imposta la variabile e riprova.")
        return

    chat = SlackChat(webhook)
    chat.send(
        titolo="Pipeline qaria-milano",
        messaggio="Test di un canale custom su Slack.",
        livello="info",
    )
    print(f"Alert spedito su {chat.nome_canale}")


if __name__ == "__main__":
    main()
