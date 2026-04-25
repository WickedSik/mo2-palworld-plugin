# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a **Mod Organizer 2 (MO2) plugin suite for Palworld** — the user's own Palworld mod installer, written from scratch as a **clean-room implementation** inspired by AbsolutePhoenix's original Palworld installer. No code is copied from the original; the design is captured independently in `docs/rebuild.md` and is implemented from that spec, including platform-aware behavior (`{STEAM}` / `{GAMEPASS}` / `{XBOX}` variant handling) layered on top of the standard Palworld mod-archive layout rewrite.

There is no build system, test suite, or package manifest — these are loose Python files that MO2 loads at runtime by copying them into its `plugins/` directory.

The codebase targets:
- **Runtime**: MO2's embedded Python (PyQt6 + the `mobase` C++ binding module — only importable inside MO2)
- **Platform**: Windows (MO2 itself), even though development happens on macOS in this checkout
- **Game**: Palworld (Steam ID 1623730) and Palworld Dedicated Server (Steam ID 2394010)

`mobase` cannot be imported outside MO2, so static analysis and direct execution of these files will fail with `ModuleNotFoundError`. Treat type hints and the `mobase` API as authoritative without trying to run the code locally.

## Reference Documentation

**Primary MO2 plugin reference: [docs/mod-organizer.md](docs/mod-organizer.md)** — read this before introducing or modifying anything that touches the `mobase` API, the plugin lifecycle, or PyQt dialog patterns. It is the authoritative reference compiled for this project and covers:

- How MO2 loads Python plugins (`createPlugin` / `createPlugins`, single-file vs. module layout)
- Every `IPlugin*` subclass surface (`IPluginInstallerSimple`, `IPluginInstallerCustom`, `IPluginGame` / `BasicGame`, `IPluginTool`, `IPluginPreview`, `IPluginDiagnose`, `IPluginModPage`, `IPluginFileMapper`, free `IPlugin`)
- `IOrganizer`, `IModList` / `IModInterface`, `IFileTree` / `FileTreeEntry` API surface and traversal semantics
- Game features (`ModDataChecker`, `SaveGameInfo`, …)
- Settings and per-mod persistent storage, `VersionInfo`, internationalization, PyQt6 vs PyQt5 differences
- Hot reload, debugging, logging, and `boost::python` gotchas
- Worked examples for both `IPluginInstallerSimple` and a `BasicGame` for Palworld

When in doubt about a `mobase` method's signature, behavior, or which MO2 version introduced it — consult that document first rather than guessing or relying on training data.

## Current Repository State

What actually exists in this checkout, as of writing:

```
plugins/basic_games/games/game_palworld.py
plugins/basic_games/games/game_palworld_server.py
docs/mod-organizer.md
```

## Plugin Components

The repo will, when complete, host two independent MO2 plugin types under `plugins/`:

### 1. `plugins/basic_games/games/` — Game support definitions (present)

Subclasses of `BasicGame` (from MO2's `basic_games` plugin) that register Palworld and Palworld Server. They declare Steam ID, binary, save extension, save directory, and override `listSaves()` to walk the user-id/game-save-id directory layout. **These files belong inside the user's `<MO2>/plugins/basic_games/games/` folder, not as a standalone plugin** — the relative imports (`..basic_features`, `..basic_game`) make that explicit.

Quirks worth knowing before editing:

- Both classes are named `PalworldGame` (different modules, so no collision when MO2 imports them).
- Server uses `%GAME_PATH%` (an MO2-resolved path token) for documents/saves; client uses `%localappdata%`. They are not interchangeable.
- `listSaves` diverges between the two: the client walks `GameSavesDirectory` directly via `os.path.expandvars`; the server walks the `folder: QDir` argument MO2 passes in. Both look for `level.sav` under a `<user>/<save_id>/` layout.

### 2. `plugins/PalworldInstaller/` — Custom archive installer (to be written)

Per the design spec at `docs/rebuild.md`, this will be an `IPluginInstallerSimple` that intercepts mod archives during installation and rewrites their file tree into Palworld's expected layout. Key shape (the spec is authoritative; the bullets below are a quick summary):

- **Settings**: `enabled`, `prefer_fomod`, `priority` (default 120), plus per-game `palworld_platform` / `palworld_server_platform` (`steam` | `gamepass` | `xbox`, default `steam`).
- **Triage**: bail out unless managed game is Palworld or Palworld Server; defer to FOMOD when `prefer_fomod` is set and `fomod/moduleconfig.xml` is present; skip archives shipping `ue4ss.dll`; otherwise claim archives containing `.pak` or `main.lua`. Do this in **one** `tree.walk()` pass.
- **Platform variant selection**: if the archive root contains `{STEAM}` / `{GAMEPASS}` / `{XBOX}` marker folders, keep the configured platform's contents and promote them to root, dropping the others. Detailed edge cases live in `docs/rebuild.md §3`.
- **Layout rewrite**: `.pak` to `Content/Paks/{ROOT|~mods|Mods|LogicMods|<custom>}/` (per-file user choice); `main.lua` to `Binaries/Win64/Mods/<modname>/` (or `Binaries/WinGDK/Mods/<modname>/` when platform is `xbox`); `.json` to `Content/Paks/LogicMods/`; everything else at archive root removed.
- **UI**: a `QDialog` with editable mod-name combo, a checkbox list of script mods, and a list of pak files with location combo + custom-path line edit.

`docs/rebuild.md §6` lists open questions (e.g., whether reinstall should pre-fill UI choices from previously persisted settings, and what schema to use if so). These should be resolved with the user before implementing the relevant code paths, not decided unilaterally.

## Working in this codebase

- **No commands to run**: there is no build, lint, or test runner. Validation happens by copying files into a real MO2 install on Windows and exercising the installer with sample archives.
- **Editing scope so far**: the only code in the repo lives under `plugins/basic_games/games/`. Any installer work will create new files under `plugins/PalworldInstaller/`; before doing so, confirm the design with the user against `docs/rebuild.md`.
- **Safe to ignore**: `__pycache__/`, `.vs/`, `.DS_Store`. None of these are checked in.
- **mobase API surface anticipated**: `IPluginInstallerSimple`, `IFileTree` (`walk`, `find`, `addDirectory`, `insert`, `remove`, `InsertPolicy.REPLACE`), `ModDataChecker`, `GuessedString.variants/update`, `InstallResult`, `PluginSetting`, `VersionInfo`, plus the `BasicGame` / `SaveGameInfo` surfaces already used in the game definitions. Don't introduce APIs without checking they exist in the MO2 version being targeted (consult `docs/mod-organizer.md`).
- **Clean-room discipline**: this implementation is *inspired by* AbsolutePhoenix's original installer, not derived from it. Do not paste, port, or reformat code from the original. Reproduce behavior from the spec at `docs/rebuild.md` and from direct observation of how Palworld mod archives are structured — never from the original source.
