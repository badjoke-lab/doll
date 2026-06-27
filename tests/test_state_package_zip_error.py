from __future__ import annotations

import zipfile
import zlib
from pathlib import Path
from typing import NoReturn

import pytest

from doll import state, state_package, workspace


def test_zip_decompression_error_is_a_bounded_state_package_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = workspace.initialize_workspace(tmp_path / "source")
    with state.initialize_state_repository(initialized.root):
        pass

    exported = tmp_path / "state-package.zip"
    with state.open_state_repository(initialized.root, read_only=True) as repository:
        state_package.export_state_package(repository, exported)

    def fail_read(
        self: zipfile.ZipFile,
        name: object,
        pwd: bytes | None = None,
    ) -> NoReturn:
        del self, name, pwd
        raise zlib.error("synthetic decompression failure")

    monkeypatch.setattr(zipfile.ZipFile, "read", fail_read)
    target = tmp_path / "target"
    with pytest.raises(
        state_package.StatePackageValidationError,
        match="state package ZIP is unreadable",
    ):
        state_package.import_state_package(exported, target)
    assert not target.exists()
