"""AC 4.4 — AltermaticRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.altermatic import AltermaticRecognizer


def _make_ctx(
    deep_folder_names: frozenset[str] = frozenset(),
    has_json_deep: bool = False,
) -> WalkContext:
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=has_json_deep,
        dll_entries=(),
        pak_entries=(),
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=deep_folder_names,
        platform="steam",
        suggested_mod_name="test",
    )


class TestAltermaticRecognizer:
    def setup_method(self):
        self.recognizer = AltermaticRecognizer()

    def test_animjson_with_json_matches(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"animjson"}),
            has_json_deep=True,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_swapjson_with_json_matches(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"swapjson"}),
            has_json_deep=True,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_both_markers_with_json_matches(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"animjson", "swapjson"}),
            has_json_deep=True,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_animjson_without_json_no_match(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"animjson"}),
            has_json_deep=False,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH

    def test_no_marker_folders_no_match(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"content", "scripts"}),
            has_json_deep=True,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH

    def test_empty_context_no_match(self):
        ctx = _make_ctx()
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH
