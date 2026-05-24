"""AC 3.2 — Model helper unit tests."""
from __future__ import annotations

import pytest

from tests.mobase_mock import IFileTree, FileTreeEntry, build_tree, FILE
from plugins.PalworldInstaller.models import (
    suffix,
    entry_parent_path,
    entry_full_path,
    move_to,
    resolve_pak_dest_path,
)


class TestSuffix:
    def test_lowercase_pak(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        assert suffix(entry) == "pak"

    def test_uppercase_pak(self):
        tree = build_tree({"MOD.PAK": FILE})
        entry = tree._children[0]
        assert suffix(entry) == "pak"

    def test_mixed_case(self):
        tree = build_tree({"Texture.Pak": FILE})
        entry = tree._children[0]
        assert suffix(entry) == "pak"

    def test_no_extension(self):
        tree = build_tree({"README": FILE})
        entry = tree._children[0]
        assert suffix(entry) == ""

    def test_dotfile(self):
        tree = build_tree({".gitignore": FILE})
        entry = tree._children[0]
        assert suffix(entry) == ""

    def test_utoc(self):
        tree = build_tree({"mod.utoc": FILE})
        entry = tree._children[0]
        assert suffix(entry) == "utoc"

    def test_json(self):
        tree = build_tree({"config.JSON": FILE})
        entry = tree._children[0]
        assert suffix(entry) == "json"


class TestEntryParentPath:
    def test_root_level_entry(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        assert entry_parent_path(entry, tree) == ""

    def test_nested_entry(self):
        tree = build_tree({"Content/": {"Paks/": {"mod.pak": FILE}}})
        pak = tree.find("Content/Paks/mod.pak")
        assert entry_parent_path(pak, tree) == "Content/Paks"

    def test_deeply_nested(self):
        tree = build_tree({"a/": {"b/": {"c/": {"file.txt": FILE}}}})
        entry = tree.find("a/b/c/file.txt")
        assert entry_parent_path(entry, tree) == "a/b/c"

    def test_one_level_deep(self):
        tree = build_tree({"Scripts/": {"main.lua": FILE}})
        entry = tree.find("Scripts/main.lua")
        assert entry_parent_path(entry, tree) == "Scripts"


class TestEntryFullPath:
    def test_root_level(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        assert entry_full_path(entry, tree) == "mod.pak"

    def test_nested(self):
        tree = build_tree({"Content/": {"Paks/": {"mod.pak": FILE}}})
        pak = tree.find("Content/Paks/mod.pak")
        assert entry_full_path(pak, tree) == "Content/Paks/mod.pak"

    def test_deeply_nested(self):
        tree = build_tree({"a/": {"b/": {"c/": {"file.txt": FILE}}}})
        entry = tree.find("a/b/c/file.txt")
        assert entry_full_path(entry, tree) == "a/b/c/file.txt"


class TestMoveTo:
    def test_already_at_destination_is_noop(self):
        tree = build_tree({"Content/": {"Paks/": {"mod.pak": FILE}}})
        entry = tree.find("Content/Paks/mod.pak")
        move_to(tree, entry, "Content/Paks/mod.pak")
        assert tree.find("Content/Paks/mod.pak") is entry

    def test_moves_to_new_location(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        move_to(tree, entry, "Content/Paks/LogicMods/mod.pak")
        assert tree.find("Content/Paks/LogicMods/mod.pak") is not None
        assert tree.find("mod.pak") is None

    def test_leading_slash_stripped(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        move_to(tree, entry, "/Content/Paks/mod.pak")
        assert tree.find("Content/Paks/mod.pak") is not None


class TestResolvePakDestPath:
    def test_tilde_mods(self):
        assert resolve_pak_dest_path("~mods") == "Content/Paks/~mods"

    def test_logicmods(self):
        assert resolve_pak_dest_path("LogicMods") == "Content/Paks/LogicMods"

    def test_custom_path(self):
        assert resolve_pak_dest_path("MyCustom/Path") == "MyCustom/Path"

    def test_another_custom(self):
        assert resolve_pak_dest_path("Content/Paks/Special") == "Content/Paks/Special"
