"""Transient secret material used by the external secret-store boundary."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event
from types import TracebackType

MAX_SECRET_MATERIAL_BYTES = 65_536


class SecretStoreContractError(RuntimeError):
    """Raised when a caller or adapter violates the non-secret contract."""


class SecretMaterialClosedError(SecretStoreContractError):
    """Raised when closed transient secret material is accessed."""


class SecretMaterial:
    """Bounded transient material with redacted representation and best-effort wiping."""

    __slots__ = ("_buffer", "_closed")

    def __init__(self, value: bytes | bytearray | memoryview) -> None:
        if not isinstance(value, bytes | bytearray | memoryview):
            raise SecretStoreContractError("secret material must be bytes-like")
        try:
            buffer = bytearray(value)
        except (TypeError, ValueError):
            raise SecretStoreContractError("secret material must be bytes-like") from None
        if not buffer:
            raise SecretStoreContractError("secret material must not be empty")
        if len(buffer) > MAX_SECRET_MATERIAL_BYTES:
            _wipe(buffer)
            raise SecretStoreContractError("secret material exceeds the accepted size limit")
        self._buffer = buffer
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    @contextmanager
    def borrow(self) -> Iterator[memoryview]:
        """Borrow a read-only view for one trusted adapter or broker operation."""

        if self._closed:
            raise SecretMaterialClosedError("secret material is closed")
        view = memoryview(self._buffer).toreadonly()
        try:
            yield view
        finally:
            view.release()

    def close(self) -> None:
        if self._closed:
            return
        _wipe(self._buffer)
        self._closed = True

    def __enter__(self) -> SecretMaterial:
        if self._closed:
            raise SecretMaterialClosedError("secret material is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    def __repr__(self) -> str:
        return "<SecretMaterial redacted>"

    __str__ = __repr__

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            return


class SecretStoreCancellationToken:
    """Thread-safe cooperative cancellation signal without secret-bearing state."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def __repr__(self) -> str:
        state = "cancelled" if self.is_cancelled else "active"
        return f"<SecretStoreCancellationToken {state}>"


def _wipe(buffer: bytearray) -> None:
    for index in range(len(buffer)):
        buffer[index] = 0


__all__ = [
    "MAX_SECRET_MATERIAL_BYTES",
    "SecretMaterial",
    "SecretMaterialClosedError",
    "SecretStoreCancellationToken",
    "SecretStoreContractError",
]
