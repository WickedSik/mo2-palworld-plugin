"""AC 3.4 — Allowed root names unit tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.installer import PalworldInstaller
from plugins.PalworldInstaller.models import DiscoveryResult, PakGroup


def _make_pak_group(group_id: str, stem: str, parent_path: str = "") -> PakGroup:
    tree = build_tree({f"{stem}.pak": FILE})
    pak = tree._children[0]
    companions = []
    if "_P" in stem:
        comp_tree = build_tree({f"{stem}.utoc": FILE})
        companions.append(comp_tree._children[0])
    return PakGroup(
        group_id=group_id,
        stem=stem,
        pak=pak,
        companions=companions,
        current_parent_path=parent_path,
    )


class TestComputeAllowedRootNames:
    def setup_method(self):
        self.installer = PalworldInstaller()

    def test_always_includes_content_and_binaries(self):
        discovery = DiscoveryResult()
        decisions = {}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert "content" in result
        assert "binaries" in result

    def test_root_group_adds_filenames(self):
        g = _make_pak_group("mod_P.pak", "mod_P")
        discovery = DiscoveryResult(pak_groups=[g])
        decisions = {"mod_P.pak": "ROOT"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert "mod_p.pak" in result
        assert "mod_p.utoc" in result

    def test_preset_adds_nothing_beyond_defaults(self):
        g = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(pak_groups=[g])
        decisions = {"mod.pak": "LogicMods"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert result == {"content", "binaries"}

    def test_tilde_mods_preset(self):
        g = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(pak_groups=[g])
        decisions = {"mod.pak": "~mods"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert result == {"content", "binaries"}

    def test_custom_path_adds_first_segment(self):
        g = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(pak_groups=[g])
        decisions = {"mod.pak": "CustomDir/SubDir/Stuff"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert "customdir" in result

    def test_skip_excludes(self):
        g = _make_pak_group("mod.pak", "mod")
        discovery = DiscoveryResult(pak_groups=[g])
        decisions = {"mod.pak": "SKIP"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert result == {"content", "binaries"}

    def test_multiple_groups_mixed(self):
        g1 = _make_pak_group("a.pak", "a")
        g2 = _make_pak_group("b.pak", "b")
        discovery = DiscoveryResult(pak_groups=[g1, g2])
        decisions = {"a.pak": "ROOT", "b.pak": "LogicMods"}
        result = self.installer._compute_allowed_root_names(discovery, decisions)
        assert "a.pak" in result
        assert "content" in result
        assert "binaries" in result
