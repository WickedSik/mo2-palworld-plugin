from __future__ import annotations

import logging

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    entry_parent_path,
    move_to,
    suffix,
)

log = logging.getLogger(__name__)

_ALTERMATIC_MARKERS = frozenset({"animjson", "swapjson"})
_PAK_COMPANION_SUFFIXES = frozenset({"pak", "utoc", "ucas"})


class AltermaticRecognizer:
    """Handles Altermatic mod archives.

    Detects archives that hold an ``AnimJSON/`` or ``SwapJSON/`` folder
    (at any depth) with JSON config files. Routes:
    - ``.pak`` with ``_P`` suffix → ``Content/Paks/~mods/``
    - ``.pak`` without ``_P`` suffix → ``Content/Paks/LogicMods/``
    - ``AnimJSON/`` and ``SwapJSON/`` dirs → ``Content/Paks/~mods/{name}/``
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
        claimed = self._collect_claimed_paths(tree, ctx)
        summary = self._build_routing_summary(tree, ctx)
        return DiscoveryResult(
            claimed_paths=claimed,
            should_show_dialog=False,
            routing_summary=summary,
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        self._route_paks(tree, ctx)
        self._route_marker_dirs(tree, ctx)

    def _route_paks(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> None:
        """Route pak files. A ``_P`` suffix goes to ~mods, everything
        else goes to LogicMods. Companion files (.utoc/.ucas) follow
        their pak."""
        groups = self._build_pak_groups(ctx, tree)
        for stem, entries in groups.items():
            if stem.endswith("_P"):
                dest_path = "Content/Paks/~mods"
            else:
                dest_path = "Content/Paks/LogicMods"

            dest = tree.addDirectory(dest_path)
            target_dir = dest.path("/")
            for entry in entries:
                log.info(
                    f"PalworldInstaller: [altermatic] routing "
                    f"{entry.name()} -> {dest_path}/"
                )
                move_to(tree, entry, f"{target_dir}/{entry.name()}")

    def _route_marker_dirs(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> None:
        """Route AnimJSON/ and SwapJSON/ directories to
        Content/Paks/~mods/{AnimJSON|SwapJSON}/."""
        marker_dirs = self._find_marker_dirs(tree)
        if not marker_dirs:
            return

        for marker_dir in marker_dirs:
            canonical_name = (
                "AnimJSON"
                if marker_dir.name().lower() == "animjson"
                else "SwapJSON"
            )
            target_path = f"Content/Paks/~mods/{canonical_name}"
            log.info(
                f"PalworldInstaller: [altermatic] routing "
                f"{marker_dir.name()}/ -> {target_path}/"
            )
            parent = tree.addDirectory("Content/Paks/~mods")
            tree.move(
                marker_dir,
                f"{parent.path('/')}/{canonical_name}",
                policy=mobase.IFileTree.InsertPolicy.MERGE,
            )

    def _build_routing_summary(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> list[str]:
        lines: list[str] = []
        groups = self._build_pak_groups(ctx, tree)
        for stem, entries in groups.items():
            if stem.endswith("_P"):
                dest = "Content/Paks/~mods/"
            else:
                dest = "Content/Paks/LogicMods/"
            names = ", ".join(e.name() for e in entries)
            lines.append(f"{names} → {dest}")

        marker_dirs = self._find_marker_dirs(tree)
        for marker_dir in marker_dirs:
            canonical = (
                "AnimJSON"
                if marker_dir.name().lower() == "animjson"
                else "SwapJSON"
            )
            lines.append(
                f"{marker_dir.name()}/ → Content/Paks/~mods/{canonical}/"
            )
        return lines

    @staticmethod
    def _build_pak_groups(
        ctx: WalkContext, tree: mobase.IFileTree
    ) -> dict[str, list[mobase.FileTreeEntry]]:
        """Group pak + companion entries by stem."""
        groups: dict[str, list[mobase.FileTreeEntry]] = {}
        all_entries = list(ctx.pak_entries) + list(ctx.companion_entries)
        for entry in all_entries:
            s = suffix(entry)
            if s not in _PAK_COMPANION_SUFFIXES:
                continue
            stem = entry.name()[: -(len(s) + 1)]
            groups.setdefault(stem, []).append(entry)
        return groups

    @staticmethod
    def _find_marker_dirs(
        tree: mobase.IFileTree,
    ) -> list[mobase.FileTreeEntry]:
        """Find all AnimJSON/SwapJSON directories at any depth."""
        dirs: list[mobase.FileTreeEntry] = []

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isDir() and entry.name().lower() in _ALTERMATIC_MARKERS:
                dirs.append(entry)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return dirs

    @staticmethod
    def _collect_claimed_paths(
        tree: mobase.IFileTree, ctx: WalkContext
    ) -> set[str]:
        paths: set[str] = set()
        for entry in ctx.pak_entries:
            parent = entry_parent_path(entry, tree)
            full = f"{parent}/{entry.name()}" if parent else entry.name()
            paths.add(full)
        for entry in ctx.companion_entries:
            parent = entry_parent_path(entry, tree)
            full = f"{parent}/{entry.name()}" if parent else entry.name()
            paths.add(full)

        def collect_dir(dir_entry: mobase.FileTreeEntry) -> None:
            def visit(
                path: str, entry: mobase.FileTreeEntry
            ) -> mobase.IFileTree.WalkReturn:
                if entry.isFile():
                    full = f"{path}/{entry.name()}" if path else entry.name()
                    paths.add(full)
                return mobase.IFileTree.WalkReturn.CONTINUE
            dir_entry.walk(visit)

        marker_dirs_seen: list[mobase.FileTreeEntry] = []

        def find_markers(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isDir() and entry.name().lower() in _ALTERMATIC_MARKERS:
                marker_dirs_seen.append(entry)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(find_markers)
        for d in marker_dirs_seen:
            collect_dir(d)

        return paths
