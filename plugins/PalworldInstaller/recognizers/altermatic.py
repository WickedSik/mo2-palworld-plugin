from __future__ import annotations

import logging

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    move_to,
    suffix,
)

log = logging.getLogger(__name__)

_ALTERMATIC_MARKERS = frozenset({"animjson", "swapjson"})


class AltermaticRecognizer:
    """Handles Altermatic user mod archives.

    Detects archives containing an ``AnimJSON/`` or ``SwapJSON/`` folder
    (at any depth) with JSON configuration files. Routes ``.json`` files
    to ``Content/Paks/LogicMods/``.
    """

    name = "altermatic"
    priority = 70

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        has_marker = bool(ctx.deep_folder_names & _ALTERMATIC_MARKERS)
        if has_marker and ctx.has_json_deep:
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        claimed = self._collect_json_paths(tree)
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
        json_files = self._find_json_entries(tree)
        if not json_files:
            return

        dest = tree.addDirectory("Content/Paks/LogicMods")
        for entry in json_files:
            target = f"{dest.path('/')}/{entry.name()}"
            log.info(
                f"PalworldInstaller: [altermatic] routing "
                f"{entry.name()} -> Content/Paks/LogicMods/"
            )
            move_to(tree, entry, target)

    @staticmethod
    def _find_json_entries(
        tree: mobase.IFileTree,
    ) -> list[mobase.FileTreeEntry]:
        entries: list[mobase.FileTreeEntry] = []

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile() and suffix(entry) == "json":
                entries.append(entry)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return entries

    @staticmethod
    def _collect_json_paths(tree: mobase.IFileTree) -> set[str]:
        paths: set[str] = set()

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile() and suffix(entry) == "json":
                full = f"{path}/{entry.name()}" if path else entry.name()
                paths.add(full)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return paths
