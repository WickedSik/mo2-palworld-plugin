from __future__ import annotations

import mobase

from ..models import (
    DiscoveryResult,
    RecognitionResult,
    ScriptMod,
    WalkContext,
    entry_full_path,
)


class LuaScriptRecognizer:
    """Handles archives containing UE4SS Lua script mods
    (``<modname>/Scripts/main.lua``).

    Routes scripts to ``Binaries/Win64/Mods/<modname>/`` (steam) or
    ``Binaries/WinGDK/Mods/<modname>/`` (xbox).
    """

    name = "lua_script"
    priority = 50

    def detect(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> RecognitionResult:
        if ctx.lua_entries:
            return RecognitionResult.MATCH
        return RecognitionResult.NO_MATCH

    def discover(
        self, tree: mobase.IFileTree, ctx: WalkContext
    ) -> DiscoveryResult:
        scripts = self._find_scripts(tree, ctx)

        claimed: set[str] = set()
        for s in scripts:
            if s.mod_dir is not tree:
                claimed.add(entry_full_path(s.mod_dir, tree))
            else:
                claimed.add(entry_full_path(s.main_lua, tree))

        should_show = any(s.ambiguous for s in scripts)

        return DiscoveryResult(
            scripts=scripts,
            claimed_paths=claimed,
            should_show_dialog=should_show,
        )

    def route(
        self,
        tree: mobase.IFileTree,
        ctx: WalkContext,
        decisions: dict[str, str],
    ) -> None:
        scripts = self._find_scripts(tree, ctx)
        mod_name = decisions.get("__mod_name__", ctx.suggested_mod_name)

        base = (
            "Binaries/WinGDK/Mods" if ctx.platform == "xbox"
            else "Binaries/Win64/Mods"
        )

        for i, script in enumerate(scripts):
            status = decisions.get(f"script_{i}", "INSTALL")

            if status == "SKIP":
                if script.mod_dir is tree:
                    tree.remove(script.main_lua)
                else:
                    tree.remove(script.mod_dir)
                continue

            if (
                script.mod_dir is tree
                or script.derived_name in ("(root)", "Scripts")
            ):
                target_modname = mod_name
            else:
                target_modname = script.derived_name

            scripts_parent = script.main_lua.parent()
            has_real_scripts_parent = (
                scripts_parent is not None
                and scripts_parent is not tree
                and scripts_parent.name().lower() == "scripts"
            )

            if (
                has_real_scripts_parent
                and script.mod_dir is not tree
                and scripts_parent is not script.mod_dir
            ):
                tree.move(
                    script.mod_dir,
                    f"{base}/{target_modname}",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )
            elif (
                has_real_scripts_parent
                and scripts_parent is script.mod_dir
            ):
                tree.move(
                    script.mod_dir,
                    f"{base}/{target_modname}/Scripts",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )
            else:
                target_scripts = tree.addDirectory(
                    f"{base}/{target_modname}/Scripts"
                )
                tree.move(
                    script.main_lua,
                    f"{target_scripts.path('/')}/main.lua",
                    policy=mobase.IFileTree.InsertPolicy.REPLACE,
                )

    # --- internal ------------------------------------------------------------

    @staticmethod
    def _find_scripts(
        tree: mobase.IFileTree, ctx: WalkContext
    ) -> list[ScriptMod]:
        found: dict[int, ScriptMod] = {}

        for entry in ctx.lua_entries:
            scripts_dir = entry.parent()
            if scripts_dir is None or scripts_dir is tree:
                sm = ScriptMod(
                    main_lua=entry,
                    mod_dir=tree if scripts_dir is None else scripts_dir,
                    derived_name="(root)",
                    main_lua_display=entry_full_path(entry, tree),
                    ambiguous=True,
                )
            elif scripts_dir.name().lower() != "scripts":
                sm = ScriptMod(
                    main_lua=entry,
                    mod_dir=scripts_dir,
                    derived_name=scripts_dir.name(),
                    main_lua_display=entry_full_path(entry, tree),
                    ambiguous=True,
                )
            else:
                parent_of_scripts = scripts_dir.parent()
                if parent_of_scripts is None or parent_of_scripts is tree:
                    sm = ScriptMod(
                        main_lua=entry,
                        mod_dir=scripts_dir,
                        derived_name="Scripts",
                        main_lua_display=entry_full_path(entry, tree),
                        ambiguous=True,
                    )
                else:
                    ambiguous = parent_of_scripts.parent() is not tree
                    sm = ScriptMod(
                        main_lua=entry,
                        mod_dir=parent_of_scripts,
                        derived_name=parent_of_scripts.name(),
                        main_lua_display=entry_full_path(entry, tree),
                        ambiguous=ambiguous,
                    )

            key = id(sm.mod_dir)
            if key not in found:
                found[key] = sm

        counts: dict[str, int] = {}
        for sm in found.values():
            counts[sm.derived_name] = counts.get(sm.derived_name, 0) + 1
        for sm in found.values():
            if counts[sm.derived_name] > 1:
                sm.ambiguous = True

        return list(found.values())
