# PalworldInstaller — Design Spec

This document is the design spec for the `PalworldInstaller` MO2 plugin: the behavior it must implement, the platform-aware features it adds, and the open decisions still to make. It is the authoritative reference for implementation — deviations should be discussed and reflected back into this document.

## 1. Purpose

`PalworldInstaller` is a custom archive installer (`IPluginInstallerSimple`) for Mod Organizer 2. It takes mod archives intended for Palworld and rewrites their internal file tree into Palworld's expected install layout. It also resolves platform-specific archive structures: many Palworld mod archives ship with top-level `{STEAM}`, `{GAMEPASS}`, and `{XBOX}` folders containing platform-specific variants of the same mod, and the installer picks the right variant based on a configurable per-managed-game setting.

This is a clean-room design. Implementation must reproduce the behaviors below from this spec and from direct observation of how Palworld mod archives are structured — not from any prior installer's source code.

## 2. Required Behaviors

### Triage — `isArchiveSupported(tree)`

Decide whether this installer claims a given archive. Order:

1. Bail out unless the managed game is `Palworld` or `Palworld Server`.
2. If the archive contains `fomod/moduleconfig.xml` AND the FOMOD installer is enabled AND `prefer_fomod` is set → return False (let FOMOD handle it).
3. If the archive contains `ue4ss.dll` → return False (UE4SS bootstrapper, not a mod payload).
4. If the archive contains any `.pak` or `main.lua` → return True. Otherwise False.

Perform this in a single `tree.walk()` pass — collect all signals once, then evaluate the rules.

### Tree rewriting — `install(name, tree, ...)`

Collect `.pak`, `.json`, and `main.lua` entries from the archive, present a `UnifiedUI` dialog for per-file destination choices, then relocate entries into Palworld's canonical layout:

| Source pattern | Destination |
|---|---|
| `.../<modname>/Scripts/main.lua` | `Binaries/Win64/Mods/<modname>/` (or `Binaries/WinGDK/Mods/<modname>/` on `xbox`) — full grandparent folder copied |
| `*.pak` (per-file user choice) | `Content/Paks/{ROOT, ~mods, Mods, LogicMods, <custom>}/` |
| `*.json` | `Content/Paks/LogicMods/` |
| Anything else at archive root | Removed (only `Binaries` and `Content` survive at root) |

A `SKIP` status returned by the UI removes the entry entirely.

The `<modname>` for `main.lua` placement is derived from the script's grandparent directory in the archive (i.e. `<modname>/Scripts/main.lua`). If an archive layout does not match that pattern, fall back to the user-chosen mod name from the dialog rather than crashing.

### Install configuration dialog — `UnifiedUI`

A `QDialog` with three sections:

1. **Mod name** — editable combo, suggested variants populated from archive name and any detected mod folder names.
2. **Script mods** — checkbox list of detected `main.lua` entries; each individually install/skip.
3. **Pak files** — list of detected `.pak` files with a per-file location combo (`ROOT` / `~mods` / `Mods` / `LogicMods` / `Custom`) and a custom-path line edit that activates only when `Custom` is selected.

Returns three things to the installer:

- `get_new_mod_name() -> str`
- `get_script_statuses() -> list[str]` — `"INSTALL"` or `"SKIP"`, positionally aligned with the script mod list
- `get_pak_locations() -> dict[str, str]` — `{pak_filename: location_or_custom_path}` where the value is one of `ROOT`, `~mods`, `Mods`, `LogicMods`, `SKIP`, or a custom path string

UI implementation rules:

- Each Qt signal connects to **one** slot. Do not double-write state by connecting the same signal to two slots.
- `get_pak_locations()` must have a single, unambiguous resolution path: read the combo, return the custom path if combo is `Custom` else return the combo value. No fall-through to a default mid-resolution.

## 3. Platform-Aware Folder Handling

### Detection

During `install()`, before any pak/lua/json triage runs, scan the archive's top-level entries for canonical marker folders:

- `{STEAM}`
- `{GAMEPASS}`
- `{XBOX}`

Match is case-insensitive against the canonical braced form. Anything else (e.g. `STEAM` without braces, `[STEAM]`) is **not** treated as a marker — these are the expected names that real archives ship with.

If none of the markers are present, skip platform branching entirely.

### Variant Selection

MO2 supports all three platforms. Xbox installations target Palworld's WinGDK binary layout instead of Win64, but otherwise follow the same selection logic as Steam and Gamepass.

1. Read the configured platform for the current managed game (see §4). Valid values: `steam`, `gamepass`, `xbox`.
2. Remove every non-matching variant folder. For example: configured platform is `steam` → remove `{GAMEPASS}` and `{XBOX}`.
3. Promote the matching folder's contents up to the archive root (move children of `{STEAM}` / `{GAMEPASS}` / `{XBOX}` to root, then remove the empty marker folder).
4. Hand off to the pak/lua/json triage as if the archive had been authored without platform variants.

### Xbox-specific path handling

When the configured platform is `xbox`, script mods (`main.lua`) install to `Binaries/WinGDK/Mods/<modname>/` instead of `Binaries/Win64/Mods/<modname>/`. This is driven by the platform setting alone — it applies whether or not the archive shipped with a `{XBOX}` marker folder. Pak and json destinations under `Content/Paks/...` are unaffected.

### Edge cases

- Archive contains only the non-selected variant (e.g. configured `xbox` but archive has only `{STEAM}`): log a warning and use whatever is available, since stripping it would leave nothing. Suggest the user check their platform setting.
- Archive contains all three markers, or any pair: normal selection logic applies, no warning needed.
- Archive contains marker folders **and** mod content at the root level: prefer marker-folder content, log that root-level content is being ignored.
- If, after variant selection, the tree contains no installable mod content, cancel installation with a log: `Archive contained no usable platform variant — installation canceled.`

## 4. Plugin Settings

### Settings shape

`mobase.PluginSetting` is global to the plugin instance, not per managed game. To get per-game behavior without going outside the standard API, register one setting per supported game and look up the appropriate key at install time:

```python
def settings(self):
    return [
        mobase.PluginSetting("enabled", "check to enable this plugin", True),
        mobase.PluginSetting("prefer_fomod", "prefer FOMOD installer when possible", True),
        mobase.PluginSetting("priority", "priority of this installer", 120),
        mobase.PluginSetting(
            "palworld_platform",
            "platform variant for Palworld (steam | gamepass | xbox)",
            "steam",
        ),
        mobase.PluginSetting(
            "palworld_server_platform",
            "platform variant for Palworld Server (steam | gamepass | xbox)",
            "steam",
        ),
    ]
```

Resolution at install time:

```python
GAME_PLATFORM_KEYS = {
    "Palworld": "palworld_platform",
    "Palworld Server": "palworld_server_platform",
}

game_name = self._organizer.managedGame().gameName()
key = GAME_PLATFORM_KEYS[game_name]
platform = self._organizer.pluginSetting(self.name(), key)
```

### Validation

Accept `"steam"`, `"gamepass"`, and `"xbox"` only (case-insensitive on read, normalized to lowercase). Any other value falls back to `"steam"` and emits a console warning:

```
Unknown platform setting "<value>" for <game>; falling back to "steam".
```

### Defaults

`steam` for both games. Reasoning: Palworld Server is Steam-only in practice, so the `gamepass` and `xbox` values on the server installer are essentially no-ops but kept for symmetry and to avoid special-casing the absence of the setting.

### Priority

`priority` defaults to `120`. Higher priority installers run first. This value is high enough to take precedence over MO2's default installer for Palworld archives, while still letting FOMOD win when `prefer_fomod` is set and the archive is a FOMOD package.

## 5. Out of Scope (v1)

- **FOMOD takeover** — when `prefer_fomod` is set and the archive is a FOMOD package, the FOMOD installer wins. No FOMOD parsing is implemented here.
- **UE4SS handling** beyond the skip in triage. Bootstrappers are not mod payloads and are not installed by this plugin.
- **Per-mod platform override** — the platform setting is global per managed game. A single archive cannot mix platforms.
- **Reinstall pre-fill** of UI choices — see §6, open question 3. Until decided, the UI starts from defaults on every install.

## 6. Open Questions

These should be resolved before the corresponding code paths are written:

1. Should the platform setting also surface in the `UnifiedUI` install dialog (e.g. as a read-only label or a per-install override dropdown)?
2. Should the installer warn when it detects only the *non-selected* variant (e.g. configured `steam` but archive has only `{GAMEPASS}`), or silently fall back to whatever is available?
3. Should reinstall pre-fill UI choices from settings persisted at the previous install? If yes, define the schema (per-mod keys via `setPluginSetting`) and the parse logic. If no, omit the persistence machinery entirely.
4. Should the platform marker matching tolerate leading/trailing whitespace or alternative bracket styles, or strictly the canonical `{STEAM}` / `{GAMEPASS}` / `{XBOX}` forms?
