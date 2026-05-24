from __future__ import annotations

import logging
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QDialog, QWidget

from .models import (
    DiscoveryResult,
    PakGroup,
    PlatformVariantMismatch,
    RecognitionResult,
    RequestManual,
    WalkContext,
    suffix,
)
from .presets import PAK_PRESETS
from .recognizers import RECOGNIZERS
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


_GAME_PLATFORM_KEYS = {
    "Palworld": "palworld_platform",
    "Palworld Server": "palworld_server_platform",
}
_VALID_PLATFORMS = ("steam", "xbox")

_WRAPPER_FOLDERS = ("palworld", "pal")
_ANIM_SWAP_FOLDERS = ("animjson", "swapjson")

# Suffixes that M1 triage treats as mod content. Used by M5 root-content
# stripping when marker folders and loose root-level mod files coexist.
_M1_TRIAGE_SUFFIXES = frozenset({"pak", "utoc", "ucas", "lua", "json"})


def _format_pak_label(g: PakGroup) -> str:
    if g.current_parent_path:
        return f"{g.pak.name()}  ({g.current_parent_path}/)"
    return g.pak.name()


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
            "M6: recognizer-based architecture with prioritized "
            "detection, M3 dialog, and M2 platform-aware variants."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 4, 0, mobase.ReleaseType.PRE_ALPHA)

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
                "recognizer.palschema.enabled",
                "enable PalSchema mod detection and routing",
                True,
            ),
            mobase.PluginSetting(
                "recognizer.altermatic.enabled",
                "enable Altermatic mod detection and routing",
                True,
            ),
            mobase.PluginSetting(
                "recognizer.ue4ss_plugin.enabled",
                "enable UE4SS plugin detection and routing",
                True,
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

        flags = {
            "fomod": False,
            "ue4ss": False,
            "pak": False,
            "lua": False,
            "json": False,
            "ue4ss_plugin": False,
        }

        def visit(path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                lower = entry.name().lower()
                if lower == "moduleconfig.xml" and path.lower().endswith("fomod"):
                    flags["fomod"] = True
                elif lower == "ue4ss.dll":
                    flags["ue4ss"] = True
                elif suffix(entry) == "pak":
                    flags["pak"] = True
                elif lower == "main.lua":
                    flags["lua"] = True
                elif suffix(entry) == "json":
                    flags["json"] = True
                elif lower == "main.dll":
                    path_lower = path.lower().replace("\\", "/")
                    if (
                        "/ue4ss/mods/" in path_lower
                        and path_lower.endswith("/dlls")
                    ):
                        flags["ue4ss_plugin"] = True
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        if flags["fomod"] and fomod_enabled and prefer_fomod:
            log.debug(
                f"PalworldInstaller: deferring to FOMOD installer "
                f"for {game}"
            )
            return False
        if flags["ue4ss"]:
            log.debug(
                "PalworldInstaller: declining: archive contains ue4ss.dll"
            )
            return False
        claimed = (
            flags["pak"]
            or flags["lua"]
            or flags["json"]
            or flags["ue4ss_plugin"]
        )
        log.debug(
            f"PalworldInstaller: archive triage: "
            f"pak={flags['pak']} lua={flags['lua']} "
            f"json={flags['json']} ue4ss_plugin={flags['ue4ss_plugin']}"
            f" -> {'claiming' if claimed else 'declining'}"
        )
        return claimed

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

            self._promote_prearranged_layout(tree)

            ctx = self._build_walk_context(tree, platform, str(name))

            log.debug(
                f"PalworldInstaller: WalkContext for {str(name)}: "
                f"pak={len(ctx.pak_entries)} lua={len(ctx.lua_entries)} "
                f"json={len(ctx.json_entries)} json_dirs={len(ctx.json_dirs)} "
                f"companions={len(ctx.companion_entries)} "
                f"fomod={ctx.has_fomod} ue4ss={ctx.has_ue4ss_dll} "
                f"json_deep={ctx.has_json_deep} "
                f"ue4ss_plugin={ctx.has_ue4ss_plugin_layout}"
            )

            active_recognizers = [
                r for r in RECOGNIZERS
                if self._is_recognizer_enabled(r.name)
            ]

            verdicts = [
                (r, r.detect(tree, ctx)) for r in active_recognizers
            ]

            for recognizer, verdict in verdicts:
                label = (
                    verdict.reason
                    if isinstance(verdict, RequestManual)
                    else verdict.name
                )
                log.debug(
                    f"PalworldInstaller: [{recognizer.name}] "
                    f"(priority {recognizer.priority}) -> {label}"
                )

            winner = None
            winner_verdict = None
            all_matches: list[str] = []
            for recognizer, verdict in verdicts:
                if verdict == RecognitionResult.MATCH or isinstance(
                    verdict, RequestManual
                ):
                    all_matches.append(recognizer.name)
                    if winner is None:
                        winner = recognizer
                        winner_verdict = verdict

            if len(all_matches) > 1 and winner is not None:
                losers = [n for n in all_matches if n != winner.name]
                log.warning(
                    f"PalworldInstaller: multiple recognizers matched "
                    f"for {str(name)}: winner={winner.name} "
                    f"(priority {winner.priority}), "
                    f"also matched: {', '.join(losers)}"
                )

            if winner is None:
                return mobase.InstallResult.NOT_ATTEMPTED

            if isinstance(winner_verdict, RequestManual):
                log.info(
                    f"PalworldInstaller: [{winner.name}] "
                    f"{winner_verdict.reason} for {str(name)}"
                )
                return mobase.InstallResult.NOT_ATTEMPTED

            log.info(
                f"PalworldInstaller: [{winner.name}] won detection "
                f"for {str(name)} (priority {winner.priority})"
            )

            discovery = winner.discover(tree, ctx)

            force_dialog = bool(
                self._organizer.pluginSetting(self.name(), "force_dialog")
            )
            if force_dialog or discovery.should_show_dialog:
                pak_rows = [
                    (
                        g.group_id,
                        discovery.default_routing[g.group_id],
                        _format_pak_label(g),
                    )
                    for g in discovery.pak_groups
                ]
                script_rows = [
                    (s.derived_name, s.main_lua_display, not s.ambiguous)
                    for s in discovery.scripts
                ]
                dlg = UnifiedUI(
                    self._parent, str(name), script_rows, pak_rows, platform
                )
                if dlg.exec() != QDialog.DialogCode.Accepted:
                    return mobase.InstallResult.CANCELED
                # Per docs/mod-organizer.md §6.1: mutate via update(),
                # never reassign the local `name` reference.
                name.update(dlg.get_new_mod_name(), mobase.GuessQuality.USER)
                decisions = self._build_decisions(
                    discovery,
                    pak_overrides=dlg.get_pak_locations(),
                    script_overrides=dlg.get_script_statuses(),
                    mod_name=str(name),
                )
            else:
                self._log_silent_install(discovery, str(name))
                decisions = self._build_decisions(
                    discovery, mod_name=str(name)
                )

            winner.route(tree, ctx, decisions)

            allowed_root = self._compute_allowed_root_names(
                discovery, decisions
            )
            removed_root = [
                e.name() for e in tree
                if e.name().lower() not in allowed_root
            ]
            if removed_root:
                log.debug(
                    f"PalworldInstaller: root cleanup: keeping "
                    f"{sorted(allowed_root)}, removing "
                    f"{sorted(removed_root)}"
                )
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
            log.exception(
                f"PalworldInstaller: Automatic installation failed for "
                f"{str(name)}. Manual installation may still be possible."
            )
            return mobase.InstallResult.FAILED

        has_content = self._tree_has_installable_content(tree)
        if not has_content:
            if had_markers:
                log.error(
                    f"PalworldInstaller: Automatic installation failed: "
                    f"matching platform variant for {platform} contained "
                    f"no installable content for {str(name)}. Manual "
                    f"installation may still be possible."
                )
                return mobase.InstallResult.FAILED
            log.warning(
                f"PalworldInstaller: no installable content survived "
                f"rewrite for {str(name)}; declining"
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
        log.debug(
            f"PalworldInstaller: found platform markers: "
            f"{[e.name() for e in markers]}, "
            f"selected {matching.name() if matching else 'none'} "
            f"for platform {platform}"
        )
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
            if suffix(entry) in _M1_TRIAGE_SUFFIXES:
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
            log.debug(
                f"PalworldInstaller: promoted root-level "
                f"{source.name()}/ to {target_path}/"
            )
            target = tree.addDirectory(target_path)
            for child in list(source):
                tree.move(
                    child,
                    f"{target.path('/')}/{child.name()}",
                    policy=mobase.IFileTree.InsertPolicy.MERGE,
                )
            tree.remove(source)

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

    # --- recognizer integration ---------------------------------------------

    def _build_walk_context(
        self,
        tree: mobase.IFileTree,
        platform: str,
        suggested_mod_name: str,
    ) -> WalkContext:
        """Single ``tree.walk()`` pass that populates every signal
        recognizers need. Runs after all pre-passes (platform resolution,
        wrapper stripping, prearranged layout promotion)."""
        has_fomod = False
        has_ue4ss_dll = False
        has_json_deep = False
        has_ue4ss_plugin_layout = False
        pak_entries: list[mobase.FileTreeEntry] = []
        companion_entries: list[mobase.FileTreeEntry] = []
        lua_entries: list[mobase.FileTreeEntry] = []
        json_entries: list[mobase.FileTreeEntry] = []
        json_dirs: list[mobase.FileTreeEntry] = []
        folder_names: set[str] = set()
        deep_folder_names: set[str] = set()

        def visit(
            path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            nonlocal has_fomod, has_ue4ss_dll
            nonlocal has_json_deep, has_ue4ss_plugin_layout
            parent = entry.parent()
            at_root = parent is None or parent is tree

            if entry.isDir():
                deep_folder_names.add(entry.name().lower())
                if at_root:
                    folder_names.add(entry.name().lower())
                    if entry.name().lower() in _ANIM_SWAP_FOLDERS:
                        json_dirs.append(entry)
                return mobase.IFileTree.WalkReturn.CONTINUE

            if not entry.isFile():
                return mobase.IFileTree.WalkReturn.CONTINUE

            lower = entry.name().lower()
            s = suffix(entry)

            if lower == "moduleconfig.xml" and path.lower().endswith("fomod"):
                has_fomod = True
            elif lower == "ue4ss.dll":
                has_ue4ss_dll = True
            elif lower == "main.dll":
                path_lower = path.lower().replace("\\", "/")
                if (
                    "/ue4ss/mods/" in path_lower
                    and path_lower.endswith("/dlls")
                ):
                    has_ue4ss_plugin_layout = True
            elif s == "pak":
                pak_entries.append(entry)
            elif s in ("utoc", "ucas"):
                companion_entries.append(entry)
            elif lower == "main.lua":
                lua_entries.append(entry)
            elif s == "json":
                has_json_deep = True
                if at_root:
                    json_entries.append(entry)

            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        return WalkContext(
            has_fomod=has_fomod,
            has_ue4ss_dll=has_ue4ss_dll,
            has_json_deep=has_json_deep,
            has_ue4ss_plugin_layout=has_ue4ss_plugin_layout,
            pak_entries=tuple(pak_entries),
            companion_entries=tuple(companion_entries),
            lua_entries=tuple(lua_entries),
            json_entries=tuple(json_entries),
            json_dirs=tuple(json_dirs),
            folder_names=frozenset(folder_names),
            deep_folder_names=frozenset(deep_folder_names),
            platform=platform,
            suggested_mod_name=suggested_mod_name,
        )

    @staticmethod
    def _build_decisions(
        discovery: DiscoveryResult,
        pak_overrides: dict[str, str] | None = None,
        script_overrides: list[str] | None = None,
        mod_name: str = "",
    ) -> dict[str, str]:
        """Merge default routing with dialog overrides into the flat
        ``decisions`` dict that recognizers consume in ``route()``."""
        decisions: dict[str, str] = {}

        if discovery.pak_groups:
            if pak_overrides is not None:
                decisions.update(pak_overrides)
            else:
                decisions.update(discovery.default_routing)

        if discovery.scripts:
            if script_overrides is not None:
                for i, status in enumerate(script_overrides):
                    decisions[f"script_{i}"] = status
            else:
                for i in range(len(discovery.scripts)):
                    decisions[f"script_{i}"] = "INSTALL"
            decisions["__mod_name__"] = mod_name

        return decisions

    def _compute_allowed_root_names(
        self,
        discovery: DiscoveryResult,
        decisions: dict[str, str],
    ) -> set[str]:
        """Names (lowercased) that survive the post-routing root cleanup.

        Always: 'content', 'binaries'. Plus, for any pak group routed to
        ROOT, the pak/companion file names. Plus, for any group routed to
        a Custom path, the first path segment of that custom path.
        """
        allowed: set[str] = {"content", "binaries"}
        for g in discovery.pak_groups:
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
        self, discovery: DiscoveryResult, mod_name: str
    ) -> None:
        """Single info-level log line for the silent-install branch."""
        parts = [
            f"{g.group_id} → "
            f"{discovery.default_routing.get(g.group_id, 'LogicMods')}"
            for g in discovery.pak_groups
        ]
        parts.extend(
            f"{s.derived_name}/Scripts/main.lua → INSTALL"
            for s in discovery.scripts
        )
        summary = "; ".join(parts) if parts else "no installable content"
        log.info(
            f"PalworldInstaller: silent install (skip-when-trivial predicate "
            f"passed) for {mod_name}: {summary}"
        )

    def _tree_has_installable_content(
        self, tree: mobase.IFileTree
    ) -> bool:
        """Single-walk validation: returns True if any installable
        content (.pak, main.lua, .json, or .dll) survived the rewrite.
        Stops at the first find."""
        found = [False]

        def visit(
            _path: str, entry: mobase.FileTreeEntry
        ) -> mobase.IFileTree.WalkReturn:
            if entry.isFile():
                s = suffix(entry)
                lower = entry.name().lower()
                if s == "pak" or lower == "main.lua" or s == "json" or s == "dll":
                    found[0] = True
                    return mobase.IFileTree.WalkReturn.STOP
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)
        return found[0]

    # --- helper ----------------------------------------------------------
    def _is_recognizer_enabled(self, recognizer_name: str) -> bool:
        key = f"recognizer.{recognizer_name}.enabled"
        val = self._organizer.pluginSetting(self.name(), key)
        if val is None:
            return True
        return bool(val)

    def _tr(self, txt: str) -> str:
        return QCoreApplication.translate("PalworldInstaller", txt)
