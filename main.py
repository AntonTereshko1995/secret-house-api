from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from logger import setup_logger
from routers import bookings, gifts, promocodes

setup_logger()

app = FastAPI(
    title="Secret House API",
    description="REST API for the Secret House web booking form",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])
app.include_router(promocodes.router, prefix="/api/promocodes", tags=["promocodes"])
app.include_router(gifts.router, prefix="/api/gifts", tags=["gifts"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
