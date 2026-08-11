from pathlib import Path

path = Path("tests/test_imp_083_lite_client_measurement.py")
text = path.read_text(encoding="utf-8")
old = '        if str(self) == "/proc/self/statm":\n'
new = '        if str(self).replace("\\\\", "/").endswith("/proc/self/statm"):\n'
if text.count(old) != 1:
    raise SystemExit(f"Windows path marker count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
