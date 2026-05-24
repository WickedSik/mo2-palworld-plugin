"""Self-tests for the mobase mock layer.

Verify that the mock IFileTree behaves correctly so that downstream
tests can trust it.
"""
from __future__ import annotations

from tests.mobase_mock import IFileTree, FileTreeEntry, build_tree, FILE


class TestBuildTree:
    def test_empty_tree(self):
        tree = build_tree({})
        assert len(tree) == 0

    def test_single_file(self):
        tree = build_tree({"mod.pak": FILE})
        assert len(tree) == 1
        assert tree._children[0].name() == "mod.pak"
        assert tree._children[0].isFile() is True

    def test_single_dir(self):
        tree = build_tree({"Scripts/": {}})
        assert len(tree) == 1
        assert tree._children[0].name() == "Scripts"
        assert tree._children[0].isDir() is True

    def test_nested_structure(self):
        tree = build_tree({
            "Content/": {"Paks/": {"mod.pak": FILE}},
        })
        content = tree._children[0]
        assert content.name() == "Content"
        assert content.isDir() is True
        paks = content._children[0]
        assert paks.name() == "Paks"
        pak = paks._children[0]
        assert pak.name() == "mod.pak"
        assert pak.isFile() is True

    def test_parent_references(self):
        tree = build_tree({"Scripts/": {"main.lua": FILE}})
        scripts = tree._children[0]
        lua = scripts._children[0]
        assert lua.parent() is scripts
        assert scripts.parent() is tree


class TestFileTreeEntry:
    def test_suffix(self):
        e = FileTreeEntry("mod.pak")
        assert e.suffix() == "pak"

    def test_suffix_no_extension(self):
        e = FileTreeEntry("README")
        assert e.suffix() == ""

    def test_suffix_dotfile(self):
        e = FileTreeEntry(".gitignore")
        assert e.suffix() == ""

    def test_is_file(self):
        e = FileTreeEntry("file.txt")
        assert e.isFile() is True
        assert e.isDir() is False


class TestIFileTreeIteration:
    def test_iterates_top_level_only(self):
        tree = build_tree({
            "a.pak": FILE,
            "b.pak": FILE,
            "Sub/": {"c.pak": FILE},
        })
        names = [e.name() for e in tree]
        assert "a.pak" in names
        assert "b.pak" in names
        assert "Sub" in names
        assert "c.pak" not in names


class TestIFileTreeWalk:
    def test_visits_all_entries(self):
        tree = build_tree({
            "a.pak": FILE,
            "Sub/": {"b.pak": FILE},
        })
        visited = []
        tree.walk(lambda path, entry: (visited.append((path, entry.name())), IFileTree.WalkReturn.CONTINUE)[1])
        assert ("", "a.pak") in visited
        assert ("", "Sub") in visited
        assert ("Sub", "b.pak") in visited

    def test_stop_halts_walk(self):
        tree = build_tree({
            "a.pak": FILE,
            "b.pak": FILE,
            "c.pak": FILE,
        })
        visited = []

        def visitor(path, entry):
            visited.append(entry.name())
            if entry.name() == "b.pak":
                return IFileTree.WalkReturn.STOP
            return IFileTree.WalkReturn.CONTINUE

        tree.walk(visitor)
        assert "a.pak" in visited
        assert "b.pak" in visited
        assert len(visited) == 2


class TestIFileTreeFind:
    def test_find_root_entry(self):
        tree = build_tree({"mod.pak": FILE})
        assert tree.find("mod.pak") is not None
        assert tree.find("mod.pak").name() == "mod.pak"

    def test_find_nested(self):
        tree = build_tree({"Content/": {"Paks/": {"mod.pak": FILE}}})
        entry = tree.find("Content/Paks/mod.pak")
        assert entry is not None
        assert entry.name() == "mod.pak"

    def test_find_nonexistent(self):
        tree = build_tree({"mod.pak": FILE})
        assert tree.find("nonexistent.pak") is None

    def test_find_directory(self):
        tree = build_tree({"Content/": {"Paks/": {}}})
        paks = tree.find("Content/Paks")
        assert paks is not None
        assert paks.isDir() is True


class TestIFileTreeAddDirectory:
    def test_creates_path(self):
        tree = build_tree({})
        result = tree.addDirectory("Content/Paks/LogicMods")
        assert result.name() == "LogicMods"
        assert tree.find("Content/Paks/LogicMods") is not None

    def test_idempotent(self):
        tree = build_tree({})
        first = tree.addDirectory("Content/Paks")
        second = tree.addDirectory("Content/Paks")
        assert first is second

    def test_preserves_existing_children(self):
        tree = build_tree({"Content/": {"Paks/": {"existing.pak": FILE}}})
        tree.addDirectory("Content/Paks/LogicMods")
        assert tree.find("Content/Paks/existing.pak") is not None
        assert tree.find("Content/Paks/LogicMods") is not None


class TestIFileTreeMove:
    def test_move_file_to_new_dir(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        tree.move(entry, "Content/Paks/LogicMods/mod.pak")
        assert tree.find("Content/Paks/LogicMods/mod.pak") is entry
        assert entry.parent().name() == "LogicMods"

    def test_move_detaches_from_old_parent(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        tree.move(entry, "Dest/mod.pak")
        root_names = [e.name() for e in tree]
        assert "mod.pak" not in root_names
        assert "Dest" in root_names

    def test_move_directory_replace(self):
        tree = build_tree({
            "Source/": {"file.txt": FILE},
            "Target/": {},
        })
        source = tree.find("Source")
        tree.move(source, "Target/Source")
        assert tree.find("Target/Source/file.txt") is not None

    def test_move_directory_merge(self):
        tree = build_tree({
            "Source/": {"new.txt": FILE},
            "Target/": {"existing.txt": FILE},
        })
        source = tree.find("Source")
        tree.move(source, "Target", policy=IFileTree.InsertPolicy.MERGE)
        assert tree.find("Target/existing.txt") is not None
        assert tree.find("Target/new.txt") is not None


class TestIFileTreeRemove:
    def test_remove_entry(self):
        tree = build_tree({"a.pak": FILE, "b.pak": FILE})
        entry = tree.find("a.pak")
        tree.remove(entry)
        assert tree.find("a.pak") is None
        assert tree.find("b.pak") is not None

    def test_remove_if(self):
        tree = build_tree({
            "keep.pak": FILE,
            "remove.txt": FILE,
            "also_remove.log": FILE,
        })
        tree.removeIf(lambda e: e.suffix() != "pak")
        assert tree.find("keep.pak") is not None
        assert tree.find("remove.txt") is None
        assert tree.find("also_remove.log") is None


class TestIFileTreePath:
    def test_root_tree_path_empty(self):
        tree = build_tree({})
        assert tree.path("/") == ""

    def test_child_dir_path(self):
        tree = build_tree({"Content/": {"Paks/": {}}})
        paks = tree.find("Content/Paks")
        assert paks.path("/") == "Content/Paks"

    def test_deeply_nested_path(self):
        tree = build_tree({"a/": {"b/": {"c/": {}}}})
        c = tree.find("a/b/c")
        assert c.path("/") == "a/b/c"


class TestIdentitySemantics:
    def test_parent_is_tree_check(self):
        tree = build_tree({"mod.pak": FILE})
        entry = tree._children[0]
        assert entry.parent() is tree

    def test_nested_parent_is_not_root(self):
        tree = build_tree({"Sub/": {"file.txt": FILE}})
        sub = tree.find("Sub")
        file_entry = tree.find("Sub/file.txt")
        assert file_entry.parent() is sub
        assert file_entry.parent() is not tree
