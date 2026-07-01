import re
from pathlib import Path

path = Path("src/doll/shutdown_escape.py")
text = path.read_text(encoding="utf-8")

query_pattern = re.compile(
    r"        conversation_rows = repository\.connection\.execute\(\n"
    r"            \"SELECT id, sensitivity FROM records WHERE record_type = 'conversation' ORDER BY id\"\n"
    r"        \)\.fetchall\(\)\n"
)
query_replacement = '''        conversation_query = "\\n".join(
            (
                "SELECT id, sensitivity",
                "FROM records",
                "WHERE record_type = 'conversation'",
                "ORDER BY id",
            )
        )
        conversation_rows = repository.connection.execute(conversation_query).fetchall()
'''
text, query_count = query_pattern.subn(lambda _: query_replacement, text)
if query_count != 1:
    raise SystemExit(f"expected one conversation query target, found {query_count}")

event_query_old = '''            SELECT id, sensitivity, json_extract(metadata_json, '$.conversation_id') AS conversation_id
'''
event_query_new = '''            SELECT
                id,
                sensitivity,
                json_extract(metadata_json, '$.conversation_id') AS conversation_id
'''
event_query_count = text.count(event_query_old)
if event_query_count != 1:
    raise SystemExit(f"expected one event query target, found {event_query_count}")
text = text.replace(event_query_old, event_query_new)

readme_pattern = re.compile(
    r"def _readme_bytes\(\) -> bytes:\n.*?(?=\n\ndef _recovery_bytes\(\) -> bytes:)",
    re.DOTALL,
)
readme_replacement = '''def _readme_bytes() -> bytes:
    return b"".join(
        (
            b"Doll shutdown escape bundle\\n",
            b"\\n",
            b"This archive is a user-owned recovery artifact.\\n",
            b"Start with RECOVERY.md and manifest.json.\\n",
            b"Run `python inspect_escape.py <bundle.zip>` after extracting inspect_escape.py.\\n",
            b"No model, cloud credential, network connection, preferred UI, ",
            b"or doll service is required.\\n",
        )
    )
'''
text, readme_count = readme_pattern.subn(lambda _: readme_replacement, text)
if readme_count != 1:
    raise SystemExit(f"expected one README function target, found {readme_count}")

path.write_text(text, encoding="utf-8", newline="\n")
