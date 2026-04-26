from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QDialog, QWidget

from .ui.dialog import UnifiedUI


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
_PRESET_PAK_DESTINATIONS = ("ROOT", "~mods", "LogicMods")


@dataclass
class PakGroup:
    """One .pak stem group: the .pak plus its same-stem .utoc/.ucas
    companions, plus any sibling AnimJSON/SwapJSON dirs at the same root
    scope (which are shared across all groups at that scope)."""

    stem: str
    pak: mobase.FileTreeEntry | None = None
    companions: list[mobase.FileTreeEntry] = field(default_factory=list)
    json_dirs: list[mobase.FileTreeEntry] = field(default_factory=list)


@dataclass
class ScriptMod:
    """One detected main.lua. ``mod_dir`` is the directory the installer
    moves on INSTALL or removes on SKIP; for ambiguous root-scope main.lua
    it may equal the tree itself (handled defensively at SKIP time)."""

    main_lua: mobase.FileTreeEntry
    mod_dir: mobase.FileTreeEntry
    derived_name: str
    main_lua_display: str
    ambiguous: bool


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
            "M3: optional UnifiedUI dialog for non-trivial archives, "
            "with M1 smart routing and M2 platform-aware variants."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 3, 0, mobase.ReleaseType.PRE_ALPHA)

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
            mobase.PluginSetting(
                "force_dialog",
                "debug: always show install dialog, even when the "
                "skip-when-trivial predicate would bypass it",
                False,
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

            # M3: discover groups and scripts post-platform-resolution; the
            # SSOT in _compute_pak_routing seeds both the silent path and
            # the dialog defaults.
            groups, json_dirs, loose_jsons = self._discover_pak_groups(tree)
            scripts = self._discover_script_mods(tree)
            default_routing = self._compute_pak_routing(groups)

            force_dialog = bool(
                self._organizer.pluginSetting(self.name(), "force_dialog")
            )
            if force_dialog or self._should_show_dialog(groups, scripts):
                pak_rows = [(g.stem, default_routing[g.stem]) for g in groups]
                script_rows = [
                    (s.derived_name, s.main_lua_display, not s.ambiguous)
                    for s in scripts
                ]
                dlg = UnifiedUI(self._parent, str(name), script_rows, pak_rows)
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return mobase.InstallResult.CANCELED
                # Per docs/mod-organizer.md §6.1: mutate via update(), never
                # reassign the local `name` reference.
                name.update(dlg.get_new_mod_name(), mobase.GuessQuality.USER)
                pak_decisions = dlg.get_pak_locations()
                script_statuses = dlg.get_script_statuses()
            else:
                self._log_silent_install(default_routing, scripts)
                pak_decisions = dict(default_routing)
                script_statuses = ["INSTALL"] * len(scripts)

            self._drop_skipped_scripts(tree, scripts, script_statuses)
            self._apply_pak_routing(
                tree, groups, pak_decisions, json_dirs, loose_jsons
            )
            self._relocate_scripts(tree, platform)

            allowed_root = self._compute_allowed_root_names(groups, pak_decisions)
            tree.removeIf(
                lambda e: e.parent() is tree
                and e.name().lower() not in allowed_root
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

    # --- M3: script discovery -------------------------------------------
    def _discover_script_mods(self, tree: mobase.IFileTree) -> list[ScriptMod]:
        """Find every main.lua in the tree and decide whether its
        <modname> derivation is unambiguous.

        A script is unambiguous iff its path is exactly
        <modname>/Scripts/main.lua at the (post wrapper-strip) archive
        root. Anything else -- bare main.lua at root, missing Scripts/
        parent, deeper nesting, or duplicate derived names -- is flagged
        ambiguous so the dialog appears and the checkbox defaults to
        unchecked.
        """
        found: dict[int, ScriptMod] = {}

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if not (entry.isFile() and entry.name().lower() == "main.lua"):
                return mobase.IFileTree.WalkReturn.CONTINUE

            scripts_dir = entry.parent()
            if scripts_dir is None or scripts_dir is tree:
                sm = ScriptMod(
                    main_lua=entry,
                    mod_dir=tree if scripts_dir is None else scripts_dir,
                    derived_name="(root)",
                    main_lua_display=path,
                    ambiguous=True,
                )
            elif scripts_dir.name().lower() != "scripts":
                sm = ScriptMod(
                    main_lua=entry,
                    mod_dir=scripts_dir,
                    derived_name=scripts_dir.name(),
                    main_lua_display=path,
                    ambiguous=True,
                )
            else:
                parent_of_scripts = scripts_dir.parent()
                if parent_of_scripts is None or parent_of_scripts is tree:
                    sm = ScriptMod(
                        main_lua=entry,
                        mod_dir=scripts_dir,
                        derived_name="Scripts",
                        main_lua_display=path,
                        ambiguous=True,
                    )
                else:
                    ambiguous = parent_of_scripts.parent() is not tree
                    sm = ScriptMod(
                        main_lua=entry,
                        mod_dir=parent_of_scripts,
                        derived_name=parent_of_scripts.name(),
                        main_lua_display=path,
                        ambiguous=ambiguous,
                    )

            key = id(sm.mod_dir)
            if key not in found:
                found[key] = sm
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        # Duplicate derived names → mark every occurrence ambiguous.
        counts: dict[str, int] = {}
        for sm in found.values():
            counts[sm.derived_name] = counts.get(sm.derived_name, 0) + 1
        for sm in found.values():
            if counts[sm.derived_name] > 1:
                sm.ambiguous = True

        return list(found.values())

    def _drop_skipped_scripts(
        self,
        tree: mobase.IFileTree,
        scripts: list[ScriptMod],
        statuses: list[str],
    ) -> None:
        """Remove the <modname> directory of every script the user marked
        SKIP, before _relocate_scripts walks the tree.

        For ambiguous scripts whose mod_dir is the tree root, only the
        main.lua entry is removed (we can't remove the tree itself).
        """
        to_remove: list[mobase.FileTreeEntry] = []
        for script, status in zip(scripts, statuses):
            if status != "SKIP":
                continue
            if script.mod_dir is tree:
                to_remove.append(script.main_lua)
            else:
                to_remove.append(script.mod_dir)
        for entry in to_remove:
            tree.remove(entry)

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

    # --- M3: pak group discovery / routing / application -----------------
    def _discover_pak_groups(
        self, tree: mobase.IFileTree
    ) -> tuple[list[PakGroup], list[mobase.FileTreeEntry], list[mobase.FileTreeEntry]]:
        """Discover pak stem groups, sibling AnimJSON/SwapJSON dirs at the
        archive root scope (associated with every group at that scope),
        and loose .json files at root scope.

        Returns: (groups, json_dirs, loose_jsons).
        """
        root_entries = list(tree)

        raw_groups: dict[str, list[mobase.FileTreeEntry]] = {}
        json_dirs: list[mobase.FileTreeEntry] = []
        loose_jsons: list[mobase.FileTreeEntry] = []

        for entry in root_entries:
            lower = entry.name().lower()
            if lower == "content":
                continue
            if entry.isFile():
                suffix = entry.suffix()
                if suffix in _PAK_COMPANION_SUFFIXES:
                    stem = entry.name()[: -(len(suffix) + 1)]
                    raw_groups.setdefault(stem, []).append(entry)
                elif suffix == "json":
                    loose_jsons.append(entry)
            elif entry.isDir() and lower in _ANIM_SWAP_FOLDERS:
                json_dirs.append(entry)

        groups: list[PakGroup] = []
        for stem, entries in raw_groups.items():
            pak = next((e for e in entries if e.suffix() == "pak"), None)
            companions = [e for e in entries if e.suffix() != "pak"]
            groups.append(
                PakGroup(
                    stem=stem,
                    pak=pak,
                    companions=companions,
                    json_dirs=list(json_dirs),
                )
            )
        return groups, json_dirs, loose_jsons

    def _compute_pak_routing(self, groups: list[PakGroup]) -> dict[str, str]:
        """SINGLE SOURCE OF TRUTH for M1 pak-routing heuristics.

        Consumed by both the silent-install path and the dialog's default
        seeding code -- there is no parallel default table elsewhere.

        Per .claude/tasks/m1-implementation-notes.md:
          - Group has sibling AnimJSON/SwapJSON dirs at root → ~mods
          - Else stem ends with _P                           → ~mods
          - Else                                             → LogicMods
        """
        decisions: dict[str, str] = {}
        for g in groups:
            if g.json_dirs:
                decisions[g.stem] = "~mods"
            elif g.stem.endswith("_P"):
                decisions[g.stem] = "~mods"
            else:
                decisions[g.stem] = "LogicMods"
        return decisions

    def _apply_pak_routing(
        self,
        tree: mobase.IFileTree,
        groups: list[PakGroup],
        decisions: dict[str, str],
        json_dirs: list[mobase.FileTreeEntry],
        loose_jsons: list[mobase.FileTreeEntry],
    ) -> None:
        """Apply pak-routing decisions group-aware: SKIP removes pak +
        .utoc / .ucas + (when every associated group is SKIP) the JSON
        dirs. Custom paths land at the typed string under archive root,
        no implicit Content/Paks prefix.
        """
        skipped_stems: set[str] = set()

        for g in groups:
            decision = decisions.get(g.stem, "LogicMods")
            members: list[mobase.FileTreeEntry] = []
            if g.pak is not None:
                members.append(g.pak)
            members.extend(g.companions)

            if decision == "SKIP":
                # Capture into a list before iterating per docs/mod-organizer.md §15.
                for entry in list(members):
                    tree.remove(entry)
                skipped_stems.add(g.stem)
            elif decision == "ROOT":
                # Stay at archive root; no move required.
                pass
            else:
                dest_path = self._resolve_pak_dest_path(decision)
                if not dest_path:
                    # Empty Custom path: leave at root and let the final
                    # cleanup pass drop it (effectively SKIP-by-omission).
                    continue
                dest = tree.addDirectory(dest_path)
                for entry in list(members):
                    tree.move(
                        entry,
                        dest.path("/") + "/" + entry.name(),
                        policy=mobase.IFileTree.InsertPolicy.REPLACE,
                    )

        self._route_associated_json_dirs(
            tree, groups, decisions, json_dirs, skipped_stems
        )

        for entry in loose_jsons:
            dest = tree.addDirectory("Content/Paks/LogicMods")
            tree.move(
                entry,
                dest.path("/") + "/" + entry.name(),
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )

    def _resolve_pak_dest_path(self, decision: str) -> str:
        """Map a non-SKIP, non-ROOT decision to a destination path.

        Preset values map to fixed Content/Paks/<dest>/. Anything else is
        treated as a Custom path and used verbatim under the archive root.
        """
        if decision == "~mods":
            return "Content/Paks/~mods"
        if decision == "LogicMods":
            return "Content/Paks/LogicMods"
        return decision

    def _route_associated_json_dirs(
        self,
        tree: mobase.IFileTree,
        groups: list[PakGroup],
        decisions: dict[str, str],
        json_dirs: list[mobase.FileTreeEntry],
        skipped_stems: set[str],
    ) -> None:
        if not json_dirs:
            return

        # When every pak group at this scope is SKIPped, drop the JSON dirs
        # too -- group-aware SKIP per AC §9.i.
        if groups and len(skipped_stems) == len(groups):
            for entry in list(json_dirs):
                tree.remove(entry)
            return

        # If exactly one non-SKIP group survives and it has a Custom
        # destination, the JSON dirs follow it (AC §9.iii). Otherwise the
        # M1 default applies: ~mods (MERGE).
        target_dest_path = "Content/Paks/~mods"
        surviving = [g for g in groups if g.stem not in skipped_stems]
        if len(surviving) == 1:
            decision = decisions.get(surviving[0].stem, "LogicMods")
            if decision not in _PRESET_PAK_DESTINATIONS and decision != "SKIP":
                resolved = self._resolve_pak_dest_path(decision)
                if resolved:
                    target_dest_path = resolved

        for entry in list(json_dirs):
            target_name = (
                "AnimJSON" if entry.name().lower() == "animjson" else "SwapJSON"
            )
            parent = tree.addDirectory(target_dest_path)
            tree.move(
                entry,
                f"{parent.path('/')}/{target_name}",
                policy=mobase.IFileTree.InsertPolicy.MERGE,
            )

    # --- M3: dialog gating -----------------------------------------------
    def _should_show_dialog(
        self,
        groups: list[PakGroup],
        scripts: list[ScriptMod],
    ) -> bool:
        """Skip-when-trivial predicate (AC §6).

        Show the dialog when more than one pak group is present, or when
        any detected script's <modname> derivation is ambiguous. Otherwise
        the silent-install path applies the M1 heuristics directly.
        """
        if len(groups) > 1:
            return True
        if any(s.ambiguous for s in scripts):
            return True
        return False

    def _compute_allowed_root_names(
        self,
        groups: list[PakGroup],
        decisions: dict[str, str],
    ) -> set[str]:
        """Names (lowercased) that survive the post-routing root cleanup.

        Always: 'content', 'binaries'. Plus, for any pak group routed to
        ROOT, the pak/companion file names. Plus, for any group routed to
        a Custom path, the first path segment of that custom path.
        """
        allowed: set[str] = {"content", "binaries"}
        for g in groups:
            decision = decisions.get(g.stem, "LogicMods")
            if decision == "SKIP":
                continue
            if decision == "ROOT":
                if g.pak is not None:
                    allowed.add(g.pak.name().lower())
                for c in g.companions:
                    allowed.add(c.name().lower())
                continue
            if decision in _PRESET_PAK_DESTINATIONS:
                continue
            normalised = decision.replace("\\", "/").lstrip("/")
            if not normalised:
                continue
            first_segment = normalised.split("/", 1)[0]
            if first_segment:
                allowed.add(first_segment.lower())
        return allowed

    def _log_silent_install(
        self,
        pak_decisions: dict[str, str],
        scripts: list[ScriptMod],
    ) -> None:
        """Single info-level log line for the silent-install branch (Q5)."""
        parts = [f"{stem}.pak → {dest}" for stem, dest in pak_decisions.items()]
        parts.extend(
            f"{s.derived_name}/Scripts/main.lua → INSTALL" for s in scripts
        )
        log.info(
            "PalworldInstaller: silent install (skip-when-trivial predicate "
            "passed): %s",
            "; ".join(parts) if parts else "no installable content",
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
