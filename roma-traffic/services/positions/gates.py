"""Catena di gate: sicurezza + applicativi (E03 + E04).

Chain of Responsibility popolata da un decoratore-registry (@in_catena):
ogni gate e' una guard clause che legge il suo segnale e, se qualcosa non torna,
esce subito con lo status giusto. L'ORDINE nella catena e' l'ordine di
DEFINIZIONE in questo file: sicurezza prima, applicativi dopo.
"""
import time
from ipaddress import ip_address, ip_network
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

Gate = Callable[[Request], Response | None]   # None = passa oltre, Response = blocca qui


# --- Topologia di rete, modellata in modo esplicito (non ottimista) (E04) ----

RETI_AMMESSE = [                              # da DOVE accettiamo richieste (allowlist)
    ip_network("10.0.0.0/8"),                # intranet
    ip_network("172.16.0.0/12"),             # es. VPN
]
PROXY_FIDATI = [                              # di CHI crediamo l'X-Forwarded-For
    ip_network("10.0.0.1/32"),               # reverse proxy
    ip_network("10.0.0.2/32"),               # load balancer interno
]                                             # VUOTO = servizio esposto -> non fidarsi di NESSUN header


def _fidato(ip) -> bool:
    return any(ip in rete for rete in PROXY_FIDATI)


def ip_client(req: Request) -> str | None:
    """IP reale del client. X-Forwarded-For letto SOLO se il peer e' un proxy fidato,
    risalendo la catena da DESTRA fino al primo IP non fidato."""
    peer_raw = req.client.host if req.client else None
    if not peer_raw:
        return None
    try:
        peer = ip_address(peer_raw)
    except ValueError:
        return None                           # peer illeggibile -> sconosciuto (poi 403)

    if not _fidato(peer):
        return str(peer)                      # non e' un nostro proxy: X-Forwarded-For IGNORATO del tutto

    # peer fidato: risali da destra, scarta i proxy fidati, fermati al primo IP non fidato = il client reale.
    xff = req.headers.get("x-forwarded-for", "")
    for tok in reversed([t.strip() for t in xff.split(",") if t.strip()]):
        try:
            ip = ip_address(tok)
        except ValueError:
            return None                       # un anello della catena e' spazzatura -> non fidarti
        if not _fidato(ip):
            return str(ip)
    return str(peer)                          # tutta la catena e' fidata (o XFF vuoto): il meglio e' il peer


# --- Token bucket per il rate limiting (free E04) ----------------------------

class TokenBucket:
    """Secchiello a gettoni: consuma 1 gettone per richiesta, si ricarica a RICARICA gettoni/s,
    con un tetto (CAPACITA) che concede raffiche brevi ma limita il regime."""

    def __init__(self, capacita: int, ricarica: float):
        self.capacita = capacita
        self.ricarica = ricarica
        self.gettoni = float(capacita)
        self.ultimo = time.monotonic()

    def consenti(self) -> bool:
        now = time.monotonic()
        # ricarica proporzionale al tempo trascorso, senza superare la capacita'
        self.gettoni = min(self.capacita, self.gettoni + (now - self.ultimo) * self.ricarica)
        self.ultimo = now
        if self.gettoni >= 1:
            self.gettoni -= 1
            return True
        return False


# --- Registry della catena ---------------------------------------------------

CATENA: list[Gate] = []


def in_catena(fn: Gate) -> Gate:
    """Registry: ogni gate si iscrive alla catena, nell'ordine di definizione."""
    CATENA.append(fn)
    return fn


def _blocca(status: int, detail: str, headers: dict | None = None) -> Response:
    return JSONResponse({"detail": detail}, status_code=status, headers=headers)


# --- Gate di sicurezza (E04): chi sei, come ti presenti, con che ritmo -------

SCRAPER_PIGRI = ("python-requests", "curl", "scrapy", "go-http-client")
_bucket: dict[str, TokenBucket] = {}          # un secchiello PER IP
CAPACITA, RICARICA = 20, 5.0                   # burst di 20, poi regime a 5 req/s


@in_catena
def gate_ip(req: Request) -> Response | None:
    ip = ip_client(req)                        # 1) CHI SEI
    if ip is None or not any(ip_address(ip) in r for r in RETI_AMMESSE):
        return _blocca(403, "accesso non consentito")
    return None


@in_catena
def gate_user_agent(req: Request) -> Response | None:
    ua = req.headers.get("user-agent", "")     # 2) COME TI PRESENTI (filtro debole, ma primo)
    if not ua or any(s in ua.lower() for s in SCRAPER_PIGRI):
        return _blocca(403, "client non riconosciuto")
    return None


@in_catena
def gate_rate_limit(req: Request) -> Response | None:
    ip = ip_client(req) or "sconosciuto"       # 3) CON CHE RITMO (gate_ip ha gia' scartato i None)
    b = _bucket.get(ip)
    if b is None:                              # get + assegnazione, NON setdefault (creerebbe un bucket ogni volta)
        b = _bucket[ip] = TokenBucket(CAPACITA, RICARICA)
    if not b.consenti():
        return _blocca(429, "troppe richieste", {"Retry-After": "1"})
    return None


# --- Gate applicativi (E03): solo lettura, niente parametri sconosciuti ------

@in_catena
def gate_solo_lettura(req: Request) -> Response | None:
    if req.method != "GET":
        return _blocca(405, "servizio di sola lettura")
    return None


PARAMETRI_NOTI = {"linea"}


@in_catena
def gate_parametri_noti(req: Request) -> Response | None:
    ignoti = set(req.query_params) - PARAMETRI_NOTI
    if ignoti:
        # rifiutare l'inatteso, non ignorarlo: un ?admin=1 di troppo e' un segnale, non rumore
        return _blocca(400, f"parametri non ammessi: {sorted(ignoti)}")
    return None


# --- Validazione del valore di 'linea' (guard clause, E03) -------------------

def valida_linea(raw: str | None) -> str | None:
    match raw:
        case None:
            return None                        # assente e' lecito: /vehicles senza filtro
        case str(s) if s.isalnum():
            return s                           # presente e sensato: passa
        case _:
            raise HTTPException(422, "parametro 'linea' non valido")   # presente e storto: fuori subito
