from pathlib import Path

path = Path("src/doll/shutdown_escape.py")
text = path.read_text(encoding="utf-8")
old = "    descriptor = os.open(path, os.O_RDONLY)\n"
new = "    descriptor = os.open(path, os.O_RDWR)\n"
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one fsync open target, found {count}")
path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
