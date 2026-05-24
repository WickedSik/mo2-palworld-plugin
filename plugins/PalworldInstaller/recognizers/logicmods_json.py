from __future__ import annotations

import logging

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    move_to,
)

log = logging.getLogger(__name__)


class LogicModsJsonRecognizer:
    """Handles json-only archives (no paks, no scripts).

    Routes ``.json`` files to ``Content/Paks/LogicMods/``.
    """

    name = "logicmods_json"
    priority = 80

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if ctx.json_entries and not ctx.pak_entries and not ctx.lua_entries:
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        claimed = {e.name() for e in ctx.json_entries}
        return DiscoveryResult(
            claimed_paths=claimed,
            should_show_dialog=False,
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        for entry in ctx.json_entries:
            log.info(
                f"PalworldInstaller: [logicmods_json] routing "
                f"{entry.name()} -> Content/Paks/LogicMods/"
            )
            dest = tree.addDirectory("Content/Paks/LogicMods")
            move_to(tree, entry, f"{dest.path('/')}/{entry.name()}")
