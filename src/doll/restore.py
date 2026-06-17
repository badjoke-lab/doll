"""Public alias for the backup restore implementation module."""

from __future__ import annotations

import sys

from doll import restore_impl as _implementation

sys.modules[__name__] = _implementation
