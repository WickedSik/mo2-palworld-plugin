from __future__ import annotations

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    RequestManual,
    WalkContext,
)


class Ue4ssSkipRecognizer:
    """Detects archives that bundle UE4SS (``ue4ss.dll`` present
    anywhere).

    UE4SS installs must be placed by hand. The automatic installer
    should not rewrite them. Returns ``RequestManual`` so the installer
    can decline the archive.

    Note: to keep the same behavior as the pre-M6 installer, the
    installer currently handles UE4SS in a pre-pass. It returns
    ``False`` from ``isArchiveSupported`` instead of going through the
    recognizer. This recognizer is here for later use, once the
    installer moves to full recognizer-driven detection.
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
