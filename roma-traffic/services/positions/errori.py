"""Eccezioni di dominio e handler centralizzati (E05).

Gli endpoint sollevano eccezioni di DOMINIO ("questo mezzo non c'e'"), non
costruiscono risposte HTTP. La mappa eccezione -> status vive SOLO qui:
un posto, una tabella.
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("positions")


class ErroreDominio(Exception):
    """Base delle eccezioni PREVISTE di positions. Ognuna mappa su uno status, in un posto solo."""


class FeedNonDisponibile(ErroreDominio):
    """Sorgente giu'/timeout/dati illeggibili E nessuna cache da servire."""


class MezzoNonTrovato(ErroreDominio):
    """/vehicles/{id} con un id che non e' nel feed."""

    def __init__(self, vehicle_id: str):
        super().__init__(vehicle_id)
        self.vehicle_id = vehicle_id


def registra_handler(app) -> None:
    """Registra gli handler sull'app. Pattern ufficiale FastAPI: un handler per classe,
    usato anche per le sottoclassi."""

    @app.exception_handler(MezzoNonTrovato)
    async def _non_trovato(req: Request, exc: MezzoNonTrovato):
        return JSONResponse({"detail": f"mezzo {exc.vehicle_id} non trovato"}, status_code=404)

    @app.exception_handler(FeedNonDisponibile)
    async def _feed_giu(req: Request, exc: FeedNonDisponibile):
        return JSONResponse(
            {"detail": "feed non disponibile"},
            status_code=503,
            headers={"Retry-After": "10"},          # dico al client QUANDO ritentare
        )

    # Handler di ULTIMA istanza: prende SOLO cio' che nessuno sopra ha gestito -> imprevisto o bug.
    @app.exception_handler(Exception)
    async def _imprevisto(req: Request, exc: Exception):
        log.exception("errore non gestito su %s", req.url.path)   # per NOI: stack trace completo nei log
        # per il CLIENT: niente dettagli (nomi di file e struttura interna sono un regalo a chi ci attacca)
        return JSONResponse({"detail": "errore interno"}, status_code=500)
