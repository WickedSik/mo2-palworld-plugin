"""DllPluginRecognizer detection and routing tests.

Regression coverage for archetype E of the UE4SS-mods failure: the
PalSchema loader (Nexus 2361) ships un-arranged as
``PalSchema/dlls/main.dll`` and was previously claimed by no recognizer
(NOT_ATTEMPTED). This recognizer arranges any root-level
``<name>/dlls/main.dll`` UE4SS C++ plugin into ``ue4ss/Mods/<name>/``.
"""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import RecognitionResult, WalkContext
from plugins.PalworldInstaller.recognizers.dll_plugin import (
    DllPluginRecognizer,
)


def _build_ctx(tree, platform="steam"):
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
        platform=platform,
        suggested_mod_name="TestMod",
    )


def _palschema_tree():
    """The PalSchema loader archive layout (Nexus 2361)."""
    return build_tree({
        "PalSchema/": {
            "dlls/": {"main.dll": FILE},
            "enabled.txt": FILE,
            "mods/": {},
        },
    })


class TestDllPluginRecognizerDetect:
    def setup_method(self):
        self.recognizer = DllPluginRecognizer()

    def test_matches_root_dll_plugin(self):
        tree = _palschema_tree()
        ctx = _build_ctx(tree)
        assert self.recognizer.detect(tree, ctx) == RecognitionResult.MATCH

    def test_ignores_prearranged_ue4ss_layout(self):
        """The already-arranged ue4ss/Mods/<name>/dlls/main.dll layout
        belongs to Ue4ssPluginRecognizer, not this one."""
        tree = build_tree({
            "ue4ss/": {
                "Mods/": {
                    "PalSchema/": {"dlls/": {"main.dll": FILE}},
                },
            },
        })
        ctx = _build_ctx(tree)
        assert self.recognizer.detect(tree, ctx) == RecognitionResult.NO_MATCH

    def test_ignores_bare_lua_archive(self):
        tree = build_tree({"MyMod/": {"Scripts/": {"main.lua": FILE}}})
        ctx = _build_ctx(tree)
        assert self.recognizer.detect(tree, ctx) == RecognitionResult.NO_MATCH

    def test_ignores_loose_dll_not_in_dlls_folder(self):
        """A dll that is not at <name>/dlls/main.dll must not match."""
        tree = build_tree({"MyMod/": {"main.dll": FILE}})
        ctx = _build_ctx(tree)
        assert self.recognizer.detect(tree, ctx) == RecognitionResult.NO_MATCH


class TestDllPluginRecognizerRoute:
    def setup_method(self):
        self.recognizer = DllPluginRecognizer()

    def test_palschema_framework_steam(self):
        tree = _palschema_tree()
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None
        # enabled.txt activation flag preserved...
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/enabled.txt"
        ) is not None
        # ...mods/ scaffold preserved...
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/mods"
        ) is not None
        # ...original root folder relocated (gone from root)...
        assert tree.find("PalSchema") is None
        # ...and NOT on the ue4ss-less path.
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/dlls/main.dll"
        ) is None

    def test_palschema_framework_xbox(self):
        # NOTE: the WinGDK path is not yet verified against a real Game
        # Pass install; this asserts internal consistency only.
        tree = _palschema_tree()
        ctx = _build_ctx(tree, platform="xbox")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/WinGDK/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None

    def test_general_named_plugin(self):
        """Any UE4SS C++ plugin in the <name>/dlls/main.dll layout is
        handled, not just PalSchema."""
        tree = build_tree({
            "SomePlugin/": {
                "dlls/": {"main.dll": FILE},
                "enabled.txt": FILE,
            },
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/SomePlugin/dlls/main.dll"
        ) is not None

    def test_multiple_plugins_each_routed(self):
        tree = build_tree({
            "PluginA/": {"dlls/": {"main.dll": FILE}},
            "PluginB/": {"dlls/": {"main.dll": FILE}},
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PluginA/dlls/main.dll"
        ) is not None
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PluginB/dlls/main.dll"
        ) is not None


class TestDllPluginRecognizerDiscover:
    def setup_method(self):
        self.recognizer = DllPluginRecognizer()

    def test_discover_claims_all_plugin_files(self):
        tree = _palschema_tree()
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert "PalSchema/dlls/main.dll" in result.claimed_paths
        assert "PalSchema/enabled.txt" in result.claimed_paths
        assert result.should_show_dialog is False
