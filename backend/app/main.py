"""FastAPI entry point for the PTO Management System backend."""

from fastapi import FastAPI

app = FastAPI(
    title="PTO Management System API",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm the API is running. Used by Render and CI."""
    return {"status": "ok"}