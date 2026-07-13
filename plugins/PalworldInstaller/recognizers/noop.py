from __future__ import annotations

import mobase

from ..models import DiscoveryResult, RequestManual, WalkContext


class NoopRecognizer:
    """Catch-all recognizer. Always returns ``RequestManual`` so the
    installer has a clear answer for every archive. Archives that no
    other recognizer claimed then show up as ``MANUAL_REQUESTED``
    instead of passing by unnoticed."""

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
