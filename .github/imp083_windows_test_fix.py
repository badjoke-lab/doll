from pathlib import Path

path = Path("tests/test_imp_083_lite_client_measurement.py")
text = path.read_text(encoding="utf-8")
old = '    monkeypatch.setattr(os, "sysconf", lambda name: 4096)\n'
new = '    monkeypatch.setattr(os, "sysconf", lambda name: 4096, raising=False)\n'
if text.count(old) != 1:
    raise SystemExit(f"Windows sysconf marker count={text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
