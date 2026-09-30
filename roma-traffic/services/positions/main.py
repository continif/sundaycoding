"""positions — il primo microservizio diffidente (assemblaggio E02 -> E06).

Espone la posizione dei mezzi di Roma dal feed GTFS-RT. Fa UNA cosa e dice di no
a tutto il resto: catena di gate (E03/E04), errori centralizzati (E05),
voce su Telegram (E06). L'app qui e' solo il montaggio: la logica vive nei moduli.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Response, status
from fastapi.responses import FileResponse

from . import gates, stato, telegram
from .errori import MezzoNonTrovato, registra_handler
from .modelli import Vehicle

DEMO_HTML = Path(__file__).parent / "demo" / "mappa.html"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("positions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = None
    if telegram.abilitato():                     # senza TELEGRAM_BOT_TOKEN il servizio parte LO STESSO
        telegram.registra_notificatore()         # gli alert di feed passano su Telegram
        task = asyncio.create_task(telegram.ascolta())   # il poller vive ACCANTO a uvicorn, stesso loop
        log.info("canale Telegram attivo (long polling)")
    yield
    if task:
        task.cancel()                            # allo spegnimento: niente task orfani
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="positions", lifespan=lifespan)

registra_handler(app)                            # eccezioni di dominio -> status, in un posto solo (E05)


@app.middleware("http")
async def applica_catena(req, call_next):
    # Chain of Responsibility: il primo gate che restituisce una Response vince (E03/E04).
    for gate in gates.CATENA:
        if (stop := gate(req)) is not None:
            return stop
    return await call_next(req)


@app.get("/", include_in_schema=False)
def home():
    # Demo: UNA rotta per UN file, non StaticFiles (che esporrebbe un'intera cartella).
    # Passa dalla stessa catena di gate dell'API, e sta sulla stessa origine => niente CORS.
    return FileResponse(DEMO_HTML, media_type="text/html")


@app.get("/vehicles", response_model=list[Vehicle])
async def get_vehicles(response: Response, linea: str | None = None):
    linea = gates.valida_linea(linea)            # guard clause sul valore del parametro
    st = await stato.aggiorna_stato()            # FRESH/STALE; se non c'e' nulla -> FeedNonDisponibile (503)
    if st is stato.Feed.STALE:
        response.headers["X-Stale"] = "true"     # 200 con dato di un attimo fa: non e' un errore, e' onesta'
    vehicles = stato._cache["vehicles"] or []
    if linea is not None:
        vehicles = [v for v in vehicles if v["linea"] == linea]   # lista vuota = linea senza mezzi ADESSO (200)
    return vehicles


@app.get("/vehicles/{vehicle_id}", response_model=Vehicle)
async def get_vehicle(vehicle_id: str, response: Response):
    st = await stato.aggiorna_stato()
    for v in (stato._cache["vehicles"] or []):
        if v["id"] == vehicle_id:
            if st is stato.Feed.STALE:
                response.headers["X-Stale"] = "true"
            return v
    raise MezzoNonTrovato(vehicle_id)            # eccezione di dominio -> handler -> 404


@app.get("/health")
def health():
    return {"status": "ok", "service": "positions"}
