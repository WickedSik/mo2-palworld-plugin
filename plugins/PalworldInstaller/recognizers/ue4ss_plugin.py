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

_UE4SS_PLUGIN_RE = re.compile(
    r"ue4ss/mods/[^/]+/dlls/main\.dll$", re.IGNORECASE
)


class Ue4ssPluginRecognizer:
    """Handles UE4SS plugin archives that are already arranged.

    Detects the ``ue4ss/Mods/<name>/dlls/main.dll`` layout used by UE4SS
    plugins (e.g. the PalSchema loader) and normalises it to the
    destination ``ue4ss_plugin_dest_base()`` gives -- either
    ``Binaries/Win{64|GDK}/ue4ss/Mods/`` or, when Root Builder is
    active, its ``Root/Pal/`` equivalent.

    Archives that already sit at that destination are left untouched.
    Archives that ship the fragment at the tree root (a bare
    ``ue4ss/Mods/<name>/``) are moved down into it -- without that they
    are stripped by the installer's root cleanup and nothing installs.
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
                    f"PalworldInstaller: [ue4ss_plugin] {name} already "
                    f"in place under {base}/{name}/"
                )
                continue

            log.info(
                f"PalworldInstaller: [ue4ss_plugin] routing {name}/ "
                f"-> {target}/ (root builder: "
                f"{'yes' if ctx.use_rootbuilder else 'no'})"
            )

    # --- internal ------------------------------------------------------------

    @staticmethod
    def _plugin_dirs(
        tree: mobase.IFileTree, ctx: WalkContext
    ) -> list[mobase.FileTreeEntry]:
        """The ``<name>/`` folders holding a matching ``dlls/main.dll``.

        The pattern can match at any depth, so walk up from the dll
        rather than assuming a position: ``main.dll`` -> ``dlls/`` ->
        ``<name>/``. Duplicates are removed by identity, so an archive
        with several plugins gives one entry per plugin.
        """
        found: dict[int, mobase.FileTreeEntry] = {}
        for entry in ctx.dll_entries:
            if not _UE4SS_PLUGIN_RE.search(entry_full_path(entry, tree)):
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
