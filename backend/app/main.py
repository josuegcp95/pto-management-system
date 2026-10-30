"""FastAPI entry point for the PTO Management System backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="PTO Management System API",
    version="0.1.0",
)

# Only our frontend may call this API from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm the API is running. Used by Render and CI."""
    return {"status": "ok"}