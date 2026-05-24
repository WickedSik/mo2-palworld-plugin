"""AC 5.1 — Platform variant selection integration tests."""
from __future__ import annotations

import pytest

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller
from plugins.PalworldInstaller.models import PlatformVariantMismatch


@pytest.fixture
def installer():
    inst = PalworldInstaller()
    return inst


class TestApplyPlatformVariant:
    def test_steam_selected_keeps_steam_only(self, installer):
        tree = build_tree({
            "{STEAM}/": {"mod.pak": FILE},
            "{XBOX}/": {"mod_xbox.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "steam")
        assert result is True
        assert tree.find("mod.pak") is not None
        assert tree.find("mod_xbox.pak") is None
        assert tree.find("{STEAM}") is None
        assert tree.find("{XBOX}") is None

    def test_xbox_selected_keeps_xbox_only(self, installer):
        tree = build_tree({
            "{STEAM}/": {"mod.pak": FILE},
            "{XBOX}/": {"mod_xbox.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "xbox")
        assert result is True
        assert tree.find("mod_xbox.pak") is not None
        assert tree.find("mod.pak") is None

    def test_gamepass_fallback_for_xbox(self, installer):
        tree = build_tree({
            "{STEAM}/": {"mod.pak": FILE},
            "{GAMEPASS}/": {"mod_gp.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "xbox")
        assert result is True
        assert tree.find("mod_gp.pak") is not None
        assert tree.find("mod.pak") is None

    def test_xbox_preferred_over_gamepass(self, installer):
        tree = build_tree({
            "{STEAM}/": {"mod.pak": FILE},
            "{XBOX}/": {"mod_xbox.pak": FILE},
            "{GAMEPASS}/": {"mod_gp.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "xbox")
        assert result is True
        assert tree.find("mod_xbox.pak") is not None
        assert tree.find("mod_gp.pak") is None

    def test_bracket_variations_recognized(self, installer):
        tree = build_tree({
            "[Steam]/": {"mod.pak": FILE},
            "(xbox)/": {"mod_xbox.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "steam")
        assert result is True
        assert tree.find("mod.pak") is not None

    def test_bare_name_recognized(self, installer):
        tree = build_tree({
            "STEAM/": {"mod.pak": FILE},
            "XBOX/": {"mod_xbox.pak": FILE},
        })
        result = installer._apply_platform_variant(tree, "steam")
        assert result is True
        assert tree.find("mod.pak") is not None

    def test_no_matching_variant_raises(self, installer):
        tree = build_tree({
            "{XBOX}/": {"mod_xbox.pak": FILE},
        })
        with pytest.raises(PlatformVariantMismatch) as exc_info:
            installer._apply_platform_variant(tree, "steam")
        assert exc_info.value.configured == "steam"
        assert "xbox" in exc_info.value.available

    def test_no_markers_returns_false(self, installer):
        tree = build_tree({
            "mod.pak": FILE,
            "Scripts/": {"main.lua": FILE},
        })
        result = installer._apply_platform_variant(tree, "steam")
        assert result is False
        assert tree.find("mod.pak") is not None
        assert tree.find("Scripts/main.lua") is not None

    def test_root_mod_content_stripped_when_markers_present(self, installer):
        tree = build_tree({
            "{STEAM}/": {"mod_steam.pak": FILE},
            "{XBOX}/": {"mod_xbox.pak": FILE},
            "loose.pak": FILE,
            "script.lua": FILE,
        })
        installer._apply_platform_variant(tree, "steam")
        assert tree.find("mod_steam.pak") is not None
        assert tree.find("loose.pak") is None
        assert tree.find("script.lua") is None
