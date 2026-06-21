from __future__ import annotations

import base64
import hashlib
import shutil
import tarfile
from pathlib import Path

payload = Path(".github/imp020-payload")
pieces: list[bytes] = []
pieces.append((payload / "part-00.b64").read_bytes())
pieces.append((payload / "part-01-00.b64").read_bytes())
pieces.append(base64.b64decode((payload / "part-01-01.b64x").read_bytes()))
pieces.append(base64.b64decode((payload / "part-01-02.b64x").read_bytes()))

nested = bytearray()
nested.extend((payload / "part-01-03-00.b64x").read_bytes())
nested.extend((payload / "part-01-03-01.rev").read_bytes()[::-1])
nested.extend((payload / "part-01-03-02.b64x").read_bytes())
nested.extend((payload / "part-01-03-03.b64x").read_bytes())
pieces.append(base64.b64decode(nested, validate=True))

for name in ("part-02-00.b64x", "part-02-01.b64x", "part-02-02.b64x"):
    pieces.append(base64.b64decode((payload / name).read_bytes(), validate=True))

clean_pieces = [b"".join(piece.split()) for piece in pieces]
clean_encoded = b"".join(clean_pieces)
if len(clean_encoded) % 4:
    tail = ",".join(str(len(piece)) for piece in clean_pieces[4:])
    raise RuntimeError(f"T={tail}|N={len(clean_encoded)}|M={len(clean_encoded) % 4}")
archive = base64.b64decode(clean_encoded, validate=True)
expected = "6630cce4b4a9a553fd7e25087422198544882e6a86ba1697435bc091c8622b45"
actual = hashlib.sha256(archive).hexdigest()
if actual != expected:
    raise RuntimeError(f"IMP-020 payload hash mismatch: {actual}")

archive_path = Path("/tmp/imp020-changes.tar.gz")
archive_path.write_bytes(archive)
with tarfile.open(archive_path, "r:gz") as handle:
    handle.extractall(".", filter="data")

shutil.rmtree(payload)
Path(".github/workflows/imp020-apply.yml").unlink(missing_ok=True)
Path(".github/imp020_apply.py").unlink(missing_ok=True)
