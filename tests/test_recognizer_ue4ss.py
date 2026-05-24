"""AC 4.1 — Ue4ssSkipRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import RecognitionResult, RequestManual, WalkContext
from plugins.PalworldInstaller.recognizers.ue4ss import Ue4ssSkipRecognizer


def _make_ctx(has_ue4ss_dll: bool = False) -> WalkContext:
    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=has_ue4ss_dll,
        has_json_deep=False,
        dll_entries=(),
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


class TestUe4ssSkipRecognizer:
    def setup_method(self):
        self.recognizer = Ue4ssSkipRecognizer()

    def test_has_ue4ss_dll_returns_request_manual(self):
        ctx = _make_ctx(has_ue4ss_dll=True)
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert isinstance(result, RequestManual)
        assert "manually" in result.reason.lower()

    def test_no_ue4ss_dll_returns_no_match(self):
        ctx = _make_ctx(has_ue4ss_dll=False)
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert result == RecognitionResult.NO_MATCH
