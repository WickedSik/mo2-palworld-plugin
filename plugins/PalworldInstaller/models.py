from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import mobase


# --- Helpers ----------------------------------------------------------------

def suffix(entry: mobase.FileTreeEntry) -> str:
    """Lower-case file suffix. mobase preserves the on-disk case in
    ``entry.suffix()``; archives in the wild use mixed case (``.PAK``,
    ``.Pak``). Normalising here keeps detection consistent."""
    return entry.suffix().lower()


def entry_parent_path(
    entry: mobase.FileTreeEntry, tree: mobase.IFileTree
) -> str:
    """Return the parent directory's path-from-tree-root, or ``""``
    for entries directly under the archive root."""
    parent = entry.parent()
    if parent is None or parent is tree:
        return ""
    return parent.path("/")


def entry_full_path(
    entry: mobase.FileTreeEntry, tree: mobase.IFileTree
) -> str:
    """Full path of ``entry`` relative to the tree root."""
    parent_path = entry_parent_path(entry, tree)
    if parent_path:
        return f"{parent_path}/{entry.name()}"
    return entry.name()


def move_to(
    tree: mobase.IFileTree,
    entry: mobase.FileTreeEntry,
    target: str,
) -> None:
    """Move ``entry`` to absolute path ``target`` unless it's already
    there (some IFileTree implementations balk at self-moves)."""
    current = entry_full_path(entry, tree)
    if current == target.lstrip("/"):
        return
    tree.move(entry, target, policy=mobase.IFileTree.InsertPolicy.REPLACE)


def resolve_pak_dest_path(decision: str) -> str:
    """Map a non-SKIP, non-ROOT decision to a destination path.

    Preset values map to fixed ``Content/Paks/<dest>/``. Anything else
    is treated as a Custom path and used verbatim under the archive root.
    """
    if decision == "~mods":
        return "Content/Paks/~mods"
    if decision == "LogicMods":
        return "Content/Paks/LogicMods"
    return decision


# --- Domain models ----------------------------------------------------------

class PlatformVariantMismatch(Exception):
    """Raised by the orchestrator pre-pass when an archive contains
    platform marker folders but none match the configured platform.

    The install must abort with ``InstallResult.FAILED`` before any
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


# --- Recognition types ------------------------------------------------------

class RecognitionResult(Enum):
    """Outcome of a recognizer's ``detect()`` call."""
    NO_MATCH = auto()
    MATCH = auto()


@dataclass(frozen=True)
class RequestManual:
    """Returned by ``detect()`` when the recognizer identifies the archive
    but declines automatic installation."""
    reason: str


DetectionVerdict = RecognitionResult | RequestManual


# --- Walk context ------------------------------------------------------------

@dataclass(frozen=True)
class WalkContext:
    """Read-only aggregation of every signal gathered from a single
    ``tree.walk()`` pass. Built by the orchestrator after pre-passes
    (platform resolution, wrapper stripping, prearranged layout
    promotion) have been applied to the tree.

    Recognizers receive this in ``detect()``, ``discover()``, and
    ``route()`` and must not walk the tree on their own.
    """

    has_fomod: bool
    has_ue4ss_dll: bool
    has_json_deep: bool
    has_ue4ss_plugin_layout: bool
    pak_entries: tuple[mobase.FileTreeEntry, ...]
    companion_entries: tuple[mobase.FileTreeEntry, ...]
    lua_entries: tuple[mobase.FileTreeEntry, ...]
    json_entries: tuple[mobase.FileTreeEntry, ...]
    json_dirs: tuple[mobase.FileTreeEntry, ...]
    folder_names: frozenset[str]
    deep_folder_names: frozenset[str]
    platform: str
    suggested_mod_name: str


# --- Plan steps --------------------------------------------------------------

@dataclass(frozen=True)
class MoveEntry:
    """Move ``entry`` to ``destination`` (absolute path from tree root)."""
    entry: mobase.FileTreeEntry
    destination: str


@dataclass(frozen=True)
class RemoveEntry:
    """Remove ``entry`` from the tree."""
    entry: mobase.FileTreeEntry


@dataclass(frozen=True)
class AddDirectory:
    """Ensure ``path`` exists as a directory in the tree."""
    path: str


PlanStep = MoveEntry | RemoveEntry | AddDirectory


# --- Discovery result --------------------------------------------------------

@dataclass
class DiscoveryResult:
    """Returned by a recognizer's ``discover()`` method.

    Provides the data the orchestrator needs to populate the dialog
    and identify unclaimed files.
    """

    pak_groups: list[PakGroup] = field(default_factory=list)
    default_routing: dict[str, str] = field(default_factory=dict)
    scripts: list[ScriptMod] = field(default_factory=list)
    claimed_paths: set[str] = field(default_factory=set)
    should_show_dialog: bool = False
    routing_summary: list[str] = field(default_factory=list)
