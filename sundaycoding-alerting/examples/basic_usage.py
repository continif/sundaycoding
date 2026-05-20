"""
basic_usage.py — Esempio minimale di uso di SundayCodingAlerting.

Lancia:
    # Senza variabili d'ambiente (usa FakeChat, scrive su file)
    python basic_usage.py

    # Con Telegram configurato
    TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python basic_usage.py

    # Con Google Chat configurato
    GCHAT_WEBHOOK_URL=... python basic_usage.py
"""

import logging
from sundaycoding_alerting import get_chat

# Abilitiamo i log per vedere cosa fa la libreria.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def main():
    # La factory sceglie il canale giusto in base alle env vars.
    chat = get_chat()
    print(f"Sto usando il canale: {chat.nome_canale}")

    # --- Alert informativo (no dedup) ---
    chat.send(
        titolo="Pipeline qaria-milano",
        messaggio="Pipeline avviata regolarmente.",
        livello="info",
    )

    # --- Alert di warning con dedup ---
    # Se rilanci lo script entro 6 ore, questo alert NON viene rispedito.
    chat.send(
        titolo="Pipeline qaria-milano",
        messaggio="Strato validations: success rate sotto soglia (62% < 90%).",
        livello="warning",
        chiave_dedup="qaria:validations:low_success",
    )

    # --- Alert critico con dedup diverso ---
    chat.send(
        titolo="Pipeline qaria-milano",
        messaggio="Strato fetches: nessun fetch riuscito da 38 ore.",
        livello="critical",
        chiave_dedup="qaria:fetches:silent_too_long",
    )


if __name__ == "__main__":
    main()
