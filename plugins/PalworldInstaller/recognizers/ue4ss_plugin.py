from __future__ import annotations

import logging
import re

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    entry_full_path,
)

log = logging.getLogger(__name__)

_UE4SS_PLUGIN_RE = re.compile(
    r"ue4ss/mods/[^/]+/dlls/main\.dll$", re.IGNORECASE
)


class Ue4ssPluginRecognizer:
    """Handles UE4SS plugin archives that are already arranged.

    Detects the ``ue4ss/Mods/<name>/dlls/main.dll`` layout used by
    UE4SS plugins (e.g. the PalSchema loader). The archive is already
    in the correct game-relative structure, so routing does nothing.
    """

    name = "ue4ss_plugin"
    priority = 25

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if any(
            _UE4SS_PLUGIN_RE.search(entry_full_path(e, tree))
            for e in ctx.dll_entries
        ):
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        return DiscoveryResult(
            claimed_paths=self._collect_paths(tree),
            should_show_dialog=False,
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        log.info(
            "PalworldInstaller: [ue4ss_plugin] pre-arranged UE4SS "
            "plugin layout accepted as-is"
        )

    @staticmethod
    def _collect_paths(tree: mobase.IFileTree) -> set[str]:
        paths: set[str] = set()

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                full = f"{path}/{entry.name()}" if path else entry.name()
                paths.add(full)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return paths
