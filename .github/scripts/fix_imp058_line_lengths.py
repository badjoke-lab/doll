from pathlib import Path

path = Path("src/doll/shutdown_escape.py")
text = path.read_text(encoding="utf-8")

old_query = '''            "SELECT id, sensitivity FROM records WHERE record_type = 'conversation' ORDER BY id"
'''
new_query = '''            """
            SELECT id, sensitivity
            FROM records
            WHERE record_type = 'conversation'
            ORDER BY id
            """
'''
old_readme = '''        b"No model, cloud credential, network connection, preferred UI, or doll service is required.\\n"
'''
new_readme = '''        b"No model, cloud credential, network connection, preferred UI, "
        b"or doll service is required.\\n"
'''

for old, new, label in (
    (old_query, new_query, "conversation query"),
    (old_readme, new_readme, "README sentence"),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one {label} target, found {count}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8", newline="\n")
