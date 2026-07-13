"""Mock mobase module for testing without MO2's C++ bindings.

Provides the subset of mobase types that the PalworldInstaller plugin
imports. The mock IFileTree is a real, mutable data structure. move(),
remove(), and addDirectory() all change internal state, so checks made
after those calls work as expected.

Based on docs/mod-organizer.md §15 and how the plugin uses these types.
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Callable
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Enums and simple types
# ---------------------------------------------------------------------------

class ReleaseType:
    PRE_ALPHA = "pre_alpha"
    ALPHA = "alpha"
    BETA = "beta"
    CANDIDATE = "candidate"
    FINAL = "final"


class InstallResult:
    CANCELED = "canceled"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"
    SUCCESS = "success"


class GuessQuality:
    USER = "user"
    GOOD = "good"
    META = "meta"
    PRESET = "preset"
    FALLBACK = "fallback"


class VersionInfo:
    def __init__(self, major=0, minor=0, patch=0, release_type=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.release_type = release_type


class PluginSetting:
    def __init__(self, key: str, description: str, default):
        self.key = key
        self.description = description
        self.default = default


class GuessedString:
    def __init__(self, value: str = ""):
        self._value = value

    def __str__(self) -> str:
        return self._value

    def update(self, value: str, quality=None) -> None:
        self._value = value


# ---------------------------------------------------------------------------
# FileTreeEntry / IFileTree
# ---------------------------------------------------------------------------

class FileTreeEntry:
    """Mock of mobase.FileTreeEntry.

    In real mobase, IFileTree inherits from FileTreeEntry. This means
    directories ARE IFileTree instances. We copy that here: IFileTree
    subclasses FileTreeEntry and returns isDir()=True.
    """

    def __init__(self, name: str, *, is_dir: bool = False):
        self._name = name
        self._parent: IFileTree | None = None

    def name(self) -> str:
        return self._name

    def suffix(self) -> str:
        dot = self._name.rfind(".")
        if dot <= 0:
            return ""
        return self._name[dot + 1:]

    def isFile(self) -> bool:
        return not self.isDir()

    def isDir(self) -> bool:
        return False

    def parent(self) -> IFileTree | None:
        return self._parent


class IFileTree(FileTreeEntry):
    """Mock of mobase.IFileTree — a mutable directory tree.

    Supports iteration, walk(), find(), addDirectory(), move(),
    remove(), and removeIf(). This matches real mobase closely enough
    for the plugin's tree-rewrite tests.
    """

    class WalkReturn(Enum):
        CONTINUE = auto()
        STOP = auto()

    class InsertPolicy(Enum):
        REPLACE = auto()
        MERGE = auto()

    def __init__(self, name: str = ""):
        super().__init__(name, is_dir=True)
        self._children: list[FileTreeEntry] = []

    def isDir(self) -> bool:
        return True

    def isFile(self) -> bool:
        return False

    # --- Iteration (top-level children) ---

    def __iter__(self):
        return iter(list(self._children))

    def __len__(self):
        return len(self._children)

    # --- path() ---

    def path(self, sep: str = "/") -> str:
        """Return this node's path from the root, using sep as separator."""
        parts: list[str] = []
        node: FileTreeEntry = self
        while node._parent is not None:
            parts.append(node.name())
            node = node._parent
        if not parts:
            return ""
        parts.reverse()
        return sep.join(parts)

    # --- walk() ---

    def walk(
        self,
        visitor: Callable[[str, FileTreeEntry], "IFileTree.WalkReturn"],
    ) -> None:
        """Recursively visit all entries. visitor(path, entry) where path
        is the slash-separated path of the entry's parent relative to
        this tree node (empty string for direct children)."""
        self._walk_recursive(visitor, "")

    def _walk_recursive(
        self,
        visitor: Callable[[str, FileTreeEntry], "IFileTree.WalkReturn"],
        current_path: str,
    ) -> bool:
        for child in list(self._children):
            result = visitor(current_path, child)
            if result == IFileTree.WalkReturn.STOP:
                return True
            if isinstance(child, IFileTree) and child.isDir():
                child_path = (
                    f"{current_path}/{child.name()}" if current_path
                    else child.name()
                )
                if child._walk_recursive(visitor, child_path):
                    return True
        return False

    # --- find() ---

    def find(self, path: str) -> FileTreeEntry | None:
        """Find an entry by slash-separated path relative to this tree."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if not parts:
            return None
        return self._find_parts(parts)

    def _find_parts(self, parts: list[str]) -> FileTreeEntry | None:
        target = parts[0]
        for child in self._children:
            if child.name() == target:
                if len(parts) == 1:
                    return child
                if isinstance(child, IFileTree):
                    return child._find_parts(parts[1:])
                return None
        return None

    # --- addDirectory() ---

    def addDirectory(self, path: str) -> "IFileTree":
        """Create the directory at path, plus any missing parent
        directories. Safe to call more than once."""
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if not parts:
            return self
        return self._ensure_dir_parts(parts)

    def _ensure_dir_parts(self, parts: list[str]) -> "IFileTree":
        target = parts[0]
        existing = None
        for child in self._children:
            if child.name().lower() == target.lower() and isinstance(child, IFileTree):
                existing = child
                break

        if existing is None:
            existing = IFileTree(target)
            existing._parent = self
            self._children.append(existing)

        if len(parts) == 1:
            return existing
        return existing._ensure_dir_parts(parts[1:])

    # --- move() ---

    def move(
        self,
        entry: FileTreeEntry,
        dest_path: str,
        policy: "IFileTree.InsertPolicy" = None,
    ) -> None:
        """Move entry to dest_path within this tree.

        dest_path is relative to the tree root. Intermediate directories
        are created as needed. The entry is detached from its current
        parent and reattached at the new location.
        """
        if policy is None:
            policy = IFileTree.InsertPolicy.REPLACE

        self._detach(entry)

        parts = [p for p in dest_path.replace("\\", "/").split("/") if p]
        if not parts:
            entry._parent = self
            self._children.append(entry)
            return

        new_name = parts[-1]
        dir_parts = parts[:-1]

        if dir_parts:
            target_dir = self._ensure_dir_parts(dir_parts)
        else:
            target_dir = self

        if isinstance(entry, IFileTree) and entry.isDir():
            existing = None
            for child in target_dir._children:
                if (
                    child.name().lower() == new_name.lower()
                    and isinstance(child, IFileTree)
                ):
                    existing = child
                    break

            if existing is not None and policy == IFileTree.InsertPolicy.MERGE:
                for sub_child in list(entry._children):
                    sub_child._parent = existing
                    _replace_or_append(existing._children, sub_child)
                return
            elif existing is not None and policy == IFileTree.InsertPolicy.REPLACE:
                target_dir._children.remove(existing)

        entry._name = new_name
        entry._parent = target_dir
        _replace_or_append(target_dir._children, entry)

    # --- remove() ---

    def remove(self, entry: FileTreeEntry) -> None:
        """Remove a single entry from the tree."""
        self._detach(entry)

    def removeIf(self, predicate: Callable[[FileTreeEntry], bool]) -> None:
        """Remove all entries that match predicate. Only the top level is
        checked, which is how mobase behaves."""
        to_remove = [e for e in self._children if predicate(e)]
        for entry in to_remove:
            self._children.remove(entry)
            entry._parent = None

    # --- internal ---

    def _detach(self, entry: FileTreeEntry) -> None:
        """Remove entry from its current parent."""
        parent = entry._parent
        if parent is not None and isinstance(parent, IFileTree):
            try:
                parent._children.remove(entry)
            except ValueError:
                pass
        elif entry in self._children:
            self._children.remove(entry)
        entry._parent = None

    def _add_child(self, entry: FileTreeEntry) -> None:
        """Internal: attach a child entry."""
        entry._parent = self
        self._children.append(entry)


def _replace_or_append(
    children: list[FileTreeEntry], entry: FileTreeEntry
) -> None:
    """Replace existing child with same name, or append."""
    for i, child in enumerate(children):
        if child.name() == entry.name():
            children[i] = entry
            return
    children.append(entry)


# ---------------------------------------------------------------------------
# IOrganizer mock
# ---------------------------------------------------------------------------

class IOrganizer:
    def __init__(self):
        self._settings: dict[str, dict[str, object]] = {}
        self._game = MagicMock()
        self._game.gameName.return_value = "Palworld"
        self._enabled_plugins: set[str] = set()

    def managedGame(self):
        return self._game

    def pluginSetting(self, plugin_name: str, key: str):
        plugin_settings = self._settings.get(plugin_name, {})
        return plugin_settings.get(key)

    def isPluginEnabled(self, name: str) -> bool:
        return name in self._enabled_plugins


# ---------------------------------------------------------------------------
# Base class stub
# ---------------------------------------------------------------------------

class IPlugin:
    pass


class IPluginInstallerSimple(IPlugin):
    def __init__(self):
        pass


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

FILE = object()


def build_tree(structure: dict, name: str = "") -> IFileTree:
    """Build a mock IFileTree from a nested dict.

    Keys ending with "/" are directories; their values are nested dicts.
    Keys not ending with "/" are files; their values should be FILE.

    Example:
        build_tree({
            "mod.pak": FILE,
            "Scripts/": {"main.lua": FILE},
        })
    """
    tree = IFileTree(name)
    _populate_tree(tree, structure)
    return tree


def _populate_tree(parent: IFileTree, structure: dict) -> None:
    for key, value in structure.items():
        if key.endswith("/"):
            dir_name = key.rstrip("/")
            child_dir = IFileTree(dir_name)
            child_dir._parent = parent
            parent._children.append(child_dir)
            if isinstance(value, dict):
                _populate_tree(child_dir, value)
        else:
            child_file = FileTreeEntry(key)
            child_file._parent = parent
            parent._children.append(child_file)
