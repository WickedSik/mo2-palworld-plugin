"""AC 3.1 — Marker detection unit tests."""
from __future__ import annotations

import pytest

from plugins.PalworldInstaller.installer import (
    _extract_marker_platform,
    _normalize_marker_inner,
    PalworldInstaller,
)


class TestNormalizeMarkerInner:
    def test_bare_lowercase(self):
        assert _normalize_marker_inner("steam") == "steam"

    def test_bare_uppercase(self):
        assert _normalize_marker_inner("STEAM") == "steam"

    def test_bare_mixed_case(self):
        assert _normalize_marker_inner("Xbox") == "xbox"

    def test_curly_braces(self):
        assert _normalize_marker_inner("{STEAM}") == "steam"

    def test_square_brackets(self):
        assert _normalize_marker_inner("[Xbox]") == "xbox"

    def test_parens(self):
        assert _normalize_marker_inner("(gamepass)") == "gamepass"

    def test_whitespace_stripped(self):
        assert _normalize_marker_inner("  {STEAM}  ") == "steam"

    def test_mismatched_brackets_not_stripped(self):
        assert _normalize_marker_inner("[steam}") == "[steam}"

    def test_empty_string(self):
        assert _normalize_marker_inner("") == ""

    def test_single_char(self):
        assert _normalize_marker_inner("x") == "x"

    def test_single_bracket_pair_empty_inner(self):
        assert _normalize_marker_inner("{}") == ""


class TestExtractMarkerPlatform:
    @pytest.mark.parametrize("name,expected", [
        ("{STEAM}", "steam"),
        ("{steam}", "steam"),
        ("[Steam]", "steam"),
        ("(STEAM)", "steam"),
        ("steam", "steam"),
        ("STEAM", "steam"),
        ("{XBOX}", "xbox"),
        ("{xbox}", "xbox"),
        ("[Xbox]", "xbox"),
        ("(XBOX)", "xbox"),
        ("xbox", "xbox"),
        ("XBOX", "xbox"),
        ("{GAMEPASS}", "xbox"),
        ("{gamepass}", "xbox"),
        ("[Gamepass]", "xbox"),
        ("(GAMEPASS)", "xbox"),
        ("gamepass", "xbox"),
        ("GAMEPASS", "xbox"),
        ("  {STEAM}  ", "steam"),
        ("{Steam}", "steam"),
    ])
    def test_valid_markers(self, name, expected):
        assert _extract_marker_platform(name) == expected

    @pytest.mark.parametrize("name", [
        "Content",
        "LogicMods",
        "~mods",
        "Scripts",
        "Binaries",
        "fomod",
        "",
        "{}",
        "{unknown}",
        "[ps5]",
        "nintendo",
        "Palworld",
    ])
    def test_non_markers_return_none(self, name):
        assert _extract_marker_platform(name) is None


class TestIsXboxMarker:
    @pytest.mark.parametrize("name,expected", [
        ("{XBOX}", True),
        ("xbox", True),
        ("[Xbox]", True),
        ("(xbox)", True),
        ("{GAMEPASS}", False),
        ("gamepass", False),
        ("[Gamepass]", False),
        ("{STEAM}", False),
        ("steam", False),
    ])
    def test_xbox_vs_gamepass(self, name, expected):
        assert PalworldInstaller._is_xbox_marker(name) == expected
