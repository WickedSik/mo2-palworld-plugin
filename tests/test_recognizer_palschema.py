"""AC 4.3 — PalSchemaRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.palschema import PalSchemaRecognizer


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


class TestPalSchemaRecognizer:
    def setup_method(self):
        self.recognizer = PalSchemaRecognizer()

    def test_palschema_folder_with_json_matches(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"palschema", "mods"}),
            has_json_deep=True,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.MATCH

    def test_palschema_folder_without_json_no_match(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"palschema"}),
            has_json_deep=False,
        )
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH

    def test_json_without_palschema_folder_no_match(self):
        ctx = _make_ctx(
            deep_folder_names=frozenset({"content", "paks"}),
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
