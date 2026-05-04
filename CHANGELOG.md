# Changelog

All notable changes to PalworldInstaller will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Installer dialog now wraps the script-mods and pak-groups sections in a scroll region capped at 500 pixels, so archives with many entries no longer push the OK/Cancel buttons off-screen. The platform indicator, mod-name combo, and button row remain pinned outside the scroll area.

## [0.3.2] - 2026-05-02

### Added
- Documented minimum supported Mod Organizer 2 version (2.5.2 or newer) in the README requirements.

### Changed
- Rewrote `README.md` for non-technical mod users with a clearer structure: intro, features, requirements & installation, FAQ-style troubleshooting, credits, and license.
- Reorganized installation steps so MO2 stays closed during file copying (Steps 1 and 2); Step 3 now consolidates launching MO2, verifying both the game list and plugin load, and configuring the platform settings.

## [0.3.1] - 2026-04-29

### Fixed
- Corrected misspelling of `AbsolutePhoenix` to `AbsolutePhoenyx` across all documentation.

## [0.3.0] - 2026-04-29

- Refactored code to make it easier to maintain

## [0.2.0] - 2026-04-26

- Add triage for incomplete or wrong mods
- Add notice of trying to install the wrong platform mods (XBOX on Steam or visa-versa)

## [0.1.0] - 2026-04-26

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
