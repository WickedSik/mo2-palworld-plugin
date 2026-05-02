# PalworldInstaller

PalworldInstaller is a Mod Organizer 2 (MO2) plugin that handles Palworld mod installations for you. When you install a mod archive in MO2, the plugin recognizes the Palworld files inside it and places them in the right folders automatically. It works for both Palworld and Palworld Dedicated Server, and it knows the difference between the Steam and Xbox/Game Pass versions of the game.

> **Note:** This readme describes the **finished** plugin. Some features are still being built and may not be available in the current development build yet. This file will be updated as the plugin evolves.

## Features

- **Installs Palworld mods automatically.** Drop a mod archive into MO2 and the plugin sorts the files into the correct locations. No manual moving needed.
- **Knows your platform.** Some mods ship separate versions for Steam and Xbox/Game Pass. The plugin picks the one that matches your game and skips the other.
- **Stays quiet when it can.** If the mod's layout is obvious, the plugin installs it silently. You only see a dialog when there is a real choice to make.
- **Pre-fills choices for you.** When the dialog does appear, the plugin already has a sensible answer for every option. Most of the time you can just click OK.
- **Keeps mod files together.** Some mods include `.pak` files plus companion files (`.utoc`, `.ucas`) or extra folders (`AnimJSON`, `SwapJSON`). The plugin treats them as one package so nothing gets separated.
- **Defers to FOMOD when appropriate.** If a mod uses MO2's standard FOMOD installer, the plugin steps aside and lets MO2 handle it. You can change this in the settings.
- **Skips framework files.** Files like `ue4ss.dll` belong to the UE4SS modding framework, not to any single mod. The plugin ignores them so they don't get installed as if they were a mod.
- **Remembers your previous choices.** If you reinstall a mod, the dialog comes back pre-filled with what you picked last time.
- **Recognizes older folder names.** Some mods still use `{GAMEPASS}` instead of `{XBOX}`. The plugin understands both.

## Requirements & Installation

### What you need

- **Mod Organizer 2**, version **2.5.2 or newer**.
- **Palworld** or **Palworld Dedicated Server**, already set up in MO2.
- **The `basic_games` plugin.** This ships with MO2 by default, so you most likely already have it.

### Step 1: Add Palworld to MO2's game list

Before MO2 knows about Palworld, you need to add two small game-definition files. These are not a separate plugin; they go *inside* MO2's existing `basic_games` plugin.

1. Make sure MO2 is closed.
2. Find your MO2 install folder.
3. Open `plugins/basic_games/games/` inside it.
4. Copy these two files into that folder:
   - `game_palworld.py`
   - `game_palworld_server.py`

### Step 2: Install the PalworldInstaller plugin

Now copy the plugin itself into MO2. Keep MO2 closed for this step too.

1. Find your MO2 install folder.
2. Copy the entire `PalworldInstaller` folder from the download into MO2's `plugins/` folder.

The result should look like:

```
<MO2 install>/plugins/PalworldInstaller/
    __init__.py
    installer.py
    ui/
        __init__.py
        dialog.py
```

### Step 3: Verify and configure

Now start MO2 and check that everything is in place.

**Check the game list.** When you create a new MO2 instance, "Palworld" and "Palworld Dedicated Server" should appear in the list of games.

**Check the plugin is loaded.** Go to **Settings → Plugins**. You should see "PalworldInstaller" in the list, with several settings underneath it.

**Set your platform.** Still in **Settings → Plugins → PalworldInstaller**, set the platform for each game:

- `palworld_platform`: for the regular game. Set to `steam` or `xbox`.
- `palworld_server_platform`: for the Dedicated Server. Set to `steam` or `xbox`.

Pick `steam` if you bought the game on Steam. Pick `xbox` if you have it through Xbox or PC Game Pass (both use the same internal layout). If you only own one of the two, set the one you use and leave the other alone.

### Other settings

You usually don't need to touch these, but here is what they do:

| Setting | What it does |
|---|---|
| `enabled` | Turns the plugin on or off. Default: on. |
| `prefer_fomod` | When a mod ships its own FOMOD installer, let MO2's built-in FOMOD handler take over instead. Default: on. |
| `priority` | Where this plugin sits in MO2's installer queue. Higher means it gets first pick. Default: 120. |
| `palworld_platform` | Steam or Xbox version of Palworld. Default: `steam`. |
| `palworld_server_platform` | Steam or Xbox version of the Dedicated Server. Default: `steam`. |
| `force_dialog` | Always show the install dialog, even when the plugin would normally install silently. Useful for testing. Default: off. |

If you have an older config that uses `gamepass` instead of `xbox`, the plugin treats it as `xbox` and writes a short note to the log. You can leave it alone, but updating to `xbox` is cleaner.

## Troubleshooting

**Why doesn't PalworldInstaller show up in Settings → Plugins?**

The plugin folder probably didn't land in the right place. Check that you copied the entire `PalworldInstaller` folder (with `__init__.py`, `installer.py`, and the `ui/` subfolder inside) into your MO2 `plugins/` folder, then restart MO2.

**Why does MO2 use a different installer when I try to install a Palworld mod?**

Usually one of these is the cause:

- A different game is active in MO2, not Palworld or Palworld Dedicated Server.
- The mod is a FOMOD package and `prefer_fomod` is on. That's intentional; FOMOD takes over for those.
- The archive doesn't contain `.pak` files or `main.lua` scripts, so there is nothing for the plugin to recognize.
- The archive contains `ue4ss.dll`, which the plugin deliberately skips because it's the modding framework rather than a mod.

**Why does the dialog show a warning about Steam or Xbox?**

The mod has files for one platform, but your settings are for the other. The plugin uses whatever is in the archive and shows the warning so you know. If the mod really does have the wrong version for your game, look for the right one on the mod page. Otherwise, double-check that your platform setting matches your installed game.

**Why does the dialog appear for some mods and not others?**

The plugin only asks when there is a real decision to make. Simple mods (one `.pak` file with an obvious destination) install silently. Mods with multiple files going to different places, several scripts, or anything ambiguous get the dialog so you can confirm. Both behaviors are normal.

**Why are some files in the archive not installed?**

The plugin only installs files it recognizes as Palworld mod files: `.pak` (and their `.utoc` / `.ucas` companions, plus `AnimJSON` / `SwapJSON` folders), `main.lua` script mods, and loose `.json` config files. Anything else sitting at the top of the archive (readmes, screenshots, source files) is left out, because it is not part of what the game actually loads.

**The mod installed but the game doesn't see it. What now?**

PalworldInstaller only places files in the right folders. If the mod is installed but the game ignores it, the cause is usually somewhere else: the mod may need UE4SS or another mod loader set up in the game itself, the mod may be disabled or out of order in MO2, or it may simply not be compatible with your game version. Check the mod's own page for setup notes.

**Where can I see what the plugin did during an install?**

Open MO2's log panel (View → Log if it's hidden). The plugin writes a short summary for each install, including any warnings about platforms or deprecated folder names.

## Credits

This plugin is a clean-room implementation inspired by **AbsolutePhoenyx**'s original [MO2 Palworld installer](https://www.nexusmods.com/palworld/mods/769). While no code is shared between the two projects, AbsolutePhoenyx's work demonstrated the value of a Palworld-aware installer for MO2 and informed the behaviors this plugin reproduces. Credit and thanks to AbsolutePhoenyx for paving the way.

## License

This project is licensed under the GNU General Public License v3 (GPL-3.0). See the [LICENSE](LICENSE) file for details.
