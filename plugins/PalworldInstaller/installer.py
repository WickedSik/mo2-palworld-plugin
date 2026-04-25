from __future__ import annotations

import logging
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QWidget


log = logging.getLogger(__name__)

_PLATFORM_MARKERS = ("{steam}", "{gamepass}", "{xbox}")
_WRAPPER_FOLDERS = ("palworld", "pal")
_ANIM_SWAP_FOLDERS = ("animjson", "swapjson")
_PAK_COMPANION_SUFFIXES = ("pak", "utoc", "ucas")


class PalworldInstaller(mobase.IPluginInstallerSimple):
    _organizer: mobase.IOrganizer
    _parent: QWidget | None = None

    def __init__(self):
        super().__init__()

    # --- IPlugin ---------------------------------------------------------
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "PalworldInstaller"

    def localizedName(self) -> str:
        return self._tr("Palworld Installer")

    def author(self) -> str:
        return "WickedSik"

    def description(self) -> str:
        return self._tr(
            "Custom installer for Palworld pak mods. "
            "M1: triage and minimal layout rewrite (single-platform)."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.PRE_ALPHA)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "enabled",
                "check to enable this plugin",
                True,
            ),
            mobase.PluginSetting(
                "prefer_fomod",
                "prefer FOMOD installer when possible",
                True,
            ),
            mobase.PluginSetting(
                "priority",
                "priority of this installer",
                120,
            ),
            mobase.PluginSetting(
                "palworld_platform",
                "platform variant for Palworld (steam | gamepass | xbox)",
                "steam",
            ),
            mobase.PluginSetting(
                "palworld_server_platform",
                "platform variant for Palworld Server (steam | gamepass | xbox)",
                "steam",
            ),
        ]

    def isActive(self) -> bool:
        return bool(self._organizer.pluginSetting(self.name(), "enabled"))

    # --- IPluginInstaller ------------------------------------------------
    def priority(self) -> int:
        return int(self._organizer.pluginSetting(self.name(), "priority"))

    def isManualInstaller(self) -> bool:
        return False

    def setParentWidget(self, parent: QWidget) -> None:
        self._parent = parent

    # --- IPluginInstallerSimple -----------------------------------------
    def isArchiveSupported(self, tree: mobase.IFileTree) -> bool:
        game = self._organizer.managedGame().gameName()
        if game not in ("Palworld", "Palworld Server"):
            return False

        # Defer marker-bearing archives to M2. Iterate top-level only.
        for entry in tree:
            if entry.isDir() and entry.name().lower() in _PLATFORM_MARKERS:
                return False

        prefer_fomod = bool(
            self._organizer.pluginSetting(self.name(), "prefer_fomod")
        )
        fomod_enabled = self._organizer.isPluginEnabled("FOMOD Installer")

        flags = {"fomod": False, "ue4ss": False, "pak": False}

        def visit(path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                lower = entry.name().lower()
                if lower == "moduleconfig.xml" and path.lower().endswith("fomod"):
                    flags["fomod"] = True
                elif lower == "ue4ss.dll":
                    flags["ue4ss"] = True
                elif entry.suffix() == "pak":
                    flags["pak"] = True
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        if flags["fomod"] and fomod_enabled and prefer_fomod:
            return False
        if flags["ue4ss"]:
            return False
        return flags["pak"]

    def install(
        self,
        name: mobase.GuessedString,
        tree: mobase.IFileTree,
        version: str,
        nexus_id: int,
    ) -> mobase.InstallResult | mobase.IFileTree:
        try:
            for wrapper in _WRAPPER_FOLDERS:
                self._strip_wrapper(tree, wrapper)

            self._route_stragglers(tree)

            tree.removeIf(
                lambda e: e.parent() is tree and e.name().lower() != "content"
            )
        except Exception:
            log.exception("PalworldInstaller: tree rewrite failed for %s", str(name))
            return mobase.InstallResult.FAILED

        if not self._tree_has_pak(tree):
            log.warning(
                "PalworldInstaller: no .pak survived rewrite for %s; declining", str(name)
            )
            return mobase.InstallResult.NOT_ATTEMPTED

        return tree

    # --- internal --------------------------------------------------------
    def _strip_wrapper(self, tree: mobase.IFileTree, wrapper_lower: str) -> None:
        wrapper = next(
            (
                e
                for e in tree
                if e.isDir() and e.name().lower() == wrapper_lower
            ),
            None,
        )
        if wrapper is None:
            return

        children = list(wrapper)
        for child in children:
            tree.move(
                child,
                child.name(),
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )
        tree.remove(wrapper)

    def _route_stragglers(self, tree: mobase.IFileTree) -> None:
        root_entries = list(tree)

        anim_swap_present = any(
            e.isDir() and e.name().lower() in _ANIM_SWAP_FOLDERS
            for e in root_entries
        )

        # Group pak/utoc/ucas siblings so companions follow their pak.
        pak_groups: dict[str, list[mobase.FileTreeEntry]] = {}
        loose_jsons: list[mobase.FileTreeEntry] = []
        json_dirs: list[mobase.FileTreeEntry] = []

        for entry in root_entries:
            lower = entry.name().lower()
            if lower == "content":
                continue
            if entry.isFile():
                suffix = entry.suffix()
                if suffix in _PAK_COMPANION_SUFFIXES:
                    stem = entry.name()[: -(len(suffix) + 1)]
                    pak_groups.setdefault(stem, []).append(entry)
                elif suffix == "json":
                    loose_jsons.append(entry)
            elif entry.isDir() and lower in _ANIM_SWAP_FOLDERS:
                json_dirs.append(entry)

        for stem, group in pak_groups.items():
            pak = next((e for e in group if e.suffix() == "pak"), None)
            # Texture/asset paks use the UE4 _P patch suffix; AnimJSON/SwapJSON
            # siblings at root signal a texture-swap mod regardless of suffix.
            is_texture = anim_swap_present or (pak is not None and stem.endswith("_P"))
            dest_path = "Content/Paks/~mods" if is_texture else "Content/Paks/LogicMods"
            dest = tree.addDirectory(dest_path)
            for entry in group:
                tree.move(
                    entry,
                    dest.path("/") + "/" + entry.name(),
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )

        for entry in json_dirs:
            target_name = "AnimJSON" if entry.name().lower() == "animjson" else "SwapJSON"
            parent = tree.addDirectory("Content/Paks/~mods")
            tree.move(
                entry,
                f"{parent.path('/')}/{target_name}",
                policy=mobase.IFileTree.InsertPolicy.MERGE,
            )

        for entry in loose_jsons:
            dest = tree.addDirectory("Content/Paks/LogicMods")
            tree.move(
                entry,
                dest.path("/") + "/" + entry.name(),
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )

    def _tree_has_pak(self, tree: mobase.IFileTree) -> bool:
        found = {"pak": False}

        def visit(_path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if entry.isFile() and entry.suffix() == "pak":
                found["pak"] = True
                return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return found["pak"]

    # --- helper ----------------------------------------------------------
    def _tr(self, txt: str) -> str:
        return QCoreApplication.translate("PalworldInstaller", txt)
