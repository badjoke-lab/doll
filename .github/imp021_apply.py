from __future__ import annotations

import base64
import hashlib
import io
import shutil
import tarfile
from pathlib import Path

PAYLOAD = Path(".github/imp021-payload")
EXPECTED_ARCHIVE_SHA256 = "9ac80e06cb84ae608204d26f213bafc1803754537108abcb14db942114188e66"
EXPECTED_FILES = {
    "src/doll/capability.py": (
        "105dd4b9cdf2c2108be3baf72e640111792e36789d850bc3ad56c1facfe53b4c",
        52504,
    ),
    "tests/test_capability.py": (
        "94a3d509649435f02b99f674c30ce65d16a07b10b0ae4e42ce56b982e3528374",
        42761,
    ),
}

encoded = "".join(
    (PAYLOAD / f"part-{index:02d}.b64").read_text(encoding="ascii")
    for index in range(4)
)
archive = base64.b64decode(encoded, validate=True)
actual_archive_hash = hashlib.sha256(archive).hexdigest()
if actual_archive_hash != EXPECTED_ARCHIVE_SHA256:
    raise RuntimeError(f"IMP-021 archive hash mismatch: {actual_archive_hash}")

with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as handle:
    members = {member.name: member for member in handle.getmembers()}
    if set(members) != set(EXPECTED_FILES):
        raise RuntimeError("IMP-021 archive member set is invalid")
    for name, (expected_hash, expected_size) in EXPECTED_FILES.items():
        member = members[name]
        if not member.isfile() or member.size != expected_size:
            raise RuntimeError(f"IMP-021 archive member metadata is invalid: {name}")
        source = handle.extractfile(member)
        if source is None:
            raise RuntimeError(f"IMP-021 archive member is unreadable: {name}")
        content = source.read()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError(f"IMP-021 file hash mismatch: {name}: {actual_hash}")
        destination = Path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

shutil.rmtree(PAYLOAD)
Path(".github/workflows/imp021-apply.yml").unlink(missing_ok=True)
Path(".github/imp021_apply.py").unlink(missing_ok=True)
