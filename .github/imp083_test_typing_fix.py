from pathlib import Path

path = Path("tests/test_imp_083_lite_client_measurement.py")
text = path.read_text(encoding="utf-8")

replacements = {
    "import json\nimport os\nfrom pathlib import Path\nfrom typing import cast\n": (
        "import ctypes\nimport json\nimport os\nfrom collections.abc import Callable\n"
        "from pathlib import Path\nfrom typing import cast\n"
    ),
    '    monkeypatch.setattr(measurement_module.os, "name", "nt")\n': (
        '    monkeypatch.setattr(os, "name", "nt")\n'
    ),
    "            rss_reader=cast(object, lambda: object()),\n": (
        "            rss_reader=cast(Callable[[], ProcessRssSnapshot], lambda: object()),\n"
    ),
    "        measurement_module._clock_value(cast(object, lambda: True))\n": (
        "        measurement_module._clock_value(cast(Callable[[], int], lambda: True))\n"
    ),
    '''    def valid_read(self: Path, *args: object, **kwargs: object) -> str:
        if str(self) == "/proc/self/statm":
            return "100 5 0 0 0 0 0\\n"
        return original(self, *args, **kwargs)
''': '''    def valid_read(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if str(self) == "/proc/self/statm":
            return "100 5 0 0 0 0 0\\n"
        return original(self, encoding=encoding, errors=errors)
''',
    '''    def invalid_read(self: Path, *args: object, **kwargs: object) -> str:
        del self, args, kwargs
        return "invalid"
''': '''    def invalid_read(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        del self, encoding, errors
        return "invalid"
''',
    '    monkeypatch.setattr(measurement_module.os, "sysconf", lambda name: 4096)\n': (
        '    monkeypatch.setattr(os, "sysconf", lambda name: 4096)\n'
    ),
    '    monkeypatch.delattr(measurement_module.ctypes, "WinDLL", raising=False)\n': (
        '    monkeypatch.delattr(ctypes, "WinDLL", raising=False)\n'
    ),
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"typing marker count={count}: {old!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
