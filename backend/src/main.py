from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import settings
from src.routers import auth, concerts, orders, venues
from src.routers import tickets



app = FastAPI(
    title="SoundPass API",
    description="API para compra y gestión de boletos de conciertos.",
    version="1.0.0",
    debug=False,
    openapi_url=None if settings.is_public else "/openapi.json",
    docs_url=None if settings.is_public else "/docs",
    redoc_url=None if settings.is_public else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(concerts.router)
app.include_router(orders.router)
app.include_router(tickets.router)
app.include_router(venues.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}

# Métricas para Prometheus en /metrics:
#   http_requests_total            contador de requests (por ruta, método y código)
#   http_request_duration_seconds  histograma de latencia
#   http_requests_inprogress       gauge de requests en curso
Instrumentator(
    should_group_status_codes=True,
    should_instrument_requests_inprogress=True,
    inprogress_labels=True,
    excluded_handlers=["/metrics", "/health"],
).instrument(app).expose(app, include_in_schema=False)