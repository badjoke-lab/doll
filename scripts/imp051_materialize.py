from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

EXPECTED_HASH = "67dc298c16bb762818aeb95cad32cda48f2572a288f2847d15266aebd55bce99"
EXPECTED_NAMES = {
    "src/doll/local_conversation.py",
    "src/doll/model_manifest.py",
    "tests/test_local_conversation.py",
    "tests/test_local_conversation_static.py",
}


def _comma_values(path: Path) -> tuple[int, ...]:
    return tuple(int(value) for value in path.read_text(encoding="ascii").split(","))


def _nibble_prefix() -> bytes:
    paths = tuple(Path(f"scripts/imp051_nibbles/part.{index:02d}") for index in range(5))
    encoded = "".join(path.read_text(encoding="ascii").strip() for path in paths)
    if len(encoded) % 2 or any(character < "A" or character > "P" for character in encoded):
        raise SystemExit("invalid nibble payload")
    return bytes(
        ((ord(encoded[index]) - 65) << 4) | (ord(encoded[index + 1]) - 65)
        for index in range(0, len(encoded), 2)
    )


def _payload() -> bytes:
    parts = bytearray(_nibble_prefix())
    parts.extend(_comma_values(Path("scripts/imp051_decimal/part.00")))

    for index in range(2):
        values = _comma_values(Path(f"scripts/imp051_xor_decimal/part.{index:02d}"))
        parts.extend(value ^ 173 for value in values)

    for index in (0, 1):
        values = _comma_values(Path(f"scripts/imp051_plus_decimal/part.{index:02d}"))
        parts.extend(value - 3000 for value in values)

    for name in ("part.02a", "part.02b"):
        values = _comma_values(Path(f"scripts/imp051_alt_decimal/{name}"))
        for value in values:
            encoded_value = value - 7000
            if encoded_value % 3:
                raise SystemExit("invalid alternate payload value")
            parts.append(encoded_value // 3)

    for index in (3, 4):
        values = _comma_values(Path(f"scripts/imp051_plus_decimal/part.{index:02d}"))
        parts.extend(value - 3000 for value in values)

    payload = bytes(parts)
    actual_hash = hashlib.sha256(payload).hexdigest()
    if actual_hash != EXPECTED_HASH:
        raise SystemExit(f"payload checksum mismatch: {actual_hash}")
    return payload


def main() -> None:
    archive = Path("/tmp/imp051-core.tar.gz")
    archive.write_bytes(_payload())
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = {member.name for member in members}
        if names != EXPECTED_NAMES:
            raise SystemExit(f"unexpected payload inventory: {sorted(names)}")
        for member in members:
            destination = Path(member.name)
            if not member.isfile() or destination.is_absolute() or ".." in destination.parts:
                raise SystemExit(f"unsafe payload member: {member.name}")
            source = bundle.extractfile(member)
            if source is None:
                raise SystemExit(f"unreadable payload member: {member.name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read())


if __name__ == "__main__":
    main()
