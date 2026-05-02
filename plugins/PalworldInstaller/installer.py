from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QDialog, QWidget

from .presets import PAK_PRESETS
from .ui.dialog import UnifiedUI


log = logging.getLogger(__name__)

# Canonical platform names recognised inside a marker folder name.
# `gamepass` is a deprecated alias of `xbox`; both share the WinGDK runtime.
_PLATFORM_BY_MARKER_NAME = {
    "steam": "steam",
    "xbox": "xbox",
    "gamepass": "xbox",
}
# Bracket pairs accepted around a marker name. The opener and closer must
# match -- `[steam}` is not a valid marker.
_MARKER_BRACKET_PAIRS = {"[": "]", "{": "}", "(": ")"}


def _normalize_marker_inner(name: str) -> str:
    """Return the bracket-stripped, lowercased inner of a marker folder
    name. Shared by `_extract_marker_platform` and `_is_xbox_marker` so
    bracket/case rules live in exactly one place."""
    inner = name.strip().lower()
    if (
        len(inner) >= 2
        and inner[0] in _MARKER_BRACKET_PAIRS
        and inner[-1] == _MARKER_BRACKET_PAIRS[inner[0]]
    ):
        inner = inner[1:-1]
    return inner


def _extract_marker_platform(name: str) -> str | None:
    """Return the canonical platform name (`steam`/`xbox`) if `name` is a
    platform marker, else ``None``.

    Accepted forms (case-insensitive): bare `steam` / `xbox` / `gamepass`,
    or wrapped in matching `[]` / `{}` / `()` -- `(STEAM)`, `[Xbox]`,
    `{gamepass}` all resolve.
    """
    return _PLATFORM_BY_MARKER_NAME.get(_normalize_marker_inner(name))


def _suffix(entry: mobase.FileTreeEntry) -> str:
    """Lower-case file suffix. mobase preserves the on-disk case in
    `entry.suffix()`; archives in the wild use mixed case (`.PAK`,
    `.Pak`). Normalising at every comparison site keeps detection
    consistent across discovery, triage, and validation passes."""
    return entry.suffix().lower()


_GAME_PLATFORM_KEYS = {
    "Palworld": "palworld_platform",
    "Palworld Server": "palworld_server_platform",
}
_VALID_PLATFORMS = ("steam", "xbox")

_WRAPPER_FOLDERS = ("palworld", "pal")
_ANIM_SWAP_FOLDERS = ("animjson", "swapjson")
_PAK_COMPANION_SUFFIXES = ("pak", "utoc", "ucas")

# Suffixes that M1 triage treats as mod content. Used by M5 root-content
# stripping when marker folders and loose root-level mod files coexist.
_M1_TRIAGE_SUFFIXES = frozenset({"pak", "utoc", "ucas", "lua", "json"})


class PlatformVariantMismatch(Exception):
    """Raised by `_apply_platform_variant` when an archive contains
    platform marker folders but none match the configured platform.

    The install must abort with `InstallResult.FAILED` before any
    destructive tree mutation occurs (so that "manual installation"
    remains a real option for the user).
    """

    def __init__(self, available: list[str], configured: str) -> None:
        self.available = available
        self.configured = configured
        super().__init__(
            f"archive contains only {sorted(set(available))} "
            f"but configured platform is {configured}"
        )


@dataclass
class PakGroup:
    """One .pak stem group: the .pak plus its same-stem .utoc/.ucas
    companions in the same parent directory, plus any sibling AnimJSON /
    SwapJSON dirs at the archive root (associated with every root-level
    group at that scope).

    ``group_id`` is the pak's full path-from-tree-root and serves as the
    stable key into routing-decision dicts -- two paks sharing a stem in
    different directories are distinct groups.

    ``current_parent_path`` is the path of the directory that holds the
    pak today (``""`` means the archive root). The routing SSOT consumes
    it to derive the default destination for pre-arranged content.
    """

    group_id: str
    stem: str
    pak: mobase.FileTreeEntry
    companions: list[mobase.FileTreeEntry] = field(default_factory=list)
    json_dirs: list[mobase.FileTreeEntry] = field(default_factory=list)
    current_parent_path: str = ""


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
        return mobase.VersionInfo(0, 3, 2, mobase.ReleaseType.PRE_ALPHA)

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
                elif _suffix(entry) == "pak":
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

            # Lift root-level pre-arranged LogicMods/ and ~Mods/ under
            # Content/Paks/ so discovery sees them and cleanup spares them.
            self._promote_prearranged_layout(tree)

            # M3: discover groups and scripts post-platform-resolution; the
            # SSOT in _compute_pak_routing seeds both the silent path and
            # the dialog defaults.
            groups, json_dirs, loose_jsons = self._discover_pak_groups(tree)
            scripts = self._discover_script_mods(tree)
            default_routing = self._compute_pak_routing(groups)

            force_dialog = bool(
                self._organizer.pluginSetting(self.name(), "force_dialog")
            )
            if force_dialog or self._should_show_dialog(
                groups, default_routing, scripts
            ):
                pak_rows = [
                    (
                        g.group_id,
                        default_routing[g.group_id],
                        self._format_pak_label(g),
                    )
                    for g in groups
                ]
                script_rows = [
                    (s.derived_name, s.main_lua_display, not s.ambiguous)
                    for s in scripts
                ]
                dlg = UnifiedUI(
                    self._parent, str(name), script_rows, pak_rows, platform
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return mobase.InstallResult.CANCELED
                # Per docs/mod-organizer.md §6.1: mutate via update(), never
                # reassign the local `name` reference.
                name.update(dlg.get_new_mod_name(), mobase.GuessQuality.USER)
                pak_decisions = dlg.get_pak_locations()
                script_statuses = dlg.get_script_statuses()
            else:
                self._log_silent_install(groups, default_routing, scripts)
                pak_decisions = dict(default_routing)
                script_statuses = ["INSTALL"] * len(scripts)

            self._drop_skipped_scripts(tree, scripts, script_statuses)
            self._apply_pak_routing(
                tree, groups, pak_decisions, json_dirs, loose_jsons
            )
            # `name` reflects either the user's dialog choice (after
            # `name.update(...)` above) or the original suggestion on the
            # silent path -- exactly the fallback the spec requires for
            # scripts that lack a usable archive-side <modname>.
            self._relocate_scripts(
                tree, platform, scripts, script_statuses, str(name)
            )

            allowed_root = self._compute_allowed_root_names(groups, pak_decisions)
            tree.removeIf(
                lambda e: e.parent() is tree
                and e.name().lower() not in allowed_root
            )
        except PlatformVariantMismatch as exc:
            log.error(
                f"PalworldInstaller: Automatic installation failed: "
                f"archive contains only {sorted(set(exc.available))} but "
                f"configured platform is {exc.configured} for {str(name)}. "
                f"Manual installation may still be possible."
            )
            return mobase.InstallResult.FAILED
        except Exception:
            log.exception(f"PalworldInstaller: tree rewrite failed for {str(name)}")
            return mobase.InstallResult.FAILED

        has_pak, has_lua = self._tree_post_install_state(tree)
        if not (has_pak or has_lua):
            if had_markers:
                log.error(
                    f"PalworldInstaller: Automatic installation failed: "
                    f"matching platform variant for {platform} contained "
                    f"no installable content for {str(name)}. Manual "
                    f"installation may still be possible."
                )
                return mobase.InstallResult.FAILED
            log.warning(
                f"PalworldInstaller: no .pak or main.lua survived rewrite "
                f"for {str(name)}; declining"
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
                f'PalworldInstaller: {key} value "gamepass" is deprecated; '
                f'treating as "xbox" (Game Pass and Xbox share the WinGDK '
                f'runtime).'
            )
            return "xbox"

        if value in _VALID_PLATFORMS:
            return value

        log.warning(
            f'PalworldInstaller: unknown platform setting "{value}" for '
            f'{game_name}; falling back to "steam".'
        )
        return "steam"

    def _apply_platform_variant(
        self, tree: mobase.IFileTree, platform: str
    ) -> bool:
        markers = [
            e
            for e in tree
            if e.isDir() and _extract_marker_platform(e.name()) is not None
        ]
        if not markers:
            return False

        matching = self._select_matching_marker(markers, platform)
        if matching is None:
            available = [_extract_marker_platform(e.name()) for e in markers]
            raise PlatformVariantMismatch(available, platform)

        # Marker-folder content wins: drop root-level loose mod files that
        # would otherwise be merged with the lifted marker children
        # (docs/rebuild.md §3 edge cases).
        self._strip_root_mod_content(tree)

        for entry in markers:
            if entry is matching:
                continue
            tree.remove(entry)

        for child in list(matching):
            tree.move(
                child,
                child.name(),
                policy=mobase.IFileTree.InsertPolicy.REPLACE,
            )
        tree.remove(matching)

        return True

    def _strip_root_mod_content(self, tree: mobase.IFileTree) -> None:
        dropped: list[str] = []
        for entry in list(tree):
            if not entry.isFile():
                continue
            if _suffix(entry) in _M1_TRIAGE_SUFFIXES:
                dropped.append(entry.name())
                tree.remove(entry)
        if dropped:
            log.warning(
                f"PalworldInstaller: marker folders coexist with "
                f"root-level mod content; dropped root-level files in "
                f"favour of marker contents: {sorted(dropped)}"
            )

    def _select_matching_marker(
        self,
        markers: list[mobase.FileTreeEntry],
        platform: str,
    ) -> mobase.FileTreeEntry | None:
        same_platform = [
            e for e in markers
            if _extract_marker_platform(e.name()) == platform
        ]
        if not same_platform:
            return None

        if platform == "xbox":
            xbox = next(
                (e for e in same_platform if self._is_xbox_marker(e.name())),
                None,
            )
            if xbox is not None:
                return xbox
            log.warning(
                "PalworldInstaller: archive uses deprecated GAMEPASS "
                "marker; treat as XBOX going forward."
            )
            return same_platform[0]

        return same_platform[0]

    @staticmethod
    def _is_xbox_marker(name: str) -> bool:
        """True iff `name` is the canonical xbox marker (not the
        deprecated gamepass alias). Used to prefer xbox over gamepass
        when both are present in the archive."""
        return _normalize_marker_inner(name) == "xbox"

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

    def _relocate_scripts(
        self,
        tree: mobase.IFileTree,
        platform: str,
        scripts: list[ScriptMod],
        statuses: list[str],
        archive_mod_name: str,
    ) -> None:
        """Move every INSTALL'd script under
        ``Binaries/{Win64|WinGDK}/Mods/<modname>/Scripts/main.lua``.

        The destination ``<modname>`` is the script's own ``derived_name``
        (the mod author's chosen directory) when meaningful; for
        scripts with no usable derivation -- bare ``main.lua`` at archive
        root, or a ``Scripts/`` folder directly at root with no parent
        modname -- we fall back to ``archive_mod_name`` (the user-chosen
        mod name from the dialog, or the suggestion in
        ``name: GuessedString`` on the silent path).

        Source layouts handled:

        * ``<modname>/Scripts/main.lua``        -> move whole ``<modname>``.
        * ``Scripts/main.lua`` at archive root  -> move ``Scripts`` under
          ``<archive_mod_name>``.
        * ``<somedir>/main.lua`` (no Scripts/)  -> create
          ``<derived_name>/Scripts`` and move just ``main.lua``.
        * Bare ``main.lua`` at archive root     -> create
          ``<archive_mod_name>/Scripts`` and move just ``main.lua``.
        """
        base = (
            "Binaries/WinGDK/Mods" if platform == "xbox"
            else "Binaries/Win64/Mods"
        )

        for script, status in zip(scripts, statuses):
            if status != "INSTALL":
                continue

            # Pick a sensible <modname>: derivations like "(root)" /
            # "Scripts" don't name a real mod, fall back to archive name.
            if (
                script.mod_dir is tree
                or script.derived_name in ("(root)", "Scripts")
            ):
                target_modname = archive_mod_name
            else:
                target_modname = script.derived_name

            scripts_parent = script.main_lua.parent()
            has_real_scripts_parent = (
                scripts_parent is not None
                and scripts_parent is not tree
                and scripts_parent.name().lower() == "scripts"
            )

            if (
                has_real_scripts_parent
                and script.mod_dir is not tree
                and scripts_parent is not script.mod_dir
            ):
                # <modname>/Scripts/main.lua: move the whole modname dir,
                # preserving its Scripts/ substructure.
                tree.move(
                    script.mod_dir,
                    f"{base}/{target_modname}",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )
            elif (
                has_real_scripts_parent
                and scripts_parent is script.mod_dir
            ):
                # Scripts/main.lua at archive root: mod_dir IS the Scripts
                # folder; nest it under <archive_mod_name>.
                tree.move(
                    script.mod_dir,
                    f"{base}/{target_modname}/Scripts",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )
            else:
                # No Scripts/ folder anywhere on the path: synthesize the
                # canonical <modname>/Scripts/ structure and move only the
                # main.lua entry.
                target_scripts = tree.addDirectory(
                    f"{base}/{target_modname}/Scripts"
                )
                tree.move(
                    script.main_lua,
                    f"{target_scripts.path('/')}/main.lua",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )

    def _promote_prearranged_layout(self, tree: mobase.IFileTree) -> None:
        """Lift root-level pre-arranged destination dirs into the standard
        ``Content/Paks/<dest>/`` layout.

        Mod authors who place ``LogicMods/`` or ``~Mods/`` at the archive
        root are expressing destination intent. We MERGE their contents
        under ``Content/Paks/...`` so the discovery pass finds the paks
        and the cleanup pass doesn't strip them. Case-insensitive.
        """
        promotions = (
            ("logicmods", "Content/Paks/LogicMods"),
            ("~mods", "Content/Paks/~mods"),
        )
        for source_lower, target_path in promotions:
            source = next(
                (
                    e for e in tree
                    if e.isDir() and e.name().lower() == source_lower
                ),
                None,
            )
            if source is None:
                continue
            target = tree.addDirectory(target_path)
            for child in list(source):
                tree.move(
                    child,
                    f"{target.path('/')}/{child.name()}",
                    policy=mobase.IFileTree.InsertPolicy.MERGE,
                )
            tree.remove(source)

    def _entry_parent_path(
        self, entry: mobase.FileTreeEntry, tree: mobase.IFileTree
    ) -> str:
        """Return the parent directory's path-from-tree-root, or ``""``
        for entries directly under the archive root."""
        parent = entry.parent()
        if parent is None or parent is tree:
            return ""
        return parent.path("/")

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
        """Walk the whole tree to find pak groups (a .pak plus its
        same-directory same-stem .utoc/.ucas companions).

        Sibling ``AnimJSON``/``SwapJSON`` dirs at the archive root and
        loose ``.json`` files at the archive root are returned alongside;
        they're root-scope-only and associate with root-level groups.

        Returns: (groups, root_json_dirs, root_loose_jsons).
        """
        # Group pak/companion entries by their parent directory + stem so
        # a stem appearing in two different dirs becomes two groups.
        bucketed: dict[tuple[int, str], list[mobase.FileTreeEntry]] = {}
        root_json_dirs: list[mobase.FileTreeEntry] = []
        root_loose_jsons: list[mobase.FileTreeEntry] = []

        def visit(
            _path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            parent = entry.parent()
            at_root = parent is None or parent is tree
            if entry.isFile():
                suffix = _suffix(entry)
                if suffix in _PAK_COMPANION_SUFFIXES:
                    stem = entry.name()[: -(len(suffix) + 1)]
                    parent_key = id(parent) if parent is not None else id(tree)
                    bucketed.setdefault((parent_key, stem), []).append(entry)
                elif suffix == "json" and at_root:
                    root_loose_jsons.append(entry)
            elif (
                entry.isDir()
                and at_root
                and entry.name().lower() in _ANIM_SWAP_FOLDERS
            ):
                root_json_dirs.append(entry)
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        groups: list[PakGroup] = []
        for (_parent_key, stem), entries in bucketed.items():
            pak = next((e for e in entries if _suffix(e) == "pak"), None)
            if pak is None:
                # Orphaned .utoc / .ucas without a .pak -- skip; the
                # cleanup pass disposes of them.
                continue
            companions = [e for e in entries if e is not pak]
            parent_path = self._entry_parent_path(pak, tree)
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

    def _compute_pak_routing(self, groups: list[PakGroup]) -> dict[str, str]:
        """SINGLE SOURCE OF TRUTH for default pak-routing decisions.

        Consumed by both the silent-install path and the dialog's default
        seeding code -- there is no parallel default table elsewhere.
        Returns a {group_id: destination} dict.

        For a group at the archive root the M1 heuristics from
        ``.claude/tasks/m1-implementation-notes.md`` apply:
          - Group has sibling AnimJSON/SwapJSON dirs at root → ~mods
          - Else stem ends with _P                           → ~mods
          - Else                                             → LogicMods

        For a pre-arranged group (already placed under some directory)
        the parent path is normalised to a known preset where possible:
        ``LogicMods`` / ``~Mods`` / ``Content/Paks/<dest>`` map to their
        canonical destination; anything else passes through verbatim and
        is rendered as a Custom path in the dialog.
        """
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

        Moves are absolute-path so groups already inside a destination
        directory (pre-arranged content) stay put on identity moves.
        """
        skipped_group_ids: set[str] = set()

        for g in groups:
            decision = decisions.get(g.group_id, "LogicMods")
            members = [g.pak, *g.companions]

            if decision == "SKIP":
                # Capture into a list before iterating per docs/mod-organizer.md §15.
                for entry in list(members):
                    tree.remove(entry)
                skipped_group_ids.add(g.group_id)
            elif decision == "ROOT":
                for entry in list(members):
                    self._move_to(tree, entry, entry.name())
            else:
                dest_path = self._resolve_pak_dest_path(decision)
                if not dest_path:
                    # Empty Custom path: leave in place and let the final
                    # cleanup pass deal with it.
                    continue
                dest = tree.addDirectory(dest_path)
                target_dir = dest.path("/")
                for entry in list(members):
                    self._move_to(tree, entry, f"{target_dir}/{entry.name()}")

        self._route_associated_json_dirs(
            tree, groups, decisions, json_dirs, skipped_group_ids
        )

        for entry in loose_jsons:
            dest = tree.addDirectory("Content/Paks/LogicMods")
            self._move_to(tree, entry, f"{dest.path('/')}/{entry.name()}")

    def _format_pak_label(self, g: PakGroup) -> str:
        """Dialog row label: filename, plus a parent-path hint when the
        pak is pre-arranged inside an existing directory."""
        if g.current_parent_path:
            return f"{g.pak.name()}  ({g.current_parent_path}/)"
        return g.pak.name()

    def _move_to(
        self,
        tree: mobase.IFileTree,
        entry: mobase.FileTreeEntry,
        target: str,
    ) -> None:
        """Move ``entry`` to absolute path ``target`` unless it's already
        there (some IFileTree implementations balk at self-moves)."""
        current_parent = self._entry_parent_path(entry, tree)
        current = (
            entry.name() if current_parent == ""
            else f"{current_parent}/{entry.name()}"
        )
        if current == target.lstrip("/"):
            return
        tree.move(entry, target, policy=mobase.IFileTree.InsertPolicy.REPLACE)

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
        skipped_group_ids: set[str],
    ) -> None:
        if not json_dirs:
            return

        # Only root-level groups own these dirs. If every root-level group
        # was SKIPped, drop the JSON dirs too (group-aware SKIP, AC §9.i).
        root_groups = [g for g in groups if g.current_parent_path == ""]
        if root_groups and all(
            g.group_id in skipped_group_ids for g in root_groups
        ):
            for entry in list(json_dirs):
                tree.remove(entry)
            return

        # If exactly one non-SKIP root-level group survives and it has a
        # Custom destination, JSON dirs follow it (AC §9.iii). Otherwise
        # the M1 default applies: ~mods (MERGE).
        target_dest_path = "Content/Paks/~mods"
        surviving = [
            g for g in root_groups if g.group_id not in skipped_group_ids
        ]
        if len(surviving) == 1:
            decision = decisions.get(surviving[0].group_id, "LogicMods")
            if decision not in PAK_PRESETS and decision != "SKIP":
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
        decisions: dict[str, str],
        scripts: list[ScriptMod],
    ) -> bool:
        """Skip-when-trivial predicate (AC §6 / docs/rebuild.md §"Install
        configuration dialog").

        Show the dialog when any of the following hold:

        1. More than one pak group is present.
        2. Any detected script's ``<modname>`` derivation is ambiguous.
        3. Any pak group's heuristic destination is a Custom path -- i.e.
           the routing SSOT returned a value outside the preset set
           (``ROOT`` / ``~mods`` / ``LogicMods``) and not ``SKIP``. The
           user must confirm Custom destinations even when the rest of
           the archive is otherwise trivial; ``UnifiedUI`` pre-fills the
           Custom line edit with the layout-derived path so accepting
           unchanged matches what the silent path would have done.

        Otherwise the silent-install path applies the M1 heuristics
        directly.
        """
        if len(groups) > 1:
            return True
        if any(s.ambiguous for s in scripts):
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
            decision = decisions.get(g.group_id, "LogicMods")
            if decision == "SKIP":
                continue
            if decision == "ROOT":
                allowed.add(g.pak.name().lower())
                for c in g.companions:
                    allowed.add(c.name().lower())
                continue
            if decision in PAK_PRESETS:
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
        groups: list[PakGroup],
        pak_decisions: dict[str, str],
        scripts: list[ScriptMod],
    ) -> None:
        """Single info-level log line for the silent-install branch (Q5)."""
        parts = [
            f"{g.group_id} → {pak_decisions.get(g.group_id, 'LogicMods')}"
            for g in groups
        ]
        parts.extend(
            f"{s.derived_name}/Scripts/main.lua → INSTALL" for s in scripts
        )
        summary = "; ".join(parts) if parts else "no installable content"
        log.info(
            f"PalworldInstaller: silent install (skip-when-trivial predicate "
            f"passed): {summary}"
        )

    def _tree_post_install_state(
        self, tree: mobase.IFileTree
    ) -> tuple[bool, bool]:
        """Single-walk validation: returns (has_pak, has_lua). Used to
        decide whether the rewrite produced any installable content; stops
        as soon as both have been seen."""
        found = {"pak": False, "lua": False}

        def visit(
            _path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                if not found["pak"] and _suffix(entry) == "pak":
                    found["pak"] = True
                elif not found["lua"] and entry.name().lower() == "main.lua":
                    found["lua"] = True
                if found["pak"] and found["lua"]:
                    return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return found["pak"], found["lua"]

    # --- helper ----------------------------------------------------------
    def _tr(self, txt: str) -> str:
        return QCoreApplication.translate("PalworldInstaller", txt)
