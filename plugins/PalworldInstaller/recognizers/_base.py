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

    Each recognizer handles one class of Palworld mod archive. The
    orchestrator calls ``detect()`` on every registered recognizer
    (gather-all), then picks the highest-priority ``MATCH`` or
    ``RequestManual`` as the winner.

    ``detect()`` should use ``ctx`` signals only — no tree walking.
    ``discover()`` and ``route()`` receive the tree for detailed
    analysis but should still prefer ``ctx`` when possible.

    ``route()`` mutates the tree directly — the orchestrator calls
    it after dialog decisions are finalised.
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
