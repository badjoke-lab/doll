from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{label} marker count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    Path("tests/test_imp_083_lite_client_measurement.py"),
    '        if str(self) == "/proc/self/statm":\n',
    '        if str(self).replace("\\\\", "/").endswith("/proc/self/statm"):\n',
    "Windows path",
)
replace_once(
    Path("src/doll/lite_measurement.py"),
    '        raise LiteClientMeasurementError("Lite measurement workspace root must not be a symbolic link")\n',
    '        raise LiteClientMeasurementError(\n'
    '            "Lite measurement workspace root must not be a symbolic link"\n'
    '        )\n',
    "root symlink formatting",
)
