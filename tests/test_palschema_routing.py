"""AC 5.7 — PalSchemaRecognizer routing integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.palschema import PalSchemaRecognizer


def _build_ctx(tree, platform="steam"):
    deep_folder_names = set()

    def visit(path, entry):
        if entry.isDir():
            deep_folder_names.add(entry.name().lower())
        return IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)

    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=True,
        dll_entries=(),
        pak_entries=(),
        companion_entries=(),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(deep_folder_names),
        platform=platform,
        suggested_mod_name="TestMod",
    )


class TestPalSchemaRecognizerRoute:
    def setup_method(self):
        self.recognizer = PalSchemaRecognizer()

    def test_structured_layout_steam(self):
        tree = build_tree({
            "PalSchema/": {
                "mods/": {
                    "MyMod/": {"schema.json": FILE},
                },
            },
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/MyMod/schema.json"
        ) is not None

    def test_structured_layout_xbox(self):
        tree = build_tree({
            "PalSchema/": {
                "mods/": {
                    "MyMod/": {"schema.json": FILE},
                },
            },
        })
        ctx = _build_ctx(tree, platform="xbox")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/WinGDK/Mods/PalSchema/mods/MyMod/schema.json"
        ) is not None

    def test_flat_layout_derives_modname_from_context(self):
        tree = build_tree({
            "PalSchema/": {
                "config.json": FILE,
                "rules.json": FILE,
            },
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/TestMod/config.json"
        ) is not None
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/TestMod/rules.json"
        ) is not None

    def test_multiple_mod_folders(self):
        tree = build_tree({
            "PalSchema/": {
                "mods/": {
                    "ModA/": {"a.json": FILE},
                    "ModB/": {"b.json": FILE},
                },
            },
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/ModA/a.json"
        ) is not None
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/ModB/b.json"
        ) is not None

    def test_already_correct_layout_is_noop(self):
        tree = build_tree({
            "Binaries/": {
                "Win64/": {
                    "Mods/": {
                        "PalSchema/": {
                            "mods/": {
                                "MyMod/": {"schema.json": FILE},
                            },
                        },
                    },
                },
            },
        })
        ctx = _build_ctx(tree, platform="steam")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/Mods/PalSchema/mods/MyMod/schema.json"
        ) is not None
