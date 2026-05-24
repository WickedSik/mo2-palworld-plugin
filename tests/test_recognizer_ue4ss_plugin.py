"""AC 4.2 — Ue4ssPluginRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, FileTreeEntry, IFileTree
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.ue4ss_plugin import Ue4ssPluginRecognizer


def _make_ctx_with_dlls(tree: IFileTree, dll_paths: list[str]) -> WalkContext:
    dll_entries = tuple(tree.find(p) for p in dll_paths if tree.find(p))
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=dll_entries,
        pak_entries=(),
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform="steam",
        suggested_mod_name="test",
    )


class TestUe4ssPluginRecognizer:
    def setup_method(self):
        self.recognizer = Ue4ssPluginRecognizer()

    def test_matching_ue4ss_plugin_layout(self):
        tree = build_tree({
            "ue4ss/": {"Mods/": {"PalSchema/": {"dlls/": {"main.dll": FILE}}}},
        })
        ctx = _make_ctx_with_dlls(tree, ["ue4ss/Mods/PalSchema/dlls/main.dll"])
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_unrelated_dll_no_match(self):
        tree = build_tree({
            "somefolder/": {"random.dll": FILE},
        })
        ctx = _make_ctx_with_dlls(tree, ["somefolder/random.dll"])
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH

    def test_empty_dlls_no_match(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _make_ctx_with_dlls(tree, [])
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH

    def test_case_insensitive_path_match(self):
        tree = build_tree({
            "UE4SS/": {"Mods/": {"MyPlugin/": {"dlls/": {"main.dll": FILE}}}},
        })
        ctx = _make_ctx_with_dlls(tree, ["UE4SS/Mods/MyPlugin/dlls/main.dll"])
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH
