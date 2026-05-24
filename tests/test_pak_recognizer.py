"""AC 5.4 — PakRecognizer discover() and route() integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.pak import PakRecognizer


def _build_ctx(tree, platform="steam"):
    """Build a WalkContext by simulating the walk the installer does."""
    pak_entries = []
    companion_entries = []
    json_entries = []
    json_dirs = []
    folder_names = set()
    deep_folder_names = set()

    def visit(path, entry):
        from tests.mobase_mock import IFileTree
        parent = entry.parent()
        at_root = parent is None or parent is tree

        if entry.isDir():
            deep_folder_names.add(entry.name().lower())
            if at_root:
                folder_names.add(entry.name().lower())
                if entry.name().lower() in ("animjson", "swapjson"):
                    json_dirs.append(entry)
            return IFileTree.WalkReturn.CONTINUE

        if entry.isFile():
            s = entry.suffix().lower()
            if s == "pak":
                pak_entries.append(entry)
            elif s in ("utoc", "ucas"):
                companion_entries.append(entry)
            elif s == "json" and at_root:
                json_entries.append(entry)
        return IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)

    return WalkContext(
        has_fomod=False,
        has_ue4ss_dll=False,
        has_json_deep=False,
        dll_entries=(),
        pak_entries=tuple(pak_entries),
        companion_entries=tuple(companion_entries),
        lua_entries=(),
        json_entries=tuple(json_entries),
        json_dirs=tuple(json_dirs),
        folder_names=frozenset(folder_names),
        deep_folder_names=frozenset(deep_folder_names),
        platform=platform,
        suggested_mod_name="TestMod",
    )


class TestPakRecognizerDiscover:
    def setup_method(self):
        self.recognizer = PakRecognizer()

    def test_single_pak_one_group(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.pak_groups) == 1
        assert result.pak_groups[0].stem == "mod"
        assert result.pak_groups[0].group_id == "mod.pak"

    def test_pak_with_companions_bundled(self):
        tree = build_tree({
            "mod.pak": FILE,
            "mod.utoc": FILE,
            "mod.ucas": FILE,
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.pak_groups) == 1
        assert len(result.pak_groups[0].companions) == 2

    def test_multiple_paks_multiple_groups(self):
        tree = build_tree({
            "alpha.pak": FILE,
            "beta.pak": FILE,
            "gamma.pak": FILE,
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.pak_groups) == 3
        assert result.should_show_dialog is True

    def test_p_suffix_routes_to_tilde_mods(self):
        tree = build_tree({"mod_P.pak": FILE})
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert result.default_routing["mod_P.pak"] == "~mods"

    def test_no_p_suffix_routes_to_logicmods(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert result.default_routing["mod.pak"] == "LogicMods"

    def test_prearranged_logicmods_preserves_location(self):
        tree = build_tree({
            "Content/": {"Paks/": {"LogicMods/": {"mod.pak": FILE}}},
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.pak_groups) == 1
        assert result.default_routing[result.pak_groups[0].group_id] == "LogicMods"

    def test_json_dirs_associated_with_root_paks(self):
        tree = build_tree({
            "mod_P.pak": FILE,
            "AnimJSON/": {"config.json": FILE},
        })
        ctx = _build_ctx(tree)
        result = self.recognizer.discover(tree, ctx)
        assert len(result.pak_groups[0].json_dirs) == 1


class TestPakRecognizerRoute:
    def setup_method(self):
        self.recognizer = PakRecognizer()

    def test_route_to_logicmods(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _build_ctx(tree)
        decisions = {"mod.pak": "LogicMods"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("Content/Paks/LogicMods/mod.pak") is not None

    def test_route_to_tilde_mods_with_companions(self):
        tree = build_tree({
            "mod.pak": FILE,
            "mod.utoc": FILE,
            "mod.ucas": FILE,
        })
        ctx = _build_ctx(tree)
        decisions = {"mod.pak": "~mods"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("Content/Paks/~mods/mod.pak") is not None
        assert tree.find("Content/Paks/~mods/mod.utoc") is not None
        assert tree.find("Content/Paks/~mods/mod.ucas") is not None

    def test_route_to_root(self):
        tree = build_tree({"Content/": {"Paks/": {"LogicMods/": {"mod.pak": FILE}}}})
        ctx = _build_ctx(tree)
        group_id = list(self.recognizer.discover(tree, ctx).default_routing.keys())[0]
        decisions = {group_id: "ROOT"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("mod.pak") is not None

    def test_route_skip_removes(self):
        tree = build_tree({"mod.pak": FILE, "mod.utoc": FILE})
        ctx = _build_ctx(tree)
        decisions = {"mod.pak": "SKIP"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("mod.pak") is None
        assert tree.find("mod.utoc") is None

    def test_route_custom_path(self):
        tree = build_tree({"mod.pak": FILE})
        ctx = _build_ctx(tree)
        decisions = {"mod.pak": "MyMods/Special"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("MyMods/Special/mod.pak") is not None

    def test_json_dirs_routed_to_tilde_mods(self):
        tree = build_tree({
            "mod_P.pak": FILE,
            "AnimJSON/": {"swap.json": FILE},
        })
        ctx = _build_ctx(tree)
        decisions = {"mod_P.pak": "~mods"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("Content/Paks/~mods/AnimJSON/swap.json") is not None

    def test_loose_root_json_to_logicmods(self):
        tree = build_tree({
            "mod.pak": FILE,
            "config.json": FILE,
        })
        ctx = _build_ctx(tree)
        decisions = {"mod.pak": "LogicMods"}
        self.recognizer.route(tree, ctx, decisions)
        assert tree.find("Content/Paks/LogicMods/config.json") is not None
