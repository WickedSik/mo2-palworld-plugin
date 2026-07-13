"""AC 5.3 — Tests that an already-arranged layout is moved up to the right place."""
from __future__ import annotations

import pytest

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller


@pytest.fixture
def installer():
    return PalworldInstaller()


class TestPromotePrearrangedLayout:
    def test_logicmods_promoted(self, installer):
        tree = build_tree({
            "LogicMods/": {"mod.pak": FILE, "config.json": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/LogicMods/mod.pak") is not None
        assert tree.find("Content/Paks/LogicMods/config.json") is not None
        assert tree.find("LogicMods") is None

    def test_tilde_mods_promoted(self, installer):
        tree = build_tree({
            "~mods/": {"mod_P.pak": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/~mods/mod_P.pak") is not None
        assert tree.find("~mods") is None

    def test_case_insensitive_logicmods(self, installer):
        tree = build_tree({
            "logicmods/": {"mod.pak": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/LogicMods/mod.pak") is not None

    def test_case_insensitive_upper(self, installer):
        tree = build_tree({
            "LOGICMODS/": {"mod.pak": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/LogicMods/mod.pak") is not None

    def test_both_promoted(self, installer):
        tree = build_tree({
            "LogicMods/": {"logic.pak": FILE},
            "~mods/": {"tilde.pak": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/LogicMods/logic.pak") is not None
        assert tree.find("Content/Paks/~mods/tilde.pak") is not None

    def test_non_matching_dir_unchanged(self, installer):
        tree = build_tree({
            "Content/": {"Paks/": {"mod.pak": FILE}},
            "Scripts/": {"main.lua": FILE},
        })
        installer._promote_prearranged_layout(tree)
        assert tree.find("Content/Paks/mod.pak") is not None
        assert tree.find("Scripts/main.lua") is not None
