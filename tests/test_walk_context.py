"""AC 5.9 — Walk context building integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller


class TestBuildWalkContext:
    def setup_method(self):
        self.installer = PalworldInstaller()

    def test_mixed_archive_all_signals(self):
        tree = build_tree({
            "mod.pak": FILE,
            "mod.utoc": FILE,
            "main.lua": FILE,
            "config.json": FILE,
            "helper.dll": FILE,
            "fomod/": {"moduleconfig.xml": FILE},
            "AnimJSON/": {"swap.json": FILE},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "TestMod")
        assert len(ctx.pak_entries) == 1
        assert len(ctx.companion_entries) == 1
        assert len(ctx.lua_entries) == 1
        assert len(ctx.json_entries) == 1
        assert len(ctx.dll_entries) == 1
        assert len(ctx.json_dirs) == 1
        assert ctx.has_fomod is True
        assert ctx.has_ue4ss_dll is False
        assert ctx.platform == "steam"
        assert ctx.suggested_mod_name == "TestMod"

    def test_empty_archive(self):
        tree = build_tree({})
        ctx = self.installer._build_walk_context(tree, "steam", "Empty")
        assert len(ctx.pak_entries) == 0
        assert len(ctx.companion_entries) == 0
        assert len(ctx.lua_entries) == 0
        assert len(ctx.json_entries) == 0
        assert len(ctx.dll_entries) == 0
        assert len(ctx.json_dirs) == 0
        assert ctx.has_fomod is False
        assert ctx.has_ue4ss_dll is False
        assert ctx.has_json_deep is False

    def test_nested_paks_found_by_walk(self):
        tree = build_tree({
            "Content/": {"Paks/": {"LogicMods/": {"mod.pak": FILE}}},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert len(ctx.pak_entries) == 1
        assert ctx.pak_entries[0].name() == "mod.pak"

    def test_animjson_swapjson_at_root_captured(self):
        tree = build_tree({
            "AnimJSON/": {"anim.json": FILE},
            "SwapJSON/": {"swap.json": FILE},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert len(ctx.json_dirs) == 2
        dir_names = {d.name() for d in ctx.json_dirs}
        assert "AnimJSON" in dir_names
        assert "SwapJSON" in dir_names

    def test_json_at_root_vs_nested(self):
        tree = build_tree({
            "root.json": FILE,
            "SubDir/": {"nested.json": FILE},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert len(ctx.json_entries) == 1
        assert ctx.json_entries[0].name() == "root.json"
        assert ctx.has_json_deep is True

    def test_deep_folder_names_all_depths(self):
        tree = build_tree({
            "TopDir/": {"MidDir/": {"DeepDir/": {"file.txt": FILE}}},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert "topdir" in ctx.deep_folder_names
        assert "middir" in ctx.deep_folder_names
        assert "deepdir" in ctx.deep_folder_names

    def test_folder_names_root_only(self):
        tree = build_tree({
            "RootDir/": {"ChildDir/": {"file.txt": FILE}},
            "OtherRoot/": {"file.txt": FILE},
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert "rootdir" in ctx.folder_names
        assert "otherroot" in ctx.folder_names
        assert "childdir" not in ctx.folder_names

    def test_ue4ss_dll_detected(self):
        tree = build_tree({
            "ue4ss.dll": FILE,
            "mod.pak": FILE,
        })
        ctx = self.installer._build_walk_context(tree, "steam", "Test")
        assert ctx.has_ue4ss_dll is True
        assert len(ctx.pak_entries) == 1
