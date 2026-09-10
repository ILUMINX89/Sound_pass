from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routers import auth, concerts, orders, venues



app = FastAPI(
    title="SoundPass API",
    description="API para compra y gestión de boletos de conciertos.",
    version="1.0.0",
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
app.include_router(venues.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}