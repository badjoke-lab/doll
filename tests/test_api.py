"""Tests for the minimal local API."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

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


def test_create_app_has_no_workspace_side_effect(monkeypatch: MonkeyPatch) -> None:
    from doll import workspace

    def fail_if_workspace_is_initialized(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_app must not initialize a workspace")

    def fail_if_default_path_is_resolved(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_app must not resolve the default workspace path")

    monkeypatch.setattr(workspace, "initialize_workspace", fail_if_workspace_is_initialized)
    monkeypatch.setattr(workspace, "default_workspace_path", fail_if_default_path_is_resolved)

    app = create_app()

    assert app.title == "doll local API"
