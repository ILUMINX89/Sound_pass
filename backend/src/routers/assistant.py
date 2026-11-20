import asyncio
import re
import unicodedata
import logging
from collections import Counter, deque
from time import monotonic
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from src.database import SessionLocal
from src.catalog import query_catalog, sync_status

from src.config import settings
from src.models import User
from src.security import get_current_user

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

# Keep decoding grammar compact; Pydantic still validates every model response.
INTENT_FORMAT = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["concerts", "help", "clarify"]},
        "order": {"type": "string", "enum": ["nearest_first", "latest_first"]},
        "artist": {"type": "string"}, "city": {"type": "string"}, "reply": {"type": "string"},
    },
    "required": ["intent", "order"], "additionalProperties": False,
}


HELP_REPLY = (
    "Para eventos importados, abre el concierto y pulsa Ver en Ticketmaster: la compra y sus condiciones se gestionan alli. "
    "Para tus compras locales anteriores de SoundPass, entra en Mis boletos, abre el detalle y descarga el PDF. "
    "Puedes cancelar una compra local confirmada desde su detalle."
)


class CatalogIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal["concerts", "help", "clarify"]
    order: Literal["nearest_first", "latest_first"] = "nearest_first"
    artist: str | None = Field(default=None, max_length=150)
    city: str | None = Field(default=None, max_length=100)
    reply: str | None = Field(default=None, max_length=200)


def validate_explicit_order(message, intent):
    """Do not let the classifier invert an explicitly requested time direction."""
    text = "".join(c for c in unicodedata.normalize("NFKD", message.casefold()) if not unicodedata.combining(c))
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


def catalog_reply(intent):
    # Called in a worker: this session is created, consumed and closed in that thread.
    with SessionLocal() as db:
        status, last = sync_status(db)
        if status == "unavailable":
            return "La información del catálogo de Ticketmaster (alcance configurado) aún no está disponible: no hay una primera sincronización exitosa."
        rows, total = query_catalog(db, city=intent.city, artist=intent.artist, order=intent.order, limit=20)
        suffix = f"Último catálogo actualizado: {last.astimezone(ZoneInfo('America/Bogota')).strftime('%d/%m/%Y %H:%M')} (Bogotá)."
        if status == "stale":
            suffix = "Última copia válida desactualizada. " + suffix
        if not rows:
            return "No hay coincidencias próximas en el catálogo consultado de Ticketmaster (alcance configurado). " + suffix
        lines = [f"Conciertos próximos de Ticketmaster (alcance configurado) ({len(rows)} de {total} coincidencias):"]
        for c in rows:
            hour = c.event_time.strftime('%H:%M') + " (hora local)" if c.event_time else "Hora por confirmar"
            lines.append(f"• {c.artist} — {c.event_date.strftime('%d/%m/%Y')}, {hour} — {c.venue.city}, {c.venue.name}")
        lines.append(suffix)
        return "\n".join(lines)



class ChatRequest(BaseModel):
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ]


class ChatResponse(BaseModel):
    reply: str


def reserve_request(user_id: int) -> None:
    now = monotonic()
    while request_times and request_times[0][0] <= now - WINDOW_SECONDS:
        _, previous_user = request_times.popleft()
        requests_by_user[previous_user] -= 1
        if not requests_by_user[previous_user]:
            del requests_by_user[previous_user]

    if requests_by_user[user_id] >= REQUESTS_PER_USER or active_requests >= MAX_CONCURRENT_REQUESTS:
        raise HTTPException(429, "Hay muchas consultas en este momento. Espera un momento.")

    request_times.append((now, user_id))
    requests_by_user[user_id] += 1


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(get_current_user)):
    global active_requests
    if not settings.ollama_base_url:
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
                    f"{settings.ollama_base_url.rstrip('/')}/api/chat",
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

        intent = validate_explicit_order(body.message, CatalogIntent.model_validate_json(response.json()["message"]["content"]))
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
