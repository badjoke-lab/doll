from pathlib import Path

path = Path("src/doll/shutdown_escape.py")
text = path.read_text(encoding="utf-8")

old_query = '''        conversation_rows = repository.connection.execute(
            "SELECT id, sensitivity FROM records WHERE record_type = 'conversation' ORDER BY id"
        ).fetchall()
'''
new_query = '''        conversation_query = "\\n".join(
            (
                "SELECT id, sensitivity",
                "FROM records",
                "WHERE record_type = 'conversation'",
                "ORDER BY id",
            )
        )
        conversation_rows = repository.connection.execute(conversation_query).fetchall()
'''
old_readme = '''def _readme_bytes() -> bytes:
    return (
        b"Doll shutdown escape bundle\\n"
        b"\\n"
        b"This archive is a user-owned recovery artifact.\\n"
        b"Start with RECOVERY.md and manifest.json.\\n"
        b"Run `python inspect_escape.py <bundle.zip>` after extracting inspect_escape.py.\\n"
        b"No model, cloud credential, network connection, preferred UI, or doll service is required.\\n"
    )
'''
new_readme = '''def _readme_bytes() -> bytes:
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

for old, new, label in (
    (old_query, new_query, "conversation query"),
    (old_readme, new_readme, "README function"),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label} target, found {count}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8", newline="\n")
