from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tests/test_project_status.py"
text = path.read_text(encoding="utf-8")
old = '''    assert tuple(item.work_item_id for item in status.next_ready_work) == (ids["ready"],)
'''
new = '''    assert tuple(item.work_item_id for item in status.next_ready_work) == (
        ids["blocker"],
        ids["ready"],
    )
'''
if old not in text:
    raise RuntimeError("ready-work expectation anchor missing")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
