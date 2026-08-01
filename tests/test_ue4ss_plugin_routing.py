"""AC 5.8 — Ue4ssPluginRecognizer routing integration tests."""
from __future__ import annotations

from tests.mobase_mock import build_tree, FILE, IFileTree
from plugins.PalworldInstaller.models import WalkContext
from plugins.PalworldInstaller.recognizers.ue4ss_plugin import Ue4ssPluginRecognizer


def _build_ctx(tree, platform="steam", use_rootbuilder=False):
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
        use_rootbuilder=use_rootbuilder,
    )


def _prearranged_tree(runtime="Win64"):
    """A plugin already sitting where UE4SS expects it."""
    return build_tree({
        "Binaries/": {
            runtime + "/": {
                "ue4ss/": {
                    "Mods/": {
                        "PalSchema/": {
                            "dlls/": {"main.dll": FILE},
                            "enabled.txt": FILE,
                        },
                    },
                },
            },
        },
    })


def _root_arranged_tree(lower=False):
    """The Root Builder layout, as some authors ship it themselves."""
    names = ["Root", "Pal", "Binaries", "Win64", "ue4ss", "Mods"]
    if lower:
        names = [n.lower() for n in names]
    node = {"PalSchema/": {"dlls/": {"main.dll": FILE}}}
    for name in reversed(names):
        node = {f"{name}/": node}
    return build_tree(node)


class TestUe4ssPluginRecognizerRoute:
    def setup_method(self):
        self.recognizer = Ue4ssPluginRecognizer()

    def test_prearranged_layout_is_left_alone(self):
        tree = _prearranged_tree()
        ctx = _build_ctx(tree)
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/enabled.txt"
        ) is not None
        assert [e.name() for e in tree] == ["Binaries"]

    def test_top_level_fragment_is_moved_into_place(self):
        """Regression: a bare ue4ss/Mods/<name>/ at the tree root used
        to be accepted as-is, then stripped by the installer's root
        cleanup -- the mod installed nothing at all."""
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
        self.recognizer.route(tree, ctx, {})
        base = "Binaries/Win64/ue4ss/Mods/PalSchema"
        assert tree.find(f"{base}/dlls/main.dll") is not None
        assert tree.find(f"{base}/enabled.txt") is not None
        # The emptied source chain is pruned, so no stray ue4ss/ is left
        # at the root for the cleanup pass to trip over.
        assert [e.name() for e in tree] == ["Binaries"]

    def test_xbox_runtime(self):
        # NOTE: the WinGDK path is not yet checked against a real Game
        # Pass install. This only checks internal consistency.
        tree = build_tree({
            "ue4ss/": {"Mods/": {"PalSchema/": {"dlls/": {"main.dll": FILE}}}},
        })
        ctx = _build_ctx(tree, platform="xbox")
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/WinGDK/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None

    def test_root_arranged_archive_is_normalised_when_rootbuilder_is_off(self):
        """Without Root Builder a Root/ folder deploys nowhere, so the
        payload is pulled back onto the normal path."""
        tree = _root_arranged_tree()
        ctx = _build_ctx(tree, use_rootbuilder=False)
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None
        assert [e.name() for e in tree] == ["Binaries"]


class TestUe4ssPluginRootBuilderRoute:
    """With Root Builder active the payload goes under Root/Pal/ so it
    is deployed to disk instead of mapped through the virtual
    filesystem."""

    def setup_method(self):
        self.recognizer = Ue4ssPluginRecognizer()

    def test_prearranged_layout_moves_under_root(self):
        tree = _prearranged_tree()
        ctx = _build_ctx(tree, use_rootbuilder=True)
        self.recognizer.route(tree, ctx, {})
        base = "Root/Pal/Binaries/Win64/ue4ss/Mods/PalSchema"
        assert tree.find(f"{base}/dlls/main.dll") is not None
        assert tree.find(f"{base}/enabled.txt") is not None
        # The old Binaries/ chain is pruned -- Binaries survives root
        # cleanup, so leaving it would ship an empty skeleton.
        assert [e.name() for e in tree] == ["Root"]

    def test_xbox_runtime(self):
        tree = _prearranged_tree()
        ctx = _build_ctx(tree, platform="xbox", use_rootbuilder=True)
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Root/Pal/Binaries/WinGDK/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None

    def test_already_root_arranged_is_left_alone(self):
        tree = _root_arranged_tree()
        ctx = _build_ctx(tree, use_rootbuilder=True)
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "Root/Pal/Binaries/Win64/ue4ss/Mods/PalSchema/dlls/main.dll"
        ) is not None
        assert [e.name() for e in tree] == ["Root"]

    def test_lowercase_root_arrangement_is_left_alone(self):
        """Archive casing varies. A case-only difference must not
        trigger a self-move."""
        tree = _root_arranged_tree(lower=True)
        ctx = _build_ctx(tree, use_rootbuilder=True)
        self.recognizer.route(tree, ctx, {})
        assert tree.find(
            "root/pal/binaries/win64/ue4ss/mods/PalSchema/dlls/main.dll"
        ) is not None
        assert [e.name() for e in tree] == ["root"]


class TestUe4ssPluginRecognizerDiscover:
    def setup_method(self):
        self.recognizer = Ue4ssPluginRecognizer()

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
        assert result.should_show_dialog is False

    def test_no_extra_root_names_without_rootbuilder(self):
        tree = _prearranged_tree()
        result = self.recognizer.discover(tree, _build_ctx(tree))
        assert result.extra_root_names == set()

    def test_claims_root_when_rootbuilder_active(self):
        """discover() and route() read the same ctx flag, so the folder
        the cleanup pass keeps always matches the one route() creates."""
        tree = _prearranged_tree()
        ctx = _build_ctx(tree, use_rootbuilder=True)
        result = self.recognizer.discover(tree, ctx)
        assert result.extra_root_names == {"root"}
