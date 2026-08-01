from __future__ import annotations

import logging
import re

import mobase

from ..models import (
    ROOT_BUILDER_DIR,
    DiscoveryResult,
    RecognitionResult,
    WalkContext,
    entry_full_path,
    move_plugin_dir,
    ue4ss_plugin_dest_base,
)

log = logging.getLogger(__name__)

# A UE4SS C++ plugin that ships without arrangement: `<name>/dlls/main.dll`
# sits right at the archive root (e.g. the PalSchema loader, Nexus 2361). The
# pre-arranged `ue4ss/Mods/<name>/dlls/main.dll` layout has more path segments
# and belongs to Ue4ssPluginRecognizer, so the two patterns never overlap.
_ROOT_DLL_PLUGIN_RE = re.compile(r"^[^/]+/dlls/main\.dll$", re.IGNORECASE)


class DllPluginRecognizer:
    """Handles UE4SS C++ plugin archives that are not yet arranged.

    Detects the standard UE4SS C++ mod layout shipped at the archive
    root -- ``<name>/dlls/main.dll`` (e.g. the PalSchema loader). It
    then moves the whole ``<name>/`` folder into the directory UE4SS
    scans: ``Binaries/Win{64|GDK}/ue4ss/Mods/<name>/``. The ``dlls/``
    folder, the ``enabled.txt`` flag, and any empty ``mods/`` folder
    move along with it, unchanged.

    When Root Builder is active the destination gains its ``Root/Pal/``
    prefix instead, so the DLL is deployed to disk rather than mapped
    virtually. ``ue4ss_plugin_dest_base()`` decides which applies.

    The already-arranged ``ue4ss/Mods/<name>/dlls/main.dll`` layout is a
    different case. ``Ue4ssPluginRecognizer`` owns it. Its priority 25
    runs ahead of this recognizer's 30.
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
            extra_root_names=(
                {ROOT_BUILDER_DIR.lower()} if ctx.use_rootbuilder else set()
            ),
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        base = ue4ss_plugin_dest_base(ctx)

        for plugin_dir in self._plugin_dirs(tree, ctx):
            name = plugin_dir.name()
            target = move_plugin_dir(tree, plugin_dir, base)

            if target is None:
                log.info(
                    f"PalworldInstaller: [dll_plugin] {name} already "
                    f"in place under {base}/{name}/"
                )
                continue

            log.info(
                f"PalworldInstaller: [dll_plugin] routing {name}/ "
                f"-> {target}/ (root builder: "
                f"{'yes' if ctx.use_rootbuilder else 'no'})"
            )

    # --- internal ------------------------------------------------------------

    @staticmethod
    def _plugin_dirs(
        tree: mobase.IFileTree, ctx: WalkContext
    ) -> list[mobase.FileTreeEntry]:
        """The root-level ``<name>/`` folders that hold a matching
        ``dlls/main.dll``. Duplicates are removed by identity, so an
        archive with several plugins gives one entry per plugin."""
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
        """Collect the full path of every file under ``dir_entry``,
        relative to the tree root. ``prefix`` is ``dir_entry``'s own
        path from the tree root, so claimed paths match the archive
        layout."""

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                rel = f"{path}/{entry.name()}" if path else entry.name()
                paths.add(f"{prefix}/{rel}" if prefix else rel)
            return mobase.IFileTree.WalkReturn.CONTINUE

        dir_entry.walk(visit)
