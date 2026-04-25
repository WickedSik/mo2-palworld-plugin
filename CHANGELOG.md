# Changelog

All notable changes to PalworldInstaller will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Palworld and Palworld Server are now recognised as managed games in MO2.
- Initial groundwork for a Palworld-aware mod installer; this release does not yet handle archives, so MO2's default install behaviour is unchanged.
- Triage logic for Palworld mod archives
- Defensive guards: tree mutations are wrapped in error handling that logs and returns `FAILED`

### Notes
- Archives shipping `{STEAM}` / `{GAMEPASS}` / `{XBOX}` marker folders are intentionally not claimed by this release and fall through to MO2's default installer
- Lua / UE4SS script mod handling (e.g. `<modname>/Scripts/main.lua` archives) are not claimed by this release
- The `Mods/` destination from earlier design drafts has been dropped
