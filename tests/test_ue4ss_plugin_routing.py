"""AC 5.8 — Ue4ssPluginRecognizer routing integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.ue4ss_plugin import Ue4ssPluginRecognizer


def _build_ctx(tree):
    dll_entries = []

    def visit(path, entry):
        if entry.isFile() and entry.suffix().lower() == "dll":
            dll_entries.append(entry)
        return IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)

    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=tuple(dll_entries),
        pak_entries=(),
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(),
        platform="steam",
        suggested_mod_name="TestMod",
    )


class TestUe4ssPluginRecognizerRoute:
    def setup_method(self):
        self.recognizer = Ue4ssPluginRecognizer()

    def test_route_is_noop(self):
        tree = build_tree({
            "ue4ss/": {"Mods/": {"PalSchema/": {"dlls/": {"main.dll": FILE}}}},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("ue4ss/Mods/PalSchema/dlls/main.dll") is not None

    def test_discover_claims_all_files(self):
        tree = build_tree({
            "ue4ss/": {
                "Mods/": {
                    "PalSchema/": {
                        "dlls/": {"main.dll": FILE},
                        "enabled.txt": FILE,
                    },
                },
            },
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert "ue4ss/Mods/PalSchema/dlls/main.dll" in result.claimed_paths
        assert "ue4ss/Mods/PalSchema/enabled.txt" in result.claimed_paths
