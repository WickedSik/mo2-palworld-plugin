from __future__ import annotations

from typing import Protocol

import mobase

from ..models import (
    DetectionVerdict,
    DiscoveryResult,
    WalkContext,
)


class ModRecognizer(Protocol):
    """Interface for archive recognizers.

    Each recognizer handles one kind of Palworld mod archive. The
    installer calls ``detect()`` on every registered recognizer, then
    picks the winner. The winner is the highest-priority ``MATCH`` or
    ``RequestManual``.

    ``detect()`` should only read signals from ``ctx``. It must not
    walk the tree. ``discover()`` and ``route()`` receive the tree for
    closer analysis, but they should still prefer ``ctx`` when they can.

    ``route()`` changes the tree in place. The installer calls it after
    the dialog choices are final.
    """

    @property
    def name(self) -> str: ...

    @property
    def priority(self) -> int: ...

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DetectionVerdict: ...

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult: ...

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None: ...
