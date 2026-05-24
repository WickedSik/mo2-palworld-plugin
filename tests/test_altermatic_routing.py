"""AC 5.6 — AltermaticRecognizer routing integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.altermatic import AltermaticRecognizer


def _build_ctx(tree, platform="steam"):
    pak_entries = []
    companion_entries = []
    deep_folder_names = set()

    def visit(path, entry):
        if entry.isDir():
            deep_folder_names.add(entry.name().lower())
        elif entry.isFile():
            s = entry.suffix().lower()
            if s == "pak":
                pak_entries.append(entry)
            elif s in ("utoc", "ucas"):
                companion_entries.append(entry)
        return IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)

    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=True,
        dll_entries=(),
        pak_entries=tuple(pak_entries),
        companion_entries=tuple(companion_entries),
        lua_entries=(),
        json_entries=(),
        json_dirs=(),
        folder_names=frozenset(),
        deep_folder_names=frozenset(deep_folder_names),
        platform=platform,
        suggested_mod_name="TestMod",
    )


class TestAltermaticRecognizerRoute:
    def setup_method(self):
        self.recognizer = AltermaticRecognizer()

    def test_pak_without_p_suffix_to_logicmods(self):
        tree = build_tree({
            "Altermatic.pak": FILE,
            "AnimJSON/": {"config.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/LogicMods/Altermatic.pak") is not None

    def test_pak_with_p_suffix_to_tilde_mods(self):
        tree = build_tree({
            "SomeMod_P.pak": FILE,
            "SwapJSON/": {"swap.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/~mods/SomeMod_P.pak") is not None

    def test_animjson_dir_routed(self):
        tree = build_tree({
            "Altermatic.pak": FILE,
            "AnimJSON/": {"config.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/~mods/AnimJSON/config.json") is not None

    def test_swapjson_dir_routed(self):
        tree = build_tree({
            "Altermatic.pak": FILE,
            "SwapJSON/": {"_LoadList.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/~mods/SwapJSON/_LoadList.json") is not None

    def test_companions_follow_pak(self):
        tree = build_tree({
            "Mod.pak": FILE,
            "Mod.utoc": FILE,
            "Mod.ucas": FILE,
            "AnimJSON/": {"data.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/LogicMods/Mod.pak") is not None
        assert tree.find("Content/Paks/LogicMods/Mod.utoc") is not None
        assert tree.find("Content/Paks/LogicMods/Mod.ucas") is not None

    def test_mixed_pak_types(self):
        tree = build_tree({
            "Logic.pak": FILE,
            "Texture_P.pak": FILE,
            "SwapJSON/": {"swap.json": FILE},
        })
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find("Content/Paks/LogicMods/Logic.pak") is not None
        assert tree.find("Content/Paks/~mods/Texture_P.pak") is not None
