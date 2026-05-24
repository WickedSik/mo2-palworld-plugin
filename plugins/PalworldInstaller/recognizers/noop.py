from __future__ import annotations

import mobase

from ..models import DiscoveryResult, RequestManual, WalkContext


class NoopRecognizer:
    """Catch-all recognizer. Always returns ``RequestManual`` so the
    orchestrator has a definitive answer for every archive — unclaimed
    archives surface as ``MANUAL_REQUESTED`` rather than slipping
    through silently."""

    name = "noop"
    priority = 999

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RequestManual:
        return RequestManual("no recognizer claimed this archive")

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        return DiscoveryResult()

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        pass
