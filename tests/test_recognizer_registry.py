"""AC 4.8 — Recognizer registry tests."""
from __future__ import annotations

from plugins.PalworldInstaller.recognizers import RECOGNIZERS


class TestRecognizerRegistry:
    def test_sorted_by_priority_ascending(self):
        priorities = [r.priority for r in RECOGNIZERS]
        assert priorities == sorted(priorities)

    def test_no_duplicate_names(self):
        names = [r.name for r in RECOGNIZERS]
        assert len(names) == len(set(names))

    def test_all_seven_recognizers_present(self):
        names = [r.name for r in RECOGNIZERS]
        assert len(names) == 7
        assert "ue4ss" in names
        assert "ue4ss_plugin" in names
        assert "lua_script" in names
        assert "palschema" in names
        assert "altermatic" in names
        assert "pak" in names
        assert "noop" in names

    def test_expected_priority_order(self):
        name_order = [r.name for r in RECOGNIZERS]
        assert name_order.index("ue4ss") < name_order.index("ue4ss_plugin")
        assert name_order.index("ue4ss_plugin") < name_order.index("lua_script")
        assert name_order.index("lua_script") < name_order.index("palschema")
        assert name_order.index("palschema") < name_order.index("altermatic")
        assert name_order.index("altermatic") < name_order.index("pak")
        assert name_order.index("pak") < name_order.index("noop")
