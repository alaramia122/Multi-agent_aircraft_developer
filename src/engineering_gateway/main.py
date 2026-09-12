"""FastAPI application entry point."""

from fastapi import FastAPI

from engineering_gateway import __version__
from engineering_gateway.config import settings

app = FastAPI(title=settings.app_name, version=__version__)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process-level health information."""

    return {"status": "ok", "service": settings.app_name, "version": __version__}
