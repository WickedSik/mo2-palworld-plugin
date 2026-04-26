# PalworldInstaller

A Mod Organizer 2 plugin suite for seamless modding of **Palworld** and **Palworld Dedicated Server**. Automatically detects and rewrites mod archives into the correct in-game directory structure, with full support for platform-aware mod variants.

> ⚠️ This readme shows the **finished** version of the plan, not the current progress. It will be updated as the plan updates, changes and improves.
> What is inside the readme is **partially** available in the current development build.

## Features

- **Automatic archive triage** — Claims and installs `.pak`, `main.lua`, and `.json` mod files.
- **Platform-aware variant selection** — Handles `{STEAM}` and `{XBOX}` marker folders in archives, installing the right variant for your platform.
- **Palworld canonical layout** — Rewrites mod archives into Palworld's expected directory structure.
- **Interactive install dialog** — Choose mod names, select which script mods to install, and specify `.pak` destination folders.
- **FOMOD deference** — Automatically defers to MO2's FOMOD installer when an archive is a FOMOD package (configurable).
- **UE4SS bootstrap skip** — Ignores UE4SS bootstrapper files, which are not mod payloads.
- **Reinstall continuity** — Pre-fills dialog choices from previous installs (per-mod settings).
- **Legacy support** — Recognizes deprecated `{GAMEPASS}` marker folders with clear deprecation warnings.

## Requirements

- **Mod Organizer 2** — Recent version with PyQt6 and the `mobase` Python binding (current stable).
- **Palworld** or **Palworld Dedicated Server** — Already managed by MO2.
- **MO2's `basic_games` plugin** — Ships with MO2 by default; required for game definitions.

## Installation

### Step 1 — Install game definitions

Copy the Palworld game definitions into MO2's `basic_games` plugin folder:

```
plugins/basic_games/games/game_palworld.py
plugins/basic_games/games/game_palworld_server.py
```

These files belong **inside** the existing `basic_games` plugin, not as a standalone plugin.

**To install:**

1. Locate your MO2 installation directory.
2. Navigate to `<MO2 install>/plugins/basic_games/games/`.
3. Copy `game_palworld.py` and `game_palworld_server.py` into this folder.
4. Restart MO2.

**Verify:** When creating a new MO2 instance, "Palworld" and "Palworld Dedicated Server" should appear in the game list.

### Step 2 — Install the PalworldInstaller plugin

Copy the entire `PalworldInstaller` folder into MO2's plugins directory:

```
plugins/PalworldInstaller/
├── __init__.py
└── installer.py
```

**To install:**

1. Locate your MO2 installation directory.
2. Copy the entire `plugins/PalworldInstaller/` folder to `<MO2 install>/plugins/`.
3. The result should be `<MO2 install>/plugins/PalworldInstaller/__init__.py` and `installer.py`.
4. Restart MO2.

**Verify:** In MO2, go to Settings → Plugins. You should see "PalworldInstaller" listed with five settings:

- `enabled` (checkbox)
- `prefer_fomod` (checkbox)
- `priority` (number)
- `palworld_platform` (dropdown)
- `palworld_server_platform` (dropdown)

### Step 3 — Configure platform settings

In MO2, go to Settings → Plugins → PalworldInstaller and set the platform for each game:

- **`palworld_platform`** — Platform variant for the Palworld client game. Accepts `steam` (default) or `xbox`.
- **`palworld_server_platform`** — Platform variant for Palworld Dedicated Server. Accepts `steam` (default) or `xbox`.

Choose the platform that matches your Palworld installation:

- **Steam** — Standard Steam version of the game.
- **Xbox** — Xbox console version or PC Game Pass version (both use the WinGDK runtime).

If you only manage one game, configure the relevant setting and leave the other at its default.

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | Boolean | `True` | Enable or disable the installer. |
| `prefer_fomod` | Boolean | `True` | Defer to MO2's FOMOD installer when an archive contains `fomod/moduleconfig.xml`. |
| `priority` | Integer | `120` | Installer priority. Higher values run first. This default ensures PalworldInstaller wins for Palworld archives but allows FOMOD to take precedence when enabled. |
| `palworld_platform` | String | `steam` | Platform variant for Palworld (client): `steam` or `xbox`. |
| `palworld_server_platform` | String | `steam` | Platform variant for Palworld Dedicated Server: `steam` or `xbox`. |

### Legacy platform values

The `gamepass` value is recognized as a deprecated alias of `xbox`. If you have `gamepass` configured, the plugin normalizes it to `xbox` and logs a one-line warning:

```
palworld_platform value "gamepass" is deprecated; treating as "xbox" (Game Pass and Xbox share the WinGDK runtime).
```

This compatibility layer exists for archives and settings from older installations. When updating, migrate to `xbox` for clarity.

## Usage

When you install a mod archive for Palworld or Palworld Dedicated Server, the plugin claims it and opens an interactive dialog.

### Install dialog

The dialog has three sections:

1. **Mod name** — An editable combo box with suggestions drawn from the archive name and detected mod folder names. This name is used for script mods placed in `Binaries/Win64/Mods/<modname>/` (or `Binaries/WinGDK/Mods/<modname>/` for Xbox).

2. **Script mods** — A checkbox list of detected `main.lua` script files. Tick the checkbox for each script you want to install; uncheck to skip.

3. **Pak files** — A list of `.pak` files with a destination chooser for each:
   - **ROOT** — `Content/Paks/ROOT/`
   - **~mods** — `Content/Paks/~mods/`
   - **Mods** — `Content/Paks/Mods/`
   - **LogicMods** — `Content/Paks/LogicMods/`
   - **Custom** — A custom path (enter in the text field below the combo)
   - **SKIP** — Do not install this `.pak` file

Choose the destination appropriate to the mod. Select **Custom** to type a custom path; it becomes active only when the combo is set to **Custom**.

### Archive layout support

The plugin claims archives containing:

- `.pak` files — Unreal Engine mod packages.
- `main.lua` — Lua script mods (expected in a `<modname>/Scripts/main.lua` structure).
- `.json` — Configuration files (installed to `Content/Paks/LogicMods/`).

Archives that also contain platform markers (`{STEAM}`, `{XBOX}`, or the legacy `{GAMEPASS}`) have the non-selected variant removed and the selected one promoted to the root, transparent to the dialog.

Archives containing `ue4ss.dll` are skipped (this is a UE4SS bootstrapper, not a mod payload).

### Where files end up

| File type | Destination |
|-----------|-------------|
| `*.pak` | `Content/Paks/{chosen_destination}/` |
| `<modname>/Scripts/main.lua` | `Binaries/Win64/Mods/<modname>/` (or `Binaries/WinGDK/Mods/<modname>/` if Xbox platform) |
| `*.json` | `Content/Paks/LogicMods/` |
| Anything else at archive root | Removed |

## Troubleshooting

### Plugin does not appear in Settings → Plugins

**Issue:** PalworldInstaller is not listed in the plugins list.

**Solution:** Check that you copied the entire `plugins/PalworldInstaller/` folder (including both `__init__.py` and `installer.py`) into `<MO2 install>/plugins/`, then restart MO2.

### Archive is not claimed by PalworldInstaller

**Issue:** Clicking "Install" on a Palworld mod shows MO2's default installer instead of PalworldInstaller.

**Possible causes:**
- The managed game is not Palworld or Palworld Dedicated Server. Ensure you have the correct game instance selected.
- The archive does not contain `.pak` files or `main.lua` script mods. Some mods may use a different structure.
- The archive contains `ue4ss.dll`, which is skipped by design (it is a bootstrapper, not a mod payload).
- The archive is a FOMOD package **and** `prefer_fomod` is enabled. FOMOD takes precedence.

**Solution:** Verify the archive structure and your MO2 game instance. If the plugin still doesn't claim it, check the MO2 console for logs.

### Dialog shows warnings about platform variants

**Issue:** A message appears about a mismatched platform variant (e.g., "Archive contains only {STEAM} but {XBOX} is configured").

**Solution:** Check your platform setting in Settings → Plugins → PalworldInstaller. If the warning is correct (you need the other platform), the plugin uses what is available and logs the discrepancy. For future installs, either update your platform setting or find an archive with the correct variant.

## Credits

This plugin is a clean-room implementation inspired by **AbsolutePhoenix**'s original [MO2 Palworld installer](https://www.nexusmods.com/palworld/mods/769). While no code is shared between the two projects, AbsolutePhoenix's work demonstrated the value of a Palworld-aware installer for MO2 and informed the behaviors this plugin reproduces. Credit and thanks to AbsolutePhoenix for paving the way.

## License

This project is licensed under the GNU General Public License v3 (GPL-3.0). See the [LICENSE](LICENSE) file for details.

---

For more information about Mod Organizer 2, visit the [Mod Organizer 2 GitHub repository](https://github.com/ModOrganizer2/modorganizer) or the [MO2 Documentation](https://modorganizer.github.io/).
