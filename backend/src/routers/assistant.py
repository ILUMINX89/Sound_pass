"""SoundPass AI assistant router (adapted from feature/sprint3-soundpass-ai for development)."""

import asyncio
import logging
import re
import unicodedata
from collections import Counter, deque
from datetime import date, timedelta
from time import monotonic
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from src.artist_origins import artist_catalog
from src.config import settings
from src.database import SessionLocal
from src.models import User
from src.security import get_current_user
from src.ticketmaster import TicketmasterError, get_public_concerts

router = APIRouter(prefix="/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60
REQUESTS_PER_USER = 3
MAX_CONCURRENT_REQUESTS = 2
request_times: deque[tuple[float, int]] = deque()
requests_by_user: Counter[int] = Counter()
active_requests = 0

SYSTEM_PROMPT = """Devuelve solo JSON compacto. Siempre intent y order; omite campos opcionales no solicitados.
intent: concerts para conciertos/fechas, help para uso de SoundPass, clarify si ambiguo o filtros no admitidos.
order: nearest_first por defecto. "de mayor a menor en tiempo", "mas lejano al mas cercano", "tiempo descendente" => latest_first.
"los mas cercanos primero" => nearest_first. "Fechas de Bad Bunny en Madrid" => concerts, artist Bad Bunny, city Madrid.
"Como descargo mis boletos?" => help. Solo artist y city como filtros. No inventes datos, disponibilidad ni politicas.
No incluyas reply salvo una pregunta breve para clarify. No incluyas null ni explicaciones.
"""

INTENT_FORMAT = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["concerts", "help", "clarify"]},
        "order": {"type": "string", "enum": ["nearest_first", "latest_first"]},
        "artist": {"type": "string"},
        "city": {"type": "string"},
        "reply": {"type": "string"},
    },
    "required": ["intent", "order"],
    "additionalProperties": False,
}

HELP_REPLY = (
    "Para eventos de Ticketmaster, abre el concierto y consulta la disponibilidad oficial desde su enlace. "
    "Para tus compras locales anteriores de SoundPass, entra en Mis boletos, abre el detalle y descarga el PDF. "
    "Puedes cancelar una compra local confirmada desde su detalle."
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ChatResponse(BaseModel):
    reply: str


class CatalogIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["concerts", "help", "clarify"]
    order: Literal["nearest_first", "latest_first"] = "nearest_first"
    artist: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, max_length=100)
    reply: str | None = Field(default=None, max_length=200)


def _fold(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").casefold())
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def validate_explicit_order(message: str, intent: CatalogIntent) -> CatalogIntent:
    """Do not let the classifier invert an explicitly requested time direction."""
    text = _fold(message)
    if intent.intent != "concerts":
        return intent
    if re.search(r"lejan\w*.*cercan", text) or re.search(r"lejan\w*\s+primero", text):
        intent.order = "latest_first"
    elif re.search(r"cercan\w*.*lejan", text) or re.search(r"cercan\w*\s+primero", text):
        intent.order = "nearest_first"
    elif any(word in text for word in ("tiempo", "fecha", "cronologic", "futuro")):
        if re.search(r"mayor.*menor", text) or "descendente" in text:
            intent.order = "latest_first"
        elif re.search(r"menor.*mayor", text) or "ascendente" in text:
            intent.order = "nearest_first"
    return intent


def catalog_reply(intent: CatalogIntent) -> str:
    """Query the live public catalog (Ticketmaster Discovery) in a worker thread."""
    with SessionLocal() as db:
        catalog = artist_catalog(db)
        db.rollback()
    try:
        events = get_public_concerts("", catalog)
    except TicketmasterError:
        return "El catálogo de conciertos de Ticketmaster no está disponible en este momento."

    floor = (date.today() - timedelta(days=1)).isoformat()
    artist_q = _fold(intent.artist)
    city_q = _fold(intent.city)
    rows = []
    for ev in events:
        ev_date = str(ev.get("event_date") or "")
        if len(ev_date) < 10 or ev_date[:10] < floor:
            continue
        if artist_q and artist_q not in _fold(ev.get("artist")):
            continue
        venue = ev.get("venue") or {}
        if city_q and city_q not in _fold(venue.get("city")):
            continue
        rows.append(ev)

    rows.sort(
        key=lambda ev: (str(ev.get("event_date") or ""), str(ev.get("event_time") or ""), str(ev.get("id") or "")),
        reverse=(intent.order == "latest_first"),
    )
    total = len(rows)
    if not rows:
        return "No hay coincidencias próximas en el catálogo actual de Ticketmaster para esa búsqueda."

    shown = rows[:12]
    lines = [f"Conciertos próximos en el catálogo de SoundPass ({len(shown)} de {total} coincidencias):"]
    for ev in shown:
        ev_date = str(ev.get("event_date") or "")
        y, m, d = ev_date[:10].split("-")
        ev_time = str(ev.get("event_time") or "")
        hour = f"{ev_time[:5]} (hora local)" if len(ev_time) >= 5 else "Hora por confirmar"
        venue = ev.get("venue") or {}
        place = ", ".join(p for p in (venue.get("name"), venue.get("city")) if p) or "Recinto por confirmar"
        lines.append(f"• {ev.get('artist')} — {d}/{m}/{y} {hour} · {place}")
    return "\n".join(lines)


def reserve_request(user_id: int) -> None:
    now = monotonic()
    while request_times and now - request_times[0][0] >= WINDOW_SECONDS:
        _, old_user = request_times.popleft()
        requests_by_user[old_user] -= 1
        if requests_by_user[old_user] <= 0:
            del requests_by_user[old_user]

    if requests_by_user[user_id] >= REQUESTS_PER_USER or active_requests >= MAX_CONCURRENT_REQUESTS:
        raise HTTPException(429, "Hay muchas consultas en este momento. Inténtalo de nuevo en un minuto.")

    request_times.append((now, user_id))
    requests_by_user[user_id] += 1


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    global active_requests
    if not settings.ollama_base_url.strip():
        raise HTTPException(503, "El asistente no está disponible en este momento.")

    reserve_request(user.id)
    active_requests += 1
    started = monotonic()
    try:
        async with asyncio.timeout(settings.ollama_timeout_seconds):
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.ollama_timeout_seconds, connect=5.0),
                trust_env=False,
            ) as client:
                response = await client.post(
                    f"{settings.ollama_base_url.strip().rstrip('/')}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": body.message},
                        ],
                        "stream": False,
                        "format": INTENT_FORMAT,
                        "options": {"num_predict": 80, "num_ctx": 1024, "temperature": 0},
                    },
                )
                response.raise_for_status()

        intent = validate_explicit_order(
            body.message,
            CatalogIntent.model_validate_json(response.json()["message"]["content"]),
        )
        if intent.intent == "concerts":
            reply = await run_in_threadpool(catalog_reply, intent)
        elif intent.intent == "help":
            reply = HELP_REPLY
        else:
            reply = intent.reply or "Aclara si buscas conciertos o ayuda con SoundPass."
        logger.info("assistant success seconds=%.2f", monotonic() - started)
        return ChatResponse(reply=reply)

    except (TimeoutError, httpx.TimeoutException):
        logger.warning("Ollama agotó el tiempo de espera")
        raise HTTPException(504, "El asistente tardó demasiado en responder.") from None
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        logger.warning("Falló la consulta a Ollama (%s)", type(error).__name__)
        raise HTTPException(502, "No fue posible obtener una respuesta del asistente.") from None
    finally:
        active_requests -= 1
