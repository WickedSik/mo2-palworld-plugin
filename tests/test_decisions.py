"""AC 3.3 — Decision building unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller
from plugins.PalworldInstaller.models import (
    DiscoveryResult,
    PakGroup,
    ScriptMod,
)


def _make_pak_group(group_id: str, stem: str) -> PakGroup:
    tree = build_tree({f"{stem}.pak": FILE})
    return PakGroup(
        group_id=group_id,
        stem=stem,
        pak=tree._children[0],
    )


def _make_script(name: str) -> ScriptMod:
    tree = build_tree({f"{name}/": {"Scripts/": {"main.lua": FILE}}})
    mod_dir = tree._children[0]
    main_lua = tree.find(f"{name}/Scripts/main.lua")
    return ScriptMod(
        main_lua=main_lua,
        mod_dir=mod_dir,
        derived_name=name,
        main_lua_display=f"{name}/Scripts/main.lua",
        ambiguous=False,
    )


class TestBuildDecisions:
    def test_empty_discovery(self):
        discovery = DiscoveryResult()
        result = PalworldInstaller._build_decisions(discovery, mod_name="Test")
        assert result == {}

    def test_paks_only_default_routing(self):
        g1 = _make_pak_group("mod.pak", "mod")
        g2 = _make_pak_group("other.pak", "other")
        discovery = DiscoveryResult(
            pak_groups=[g1, g2],
            default_routing={"mod.pak": "LogicMods", "other.pak": "~mods"},
        )
        result = PalworldInstaller._build_decisions(discovery, mod_name="Test")
        assert result == {"mod.pak": "LogicMods", "other.pak": "~mods"}

    def test_paks_with_overrides(self):
        g1 = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(
            pak_groups=[g1],
            default_routing={"mod.pak": "LogicMods"},
        )
        overrides = {"mod.pak": "ROOT"}
        result = PalworldInstaller._build_decisions(
            discovery, pak_overrides=overrides, mod_name="Test"
        )
        assert result == {"mod.pak": "ROOT"}

    def test_scripts_indexed(self):
        s0 = _make_script("ModAlpha")
        s1 = _make_script("ModBeta")
        discovery = DiscoveryResult(scripts=[s0, s1])
        result = PalworldInstaller._build_decisions(
            discovery, mod_name="TestMod"
        )
        assert result["script_0"] == "INSTALL"
        assert result["script_1"] == "INSTALL"
        assert result["__mod_name__"] == "TestMod"

    def test_scripts_with_overrides(self):
        s0 = _make_script("ModAlpha")
        s1 = _make_script("ModBeta")
        discovery = DiscoveryResult(scripts=[s0, s1])
        result = PalworldInstaller._build_decisions(
            discovery,
            script_overrides=["INSTALL", "SKIP"],
            mod_name="TestMod",
        )
        assert result["script_0"] == "INSTALL"
        assert result["script_1"] == "SKIP"
        assert result["__mod_name__"] == "TestMod"

    def test_paks_and_scripts_combined(self):
        g1 = _make_pak_group("mod.pak", "mod")
        s0 = _make_script("ScriptMod")
        discovery = DiscoveryResult(
            pak_groups=[g1],
            default_routing={"mod.pak": "~mods"},
            scripts=[s0],
        )
        result = PalworldInstaller._build_decisions(
            discovery, mod_name="Combined"
        )
        assert result["mod.pak"] == "~mods"
        assert result["script_0"] == "INSTALL"
        assert result["__mod_name__"] == "Combined"

    def test_mod_name_not_set_without_scripts(self):
        g1 = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(
            pak_groups=[g1],
            default_routing={"mod.pak": "LogicMods"},
        )
        result = PalworldInstaller._build_decisions(discovery, mod_name="Test")
        assert "__mod_name__" not in result
