"""Shared fakes for PropertyCollector-based scale regression tests.

The ops layer batches every inventory read through
``inventory._collect`` / ``inventory._collect_object``
(``PropertyCollector.RetrievePropertiesEx`` + continuation-token paging) so that
large inventories don't trigger a lazy SOAP round-trip per property per object
(GitHub issue #31 and its follow-ups on alarms / health / log scanning).

These fakes let a test feed canned property values through that exact path while
using managed objects that raise on ANY attribute access — so any regression to
per-object lazy reads fails loudly instead of silently going slow.
"""

from __future__ import annotations

from pyVmomi import vim


class _CountingStub:
    """SOAP stub that records how many managed methods were invoked on it.

    A ContainerView's only invoked method is ``DestroyView`` (``view.Destroy()``),
    so ``calls`` doubles as a "destroyed N times" counter.
    """

    def __init__(self) -> None:
        self.calls = 0

    def InvokeMethod(self, mo, info, args):  # noqa: N802 - pyVmomi contract
        self.calls += 1
        return None


class NoLazyMO:
    """Fake managed object: any attribute read is a lazy round-trip = a bug."""

    def __init__(self, label: str) -> None:
        object.__setattr__(self, "_label", label)

    def __getattr__(self, name: str):  # pragma: no cover - only hit on regression
        raise AssertionError(
            f"lazy property access '{name}' on {object.__getattribute__(self, '_label')}"
            " — collection must use PropertyCollector, not per-object attributes"
        )

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other


class _Prop:
    def __init__(self, name, val) -> None:
        self.name = name
        self.val = val


class _ObjContent:
    def __init__(self, obj, props: dict) -> None:
        self.obj = obj
        self.propSet = [_Prop(k, v) for k, v in props.items()]


class _Batch:
    def __init__(self, objects, token=None) -> None:
        self.objects = objects
        self.token = token


class FakePropertyCollector:
    """Returns canned ObjectContent keyed by the requested managed-object type.

    ``fixtures`` maps a vim type -> list of ``(managed_object, props-dict)``.
    Paging is honored so the continuation-token loop is exercised. The same
    keying serves both ``_collect`` (all rows) and ``_collect_object`` (first
    row of the type).
    """

    def __init__(self, fixtures: dict, page_size: int = 1000) -> None:
        self._fixtures = fixtures
        self._page_size = page_size
        self._pending: dict[str, list] = {}
        self._counter = 0
        self.call_count = 0

    def _pages(self, rows):
        return [
            rows[i:i + self._page_size]
            for i in range(0, len(rows), self._page_size)
        ] or [[]]

    def RetrievePropertiesEx(self, specs, options):  # noqa: N802
        self.call_count += 1
        obj_type = specs[0].propSet[0].type
        rows = self._fixtures.get(obj_type, [])
        pages = self._pages(rows)
        first = pages[0]
        token = None
        if len(pages) > 1:
            self._counter += 1
            token = f"tok{self._counter}"
            self._pending[token] = pages[1:]
        return _Batch(
            [_ObjContent(obj, props) for obj, props in first], token=token
        )

    def ContinueRetrievePropertiesEx(self, token):  # noqa: N802
        pages = self._pending.pop(token)
        page = pages[0]
        next_token = None
        if len(pages) > 1:
            self._counter += 1
            next_token = f"tok{self._counter}"
            self._pending[next_token] = pages[1:]
        return _Batch(
            [_ObjContent(obj, props) for obj, props in page], token=next_token
        )


class FakeViewManager:
    """Hands out real ContainerView morefs backed by counting stubs.

    Each created view is recorded so tests can assert every view was destroyed
    exactly once (``view.Destroy()`` -> the stub's single InvokeMethod).
    """

    def __init__(self) -> None:
        self.views: list[_CountingStub] = []

    def CreateContainerView(self, root, obj_type, recursive):  # noqa: N802
        stub = _CountingStub()
        self.views.append(stub)
        return vim.view.ContainerView("cv-fake", stub)


class _FakeContent:
    def __init__(self, pc: FakePropertyCollector) -> None:
        self.viewManager = FakeViewManager()
        self.propertyCollector = pc
        # Real Folder moref so _collect_object's ObjectSpec(obj=...) type-checks.
        self.rootFolder = vim.Folder("group-d1", _CountingStub())


class FakeSI:
    """Minimal ServiceInstance whose RetrieveContent() drives the fakes above."""

    def __init__(self, fixtures: dict, page_size: int = 1000) -> None:
        self.pc = FakePropertyCollector(fixtures, page_size)
        self._content = _FakeContent(self.pc)

    def RetrieveContent(self):  # noqa: N802
        return self._content

    @property
    def views(self) -> list[_CountingStub]:
        return self._content.viewManager.views


def make_si(fixtures: dict, page_size: int = 1000) -> FakeSI:
    """Build a fake ServiceInstance from ``{vim_type: [(obj, props), ...]}``."""
    return FakeSI(fixtures, page_size)
