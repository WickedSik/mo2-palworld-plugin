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
- Platform-aware variant selection: `{STEAM}` / `{XBOX}` marker folders are resolved per the configured `palworld_platform` / `palworld_server_platform` setting, with `{GAMEPASS}` accepted as a deprecated alias of `{XBOX}` (logs a one-line deprecation warning).
- Lua / UE4SS script mods are now claimed in triage and routed to `Binaries/Win64/Mods/<modname>/` (or `Binaries/WinGDK/Mods/<modname>/` when the resolved platform is `xbox`).
- Installer UI created and can be forcibly shown upon archive installation

### Notes
- The `Mods/` destination from earlier design drafts has been dropped
