from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import mobase


# --- Helpers ----------------------------------------------------------------

def suffix(entry: mobase.FileTreeEntry) -> str:
    """Lower-case file suffix. mobase keeps the on-disk case in
    ``entry.suffix()``. Real archives use mixed case (``.PAK``,
    ``.Pak``). Lowercasing here keeps detection consistent."""
    return entry.suffix().lower()


def entry_parent_path(
    entry: mobase.FileTreeEntry, tree: mobase.IFileTree
) -> str:
    """Return the parent directory's path from the tree root, or ``""``
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
    """Move ``entry`` to the absolute path ``target``, unless it is
    already there. Some IFileTree implementations fail on self-moves."""
    current = entry_full_path(entry, tree)
    if current == target.lstrip("/"):
        return
    tree.move(entry, target, policy=mobase.IFileTree.InsertPolicy.REPLACE)


def resolve_pak_dest_path(decision: str) -> str:
    """Map a decision that is not SKIP or ROOT to a destination path.

    Preset values map to a fixed ``Content/Paks/<dest>/``. Anything else
    is treated as a Custom path and used as-is under the archive root.
    """
    if decision == "~mods":
        return "Content/Paks/~mods"
    if decision == "LogicMods":
        return "Content/Paks/LogicMods"
    return decision


def ue4ss_mods_base(platform: str) -> str:
    """Return the UE4SS ``Mods`` directory (relative to the game data
    root) that the UE4SS runtime scans for script and plugin mods.

    This is the one place that defines this path. The ``ue4ss/`` segment
    is required. UE4SS only loads mods placed under
    ``Binaries/<runtime>/ue4ss/Mods/``. Leave it out and every script
    mod silently fails to load. ``Win64`` is the Steam runtime,
    ``WinGDK`` the Xbox / Game Pass runtime.

    NOTE: the Steam (``Win64``) path is checked against real UE4SS mod
    archives. The ``WinGDK`` path follows the documented Xbox runtime,
    but is not yet confirmed against a live Game Pass install.
    """
    runtime = "WinGDK" if platform == "xbox" else "Win64"
    return f"Binaries/{runtime}/ue4ss/Mods"


ROOT_BUILDER_DIR = "Root"
"""Top-level folder Kezyma's Root Builder deploys into the game install
root. Root Builder copies or hard-links ``<mod>/Root/X`` to ``<game>/X``
when the game launches, bypassing MO2's virtual filesystem."""

DEFAULT_GAME_ROOT_OFFSET = "Pal"
"""Path from the game install root down to MO2's data root.

Both Palworld and Palworld Server declare ``GameDataPath = "Pal"``, so
MO2's data root is ``<install>/Pal/`` and every path this module builds
is relative to it. Root Builder works from the install root instead, so
its targets need this offset put back in front.
"""


def rootbuilder_ue4ss_mods_base(platform: str) -> str:
    """The UE4SS ``Mods`` directory written as a Root Builder path.

    The Windows loader maps a ``.dll`` at process start and does not
    reliably honour USVFS hooks, so UE4SS C++ plugins often fail to load
    when they are only mapped virtually. Routing them here makes Root
    Builder place them on disk instead.

    ``ue4ss_mods_base()`` stays the one source of the UE4SS path. This
    only prefixes it, so the two can never drift apart.
    """
    return (
        f"{ROOT_BUILDER_DIR}/{DEFAULT_GAME_ROOT_OFFSET}/"
        f"{ue4ss_mods_base(platform)}"
    )


def prune_empty_dirs(
    tree: mobase.IFileTree,
    start: mobase.FileTreeEntry | None,
) -> None:
    """Remove ``start`` and its ancestors while they are empty
    directories. Stops at the first non-empty one, and never removes the
    tree root itself.

    Moving a plugin folder out of ``Binaries/Win64/ue4ss/Mods/`` leaves
    that chain behind. ``Binaries`` survives the installer's root
    cleanup, so without this the mod ships an empty skeleton.
    """
    node = start
    while (
        node is not None
        and node is not tree
        and node.isDir()
        and len(node) == 0
    ):
        parent = node.parent()
        tree.remove(node)
        node = parent


def move_plugin_dir(
    tree: mobase.IFileTree,
    plugin_dir: mobase.FileTreeEntry,
    base: str,
) -> str | None:
    """Move a UE4SS plugin folder to ``<base>/<name>``.

    Returns the destination path, or ``None`` when the folder is already
    there. Directories left empty by the move are pruned.

    The already-there check ignores case. Archive casing varies, and
    both recognizer patterns match case-insensitively, so the guard has
    to as well -- a self-move can fail on a real IFileTree.
    """
    target = f"{base}/{plugin_dir.name()}"
    if entry_full_path(plugin_dir, tree).lower() == target.lower():
        return None

    old_parent = plugin_dir.parent()
    tree.move(plugin_dir, target, policy=mobase.IFileTree.InsertPolicy.REPLACE)
    prune_empty_dirs(tree, old_parent)
    return target


# --- Domain models ----------------------------------------------------------

class PlatformVariantMismatch(Exception):
    """Raised by an early installer pass when an archive has platform
    marker folders but none match the configured platform.

    The install must stop with ``InstallResult.FAILED`` before it makes
    any destructive change to the tree. This keeps "manual installation"
    a real option for the user.
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
    """One .pak stem group. This is the .pak plus its same-stem
    .utoc/.ucas companions in the same parent directory, plus any
    sibling AnimJSON / SwapJSON dirs at the archive root (linked to
    every root-level group at that level).

    ``group_id`` is the pak's full path from the tree root. It is the
    stable key into the routing-decision dicts. Two paks that share a
    stem in different directories are separate groups.

    ``current_parent_path`` is the path of the directory that holds the
    pak now (``""`` means the archive root). The routing logic uses it
    to work out the default destination for prearranged content.
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
    moves on INSTALL or removes on SKIP. For an unclear root-level
    main.lua it may equal the tree itself, which SKIP handles to be
    safe."""

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
    """Read-only signals for one install: everything gathered from a
    single ``tree.walk()`` pass, plus the resolved settings recognizers
    need (``platform``, ``use_rootbuilder``). Built by the installer
    after the earlier passes (platform resolution, wrapper stripping,
    moving prearranged folders up) have run on the tree.

    Recognizers get this in ``detect()``, ``discover()``, and
    ``route()`` and must not walk the tree themselves.
    """

    has_fomod: bool
    has_ue4ss_dll: bool
    has_json_deep: bool
    dll_entries: tuple[mobase.FileTreeEntry, ...]
    pak_entries: tuple[mobase.FileTreeEntry, ...]
    companion_entries: tuple[mobase.FileTreeEntry, ...]
    lua_entries: tuple[mobase.FileTreeEntry, ...]
    json_entries: tuple[mobase.FileTreeEntry, ...]
    json_dirs: tuple[mobase.FileTreeEntry, ...]
    folder_names: frozenset[str]
    deep_folder_names: frozenset[str]
    platform: str
    suggested_mod_name: str
    use_rootbuilder: bool = False


def ue4ss_plugin_dest_base(ctx: WalkContext) -> str:
    """Where UE4SS C++ DLL plugins go.

    Only ``ue4ss_plugin`` and ``dll_plugin`` call this. Lua scripts,
    PalSchema content, paks, and json stay on ``ue4ss_mods_base()`` --
    they load fine through the virtual filesystem and gain nothing from
    Root Builder.
    """
    if ctx.use_rootbuilder:
        return rootbuilder_ue4ss_mods_base(ctx.platform)
    return ue4ss_mods_base(ctx.platform)


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

    Provides the data the installer needs to fill the dialog and find
    unclaimed files.
    """

    pak_groups: list[PakGroup] = field(default_factory=list)
    default_routing: dict[str, str] = field(default_factory=dict)
    scripts: list[ScriptMod] = field(default_factory=list)
    claimed_paths: set[str] = field(default_factory=set)
    should_show_dialog: bool = False
    routing_summary: list[str] = field(default_factory=list)
    extra_root_names: set[str] = field(default_factory=set)
    """Extra top-level directory names that must survive root cleanup.

    A recognizer that routes into a directory the installer does not
    know about -- Root Builder's ``Root/`` is the only one today --
    declares it here. Matched case-insensitively.
    """
