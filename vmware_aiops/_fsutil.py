"""Filesystem permission helpers for owner-only state files.

State written under ``~/.vmware-aiops/`` (TTL store, plans, image registry)
can carry VM names, operation plans, and infrastructure topology. Keep the
directory owner-only (0700) and the files owner-read/write (0600). All helpers
are best-effort: a failed chmod must never break the operation it guards.
"""

from __future__ import annotations

import os
from pathlib import Path


def secure_mkdir(directory: Path) -> None:
    """Create ``directory`` (and parents) as 0700, enforcing mode past umask."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass


def secure_chmod_file(path: Path) -> None:
    """Restrict ``path`` to 0600 if it exists. Best-effort."""
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        pass
