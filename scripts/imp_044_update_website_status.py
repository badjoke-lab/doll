from pathlib import Path

path = Path(__file__).resolve().parents[1] / "website/project-status.json"
text = path.read_text(encoding="utf-8")
old = '"next_implementation": 44'
new = '"next_implementation": 45'
if old not in text:
    raise RuntimeError("next implementation anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
