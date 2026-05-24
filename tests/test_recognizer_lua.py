"""AC 4.5 — LuaScriptRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, FileTreeEntry
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.lua_script import LuaScriptRecognizer


def _make_ctx(lua_entries: tuple = ()) -> WalkContext:
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=(),
        pak_entries=(),
        companion_entries=(),
        lua_entries=lua_entries,
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform="steam",
        suggested_mod_name="test",
    )


class TestLuaScriptRecognizer:
    def setup_method(self):
        self.recognizer = LuaScriptRecognizer()

    def test_has_lua_entries_matches(self):
        tree = build_tree({"ModName/": {"Scripts/": {"main.lua": FILE}}})
        lua = tree.find("ModName/Scripts/main.lua")
        ctx = _make_ctx(lua_entries=(lua,))
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_no_lua_entries_no_match(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _make_ctx(lua_entries=())
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH
