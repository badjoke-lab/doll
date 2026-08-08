"""Hosted macOS acceptance for the real IMP-077 Vision OCR adapter."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast

import pytest

from doll.local_ocr import OcrmacAdapter, extract_local_image_ocr


class _GeneratedImage(Protocol):
    def save(self, path: Path, *, format: str) -> None: ...


class _ImageDraw(Protocol):
    def text(
        self,
        xy: tuple[int, int],
        text: str,
        *,
        fill: str,
        font: object,
    ) -> None: ...


def _required_callable(module: ModuleType, name: str) -> Callable[..., object]:
    value = getattr(module, name, None)
    assert callable(value)
    return cast(Callable[..., object], value)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Vision acceptance")
def test_real_ocrmac_vision_recognizes_deterministic_local_text(tmp_path: Path) -> None:
    image_module = importlib.import_module("PIL.Image")
    draw_module = importlib.import_module("PIL.ImageDraw")
    font_module = importlib.import_module("PIL.ImageFont")

    image = cast(
        _GeneratedImage,
        _required_callable(image_module, "new")("RGB", (1600, 500), "white"),
    )
    draw = cast(_ImageDraw, _required_callable(draw_module, "Draw")(image))
    font = _required_callable(font_module, "load_default")(size=160)
    draw.text((80, 140), "DOLL OCR 123", fill="black", font=font)

    source = tmp_path / "vision-ocr.png"
    image.save(source, format="PNG")

    result = extract_local_image_ocr(source, adapter=OcrmacAdapter.load())
    normalized = " ".join(line.text.upper() for line in result.lines)

    assert result.adapter_id == "ocrmac-vision"
    assert result.adapter_version == "1.0.1"
    assert result.line_count >= 1
    assert "DOLL" in normalized
    assert "OCR" in normalized
    assert "123" in normalized
    assert result.network_access_used is False if hasattr(result, "network_access_used") else True
