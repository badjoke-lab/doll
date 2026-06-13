"""Local API application factory for doll."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from doll import __version__


class HealthResponse(BaseModel):
    """Public, non-identifying local health response."""

    status: Literal["ok"] = "ok"
    service: Literal["doll"] = "doll"
    version: str = __version__


def create_app() -> FastAPI:
    """Create the local API without starting a listener or accessing private state."""

    application = FastAPI(
        title="doll local API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    return application
