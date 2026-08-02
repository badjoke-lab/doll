from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one match in {path}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


state_db = ROOT / "src/doll/state_db.py"
replace_once(
    state_db,
    "def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:\n"
    "    if read_only:\n"
    "        connection = sqlite3.connect(\n"
    "            f\"{path.resolve().as_uri()}?mode=ro\",\n"
    "            uri=True,\n"
    "            isolation_level=None,\n"
    "        )\n"
    "    else:\n"
    "        connection = sqlite3.connect(path, isolation_level=None)\n",
    "def _connect(\n"
    "    path: Path,\n"
    "    *,\n"
    "    read_only: bool,\n"
    "    immutable: bool = False,\n"
    ") -> sqlite3.Connection:\n"
    "    if immutable and not read_only:\n"
    "        raise ValueError(\"immutable SQLite access requires read-only mode\")\n"
    "    if read_only:\n"
    "        immutable_query = \"&immutable=1\" if immutable else \"\"\n"
    "        connection = sqlite3.connect(\n"
    "            f\"{path.resolve().as_uri()}?mode=ro{immutable_query}\",\n"
    "            uri=True,\n"
    "            isolation_level=None,\n"
    "        )\n"
    "    else:\n"
    "        connection = sqlite3.connect(path, isolation_level=None)\n",
)

state_schema = ROOT / "src/doll/state_schema.py"
replace_once(
    state_schema,
    "def open_state_repository(\n"
    "    path: Path | None = None,\n"
    "    *,\n"
    "    read_only: bool = False,\n"
    "    migrations: Iterable[Migration] = MIGRATIONS,\n"
    ") -> StateRepository:\n",
    "def open_state_repository(\n"
    "    path: Path | None = None,\n"
    "    *,\n"
    "    read_only: bool = False,\n"
    "    immutable: bool = False,\n"
    "    migrations: Iterable[Migration] = MIGRATIONS,\n"
    ") -> StateRepository:\n",
)
replace_once(
    state_schema,
    "    connection = _connect(database_path, read_only=read_only)\n",
    "    if immutable and not read_only:\n"
    "        raise ValueError(\"immutable state access requires read-only mode\")\n"
    "    connection = _connect(\n"
    "        database_path,\n"
    "        read_only=read_only,\n"
    "        immutable=immutable,\n"
    "    )\n",
)

doctor = ROOT / "src/doll/doctor.py"
replace_once(
    doctor,
    "from doll.state import CURRENT_SCHEMA_VERSION, StateError, open_state_repository\n",
    "from doll.state import (\n"
    "    CURRENT_SCHEMA_VERSION,\n"
    "    STATE_DATABASE_NAME,\n"
    "    StateError,\n"
    "    open_state_repository,\n"
    ")\n",
)
replace_once(
    doctor,
    "    try:\n"
    "        with open_state_repository(workspace.root, read_only=True) as repository:\n",
    "    database_path = workspace.root / \"state\" / STATE_DATABASE_NAME\n"
    "    if _has_pending_sqlite_journal(database_path):\n"
    "        checks.append(\n"
    "            DoctorCheck(\n"
    "                check_id=\"state_repository\",\n"
    "                status=\"fail\",\n"
    "                summary=\"Authoritative state has an active SQLite journal.\",\n"
    "                guidance=(\n"
    "                    \"Close active doll processes and retry the read-only diagnostic.\",\n"
    "                    \"Do not delete SQLite journal files manually.\",\n"
    "                ),\n"
    "            )\n"
    "        )\n"
    "        return _report(\n"
    "            checks,\n"
    "            profile_preference=workspace.record.profile_preference,\n"
    "        )\n\n"
    "    try:\n"
    "        with open_state_repository(\n"
    "            workspace.root,\n"
    "            read_only=True,\n"
    "            immutable=True,\n"
    "        ) as repository:\n",
)
replace_once(
    doctor,
    "def _safe_workspace_directory(root: Path, name: str) -> bool:\n",
    "def _has_pending_sqlite_journal(database_path: Path) -> bool:\n"
    "    for suffix in (\"-wal\", \"-journal\"):\n"
    "        candidate = Path(f\"{database_path}{suffix}\")\n"
    "        try:\n"
    "            if candidate.is_file() and candidate.stat().st_size > 0:\n"
    "                return True\n"
    "        except OSError:\n"
    "            return True\n"
    "    return False\n\n\n"
    "def _safe_workspace_directory(root: Path, name: str) -> bool:\n",
)

tests = ROOT / "tests/test_imp_072_doctor.py"
replace_once(
    tests,
    "        assert kwargs == {\"read_only\": True}\n",
    "        assert kwargs == {\"read_only\": True, \"immutable\": True}\n",
)

print("IMP-072 immutable read-only patch applied")
