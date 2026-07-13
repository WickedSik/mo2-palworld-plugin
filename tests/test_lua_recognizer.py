"""AC 5.5 — LuaScriptRecognizer discover() and route() integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.lua_script import LuaScriptRecognizer


def _build_ctx(tree, platform="steam"):
    lua_entries = []

    def visit(path, entry):
        if entry.isFile() and entry.name().lower() == "main.lua":
            lua_entries.append(entry)
        return IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)

    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=(),
        pak_entries=(),
        companion_entries=(),
        lua_entries=tuple(lua_entries),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform=platform,
        suggested_mod_name="TestMod",
    )


class TestLuaScriptRecognizerDiscover:
    def setup_method(self):
        self.recognizer = LuaScriptRecognizer()

    def test_standard_layout_unambiguous(self):
        tree = build_tree({
            "MyMod/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.scripts) == 1
        assert result.scripts[0].derived_name == "MyMod"
        assert result.scripts[0].ambiguous is False

    def test_bare_root_main_lua_ambiguous(self):
        tree = build_tree({"main.lua": FILE})
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.scripts) == 1
        assert result.scripts[0].ambiguous is True

    def test_scripts_dir_at_root_ambiguous(self):
        tree = build_tree({
            "Scripts/": {"main.lua": FILE},
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.scripts) == 1
        assert result.scripts[0].ambiguous is True
        assert result.scripts[0].derived_name == "Scripts"

    def test_multiple_scripts_discovered(self):
        tree = build_tree({
            "ModA/": {"Scripts/": {"main.lua": FILE}},
            "ModB/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.scripts) == 2
        names = {s.derived_name for s in result.scripts}
        assert names == {"ModA", "ModB"}


class TestLuaScriptRecognizerRoute:
    def setup_method(self):
        self.recognizer = LuaScriptRecognizer()

    def test_route_steam_platform(self):
        tree = build_tree({
            "MyMod/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree, platform="steam")
        decisions = {"script_0": "INSTALL", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/MyMod/Scripts/main.lua"
        ) is not None

    def test_route_xbox_platform(self):
        tree = build_tree({
            "MyMod/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree, platform="xbox")
        decisions = {"script_0": "INSTALL", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find(
            "Binaries/WinGDK/ue4ss/Mods/MyMod/Scripts/main.lua"
        ) is not None

    def test_route_skip_removes_mod_dir(self):
        tree = build_tree({
            "MyMod/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree, platform="steam")
        decisions = {"script_0": "SKIP", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("MyMod") is None
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/MyMod/Scripts/main.lua"
        ) is None

    def test_ambiguous_root_lua_uses_mod_name(self):
        tree = build_tree({"main.lua": FILE})
        ctx = _build_ctx(tree, platform="steam")
        decisions = {"script_0": "INSTALL", "__mod_name__": "FallbackName"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/FallbackName/Scripts/main.lua"
        ) is not None

    def test_route_places_scripts_under_ue4ss_segment(self):
        """Regression: the canonical UE4SS Mods path MUST contain the
        ``ue4ss/`` segment. Writing to Binaries/Win64/Mods/... (without
        it) means UE4SS never loads the mod (the M8 defect)."""
        tree = build_tree({
            "MyMod/": {"Scripts/": {"main.lua": FILE}},
        })
        ctx = _build_ctx(tree, platform="steam")
        decisions = {"script_0": "INSTALL", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find(
            "Binaries/Win64/Mods/MyMod/Scripts/main.lua"
        ) is None


class TestLuaScriptRecognizerPrearranged:
    """Regression guard for the M8 UE4SS-mod failure: archives that
    already ship the full ``Binaries/Win64/ue4ss/Mods/<name>/Scripts/``
    layout (e.g. Expanded World Options 3336, Infinite Weight In Camp
    214) must SURVIVE routing untouched -- never be demoted by having
    the ``ue4ss/`` segment stripped."""

    def setup_method(self):
        self.recognizer = LuaScriptRecognizer()

    def _prearranged_tree(self, runtime="Win64"):
        return build_tree({
            "Binaries/": {
                runtime + "/": {
                    "ue4ss/": {
                        "Mods/": {
                            "ExpandedWorldSettings/": {
                                "enabled.txt": FILE,
                                "Scripts/": {
                                    "main.lua": FILE,
                                    "config.lua": FILE,
                                },
                            },
                        },
                    },
                },
            },
        })

    def test_prearranged_steam_survives_untouched(self):
        tree = self._prearranged_tree("Win64")
        ctx = _build_ctx(tree, platform="steam")
        decisions = {"script_0": "INSTALL", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        # Still at the canonical path...
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/ExpandedWorldSettings/"
            "Scripts/main.lua"
        ) is not None
        # ...sidecars preserved...
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/ExpandedWorldSettings/enabled.txt"
        ) is not None
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/ExpandedWorldSettings/"
            "Scripts/config.lua"
        ) is not None
        # ...and NOT demoted to the ue4ss-less path.
        assert tree.find(
            "Binaries/Win64/Mods/ExpandedWorldSettings/Scripts/main.lua"
        ) is None

    def test_prearranged_xbox_survives_untouched(self):
        # NOTE: the WinGDK path is not yet verified against a real Game
        # Pass install; this asserts internal consistency, not the live
        # Xbox contract.
        tree = self._prearranged_tree("WinGDK")
        ctx = _build_ctx(tree, platform="xbox")
        decisions = {"script_0": "INSTALL", "__mod_name__": "TestMod"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find(
            "Binaries/WinGDK/ue4ss/Mods/ExpandedWorldSettings/"
            "Scripts/main.lua"
        ) is not None
