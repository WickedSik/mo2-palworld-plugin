from __future__ import annotations

import logging
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QWidget


log = logging.getLogger(__name__)

# Marker folder name (lowercase) → canonical platform.
# {GAMEPASS} is a deprecated alias of {XBOX}; both share the WinGDK runtime.
_MARKER_TO_PLATFORM = {
    "{steam}": "steam",
    "{xbox}": "xbox",
    "{gamepass}": "xbox",
}
_PLATFORM_MARKERS = tuple(_MARKER_TO_PLATFORM)

_GAME_PLATFORM_KEYS = {
    "Palworld": "palworld_platform",
    "Palworld Server": "palworld_server_platform",
}
_VALID_PLATFORMS = ("steam", "xbox")

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
            "Custom installer for Palworld pak and lua script mods. "
            "M2: platform-aware variant selection (Steam / Xbox)."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 2, 0, mobase.ReleaseType.PRE_ALPHA)

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
                "platform variant for Palworld (steam | xbox)",
                "steam",
            ),
            mobase.PluginSetting(
                "palworld_server_platform",
                "platform variant for Palworld Server (steam | xbox)",
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
        if game not in _GAME_PLATFORM_KEYS:
            return False

        prefer_fomod = bool(
            self._organizer.pluginSetting(self.name(), "prefer_fomod")
        )
        fomod_enabled = self._organizer.isPluginEnabled("FOMOD Installer")

        flags = {"fomod": False, "ue4ss": False, "pak": False, "lua": False}

        def visit(path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                lower = entry.name().lower()
                if lower == "moduleconfig.xml" and path.lower().endswith("fomod"):
                    flags["fomod"] = True
                elif lower == "ue4ss.dll":
                    flags["ue4ss"] = True
                elif entry.suffix() == "pak":
                    flags["pak"] = True
                elif lower == "main.lua":
                    flags["lua"] = True
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        if flags["fomod"] and fomod_enabled and prefer_fomod:
            return False
        if flags["ue4ss"]:
            return False
        return flags["pak"] or flags["lua"]

    def install(
        self,
        name: mobase.GuessedString,
        tree: mobase.IFileTree,
        version: str,
        nexus_id: int,
    ) -> mobase.InstallResult | mobase.IFileTree:
        try:
            platform = self._resolve_platform()
            had_markers = self._apply_platform_variant(tree, platform)

            for wrapper in _WRAPPER_FOLDERS:
                self._strip_wrapper(tree, wrapper)

            self._route_stragglers(tree)
            self._relocate_scripts(tree, platform)

            tree.removeIf(
                lambda e: e.parent() is tree
                and e.name().lower() not in ("content", "binaries")
            )
        except Exception:
            log.exception("PalworldInstaller: tree rewrite failed for %s", str(name))
            return mobase.InstallResult.FAILED

        has_pak = self._tree_has_pak(tree)
        has_lua = self._tree_has_lua(tree)
        if not (has_pak or has_lua):
            if had_markers:
                log.error(
                    "PalworldInstaller: variant selection left no installable "
                    "content for %s on platform %s; failing.",
                    str(name), platform,
                )
                return mobase.InstallResult.FAILED
            log.warning(
                "PalworldInstaller: no .pak or main.lua survived rewrite for %s; declining",
                str(name),
            )
            return mobase.InstallResult.NOT_ATTEMPTED

        return tree

    # --- internal --------------------------------------------------------
    def _resolve_platform(self) -> str:
        game_name = self._organizer.managedGame().gameName()
        key = _GAME_PLATFORM_KEYS.get(game_name)
        if key is None:
            return "steam"

        raw = self._organizer.pluginSetting(self.name(), key)
        value = str(raw).strip().lower() if raw is not None else "steam"

        if value == "gamepass":
            log.warning(
                '%s value "gamepass" is deprecated; treating as "xbox" '
                "(Game Pass and Xbox share the WinGDK runtime).",
                key,
            )
            return "xbox"

        if value in _VALID_PLATFORMS:
            return value

        log.warning(
            'Unknown platform setting "%s" for %s; falling back to "steam".',
            value, game_name,
        )
        return "steam"

    def _apply_platform_variant(
        self, tree: mobase.IFileTree, platform: str
    ) -> bool:
        markers = [
            e
            for e in tree
            if e.isDir() and e.name().lower() in _MARKER_TO_PLATFORM
        ]
        if not markers:
            return False

        matching = self._select_matching_marker(markers, platform)

        for entry in markers:
            if entry is matching:
                continue
            tree.remove(entry)

        if matching is not None:
            for child in list(matching):
                tree.move(
                    child,
                    child.name(),
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )
            tree.remove(matching)

        return True

    def _select_matching_marker(
        self,
        markers: list[mobase.FileTreeEntry],
        platform: str,
    ) -> mobase.FileTreeEntry | None:
        same_platform = [
            e for e in markers
            if _MARKER_TO_PLATFORM[e.name().lower()] == platform
        ]
        if not same_platform:
            return None

        if platform == "xbox":
            xbox = next(
                (e for e in same_platform if e.name().lower() == "{xbox}"),
                None,
            )
            if xbox is not None:
                return xbox
            log.warning(
                "Archive uses deprecated {GAMEPASS} marker; "
                "treat as {XBOX} going forward."
            )
            return same_platform[0]

        return same_platform[0]

    def _relocate_scripts(self, tree: mobase.IFileTree, platform: str) -> None:
        targets: list[mobase.FileTreeEntry] = []

        def visit(_path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if not (entry.isFile() and entry.name().lower() == "main.lua"):
                return mobase.IFileTree.WalkReturn.CONTINUE
            scripts_dir = entry.parent()
            if scripts_dir is None or scripts_dir is tree:
                return mobase.IFileTree.WalkReturn.CONTINUE
            if scripts_dir.name().lower() != "scripts":
                return mobase.IFileTree.WalkReturn.CONTINUE
            mod_dir = scripts_dir.parent()
            if mod_dir is None or mod_dir is tree:
                return mobase.IFileTree.WalkReturn.CONTINUE
            if mod_dir not in targets:
                targets.append(mod_dir)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        if not targets:
            return

        base = "Binaries/WinGDK/Mods" if platform == "xbox" else "Binaries/Win64/Mods"
        dest = tree.addDirectory(base)
        for mod_dir in targets:
            tree.move(
                mod_dir,
                f"{dest.path('/')}/{mod_dir.name()}",
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )

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

    def _tree_has_lua(self, tree: mobase.IFileTree) -> bool:
        found = {"lua": False}

        def visit(_path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if entry.isFile() and entry.name().lower() == "main.lua":
                found["lua"] = True
                return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return found["lua"]

    # --- helper ----------------------------------------------------------
    def _tr(self, txt: str) -> str:
        return QCoreApplication.translate("PalworldInstaller", txt)
