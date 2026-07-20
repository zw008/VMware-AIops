"""Session plumbing for the capability evals.

The ``board`` fixture is session-scoped so that one ``pytest -m capability`` run
produces one ``_scores.json`` holding every measurement taken. Running a single
capability file rewrites the file with only that file's scores — intentional, so
a partial run is never mistaken for a full one; regenerate with the full
``-m capability`` selection before committing a score change.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from typing import Any

import pytest

from ._scoring import ScoreBoard
from ._skill import SERVER_MODULE, get_server

#: Prefix of the modules the read-only gate affects at import time.
_SERVER_PREFIX = SERVER_MODULE.split(".")[0] + ".mcp_server"

_READ_ONLY_ENV = "VMWARE_READ_ONLY"


def load_tools(read_only: bool = False) -> tuple[Any, ...]:
    """Import the MCP server fresh and return the tools it registers.

    Re-imports rather than reusing the loaded module because the read-only gate
    runs at import time. The original module objects are restored afterwards —
    deleting them would leave other test files monkeypatching a module nobody
    imports any more, and their patches would silently stop applying.
    """
    saved = {n: m for n, m in sys.modules.items() if n.startswith(_SERVER_PREFIX)}
    prior = os.environ.get(_READ_ONLY_ENV)
    try:
        if read_only:
            os.environ[_READ_ONLY_ENV] = "true"
        else:
            os.environ.pop(_READ_ONLY_ENV, None)
        for name in list(saved):
            del sys.modules[name]
        mod = importlib.import_module(SERVER_MODULE)
        return tuple(asyncio.run(get_server(mod).list_tools()))
    finally:
        if prior is None:
            os.environ.pop(_READ_ONLY_ENV, None)
        else:
            os.environ[_READ_ONLY_ENV] = prior
        for name in [n for n in sys.modules if n.startswith(_SERVER_PREFIX)]:
            del sys.modules[name]
        sys.modules.update(saved)


@pytest.fixture(scope="session")
def board() -> Any:
    b = ScoreBoard()
    yield b
    b.write()


@pytest.fixture(scope="session")
def tools() -> tuple[Any, ...]:
    """Every tool the real FastMCP registry exposes, as the agent would see it.

    Read from ``mcp.list_tools()`` rather than from the source, because the
    registry is the only thing that reflects decorators, gating, and the schema
    FastMCP actually derives from each signature — which is what lands in the
    model's context, not the docstring as written.
    """
    return load_tools(read_only=False)


@pytest.fixture(scope="session")
def gated_tools() -> tuple[Any, ...]:
    """The surface an operator gets under ``VMWARE_READ_ONLY=true``."""
    return load_tools(read_only=True)
