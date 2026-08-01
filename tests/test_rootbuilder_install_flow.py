"""End-to-end install() coverage for UE4SS C++ DLL plugin archives.

The recognizer tests call route() directly and so never exercise the
root cleanup that runs after it. That pass deletes any top-level folder
it does not recognise, which is exactly what would silently discard
Root Builder's Root/ folder -- and what used to discard a top-level
ue4ss/ fragment entirely.
"""
from __future__ import annotations

import pytest

from tests.mobase_mock import build_tree, FILE, GuessedString, IFileTree


UNARRANGED = {"PalSchema/": {"dlls/": {"main.dll": FILE}, "enabled.txt": FILE}}
TOP_LEVEL = {"ue4ss/": {"Mods/": {"PalSchema/": {"dlls/": {"main.dll": FILE}}}}}
PREARRANGED = {
    "Binaries/": {
        "Win64/": {
            "ue4ss/": {"Mods/": {"PalSchema/": {"dlls/": {"main.dll": FILE}}}},
        },
    },
}

ALL_LAYOUTS = [
    pytest.param(UNARRANGED, id="unarranged"),
    pytest.param(TOP_LEVEL, id="top-level-ue4ss"),
    pytest.param(PREARRANGED, id="prearranged"),
]


def _installed_files(installer, layout):
    """Run a full install and return the surviving file paths."""
    tree = build_tree(layout)
    result = installer.install(GuessedString("PalSchema"), tree, "1.0", 0)
    assert hasattr(result, "walk"), f"install declined: {result}"

    paths: list[str] = []

    def visit(path, entry):
        if entry.isFile():
            paths.append(f"{path}/{entry.name()}" if path else entry.name())
        return IFileTree.WalkReturn.CONTINUE

    result.walk(visit)
    return sorted(paths)


class TestWithoutRootBuilder:
    @pytest.mark.parametrize("layout", ALL_LAYOUTS)
    def test_lands_on_the_normal_ue4ss_path(self, make_installer, layout):
        files = _installed_files(make_installer, layout)
        assert files
        assert all(
            f.startswith("Binaries/Win64/ue4ss/Mods/PalSchema/") for f in files
        ), files

    def test_top_level_fragment_no_longer_installs_nothing(
        self, make_installer
    ):
        """Regression: root cleanup used to strip the whole ue4ss/
        folder, leaving the install with no content at all."""
        assert _installed_files(make_installer, TOP_LEVEL) == [
            "Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll"
        ]

    def test_companion_files_survive(self, make_installer):
        assert _installed_files(make_installer, UNARRANGED) == [
            "Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll",
            "Binaries/Win64/ue4ss/Mods/PalSchema/enabled.txt",
        ]


class TestWithRootBuilder:
    @pytest.mark.parametrize("layout", ALL_LAYOUTS)
    def test_survives_root_cleanup(
        self, make_installer, rootbuilder_enabled, layout
    ):
        files = _installed_files(make_installer, layout)
        assert files
        assert all(
            f.startswith("Root/Pal/Binaries/Win64/ue4ss/Mods/PalSchema/")
            for f in files
        ), files

    def test_companion_files_survive(
        self, make_installer, rootbuilder_enabled
    ):
        base = "Root/Pal/Binaries/Win64/ue4ss/Mods/PalSchema"
        assert _installed_files(make_installer, UNARRANGED) == [
            f"{base}/dlls/main.dll",
            f"{base}/enabled.txt",
        ]

    def test_never_setting_keeps_the_normal_path(
        self, make_installer, rootbuilder_enabled
    ):
        rootbuilder_enabled._settings["PalworldInstaller"][
            "use_rootbuilder"
        ] = "never"
        files = _installed_files(make_installer, UNARRANGED)
        assert all(f.startswith("Binaries/Win64/") for f in files), files

    def test_always_setting_without_rootbuilder_installed(
        self, make_installer, mock_organizer
    ):
        """Routing still happens so the user can install Root Builder
        afterwards -- the installer never refuses the archive."""
        mock_organizer._settings["PalworldInstaller"][
            "use_rootbuilder"
        ] = "always"
        files = _installed_files(make_installer, UNARRANGED)
        assert all(f.startswith("Root/Pal/") for f in files), files
