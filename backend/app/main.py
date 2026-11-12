"""FastAPI entry point for the PTO Management System backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title="PTO Management System API",
    version="0.1.0",
)

# Every error response uses the standard {"error": {...}} format.
register_exception_handlers(app)

# Only our frontend may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm the API is running. Used by Render and CI."""
    return {"status": "ok"}