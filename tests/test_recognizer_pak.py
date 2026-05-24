"""AC 4.6 — PakRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, FileTreeEntry
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.pak import PakRecognizer


def _make_ctx(pak_entries: tuple = ()) -> WalkContext:
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=(),
        pak_entries=pak_entries,
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform="steam",
        suggested_mod_name="test",
    )


class TestPakRecognizer:
    def setup_method(self):
        self.recognizer = PakRecognizer()

    def test_has_pak_entries_matches(self):
        tree = build_tree({"mod.pak": FILE})
        pak = tree._children[0]
        ctx = _make_ctx(pak_entries=(pak,))
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_no_pak_entries_no_match(self):
        tree = build_tree({"main.lua": FILE})
        ctx = _make_ctx(pak_entries=())
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH
