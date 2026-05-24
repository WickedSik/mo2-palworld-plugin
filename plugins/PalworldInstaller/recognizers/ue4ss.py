from __future__ import annotations

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    RequestManual,
    WalkContext,
)


class Ue4ssSkipRecognizer:
    """Detects archives bundling UE4SS (``ue4ss.dll`` present anywhere).

    UE4SS installations require manual placement and should not be
    rewritten by the automatic installer. Returns ``RequestManual``
    so the orchestrator can decline the archive.

    Note: for behavioral parity with the pre-M6 installer, the
    orchestrator currently handles UE4SS as a pre-pass (returning
    ``False`` from ``isArchiveSupported``) rather than routing
    through the recognizer. This recognizer exists for future use
    when the orchestrator migrates to full recognizer-driven
    detection.
    """

    name = "ue4ss"
    priority = 20

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult | RequestManual:
        if ctx.has_ue4ss_dll:
            return RequestManual(
                "UE4SS install should be performed manually"
            )
        return RecognitionResult.NO_MATCH

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
