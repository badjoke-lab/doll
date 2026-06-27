from pathlib import Path

module_path = Path("src/doll/state_package.py")
module = module_path.read_text(encoding="utf-8")
if "import zlib\n" not in module:
    module = module.replace("import zipfile\n", "import zipfile\nimport zlib\n", 1)
old = """        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
"""
new = """        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
    ) as exc:
"""
if old not in module:
    raise SystemExit("state package ZIP error tuple not found")
module_path.write_text(module.replace(old, new, 1), encoding="utf-8")
