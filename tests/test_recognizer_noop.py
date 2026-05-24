"""AC 4.7 — NoopRecognizer detection tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import RequestManual, WalkContext
from plugins.PalworldInstaller.recognizers.noop import NoopRecognizer


def _make_ctx() -> WalkContext:
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
        platform="steam",
        suggested_mod_name="test",
    )


class TestNoopRecognizer:
    def setup_method(self):
        self.recognizer = NoopRecognizer()

    def test_always_returns_request_manual(self):
        ctx = _make_ctx()
        tree = build_tree({})
        result = self.recognizer.detect(tree, ctx)
        assert isinstance(result, RequestManual)
        assert result.reason == "no recognizer claimed this archive"
