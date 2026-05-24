"""AC 5.2 — Wrapper stripping integration tests."""
from __future__ import annotations

import pytest

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller


@pytest.fixture
def installer():
    return PalworldInstaller()


class TestStripWrapper:
    def test_palworld_wrapper_promotes_children(self, installer):
        tree = build_tree({
            "Palworld/": {
                "Content/": {"Paks/": {"mod.pak": FILE}},
                "Binaries/": {"Win64/": {"main.dll": FILE}},
            },
        })
        installer._strip_wrapper(tree, "palworld")
        assert tree.find("Content/Paks/mod.pak") is not None
        assert tree.find("Binaries/Win64/main.dll") is not None
        assert tree.find("Palworld") is None

    def test_pal_wrapper_promotes_children(self, installer):
        tree = build_tree({
            "Pal/": {
                "Content/": {"Paks/": {"mod.pak": FILE}},
            },
        })
        installer._strip_wrapper(tree, "pal")
        assert tree.find("Content/Paks/mod.pak") is not None
        assert tree.find("Pal") is None

    def test_no_wrapper_leaves_tree_unchanged(self, installer):
        tree = build_tree({
            "Content/": {"Paks/": {"mod.pak": FILE}},
        })
        installer._strip_wrapper(tree, "palworld")
        assert tree.find("Content/Paks/mod.pak") is not None

    def test_case_insensitive_palworld(self, installer):
        tree = build_tree({
            "PALWORLD/": {"mod.pak": FILE},
        })
        installer._strip_wrapper(tree, "palworld")
        assert tree.find("mod.pak") is not None
        assert tree.find("PALWORLD") is None

    def test_case_insensitive_mixed(self, installer):
        tree = build_tree({
            "palWorld/": {"mod.pak": FILE},
        })
        installer._strip_wrapper(tree, "palworld")
        assert tree.find("mod.pak") is not None
