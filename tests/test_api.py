"""Tests for the minimal local API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from doll import __version__
from doll.api import create_app


def test_health_endpoint_is_public_and_non_identifying() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "doll",
        "version": __version__,
    }


def test_openapi_documentation_routes_are_disabled() -> None:
    client = TestClient(create_app())

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
