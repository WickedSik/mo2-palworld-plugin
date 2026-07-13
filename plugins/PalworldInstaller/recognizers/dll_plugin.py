from __future__ import annotations

import logging
import re

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    entry_full_path,
    ue4ss_mods_base,
)

log = logging.getLogger(__name__)

# A UE4SS C++ plugin shipped un-arranged: `<name>/dlls/main.dll` directly at
# the archive root (e.g. the PalSchema loader, Nexus 2361). The pre-arranged
# `ue4ss/Mods/<name>/dlls/main.dll` layout has more path segments and is owned
# by Ue4ssPluginRecognizer, so the two patterns never overlap.
_ROOT_DLL_PLUGIN_RE = re.compile(r"^[^/]+/dlls/main\.dll$", re.IGNORECASE)


class DllPluginRecognizer:
    """Handles un-arranged UE4SS C++ plugin archives.

    Detects the standard UE4SS C++ mod layout shipped at the archive
    root -- ``<name>/dlls/main.dll`` (e.g. the PalSchema loader) -- and
    arranges the whole ``<name>/`` folder into the directory UE4SS
    scans: ``Binaries/Win{64|GDK}/ue4ss/Mods/<name>/``. The ``dlls/``,
    ``enabled.txt`` activation flag, and any ``mods/`` scaffold ride
    along unchanged.

    The already-arranged ``ue4ss/Mods/<name>/dlls/main.dll`` layout is a
    structurally distinct case owned by ``Ue4ssPluginRecognizer`` (which
    accepts it as-is, priority 25 -- ahead of this recognizer's 30).
    """

    name = "dll_plugin"
    priority = 30

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if any(
            _ROOT_DLL_PLUGIN_RE.search(entry_full_path(e, tree))
            for e in ctx.dll_entries
        ):
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        claimed: set[str] = set()
        for plugin_dir in self._plugin_dirs(tree, ctx):
            prefix = entry_full_path(plugin_dir, tree)
            self._collect_paths_under(plugin_dir, prefix, claimed)

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
        base = ue4ss_mods_base(ctx.platform)

        for plugin_dir in self._plugin_dirs(tree, ctx):
            name = plugin_dir.name()
            target = f"{base}/{name}"

            if entry_full_path(plugin_dir, tree) == target:
                log.info(
                    f"PalworldInstaller: [dll_plugin] {name} already "
                    f"in canonical UE4SS layout under {target}/"
                )
                continue

            log.info(
                f"PalworldInstaller: [dll_plugin] routing {name}/ "
                f"-> {target}/"
            )
            tree.move(
                plugin_dir,
                target,
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )

    # --- internal ------------------------------------------------------------

    @staticmethod
    def _plugin_dirs(
        tree: mobase.IFileTree, ctx: WalkContext
    ) -> list[mobase.FileTreeEntry]:
        """The root-level ``<name>/`` folders that hold a matching
        ``dlls/main.dll``. De-duplicated by identity so an archive with
        several plugins yields one entry per plugin."""
        found: dict[int, mobase.FileTreeEntry] = {}
        for entry in ctx.dll_entries:
            if not _ROOT_DLL_PLUGIN_RE.search(entry_full_path(entry, tree)):
                continue
            dlls_dir = entry.parent()
            if dlls_dir is None:
                continue
            name_dir = dlls_dir.parent()
            if name_dir is None or name_dir is tree:
                continue
            found.setdefault(id(name_dir), name_dir)
        return list(found.values())

    @staticmethod
    def _collect_paths_under(
        dir_entry: mobase.IFileTree, prefix: str, paths: set[str]
    ) -> None:
        """Collect full tree-root-relative paths of every file under
        ``dir_entry``. ``prefix`` is ``dir_entry``'s own path from the
        tree root, so claimed paths match the archive layout."""

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                rel = f"{path}/{entry.name()}" if path else entry.name()
                paths.add(f"{prefix}/{rel}" if prefix else rel)
            return mobase.IFileTree.WalkReturn.CONTINUE

        dir_entry.walk(visit)
