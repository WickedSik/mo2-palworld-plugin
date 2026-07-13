from __future__ import annotations

import logging

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    entry_full_path,
    move_to,
    ue4ss_mods_base,
)

log = logging.getLogger(__name__)


class PalSchemaRecognizer:
    """Handles PalSchema mod archives.

    Detects archives containing a ``PalSchema/`` folder (at any depth)
    with JSON schema files. Routes content to the PalSchema mods
    directory under the UE4SS runtime:
    ``Binaries/Win{64|GDK}/ue4ss/Mods/PalSchema/mods/<modname>/``.
    """

    name = "palschema"
    priority = 65

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if "palschema" in ctx.deep_folder_names and ctx.has_json_deep:
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        palschema_dir = self._find_palschema_dir(tree)
        if palschema_dir is None:
            return DiscoveryResult()

        claimed: set[str] = set()
        self._collect_paths_under(palschema_dir, claimed)

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
        palschema_dir = self._find_palschema_dir(tree)
        if palschema_dir is None:
            raise RuntimeError(
                "PalSchema marker present but folder not found during route"
            )

        mods_base = ue4ss_mods_base(ctx.platform)
        mods_dir = self._find_child_dir(palschema_dir, "mods")

        if mods_dir is not None:
            mod_folders = [e for e in mods_dir if e.isDir()]
            if mod_folders:
                self._route_structured(
                    tree, mod_folders, mods_base
                )
                return
            self._route_flat_from(
                tree, mods_dir, mods_base, ctx
            )
            return

        self._route_flat_from(tree, palschema_dir, mods_base, ctx)

    def _route_structured(
        self,
        tree: mobase.IFileTree,
        mod_folders: list[mobase.FileTreeEntry],
        mods_base: str,
    ) -> None:
        """Route when archive has PalSchema/mods/<modname>/ structure.
        Each subfolder under mods/ is a separate mod."""
        for mod_folder in mod_folders:
            modname = mod_folder.name()
            dest_base = (
                f"{mods_base}/PalSchema/mods/{modname}"
            )
            entries = self._collect_file_entries(mod_folder)
            if not entries:
                continue

            all_correct = all(
                entry_full_path(entry, tree) == f"{dest_base}/{rel}"
                for entry, rel in entries
            )
            if all_correct:
                log.info(
                    f"PalworldInstaller: [palschema] {modname} already "
                    f"in correct layout under {dest_base}/"
                )
                continue

            tree.addDirectory(dest_base)
            for entry, rel_path in entries:
                target = f"{dest_base}/{rel_path}"
                log.info(
                    f"PalworldInstaller: [palschema] routing "
                    f"{modname}/{rel_path} -> {target}"
                )
                move_to(tree, entry, target)

    def _route_flat_from(
        self,
        tree: mobase.IFileTree,
        source_dir: mobase.IFileTree,
        mods_base: str,
        ctx: WalkContext,
    ) -> None:
        """Route when content is flat (no mods/<modname>/ nesting).
        Derives modname from context."""
        modname = self._derive_modname_flat(source_dir, tree, ctx)
        if not modname:
            raise RuntimeError(
                "PalSchema marker present but no usable mod-name folder "
                "could be derived"
            )

        dest_base = (
            f"{mods_base}/PalSchema/mods/{modname}"
        )
        entries = self._collect_file_entries(source_dir)
        if not entries:
            raise RuntimeError(
                "PalSchema marker present but no content found to route"
            )

        tree.addDirectory(dest_base)
        for entry, rel_path in entries:
            target = f"{dest_base}/{rel_path}"
            log.info(
                f"PalworldInstaller: [palschema] routing "
                f"{rel_path} -> {target}"
            )
            move_to(tree, entry, target)

    def _find_palschema_dir(
        self, tree: mobase.IFileTree
    ) -> mobase.IFileTree | None:
        """Find the first directory named PalSchema (case-insensitive)
        at any depth."""
        result: list[mobase.IFileTree] = []

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isDir() and entry.name().lower() == "palschema":
                result.append(entry)
                return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return result[0] if result else None

    @staticmethod
    def _find_child_dir(
        parent: mobase.IFileTree, name_lower: str
    ) -> mobase.IFileTree | None:
        return next(
            (e for e in parent if e.isDir()
             and e.name().lower() == name_lower),
            None,
        )

    def _derive_modname_flat(
        self,
        source_dir: mobase.IFileTree,
        tree: mobase.IFileTree,
        ctx: WalkContext,
    ) -> str:
        """Derive modname when no mods/<modname>/ structure exists.
        Priority: wrapping folder above PalSchema > GuessedString."""
        palschema_dir = self._find_palschema_dir(tree)
        if palschema_dir is not None:
            parent = palschema_dir.parent()
            if parent is not None and parent is not tree:
                return parent.name()

        if ctx.suggested_mod_name:
            return ctx.suggested_mod_name

        return ""

    @staticmethod
    def _collect_file_entries(
        dir_entry: mobase.IFileTree,
    ) -> list[tuple[mobase.FileTreeEntry, str]]:
        """Collect all file entries under a directory with paths
        relative to that directory."""
        entries: list[tuple[mobase.FileTreeEntry, str]] = []

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                rel = f"{path}/{entry.name()}" if path else entry.name()
                entries.append((entry, rel))
            return mobase.IFileTree.WalkReturn.CONTINUE

        dir_entry.walk(visit)
        return entries

    @staticmethod
    def _collect_paths_under(
        dir_entry: mobase.IFileTree, paths: set[str]
    ) -> None:
        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                full = f"{path}/{entry.name()}" if path else entry.name()
                paths.add(full)
            return mobase.IFileTree.WalkReturn.CONTINUE

        dir_entry.walk(visit)
