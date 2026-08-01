"""Root Builder path helpers and the shared tree-move machinery."""
from __future__ import annotations

import pytest

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import (
    DEFAULT_GAME_ROOT_OFFSET,
    ROOT_BUILDER_DIR,
    WalkContext,
    move_plugin_dir,
    prune_empty_dirs,
    rootbuilder_ue4ss_mods_base,
    ue4ss_mods_base,
    ue4ss_plugin_dest_base,
)


def _ctx(platform="steam", use_rootbuilder=False):
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=(),
        pak_entries=(),
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform=platform,
        suggested_mod_name="TestMod",
        use_rootbuilder=use_rootbuilder,
    )


class TestRootbuilderUe4ssModsBase:
    def test_steam(self):
        assert (
            rootbuilder_ue4ss_mods_base("steam")
            == "Root/Pal/Binaries/Win64/ue4ss/Mods"
        )

    def test_xbox(self):
        assert (
            rootbuilder_ue4ss_mods_base("xbox")
            == "Root/Pal/Binaries/WinGDK/ue4ss/Mods"
        )

    @pytest.mark.parametrize("platform", ["steam", "xbox"])
    def test_composes_onto_the_single_source_of_truth(self, platform):
        """The UE4SS path lives in ue4ss_mods_base() alone. This helper
        may only prefix it -- never re-derive it."""
        assert rootbuilder_ue4ss_mods_base(platform).endswith(
            ue4ss_mods_base(platform)
        )

    @pytest.mark.parametrize("platform", ["steam", "xbox"])
    def test_starts_with_root_and_game_offset(self, platform):
        assert rootbuilder_ue4ss_mods_base(platform).startswith(
            f"{ROOT_BUILDER_DIR}/{DEFAULT_GAME_ROOT_OFFSET}/"
        )


class TestUe4ssPluginDestBase:
    def test_rootbuilder_off_uses_plain_path(self):
        assert ue4ss_plugin_dest_base(_ctx()) == ue4ss_mods_base("steam")

    def test_rootbuilder_on_uses_root_path(self):
        assert (
            ue4ss_plugin_dest_base(_ctx(use_rootbuilder=True))
            == rootbuilder_ue4ss_mods_base("steam")
        )

    def test_rootbuilder_on_xbox(self):
        assert (
            ue4ss_plugin_dest_base(_ctx("xbox", use_rootbuilder=True))
            == "Root/Pal/Binaries/WinGDK/ue4ss/Mods"
        )


class TestPruneEmptyDirs:
    def test_prunes_whole_empty_chain(self):
        tree = build_tree({"Binaries/": {"Win64/": {"ue4ss/": {"Mods/": {}}}}})
        prune_empty_dirs(tree, tree.find("Binaries/Win64/ue4ss/Mods"))
        assert [e.name() for e in tree] == []

    def test_stops_at_non_empty_ancestor(self):
        tree = build_tree({
            "Binaries/": {
                "Win64/": {"ue4ss/": {"Mods/": {}}, "keep.txt": FILE},
            },
        })
        prune_empty_dirs(tree, tree.find("Binaries/Win64/ue4ss/Mods"))
        assert tree.find("Binaries/Win64/ue4ss") is None
        assert tree.find("Binaries/Win64/keep.txt") is not None

    def test_tolerates_none(self):
        tree = build_tree({"a/": {}})
        prune_empty_dirs(tree, None)
        assert [e.name() for e in tree] == ["a"]

    def test_never_removes_tree_root(self):
        tree = build_tree({})
        prune_empty_dirs(tree, tree)
        assert tree is not None


class TestMovePluginDir:
    def test_moves_and_returns_destination(self):
        tree = build_tree({"PalSchema/": {"dlls/": {"main.dll": FILE}}})
        dest = move_plugin_dir(
            tree, tree.find("PalSchema"), "Binaries/Win64/ue4ss/Mods"
        )
        assert dest == "Binaries/Win64/ue4ss/Mods/PalSchema"
        assert tree.find(f"{dest}/dlls/main.dll") is not None
        assert tree.find("PalSchema") is None

    def test_returns_none_when_already_in_place(self):
        tree = build_tree({
            "Binaries/": {
                "Win64/": {
                    "ue4ss/": {"Mods/": {"X/": {"dlls/": {"main.dll": FILE}}}},
                },
            },
        })
        assert move_plugin_dir(
            tree,
            tree.find("Binaries/Win64/ue4ss/Mods/X"),
            "Binaries/Win64/ue4ss/Mods",
        ) is None

    def test_case_only_difference_is_not_a_move(self):
        """Archive casing varies; both recognizer patterns ignore case,
        so the guard must too -- a self-move can fail on real mobase."""
        tree = build_tree({
            "root/": {
                "pal/": {
                    "binaries/": {
                        "win64/": {
                            "ue4ss/": {
                                "mods/": {"X/": {"dlls/": {"main.dll": FILE}}},
                            },
                        },
                    },
                },
            },
        })
        entry = tree.find("root/pal/binaries/win64/ue4ss/mods/X")
        assert move_plugin_dir(
            tree, entry, rootbuilder_ue4ss_mods_base("steam")
        ) is None

    def test_prunes_the_directories_it_empties(self):
        tree = build_tree({
            "ue4ss/": {"Mods/": {"X/": {"dlls/": {"main.dll": FILE}}}},
        })
        move_plugin_dir(
            tree, tree.find("ue4ss/Mods/X"), "Binaries/Win64/ue4ss/Mods"
        )
        assert tree.find("Binaries/Win64/ue4ss/Mods/X/dlls/main.dll") is not None
        assert [e.name() for e in tree] == ["Binaries"]
