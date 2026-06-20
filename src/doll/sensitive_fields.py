"""Shared classification for secret-like and private-environment field names."""

from __future__ import annotations

import re

SECRET_FIELD_MARKER = "[REDACTED:secret_field]"
PRIVATE_ENVIRONMENT_MARKER = "[REDACTED:private_environment]"

_SEPARATOR_PATTERN = re.compile(r"[^a-z0-9]+")

_SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "passwd",
        "passphrase",
        "secret",
        "secret_value",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "client_secret",
        "authorization",
        "proxy_authorization",
        "bearer_token",
        "cookie",
        "set_cookie",
        "session_cookie",
        "session_token",
        "private_key",
        "recovery_phrase",
        "seed_phrase",
        "mnemonic",
        "credential",
        "credentials",
        "credential_value",
    }
)
_SECRET_FIELD_PARTS = frozenset(
    {
        "password",
        "passwd",
        "passphrase",
        "secret",
        "authorization",
        "cookie",
        "mnemonic",
        "credential",
        "credentials",
    }
)
_SECRET_FIELD_PAIRS = (
    frozenset({"api", "key"}),
    frozenset({"access", "token"}),
    frozenset({"refresh", "token"}),
    frozenset({"client", "secret"}),
    frozenset({"session", "cookie"}),
    frozenset({"session", "token"}),
    frozenset({"private", "key"}),
    frozenset({"recovery", "phrase"}),
    frozenset({"seed", "phrase"}),
    frozenset({"bearer", "token"}),
)

_PRIVATE_ENVIRONMENT_FIELD_NAMES = frozenset(
    {
        "username",
        "user_name",
        "os_user",
        "login_name",
        "hostname",
        "host_name",
        "machine_name",
        "computer_name",
        "home",
        "home_dir",
        "home_directory",
        "home_path",
        "cwd",
        "current_working_directory",
        "working_directory",
        "absolute_path",
        "local_absolute_path",
        "environment",
        "environment_variables",
        "env",
    }
)


def normalize_field_name(value: str) -> str:
    """Return a stable lowercase underscore form for field classification."""

    normalized = _SEPARATOR_PATTERN.sub("_", value.strip().lower()).strip("_")
    return normalized


def is_secret_field_name(value: str) -> bool:
    """Return whether a field name conventionally carries a secret value."""

    normalized = normalize_field_name(value)
    if normalized in _SECRET_FIELD_NAMES:
        return True
    parts = frozenset(part for part in normalized.split("_") if part)
    if parts & _SECRET_FIELD_PARTS:
        return True
    return any(pair <= parts for pair in _SECRET_FIELD_PAIRS)


def is_private_environment_field_name(value: str) -> bool:
    """Return whether a field exposes a private local-environment detail."""

    return normalize_field_name(value) in _PRIVATE_ENVIRONMENT_FIELD_NAMES


def field_redaction_marker(value: str) -> str | None:
    """Return the sink-safe marker for a classified field, if any."""

    if is_secret_field_name(value):
        return SECRET_FIELD_MARKER
    if is_private_environment_field_name(value):
        return PRIVATE_ENVIRONMENT_MARKER
    return None


__all__ = [
    "PRIVATE_ENVIRONMENT_MARKER",
    "SECRET_FIELD_MARKER",
    "field_redaction_marker",
    "is_private_environment_field_name",
    "is_secret_field_name",
    "normalize_field_name",
]
