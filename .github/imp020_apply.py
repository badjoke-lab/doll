from __future__ import annotations

import shutil
from pathlib import Path

payload = Path(".github/imp020-payload")
if payload.exists():
    shutil.rmtree(payload)
Path(".github/workflows/imp020-apply.yml").unlink(missing_ok=True)
Path(".github/imp020_apply.py").unlink(missing_ok=True)
