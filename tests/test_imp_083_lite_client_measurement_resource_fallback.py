"""Cross-platform fallback coverage for the IMP-083 process RSS adapter."""

from __future__ import annotations

import os
import sys
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
from pytest import MonkeyPatch

from doll.lite_measurement import (
    LiteClientMeasurementError,
    ProcessRssSnapshot,
    read_process_rss,
)


def _select_resource_adapter(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(os, "name", "posix")
    monkeypatch.setattr(sys, "platform", "win32")


def test_resource_adapter_reports_unavailable_when_getrusage_fails(
    monkeypatch: MonkeyPatch,
) -> None:
    _select_resource_adapter(monkeypatch)

    def fail_getrusage(kind: object) -> object:
        del kind
        raise OSError("synthetic resource failure")

    resource = cast(
        ModuleType,
        SimpleNamespace(RUSAGE_SELF=0, getrusage=fail_getrusage),
    )
    monkeypatch.setitem(sys.modules, "resource", resource)

    assert read_process_rss() == ProcessRssSnapshot(
        source="unavailable",
        current_bytes=None,
        peak_bytes=None,
    )


def test_resource_adapter_normalizes_non_darwin_peak_rss(
    monkeypatch: MonkeyPatch,
) -> None:
    _select_resource_adapter(monkeypatch)

    def getrusage(kind: object) -> SimpleNamespace:
        del kind
        return SimpleNamespace(ru_maxrss=7)

    resource = cast(
        ModuleType,
        SimpleNamespace(RUSAGE_SELF=0, getrusage=getrusage),
    )
    monkeypatch.setitem(sys.modules, "resource", resource)

    assert read_process_rss() == ProcessRssSnapshot(
        source="resource-ru_maxrss",
        current_bytes=None,
        peak_bytes=7 * 1024,
    )


def test_resource_adapter_rejects_negative_peak_rss(
    monkeypatch: MonkeyPatch,
) -> None:
    _select_resource_adapter(monkeypatch)

    def getrusage(kind: object) -> SimpleNamespace:
        del kind
        return SimpleNamespace(ru_maxrss=-1)

    resource = cast(
        ModuleType,
        SimpleNamespace(RUSAGE_SELF=0, getrusage=getrusage),
    )
    monkeypatch.setitem(sys.modules, "resource", resource)

    with pytest.raises(LiteClientMeasurementError, match="peak RSS is invalid"):
        read_process_rss()
