"""Interazioni via Telegram: long polling, alert sul fronte, comandi read-only (E06).

Scelte di progetto (il "perche'" sta nella free "Il server che ti scrive su Telegram"):
- long polling, non webhook: il servizio vive sull'intranet, non apriamo porte.
- Telegram e' OPZIONALE: senza TELEGRAM_BOT_TOKEN il servizio parte e serve identico.
- comandi a SOLA LETTURA, allowlist sul chat_id come primo gate, solo la prima parola.
"""
import asyncio
import logging
import os

import httpx

from . import stato

log = logging.getLogger("positions")


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _api() -> str:
    return f"https://api.telegram.org/bot{_token()}"


def _ammessi() -> set[int]:
    # allowlist dei chat_id da ambiente: solo questi possono scrivere al bot
    return {int(x) for x in os.environ.get("TELEGRAM_ALLOWLIST", "").split(",") if x.strip()}


async def _invia(chat_id: int, testo: str) -> None:
    # POST a sendMessage con timeout stretto: la voce del servizio non deve bloccare il servizio
    async with httpx.AsyncClient(timeout=5) as c:
        await c.post(f"{_api()}/sendMessage", json={"chat_id": chat_id, "text": testo})


async def avvisa_tutti(testo: str) -> None:
    """Alert in uscita a tutti gli operatori in allowlist. Registrata come notificatore di stato."""
    for cid in _ammessi():
        try:
            await _invia(cid, testo)
        except httpx.HTTPError as e:
            log.warning("alert telegram non inviato a %s: %s", cid, e)   # un alert perso non e' un guasto


# --- Comandi: dispatch table, sola lettura -----------------------------------

def _cmd_stato() -> str:
    # legge lo stato che il servizio HA GIA': il bot e' una finestra read-only, non una 2a strada verso il feed
    n = len(stato._cache["vehicles"] or [])
    breaker = "aperto" if stato._breaker_aperto() else "chiuso"
    return f"stato: {stato.stato_corrente().name} - {n} mezzi in cache - breaker {breaker}"


def _cmd_ultimi() -> str:
    vehicles = list(stato._cache["vehicles"] or [])[:5]
    if not vehicles:
        return "nessun mezzo in cache"
    return "\n".join(f"{v['id']}: linea {v['linea'] or '?'}" for v in vehicles)


COMANDI = {                                    # dispatch table: nuovo comando = una riga, zero if annidati
    "/stato": _cmd_stato,
    "/ultimi": _cmd_ultimi,
}


async def _gestisci(msg: dict) -> None:
    chat_id = msg.get("chat", {}).get("id")
    if chat_id not in _ammessi():              # PRIMA di tutto: mittente non ammesso = per noi non esiste
        return                                 # silenzio: non confermo nemmeno di essere qui
    testo = (msg.get("text") or "").strip()
    comando = testo.split()[0] if testo else ""   # SOLO la prima parola: niente argomenti = niente superficie
    handler = COMANDI.get(comando)
    if handler is None:
        await _invia(chat_id, "comandi: /stato /ultimi")
        return
    await _invia(chat_id, handler())           # il handler LEGGE lo stato, non tocca rete ne' shell


# --- Long polling ------------------------------------------------------------

async def ascolta() -> None:
    offset = 0
    async with httpx.AsyncClient(timeout=35) as c:   # 35 > 30: lascio a Telegram i suoi 30s di long poll
        while True:
            try:
                r = await c.get(
                    f"{_api()}/getUpdates",
                    params={"offset": offset, "timeout": 30,
                            "allowed_updates": ["message"]},   # filtro server-side: solo i messaggi
                )
                for u in r.json()["result"]:
                    offset = u["update_id"] + 1              # ricevuta: il prossimo giro non mi ridà l'update
                    await _gestisci(u.get("message", {}))
            except asyncio.CancelledError:
                raise                                        # spegnimento pulito: lascio propagare
            except (httpx.HTTPError, KeyError, ValueError) as e:
                log.warning("polling telegram: %s", e)       # un giro a vuoto NON deve uccidere il loop
                await asyncio.sleep(3)                        # respiro e ritento: Telegram giu' = guasto tollerabile


def abilitato() -> bool:
    return bool(_token())


def registra_notificatore() -> None:
    """Aggancia gli alert di stato (E06) ai cambi di stato del feed, senza dipendenze circolari."""
    if avvisa_tutti not in stato.notificatori:
        stato.notificatori.append(avvisa_tutti)
