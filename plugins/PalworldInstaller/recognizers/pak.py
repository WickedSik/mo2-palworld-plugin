from __future__ import annotations

import logging

import mobase

from ..models import (
    DiscoveryResult,
    PakGroup,
    RecognitionResult,
    WalkContext,
    entry_parent_path,
    move_to,
    resolve_pak_dest_path,
    suffix,
)
from ..presets import PAK_PRESETS

log = logging.getLogger(__name__)

_PAK_COMPANION_SUFFIXES = ("pak", "utoc", "ucas")
_ANIM_SWAP_FOLDERS = ("animjson", "swapjson")


class PakRecognizer:
    """Handles archives that hold ``.pak`` files. This also covers their
    ``.utoc``/``.ucas`` companions, any linked AnimJSON/SwapJSON dirs,
    and loose ``.json`` files at the root.

    Routes paks to ``Content/Paks/<destination>/``. The destination
    comes from the M1 rules (stem suffix and whether a json dir is
    present) or from the user's dialog choice.
    """

    name = "pak"
    priority = 100

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if ctx.pak_entries:
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        groups, json_dirs, loose_jsons = self._build_pak_groups(tree, ctx)
        default_routing = self._compute_default_routing(groups)

        log.debug(
            f"PalworldInstaller: [pak] discovered {len(groups)} group(s), "
            f"{len(json_dirs)} json dir(s), {len(loose_jsons)} loose json(s)"
        )
        for g in groups:
            log.debug(
                f"PalworldInstaller: [pak]   group {g.group_id} "
                f"-> default {default_routing.get(g.group_id, '?')}"
            )

        claimed: set[str] = set()
        for g in groups:
            claimed.add(g.group_id)
            for c in g.companions:
                claimed.add(
                    f"{g.current_parent_path}/{c.name()}".lstrip("/")
                )
        for d in json_dirs:
            claimed.add(d.name())
        for j in loose_jsons:
            claimed.add(j.name())

        should_show = self._should_show_dialog(groups, default_routing)

        return DiscoveryResult(
            pak_groups=groups,
            default_routing=default_routing,
            claimed_paths=claimed,
            should_show_dialog=should_show,
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        groups, json_dirs, loose_jsons = self._build_pak_groups(tree, ctx)
        skipped_group_ids: set[str] = set()

        for g in groups:
            decision = decisions.get(g.group_id, "LogicMods")
            log.info(
                f"PalworldInstaller: [pak] routing {g.group_id} "
                f"-> {decision}"
            )

        for g in groups:
            decision = decisions.get(g.group_id, "LogicMods")
            members = [g.pak, *g.companions]

            if decision == "SKIP":
                for entry in list(members):
                    tree.remove(entry)
                skipped_group_ids.add(g.group_id)
            elif decision == "ROOT":
                for entry in list(members):
                    move_to(tree, entry, entry.name())
            else:
                dest_path = resolve_pak_dest_path(decision)
                if not dest_path:
                    continue
                dest = tree.addDirectory(dest_path)
                target_dir = dest.path("/")
                for entry in list(members):
                    move_to(tree, entry, f"{target_dir}/{entry.name()}")

        self._route_json_dirs(
            tree, groups, decisions, json_dirs, skipped_group_ids
        )

        for entry in loose_jsons:
            dest = tree.addDirectory("Content/Paks/LogicMods")
            move_to(tree, entry, f"{dest.path('/')}/{entry.name()}")

    # --- internal ------------------------------------------------------------

    def _build_pak_groups(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> tuple[list[PakGroup], list[mobase.FileTreeEntry], list[mobase.FileTreeEntry]]:
        all_entries = list(ctx.pak_entries) + list(ctx.companion_entries)
        bucketed: dict[tuple[int, str], list[mobase.FileTreeEntry]] = {}
        for entry in all_entries:
            s = suffix(entry)
            if s not in _PAK_COMPANION_SUFFIXES:
                continue
            stem = entry.name()[: -(len(s) + 1)]
            parent = entry.parent()
            parent_key = id(parent) if parent is not None else id(tree)
            bucketed.setdefault((parent_key, stem), []).append(entry)

        root_json_dirs = list(ctx.json_dirs)
        root_loose_jsons = list(ctx.json_entries)

        groups: list[PakGroup] = []
        for (_parent_key, stem), entries in bucketed.items():
            pak = next((e for e in entries if suffix(e) == "pak"), None)
            if pak is None:
                continue
            companions = [e for e in entries if e is not pak]
            parent_path = entry_parent_path(pak, tree)
            is_at_root = parent_path == ""
            groups.append(
                PakGroup(
                    group_id=f"{parent_path}/{pak.name()}".lstrip("/"),
                    stem=stem,
                    pak=pak,
                    companions=companions,
                    json_dirs=list(root_json_dirs) if is_at_root else [],
                    current_parent_path=parent_path,
                )
            )
        return groups, root_json_dirs, root_loose_jsons

    @staticmethod
    def _compute_default_routing(groups: list[PakGroup]) -> dict[str, str]:
        decisions: dict[str, str] = {}
        for g in groups:
            normalized = g.current_parent_path.strip().strip("/").lower()
            if normalized.startswith("content/paks/"):
                normalized = normalized[len("content/paks/"):]

            if normalized == "":
                if g.json_dirs:
                    decisions[g.group_id] = "~mods"
                elif g.stem.endswith("_P"):
                    decisions[g.group_id] = "~mods"
                else:
                    decisions[g.group_id] = "LogicMods"
            elif normalized == "logicmods":
                decisions[g.group_id] = "LogicMods"
            elif normalized == "~mods":
                decisions[g.group_id] = "~mods"
            else:
                decisions[g.group_id] = g.current_parent_path
        return decisions

    @staticmethod
    def _should_show_dialog(
        groups: list[PakGroup], decisions: dict[str, str]
    ) -> bool:
        if len(groups) > 1:
            return True
        for g in groups:
            decision = decisions.get(g.group_id)
            if (
                decision is not None
                and decision != "SKIP"
                and decision not in PAK_PRESETS
            ):
                return True
        return False

    @staticmethod
    def _route_json_dirs(
        tree: mobase.IFileTree,
        groups: list[PakGroup],
        decisions: dict[str, str],
        json_dirs: list[mobase.FileTreeEntry],
        skipped_group_ids: set[str],
    ) -> None:
        if not json_dirs:
            return

        root_groups = [g for g in groups if g.current_parent_path == ""]
        if root_groups and all(
            g.group_id in skipped_group_ids for g in root_groups
        ):
            for entry in list(json_dirs):
                tree.remove(entry)
            return

        target_dest_path = "Content/Paks/~mods"
        surviving = [
            g for g in root_groups if g.group_id not in skipped_group_ids
        ]
        if len(surviving) == 1:
            decision = decisions.get(surviving[0].group_id, "LogicMods")
            if decision not in PAK_PRESETS and decision != "SKIP":
                resolved = resolve_pak_dest_path(decision)
                if resolved:
                    target_dest_path = resolved

        for entry in list(json_dirs):
            target_name = (
                "AnimJSON"
                if entry.name().lower() == "animjson"
                else "SwapJSON"
            )
            parent = tree.addDirectory(target_dest_path)
            tree.move(
                entry,
                f"{parent.path('/')}/{target_name}",
                policy=mobase.IFileTree.InsertPolicy.MERGE,
            )

    @staticmethod
    def format_pak_label(g: PakGroup) -> str:
        """Label for a dialog row. Shows the filename, and adds a
        parent-path hint when the pak already sits inside a directory."""
        if g.current_parent_path:
            return f"{g.pak.name()}  ({g.current_parent_path}/)"
        return g.pak.name()
