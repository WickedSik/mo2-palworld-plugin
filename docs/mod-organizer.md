# Mod Organizer 2 Python Plugin Reference

A complete reference for building Python plugins for Mod Organizer 2 (MO2). Covers
both general plugin types and the installer family. Targets MO2 2.4+ which ships
with PyQt6 bindings; older 2.3.x releases use PyQt5.

> Sources of truth used to compile this document are listed at the bottom. Where
> the API has changed between versions, the modern (PyQt6, MO2 2.4+) form is shown
> first.

---

## Table of contents

1. [How MO2 loads Python plugins](#1-how-mo2-loads-python-plugins)
2. [Project layout: single file vs module](#2-project-layout-single-file-vs-module)
3. [The `IPlugin` base contract](#3-the-iplugin-base-contract)
4. [Plugin types overview](#4-plugin-types-overview)
5. [`IPluginTool`](#5-iplugintool)
6. [`IPluginInstaller` family](#6-iplugininstaller-family)
   - 6.1 [`IPluginInstallerSimple`](#61-iplugininstallersimple)
   - 6.2 [`IPluginInstallerCustom`](#62-iplugininstallercustom)
   - 6.3 [Installer lifecycle, priorities, and reinstall hooks](#63-installer-lifecycle-priorities-and-reinstall-hooks)
7. [`IPluginGame` and the `BasicGame` meta-plugin](#7-iplugingame-and-the-basicgame-meta-plugin)
8. [`IPluginPreview`](#8-iplugin-preview)
9. [`IPluginDiagnose`](#9-iplugin-diagnose)
10. [`IPluginModPage`](#10-iplugin-modpage)
11. [`IPluginFileMapper`](#11-iplugin-filemapper)
12. [`IPlugin` "free" plugins (UI-injecting / event-only)](#12-iplugin-free-plugins)
13. [The `IOrganizer` API surface](#13-the-iorganizer-api-surface)
14. [`IModList` and `IModInterface`](#14-imodlist-and-imodinterface)
15. [`IFileTree` and `FileTreeEntry`](#15-ifiletree-and-filetreeentry)
16. [Game features (`ModDataChecker`, `SaveGameInfo`, …)](#16-game-features)
17. [Settings, persistent storage, and per-mod settings](#17-settings-persistent-storage-and-per-mod-settings)
18. [Versioning with `VersionInfo`](#18-versioning-with-versioninfo)
19. [PyQt usage and dialog patterns](#19-pyqt-usage-and-dialog-patterns)
20. [Internationalization](#20-internationalization)
21. [Setting up a development environment](#21-setting-up-a-development-environment)
22. [Hot reload, debugging, and logging](#22-hot-reload-debugging-and-logging)
23. [Common pitfalls and `boost::python` gotchas](#23-common-pitfalls)
24. [Worked example: a minimal `IPluginInstallerSimple`](#24-worked-example-a-minimal-iplugininstallersimple)
25. [Worked example: a `BasicGame` for Palworld](#25-worked-example-a-basicgame-for-palworld)
26. [Sources](#sources)

---

## 1. How MO2 loads Python plugins

MO2 itself is a C++ application. The `plugin_python.dll` proxy plugin embeds
a CPython interpreter and walks the `plugins/` folder at startup, importing each
`.py` file or each Python package (folder containing `__init__.py`). For every
imported module it calls **`createPlugin()`** (single-plugin) or
**`createPlugins()`** (multi-plugin) and registers the returned object(s) with
the host.

```text
ModOrganizer.exe
    plugin_python.dll  ──► imports every  *.py / package  in plugins/
                          calls createPlugin() or createPlugins()
                          registers each returned IPlugin* with the core
```

Key consequences:

- The plugin file is loaded once per MO2 run (or once per `reload-plugin` call,
  see §22). It is module-level Python — top-level imports run during discovery.
- The CPython version is fixed by the bundled DLL. MO2 2.4 ships with the
  matching `pythonXX.dll` next to `ModOrganizer.exe`. You cannot pick your own.
- `mobase` is a C++ extension exposed via `boost::python`. It is only importable
  inside MO2's interpreter — outside of it, `import mobase` raises
  `ModuleNotFoundError`. Use [`mobase-stubs`](https://pypi.org/project/mobase-stubs/)
  for IDE/type-checking support.

---

## 2. Project layout: single file vs module

### Single-file plugin

```
$MO2DIR/plugins/
    myplugin.py        # contains createPlugin()
```

```python
# myplugin.py
import mobase

class MyPlugin(mobase.IPluginTool):
    ...

def createPlugin() -> mobase.IPlugin:
    return MyPlugin()
```

### Module plugin (recommended since MO2 2.3)

```
$MO2DIR/plugins/
    myplugin/
        __init__.py     # contains createPlugin()
        plugin.py       # the actual class
        ui/             # generated PyQt UI
        resources/      # icons, .qm translation files
        lib/            # vendored deps if needed
```

```python
# __init__.py
import mobase
from .plugin import MyPlugin   # always relative import

def createPlugin() -> mobase.IPlugin:
    return MyPlugin()
```

```python
# plugin.py
import mobase

class MyPlugin(mobase.IPluginTool):
    ...
```

Rules:

- The folder name does **not** have to be a valid Python identifier (MO2 imports
  it via path manipulation, not `import name`). Inside the package always use
  **relative imports** (`from .x import Y`).
- `createPlugins() -> list[mobase.IPlugin]` is supported when one package ships
  several plugins (e.g. a tool + a diagnose pair).
- A `lib/` sibling is convention for vendored third-party packages. Add it to
  `sys.path` (or `site.addsitedir`) inside `__init__.py` before importing
  anything that depends on it.

### Returning multiple plugins

```python
from typing import List
import mobase

def createPlugins() -> List[mobase.IPlugin]:
    return [MyTool(), MyDiagnose()]
```

> **Note:** Add the return type-hint. `mypy` then validates each plugin
> implements every abstract method.

---

## 3. The `IPlugin` base contract

Every plugin (regardless of subtype) inherits from `mobase.IPlugin`, directly or
indirectly. The abstract surface is:

| Method | Return | Purpose |
|---|---|---|
| `init(organizer: IOrganizer) -> bool` | `bool` | Called once after construction. Store `organizer`. Return `True` to keep the plugin loaded, `False` to disable it for this session. |
| `name() -> str` | `str` | **Stable internal id.** Used as the key for `pluginSetting`, `setPluginSetting`, `persistent`, and on-disk settings. Do not change between releases. |
| `localizedName() -> str` | `str` | (Optional) UI-facing translated name. Defaults to `name()`. |
| `author() -> str` | `str` | Display author. |
| `description() -> str` | `str` | Display description (translatable). |
| `version() -> VersionInfo` | `VersionInfo` | Plugin version. |
| `settings() -> Sequence[PluginSetting]` | list | Settings exposed to the user in the plugin settings dialog. |
| `enabledByDefault() -> bool` | `bool` | (Optional) initial state on first load. |
| `master() -> str` | `str` | (Optional) the `name()` of a "master" plugin this depends on; lets MO2 keep them in sync. |
| `requirements() -> list[IPluginRequirement]` | list | (Optional) declarative requirements (specific game, plugins, etc.). Used to gray out the plugin in the UI when unmet. |

Minimal scaffold:

```python
from typing import List
import mobase

class MyPlugin(mobase.IPluginTool):  # base class depends on plugin type
    _organizer: mobase.IOrganizer

    def __init__(self):
        super().__init__()           # MUST be called explicitly (boost::python)

    # --- IPlugin ---------------------------------------------------------
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "MyPlugin"

    def author(self) -> str:
        return "You"

    def description(self) -> str:
        return self.__tr("What this plugin does.")

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled", "Enable plugin", True),
        ]

    def isActive(self) -> bool:
        return bool(self._organizer.pluginSetting(self.name(), "enabled"))

    # --- helper ---------------------------------------------------------
    def __tr(self, txt: str) -> str:
        from PyQt6.QtCore import QCoreApplication
        return QCoreApplication.translate("MyPlugin", txt)
```

Things that bite people:

- Forgetting `super().__init__()` causes a `Boost.Python.ArgumentError` on
  first method dispatch.
- `name()` is the stable id used for setting persistence — never localise it.
- `init` is called **before** the user interface exists. To touch the UI use
  `organizer.onUserInterfaceInitialized(callback)` instead.

---

## 4. Plugin types overview

There are seven principal plugin interfaces plus two "extension" interfaces.
Multiple inheritance is supported, so a plugin can, for example, be both an
`IPluginTool` and an `IPluginDiagnose`.

| Interface | Where it shows up | Typical use |
|---|---|---|
| `IPlugin` | nowhere by itself | event listeners; UI injection via `onUserInterfaceInitialized`. |
| `IPluginTool` | Tools menu | a self-contained utility window. |
| `IPluginInstallerSimple` | mod install pipeline | rewrite the in-memory tree of an extracted archive. |
| `IPluginInstallerCustom` | mod install pipeline | take over installation entirely (no auto-extract). |
| `IPluginGame` | New Instance / game support | full game support definition. |
| `IPluginPreview` | Data tab right-pane | preview a file format. |
| `IPluginDiagnose` | "Problems" notification icon | detect issues and offer fixes. |
| `IPluginModPage` | Mod download UI | implement a mod repository client. |
| `IPluginFileMapper` | virtual file system | inject extra virtual files / dirs. |

Extension interfaces (mix into another plugin type):

- `IPluginDiagnose` — adds a problem report to the global "Problems" UI.
- `IPluginFileMapper` — contributes additional VFS entries.

Plugins are passive: MO2 calls into them in response to user actions or core
events. Long-running work must happen on the Qt event loop or in a
`QThread` — never block `init`.

---

## 5. `IPluginTool`

Adds an icon to the **Tools** menu. When clicked, MO2 calls `display()`. The
tool can do anything an MO2 user can do (modify the mod list, install mods,
launch the game, write to overwrite, etc.).

Required overrides:

```python
class IPluginTool(IPlugin):
    def displayName(self) -> str: ...        # menu entry text
    def tooltip(self) -> str: ...            # menu entry tooltip
    def icon(self) -> PyQt6.QtGui.QIcon: ...
    def setParentWidget(self, parent: PyQt6.QtWidgets.QWidget) -> None: ...
    def display(self) -> None: ...           # called when user clicks the menu
```

Pattern: cache the parent widget so dialogs you spawn are properly modal.

```python
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox, QWidget
import mobase


class HelloTool(mobase.IPluginTool):
    _organizer: mobase.IOrganizer
    _parent: QWidget | None = None

    def __init__(self):
        super().__init__()

    def init(self, organizer):
        self._organizer = organizer
        return True

    def name(self):           return "HelloTool"
    def author(self):         return "You"
    def description(self):    return self.__tr("Says hi.")
    def version(self):        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)
    def settings(self):       return []
    def isActive(self):       return True

    def displayName(self):    return self.__tr("Hello")
    def tooltip(self):        return self.__tr("Say hello to MO2")
    def icon(self):           return QIcon()

    def setParentWidget(self, parent):
        self._parent = parent

    def display(self) -> None:
        QMessageBox.information(self._parent, "Hello", "Hello, Imperium!")

    def __tr(self, t):  return QCoreApplication.translate("HelloTool", t)


def createPlugin():
    return HelloTool()
```

---

## 6. `IPluginInstaller` family

`IPluginInstaller` is the abstract base. **Don't subclass it directly** — pick
one of the two subclasses below depending on whether you want MO2 to do the
archive extraction for you.

Common base interface:

```python
class IPluginInstaller(IPlugin):
    def priority(self) -> int: ...                    # higher runs first
    def isManualInstaller(self) -> bool: ...          # True if it's the "manual" fallback
    def isArchiveSupported(self, tree: IFileTree) -> bool: ...
    def setParentWidget(self, parent: QWidget) -> None: ...
    def setInstallationManager(self, manager: IInstallationManager) -> None: ...
    def onInstallationStart(
        self, archive: str, reinstallation: bool,
        current_mod: IModInterface | None
    ) -> None: ...
    def onInstallationEnd(
        self, result: InstallResult, new_mod: IModInterface
    ) -> None: ...

    # internal accessors (don't override, just call):
    def _manager(self) -> IInstallationManager: ...
    def _parentWidget(self) -> QWidget: ...
```

**Priority** controls evaluation order — when several installers all return
`True` from `isArchiveSupported`, MO2 picks the highest-priority one. Built-in
installers occupy roughly:

| Installer | Priority |
|---|---|
| `installer_fomod` | 110–120 |
| `installer_bain` | 100 |
| `installer_quick` | 50 |
| `installer_manual` | 0 (always the catch-all) |

So custom rewriters that should beat FOMOD typically sit above 120.

### 6.1 `IPluginInstallerSimple`

MO2 has already extracted the archive in memory and passes you an `IFileTree`.
You return either a status code or a (possibly modified) tree.

```python
class IPluginInstallerSimple(IPluginInstaller):
    def install(
        self,
        name: GuessedString,        # mutable suggested mod name
        tree: IFileTree,            # the archive contents
        version: str,               # version string from Nexus, may be ""
        nexus_id: int,              # Nexus mod id, -1 if unknown
    ) -> Union[
        InstallResult,                                           # plain status
        IFileTree,                                               # rewritten tree, success implied
        tuple[InstallResult, IFileTree, str, int],               # full quad
    ]: ...
```

Return semantics:

- `mobase.InstallResult.SUCCESS` — install whatever's in `tree` (you mutated it
  in place).
- `mobase.InstallResult.FAILED` — abort.
- `mobase.InstallResult.CANCELED` — user backed out; no error displayed.
- `mobase.InstallResult.MANUAL_REQUESTED` — punt to the manual installer.
- `mobase.InstallResult.NOT_ATTEMPTED` — declined to handle (rare; usually used
  internally).
- Returning a bare `IFileTree` is shorthand for `(SUCCESS, tree, name, nexus_id)`.
- Returning the full tuple lets you also override the final `name` (if you
  changed it) and the `nexus_id`.

Mutate `name` via `name.update("New name", mobase.GuessQuality.USER)` if the
user picked one. Don't reassign `name = ...` — that swaps out the local
reference and MO2 won't see the change.

#### `isArchiveSupported(tree: IFileTree) -> bool`

Called for every installer in priority order. Cheap walk the tree to decide
whether to claim the archive. Return `False` quickly when not interested.

A typical pattern (single-pass walk that consolidates several checks):

```python
def isArchiveSupported(self, tree: mobase.IFileTree) -> bool:
    game = self._organizer.managedGame().gameName()
    if game not in ("Palworld", "Palworld Server"):
        return False

    saw_pak = False
    saw_lua = False

    def visit(path: str, entry: mobase.FileTreeEntry) -> mobase.IFileTree.WalkReturn:
        nonlocal saw_pak, saw_lua
        # Bail entirely for FOMOD archives if the user prefers FOMOD.
        if entry.isFile() and entry.name() == "moduleconfig.xml" \
                and path.endswith("fomod"):
            return mobase.IFileTree.WalkReturn.STOP
        # Bail entirely for UE4SS archives.
        if entry.isFile() and entry.name() == "ue4ss.dll":
            return mobase.IFileTree.WalkReturn.STOP
        if entry.isFile():
            if entry.suffix() == "pak":
                saw_pak = True
            elif entry.name() == "main.lua":
                saw_lua = True
        return mobase.IFileTree.WalkReturn.CONTINUE

    tree.walk(visit)
    return saw_pak or saw_lua
```

> `walk` invokes the callback for every descendant. Returning `SKIP` stops
> recursion into the current directory but continues with siblings; `STOP`
> aborts the entire walk.

### 6.2 `IPluginInstallerCustom`

Use this when you cannot work from an in-memory tree — for example you need
`7z` to selectively extract certain files, or the "archive" is actually a
folder/URL.

```python
class IPluginInstallerCustom(IPluginInstaller):
    def supportedExtensions(self) -> set[str]: ...
    def isArchiveSupported(self, tree: IFileTree) -> bool: ...
    def isArchiveSupported(self, archive_name: str) -> bool: ...   # overload
    def install(
        self,
        mod_name: GuessedString,
        game_name: str,
        archive_name: str,
        version: str,
        nexus_id: int,
    ) -> InstallResult: ...
```

You receive the archive **path on disk** and are responsible for everything:
extraction, file placement (use `IInstallationManager.createFile` /
`installArchive`), and creating the mod entry. Most plugins should prefer the
Simple variant.

### 6.3 Installer lifecycle, priorities, and reinstall hooks

Order of calls during an install:

1. MO2 enumerates installers by descending `priority()`.
2. For each, calls `isArchiveSupported(tree)`. First `True` wins.
3. `setParentWidget(parent)` is called (cache it for any dialogs).
4. `onInstallationStart(archive, reinstallation, current_mod)` — `reinstallation`
   is `True` when overwriting an existing mod; `current_mod` is the existing
   `IModInterface` or `None`. Use this to **read previous per-mod settings**
   and pre-populate your dialog.
5. `install(...)` — does the work and returns.
6. `onInstallationEnd(result, new_mod)` — write per-mod settings back via
   `new_mod.setPluginSetting(self.name(), key, value)` so reinstalls can
   restore them.

```python
def onInstallationStart(self, archive, reinstallation, current_mod):
    self._previous_choices = {}
    if reinstallation and current_mod is not None:
        # Pull every prior setting we wrote during onInstallationEnd.
        all_settings = current_mod.pluginSettings(self.name())
        self._previous_choices = dict(all_settings)

def onInstallationEnd(self, result, new_mod):
    if result == mobase.InstallResult.SUCCESS:
        for k, v in self._user_choices.items():
            new_mod.setPluginSetting(self.name(), k, v)
```

---

## 7. `IPluginGame` and the `BasicGame` meta-plugin

`IPluginGame` is wide and complex (40+ methods, designed primarily for
Gamebryo/Creation Engine titles). For everything that isn't a Bethesda game,
inherit from **`BasicGame`** instead — it ships with MO2 2.4 inside the
`basic_games` plugin folder and handles ~90 % of the boilerplate via class
attributes.

### 7.1 Bare `IPluginGame` (full surface)

```python
class IPluginGame(IPlugin):
    # identity
    def gameName(self) -> str
    def gameShortName(self) -> str
    def displayGameName(self) -> str          # optional override
    def gameNexusName(self) -> str
    def gameVariants(self) -> Sequence[str]
    def setGameVariant(self, variant: str) -> None
    def gameIcon(self) -> QIcon
    def gameVersion(self) -> str
    def lootGameName(self) -> str
    def nexusGameID(self) -> int
    def nexusModOrganizerID(self) -> int
    def steamAPPId(self) -> str

    # detection / paths
    def detectGame(self) -> None
    def isInstalled(self) -> bool
    def gameDirectory(self) -> QDir
    def dataDirectory(self) -> QDir
    def secondaryDataDirectories(self) -> dict[str, QDir]
    def documentsDirectory(self) -> QDir
    def savesDirectory(self) -> QDir
    def setGamePath(self, path: str) -> None
    def looksValid(self, directory: QDir) -> bool
    def primarySources(self) -> Sequence[str]    # "steam", "gog", "epic", ...
    def getSupportURL(self) -> str

    # profile
    def initializeProfile(self, directory: QDir, settings: ProfileSetting) -> None
    def iniFiles(self) -> Sequence[str]
    def listSaves(self, folder: QDir) -> list[ISaveGame]

    # plugins (Gamebryo-style esp/esm)
    def primaryPlugins(self) -> Sequence[str]
    def enabledPlugins(self) -> Sequence[str]
    def DLCPlugins(self) -> Sequence[str]
    def CCPlugins(self) -> Sequence[str]
    def loadOrderMechanism(self) -> LoadOrderMechanism
    def sortMechanism(self) -> SortMechanism
    def validShortNames(self) -> Sequence[str]

    # executables
    def binaryName(self) -> str
    def getLauncherName(self) -> str
    def executables(self) -> Sequence[ExecutableInfo]
    def executableForcedLoads(self) -> Sequence[ExecutableForcedLoadSetting]
```

`initializeProfile(directory, settings)` is called when MO2 creates a new
profile. `settings` is a bitmask of `ProfileSetting` (`CONFIGURATION`,
`MODS`, `SAVEGAMES`, …); copy or symlink the relevant defaults into
`directory`.

### 7.2 `BasicGame`

`BasicGame` is a `mobase.IPluginGame` subclass that turns the tedious
detection / path / executable boilerplate into class attributes resolved by
`BasicGameMappings`. Subclass it, set the attributes you have, override the
methods you need.

Recognised class attributes:

| Attribute | Purpose |
|---|---|
| `Name`, `Author`, `Version`, `Description` | normal `IPlugin` metadata |
| `GameName` | display name |
| `GameShortName` | internal id (e.g. `"palworld"`) |
| `GameNexusName` | nexus URL slug |
| `GameNexusId` | numeric nexus game id |
| `GameValidShortNames` | list of aliases |
| `GameBinary` | exe path relative to game dir |
| `GameLauncher` | launcher exe path (optional) |
| `GameDataPath` | mods install dir relative to game dir |
| `GameSaveExtension` | save file extension (no dot) |
| `GameSavesDirectory` | absolute or `%`-templated saves path |
| `GameDocumentsDirectory` | template path for the docs folder |
| `GameIniFiles` | list of ini files for profile-local INIs |
| `GameSteamId`, `GameGogId`, `GameOriginManifestIds`, `GameEpicId`, `GameEaDesktopId` | store ids for auto-detection |
| `GameSupportURL` | help link shown in the UI |

Path templates accept these tokens:

- `%GAME_PATH%` — the resolved game directory
- `%DOCUMENTS%` — current user's `Documents`
- `%USERPROFILE%` — `%USERPROFILE%` env var
- `%GAME_DOCUMENTS%` — value of `GameDocumentsDirectory`

### 7.3 `BasicGame` skeleton

```python
from PyQt6.QtCore import QDir
import mobase
from ..basic_game import BasicGame


class PalworldGame(BasicGame):
    Name           = "Palworld Support Plugin"
    Author         = "You"
    Version        = "1.0.0"

    GameName       = "Palworld"
    GameShortName  = "palworld"
    GameBinary     = "Pal/Binaries/Win64/Palworld-Win64-Shipping-Cmd.exe"
    GameDataPath   = "Pal/Content/Paks"
    GameSaveExtension = "sav"
    GameSavesDirectory = "%GAME_DOCUMENTS%/Saved/SaveGames"
    GameDocumentsDirectory = "%DOCUMENTS%/Palworld"
    GameSteamId    = 1623730

    def version(self):
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        # Walk userid/gamesaveid/Level.sav etc. Customised per game.
        ...
```

`BasicGame` plugins live in `plugins/basic_games/games/` — drop `game_xxx.py`
there. The container plugin `basic_games` discovers them.

### 7.4 Registering game features

Inside a `BasicGame` you register features with the host through
`organizer.gameFeatures().registerFeature(...)`. Example with
`BasicModDataChecker`:

```python
from ..basic_features.basic_mod_data_checker import BasicModDataChecker, GlobPatterns


class PalworldGame(BasicGame):
    ...
    def init(self, organizer: mobase.IOrganizer):
        super().init(organizer)
        organizer.gameFeatures().registerFeature(
            self,
            BasicModDataChecker(GlobPatterns(
                valid=["Pal/Content/Paks/*.pak", "Pal/Binaries/Win64/Mods/*"],
                move={"*.pak": "Pal/Content/Paks/"},
            )),
            0,                                 # priority
            replace=True,
        )
        return True
```

---

## 8. `IPluginPreview`

Adds a renderer for a file extension to the **Data** tab preview pane.

```python
class IPluginPreview(IPlugin):
    def supportedExtensions(self) -> set[str]
    def previewSupported(self, filename: str) -> bool        # optional fine-grained check
    def genFilePreview(self, filename: str, max_size: QSize) -> QWidget
    def setParentWidget(self, parent: QWidget) -> None
```

Return any `QWidget` from `genFilePreview` — a `QTextEdit`, a custom
`QGraphicsView`, an OpenGL surface, etc. Preview the file at most up to
`max_size`.

```python
class XmlPreview(mobase.IPluginPreview):
    def __init__(self):  super().__init__()

    def name(self):        return "XML Preview"
    def author(self):      return "You"
    def description(self): return "Plain-text preview for .xml files."
    def version(self):     return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)
    def settings(self):    return []
    def isActive(self):    return True

    def supportedExtensions(self):
        return {"xml"}

    def genFilePreview(self, filename, max_size):
        from PyQt6.QtWidgets import QTextEdit
        widget = QTextEdit()
        widget.setReadOnly(True)
        with open(filename, "r", encoding="utf-8") as fh:
            widget.setPlainText(fh.read())
        return widget
```

---

## 9. `IPluginDiagnose`

Reports issues to the **Problems** notification icon next to the toolbar, with
optional one-click fixes.

```python
class IPluginDiagnose(IPlugin):
    def activeProblems(self) -> list[int]              # ids of currently raised problems
    def shortDescription(self, key: int) -> str
    def fullDescription(self, key: int) -> str         # may include HTML
    def hasGuidedFix(self, key: int) -> bool
    def startGuidedFix(self, key: int) -> None
    def _invalidate(self) -> None                      # call to force MO2 to re-poll
```

Real example (annotated, adapted from `DiagnoseEmptyOverwrite`):

```python
import os
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QMessageBox
import mobase


class DiagnoseEmptyOverwrite(mobase.IPluginDiagnose):
    def __init__(self):
        super().__init__()
        self._organizer: mobase.IOrganizer | None = None

    def init(self, organizer):
        self._organizer = organizer
        # Recompute when the overwrite mod's state changes.
        organizer.modList().onModStateChanged(
            lambda changes: self._invalidate()
        )
        return True

    def name(self):        return "Empty Overwrite Diagnosis"
    def author(self):      return "AnyOldName3"
    def description(self): return self.__tr("Warns when Overwrite is empty.")
    def version(self):     return mobase.VersionInfo(1, 1, 0, mobase.ReleaseType.FINAL)
    def settings(self):    return []
    def isActive(self):    return True

    # --- IPluginDiagnose --------------------------------------------------
    def activeProblems(self):
        if not os.listdir(self._organizer.overwritePath()):
            return [0]
        return []

    def shortDescription(self, key):
        return self.__tr("Empty Overwrite directory")

    def fullDescription(self, key):
        return self.__tr(
            "Your Overwrite is empty. Click Fix to create a placeholder file."
        )

    def hasGuidedFix(self, key): return True

    def startGuidedFix(self, key):
        path = os.path.join(self._organizer.overwritePath(), "blank.txt")
        open(path, "a").close()
        self._organizer.refresh()
        QMessageBox.information(None, self.__tr("Done"), self.__tr("Created."))

    def __tr(self, t):
        return QCoreApplication.translate("DiagnoseEmptyOverwrite", t)


def createPlugin():
    return DiagnoseEmptyOverwrite()
```

Each problem is identified by an integer key. Use multiple keys to report
several distinct issues from the same plugin.

---

## 10. `IPluginModPage`

Implements a "mod download community" — a Nexus-style page accessible from
within MO2.

```python
class IPluginModPage(IPlugin):
    def displayName(self) -> str
    def icon(self) -> QIcon
    def pageURL(self) -> QUrl
    def useIntegratedBrowser(self) -> bool
    def handlesDownload(
        self, page_url: QUrl, download_url: QUrl, file_info: ModRepositoryFileInfo
    ) -> bool
    def setParentWidget(self, widget: QWidget) -> None
```

This interface is incomplete in the upstream code. Treat it as experimental.

---

## 11. `IPluginFileMapper`

Adds extra entries to MO2's **virtual file system** (the on-the-fly merged
view that backs the launched game). Useful for profile-local INI files,
load orders, save folders, etc.

```python
class IPluginFileMapper(IPlugin):
    def mappings(self) -> list[Mapping]


class Mapping:
    source: str          # absolute path on disk
    destination: str     # virtual path inside the game's data dir
    is_directory: bool
    create_target: bool  # create destination on demand
```

Often combined with `IPluginGame` (for game-specific virtual paths) or
`IPluginTool` (to expose a UI for managing them).

---

## 12. `IPlugin` "free" plugins

A plain `mobase.IPlugin` does nothing on its own — but plugins that subscribe
to organizer events (or inject UI widgets after `onUserInterfaceInitialized`)
use it as the cheapest base class. Example: a plugin that toggles the
visibility of the right-hand "Run" panel.

```python
import mobase
from PyQt6.QtWidgets import QFrame


class HideRunPanel(mobase.IPlugin):
    def __init__(self):
        super().__init__()
        self._frame: QFrame | None = None

    def name(self):        return "Hide Run Panel"
    def author(self):      return "Holt59"
    def description(self): return "Hides the run panel based on a setting."
    def version(self):     return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)
    def settings(self):
        return [mobase.PluginSetting("visible", "Show the run panel", False)]
    def isActive(self):    return True

    def init(self, organizer):
        organizer.onUserInterfaceInitialized(self._on_ui_ready)
        organizer.onPluginSettingChanged(self._on_setting_changed)
        return True

    def _on_ui_ready(self, main_window):
        self._frame = main_window.findChild(QFrame, "startGroup")
        if self._frame is not None:
            self._frame.setVisible(self._is_visible())

    def _on_setting_changed(self, plugin_name, setting, _old, new):
        if plugin_name == self.name() and setting == "visible" and self._frame:
            self._frame.setVisible(bool(new))

    def _is_visible(self):
        return bool(self._organizer.pluginSetting(self.name(), "visible"))


def createPlugin():
    return HideRunPanel()
```

Multiple inheritance lets one class be both `IPlugin` *and* `IPluginDiagnose`,
or `IPluginTool` *and* `IPluginFileMapper`, etc. Just override every required
method from each base.

---

## 13. The `IOrganizer` API surface

`IOrganizer` is the gateway to the rest of MO2. Stored in `init()`, used
everywhere. Selected methods:

```python
class IOrganizer:
    # version / paths
    def appVersion(self) -> VersionInfo
    def basePath(self) -> str
    def modsPath(self) -> str
    def overwritePath(self) -> str
    def downloadsPath(self) -> str
    def profilePath(self) -> str
    def pluginDataPath(self) -> str             # writable plugin scratch dir
    @staticmethod
    def getPluginDataPath() -> str

    # accessors
    def managedGame(self) -> IPluginGame
    def getGame(self, name: str) -> IPluginGame
    def profile(self) -> IProfile
    def profileName(self) -> str
    def modList(self) -> IModList
    def pluginList(self) -> IPluginList
    def downloadManager(self) -> IDownloadManager
    def gameFeatures(self) -> IGameFeatures
    def virtualFileTree(self) -> IFileTree

    # mod/file operations
    def createMod(self, name: GuessedString) -> IModInterface
    def installMod(self, filename, name_suggestion: str = "") -> IModInterface
    def modDataChanged(self, mod: IModInterface) -> None
    def refresh(self, save_changes: bool = True) -> None

    # filesystem helpers
    def listDirectories(self, directory: str) -> Sequence[str]
    def findFiles(self, path, filter=...) -> Sequence[str]
    def findFileInfos(self, path, filter) -> Sequence[FileInfo]
    def getFileOrigins(self, filename: str) -> Sequence[str]
    def resolvePath(self, filename) -> str

    # settings
    def pluginSetting(self, plugin_name: str, key: str) -> MoVariant
    def setPluginSetting(self, plugin_name: str, key: str, value: MoVariant) -> None
    def persistent(self, plugin_name: str, key: str, default=None) -> MoVariant
    def setPersistent(self, plugin_name: str, key: str, value, sync=True) -> None

    # process control
    def startApplication(
        self, executable, args=[], cwd="", profile="",
        forcedCustomOverwrite="", ignoreCustomOverwrite=False,
    ) -> int
    def waitForApplication(self, handle: int, refresh: bool = True) -> tuple[bool, int]

    # event subscriptions (callbacks return None or bool)
    def onAboutToRun(self, cb)
    def onFinishedRun(self, cb)
    def onUserInterfaceInitialized(self, cb)        # cb(main_window: QMainWindow)
    def onProfileCreated(self, cb)
    def onProfileChanged(self, cb)
    def onProfileRenamed(self, cb)
    def onProfileRemoved(self, cb)
    def onPluginEnabled(self, cb)
    def onPluginDisabled(self, cb)
    def onPluginSettingChanged(self, cb)            # cb(plugin, key, old, new)
    def onNextRefresh(self, cb, immediate_if_possible: bool = True)
```

`pluginSetting`/`setPluginSetting` are the keyed store that mirrors the user's
settings dialog. Use `persistent`/`setPersistent` for any plugin-private state
that you don't want exposed in the UI (last-used path, cached metadata, etc.).

---

## 14. `IModList` and `IModInterface`

`IModList` is the global list. `IModInterface` is one mod.

```python
class IModList:
    def allMods(self) -> Sequence[str]
    def allModsByProfilePriority(self, profile: IProfile | None = None) -> Sequence[str]
    def displayName(self, name: str) -> str
    def getMod(self, name: str) -> IModInterface
    def state(self, name: str) -> ModState
    def priority(self, name: str) -> int
    def setActive(self, name: str, active: bool) -> bool
    def setActive(self, names: Sequence[str], active: bool) -> int
    def setPriority(self, name: str, priority: int) -> bool
    def removeMod(self, mod: IModInterface) -> bool
    def renameMod(self, mod: IModInterface, name: str) -> IModInterface

    # events
    def onModInstalled(self, cb)
    def onModRemoved(self, cb)
    def onModMoved(self, cb)
    def onModStateChanged(self, cb)         # cb({mod_name: ModState})


class IModInterface:
    def name(self) -> str
    def absolutePath(self) -> str
    def fileTree(self) -> IFileTree
    def categories(self) -> Sequence[str]
    def addCategory(self, name: str)
    def removeCategory(self, name: str) -> bool
    def primaryCategory(self) -> int
    def addNexusCategory(self, category_id: int)
    def gameName(self) -> str
    def setGameName(self, name: str)
    def nexusId(self) -> int
    def setNexusID(self, nexus_id: int)
    def url(self) -> str
    def setUrl(self, url: str)
    def version(self) -> VersionInfo
    def setVersion(self, version: VersionInfo)
    def newestVersion(self) -> VersionInfo
    def setNewestVersion(self, v: VersionInfo)
    def ignoredVersion(self) -> VersionInfo
    def installationFile(self) -> str
    def isBackup(self) -> bool
    def isForeign(self) -> bool
    def isOverwrite(self) -> bool
    def isSeparator(self) -> bool
    def trackedState(self) -> TrackedState
    def endorsedState(self) -> EndorsedState
    def setIsEndorsed(self, endorsed: bool)
    def color(self) -> QColor
    def comments(self) -> str
    def notes(self) -> str

    # per-mod plugin settings (used by installers to persist user choices)
    def pluginSetting(self, plugin_name: str, key: str, default=None) -> MoVariant
    def pluginSettings(self, plugin_name: str) -> dict[str, MoVariant]
    def setPluginSetting(self, plugin_name: str, key: str, value: MoVariant) -> bool
    def clearPluginSettings(self, plugin_name: str) -> dict[str, MoVariant]
```

---

## 15. `IFileTree` and `FileTreeEntry`

The most-used class for installers. Trees are mutable in-memory representations
of file/dir hierarchies extracted from archives.

```python
class FileTreeEntry:
    class FileTypes(Enum):
        FILE
        DIRECTORY
        FILE_OR_DIRECTORY

    def name(self) -> str
    def suffix(self) -> str                   # extension without dot, lowercase
    def hasSuffix(self, suffixes: Sequence[str] | str) -> bool
    def path(self, sep: str = "\\") -> str    # full path from root
    def pathFrom(self, tree: IFileTree, sep: str = "\\") -> str
    def parent(self) -> IFileTree | None
    def isDir(self) -> bool
    def isFile(self) -> bool
    def fileType(self) -> FileTypes
    def detach(self) -> bool                  # remove from parent (keep alive)
    def moveTo(self, tree: IFileTree) -> bool


class IFileTree(FileTreeEntry):
    class InsertPolicy(Enum):
        FAIL_IF_EXISTS
        REPLACE
        MERGE

    class WalkReturn(Enum):
        CONTINUE
        SKIP            # don't recurse into current dir, continue siblings
        STOP            # abort entire walk

    # iteration
    def __iter__(self) -> Iterator[FileTreeEntry]
    def __len__(self) -> int
    def __getitem__(self, i: int) -> FileTreeEntry
    def __bool__(self) -> bool                 # False if empty

    # lookup
    def exists(self, path: str, type=FileTypes.FILE_OR_DIRECTORY) -> bool
    def find(self, path: str, type=FileTypes.FILE_OR_DIRECTORY) -> FileTreeEntry | IFileTree | None
    def pathTo(self, entry: FileTreeEntry, sep="\\") -> str

    # mutation
    def addDirectory(self, path: str) -> IFileTree
    def addFile(self, path: str, replace_if_exists: bool = False) -> FileTreeEntry
    def insert(self, entry: FileTreeEntry, policy=InsertPolicy.FAIL_IF_EXISTS) -> bool
    def copy(self, entry, path: str = "", insert_policy=InsertPolicy.FAIL_IF_EXISTS) -> FileTreeEntry
    def move(self, entry, path: str, policy=InsertPolicy.FAIL_IF_EXISTS) -> bool
    def merge(self, other: IFileTree, overwrites: bool = False) -> dict[FileTreeEntry, FileTreeEntry] | int
    def remove(self, name_or_entry) -> bool
    def removeAll(self, names: Sequence[str]) -> int
    def removeIf(self, predicate: Callable[[FileTreeEntry], bool]) -> int
    def clear(self) -> bool

    # recursion
    def walk(self, callback: Callable[[str, FileTreeEntry], WalkReturn], sep="\\") -> None

    # advanced
    def createOrphanTree(self, name: str = "") -> IFileTree
```

#### Common operations

**Walk every entry once and decide per-entry**:

```python
def visit(path: str, entry: mobase.FileTreeEntry):
    if entry.isFile() and entry.suffix() == "pak":
        ...
    return mobase.IFileTree.WalkReturn.CONTINUE

tree.walk(visit)
```

**Move a file into a new sub-directory**:

```python
dest = tree.addDirectory("Content/Paks/LogicMods")
tree.move(entry, dest.path() + "/" + entry.name(),
          policy=mobase.IFileTree.InsertPolicy.REPLACE)
```

> Use `addDirectory` to materialise the destination (it's idempotent — returns
> the existing dir if it already exists).

**Strip everything that isn't a known top-level dir**:

```python
KEEP = {"Binaries", "Content"}
tree.removeIf(lambda e: e.parent() is tree and e.name() not in KEEP)
```

**Merge two trees** (e.g. when handling a multi-pack archive):

```python
overwrites = tree.merge(other_tree, overwrites=True)
# overwrites is a dict[old_entry -> new_entry] when overwrites=True,
# or an int (count) when overwrites=False.
```

**Pitfalls**:

- `tree.remove("LogicMods")` deletes the **directory** from the tree. Don't
  call it inside a loop that iterates that directory; capture the entries
  first.
- `walk` calls back for every descendant in DFS order. To process only one
  level use plain iteration: `for entry in tree:`.
- `path()` uses `\\` by default — pass `sep="/"` for portable strings.
- `Path(entry.path()).parts[-3]` is fragile across archive layouts; prefer
  walking up via `entry.parent()` until you hit a known marker.

---

## 16. Game features

`IGameFeatures` (accessed via `organizer.gameFeatures()`) lets games and other
plugins register/query optional **features**. Each feature is a dedicated
abstract class. Common ones:

| Feature | Purpose |
|---|---|
| `ModDataChecker` | Validate / normalise the layout of a mod archive during install. Result: `VALID`, `FIXABLE`, `INVALID`. Used by `IPluginInstaller` plumbing. |
| `ModDataContent` | Emit content tags for the mod list (e.g. "Skyrim - Voice Files"). |
| `SaveGameInfo` | Provide rich save metadata (preview image, character info) shown in MO2's save tab. |
| `ScriptExtender` | Describe SKSE/SFSE/etc. (loader name, version detection). |
| `LocalSavegames` | Activate / deactivate per-profile save game folders. |
| `BSAInvalidation`, `DataArchives`, `GamePlugins` | Bethesda-specific. |

Use `gameFeatures().registerFeature(plugin, feature_instance, priority, replace=False)`
to provide one, and `gameFeatures().gameFeature(FeatureClass)` to consume one.

`BasicGame` ships ergonomic helpers in `basic_features/`:

- `BasicModDataChecker(GlobPatterns(valid=[...], unfold=[...], move={glob: dest}, delete=[...]))`
- `BasicGameSaveGameInfo` — for screenshot-bearing saves.

Example registration in a `BasicGame.init`:

```python
def init(self, organizer):
    super().init(organizer)
    organizer.gameFeatures().registerFeature(
        self,
        BasicModDataChecker(GlobPatterns(
            valid=["Pal/Content/Paks/*.pak"],
            move={"*.pak": "Pal/Content/Paks/"},
        )),
        priority=0,
        replace=True,
    )
    return True
```

### Anti-pattern: `self._featureMap[...]`

Older `BasicGame` builds exposed a private `_featureMap` dict that you could
mutate directly to register features, e.g.:

```python
# DO NOT USE — raises AttributeError on current MO2:
#   'PalworldGame' object has no attribute '_featureMap'
self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(...)
```

That attribute does not exist on the version of `BasicGame` shipped with
current MO2 releases. Sample code that still uses it (often copy-pasted from
old game plugins or stale tutorials) will fail to load with the error above.

Always go through `organizer.gameFeatures().registerFeature(self, feature,
priority, replace=...)` from inside `init(organizer)`. Never poke at private
attributes of `BasicGame`.

---

## 17. Settings, persistent storage, and per-mod settings

Three distinct stores:

| API | Scope | Survives restart | Visible in UI |
|---|---|---|---|
| `PluginSetting` returned by `settings()` + `organizer.pluginSetting(...)` | per-plugin | yes (in `ModOrganizer.ini`) | **yes**, in the plugin settings dialog |
| `organizer.persistent(name, key, default)` | per-plugin | yes (in plugin storage file) | no |
| `mod.pluginSetting(plugin, key)` | **per-mod** | yes (in the mod's `meta.ini`) | no |

### Declaring user-visible settings

```python
def settings(self) -> list[mobase.PluginSetting]:
    return [
        mobase.PluginSetting("enabled",       "Enable plugin",        True),
        mobase.PluginSetting("priority",      "Installer priority",   120),
        mobase.PluginSetting("prefer_fomod",  "Defer to FOMOD when present", True),
        mobase.PluginSetting("custom_paths",
                             "Comma-separated extra destinations",
                             ""),
    ]

# Read:
val = self._organizer.pluginSetting(self.name(), "priority")
# Write (rare; usually the user does this through the UI):
self._organizer.setPluginSetting(self.name(), "priority", 130)
```

`PluginSetting` value types: `bool`, `int`, `str`, `list[str]`. Anything else
must be serialised yourself.

### Per-mod settings (the "remember last install choices" pattern)

```python
def onInstallationEnd(self, result, mod):
    if result != mobase.InstallResult.SUCCESS:
        return
    for i, choice in enumerate(self._user_choices):
        mod.setPluginSetting(self.name(), f"select{i}-description", choice.description)
        for j, opt in enumerate(choice.options):
            mod.setPluginSetting(self.name(), f"select{i}-option{j}", opt)

def onInstallationStart(self, archive, reinstallation, current_mod):
    self._previous = {}
    if reinstallation and current_mod is not None:
        self._previous = dict(current_mod.pluginSettings(self.name()))
```

Use stable, machine-readable keys (`select{i}-option{j}`) and parse them back
with regular expressions.

---

## 18. Versioning with `VersionInfo`

```python
class ReleaseType(Enum):
    PRE_ALPHA
    ALPHA
    BETA
    RELEASE_CANDIDATE
    FINAL

class VersionScheme(Enum):
    DISCOVER
    REGULAR
    DECIMAL_MARK
    NUMBERS_AND_LETTERS
    DATE
    LITERAL

mobase.VersionInfo()                                              # invalid
mobase.VersionInfo("1.2.3-alpha")                                 # parsed
mobase.VersionInfo(1, 2, 3, mobase.ReleaseType.FINAL)             # tuple
mobase.VersionInfo(1, 2, 3, 4, mobase.ReleaseType.FINAL)          # quad
mobase.VersionInfo("1.2.3", mobase.VersionScheme.LITERAL)         # opaque
```

`VersionInfo` supports `==`, `<`, `>` etc. — useful for comparing against
`mod.newestVersion()`.

---

## 19. PyQt usage and dialog patterns

MO2 2.4 ships PyQt6 (`from PyQt6.QtWidgets import ...`). Earlier versions are
PyQt5. Code that must straddle both can do:

```python
try:
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QDialog
except ImportError:
    from PyQt5.QtCore import QCoreApplication
    from PyQt5.QtWidgets import QDialog
```

Conventions:

- Cache the `parent` widget supplied via `setParentWidget` and pass it to all
  spawned dialogs so they're properly modal and inherit MO2's style.
- The Qt event loop is already running. Don't call `app.exec()` yourself; use
  `dialog.exec()` (modal) or `dialog.show()` (modeless) and connect signals.
- For UI built in Qt Designer, generate the `.py` once with
  `pyuic6 ui/foo.ui -o ui/foo.py` and import it: `from .ui.foo import Ui_Foo`.
- Resources (`.qrc`) compile via `pyrcc6` — but most plugins skip resources
  entirely and just `QIcon(":/inline.png")` is rarely needed.

### Skeleton dialog returning structured choices

```python
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

class InstallerDialog(QDialog):
    def __init__(self, parent, mod_name: str, files: list[str]):
        super().__init__(parent)
        self._mod_name = mod_name
        self._choices: dict[str, str] = {}
        layout = QVBoxLayout(self)
        # ... build widgets ...
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Help
        )
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def choices(self) -> dict[str, str]: return self._choices
    def mod_name(self) -> str: return self._mod_name
```

Inside `install()`:

```python
def install(self, name, tree, version, nexus_id):
    dlg = InstallerDialog(self._parentWidget(), str(name), self._collect(tree))
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return mobase.InstallResult.CANCELED
    name.update(dlg.mod_name(), mobase.GuessQuality.USER)
    self._apply_choices(tree, dlg.choices())
    return tree
```

---

## 20. Internationalization

MO2 uses Qt's translation system. To support translations:

1. Add a `__tr` helper to every class with translatable strings:

   ```python
   from PyQt6.QtCore import QCoreApplication
   class MyPlugin(mobase.IPluginTool):
       def __tr(self, txt):
           return QCoreApplication.translate("MyPlugin", txt)  # CONTEXT == class name
   ```

2. Wrap user-visible strings: `self.__tr("Hello!")`.

3. Generate the `.ts` file (Qt source translation):

   ```bash
   pyuic5 ui/dialog.ui -o ui/dialog.py        # if you have UI files
   pylupdate5 plugin.py ui/dialog.py -ts plugin.ts
   # On PyQt6 use pyuic6 / pylupdate6 (if available; pyqt5 tools also work).
   ```

4. Translate `.ts` (Qt Linguist or Transifex), then compile to `.qm`:

   ```bash
   lrelease plugin.ts            # produces plugin.qm
   ```

5. Naming for shipping:
   - Single-file plugin `myplugin.py` → `myplugin_<lang>.qm` (e.g. `myplugin_fr.qm`).
   - Module plugin `mymoduleplugin/` → `mymoduleplugin_<lang>.qm` placed
     inside the module folder.

`<lang>` is the Qt locale code: `fr`, `de`, `pt_BR`, etc. MO2 loads the matching
file based on its current locale.

---

## 21. Setting up a development environment

### Required tooling

- **Mod Organizer 2 ≥ 2.3.0** (the proxy is bundled).
- **CPython matching MO2's bundled version.** Look at `pythonXX.dll` next to
  `ModOrganizer.exe`. MO2 2.4 ships Python 3.11; 2.3.x ships 3.8.
- **`mobase-stubs`** for IDE / type checking:

  ```bash
  pip install mobase-stubs
  ```

  This also installs `PyQt6-stubs` (or `PyQt5-stubs` for older versions).

### IDE configuration (VS Code example)

`.vscode/settings.json`:

```json
{
  "python.analysis.typeCheckingMode": "basic",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "[python]": { "editor.defaultFormatter": "ms-python.black-formatter" }
}
```

`pyproject.toml` (optional):

```toml
[tool.mypy]
ignore_missing_imports = true     # mobase is a stub, third-party deps may not be typed

[tool.black]
line-length = 100
```

### Vendoring third-party dependencies

If your plugin needs a pure-Python package not available in MO2's interpreter,
vendor it in a `lib/` folder:

```
plugins/myplugin/
    __init__.py
    plugin.py
    lib/
        somepackage/
            __init__.py
            ...
```

Add `lib/` to `sys.path` early in `__init__.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
```

C extensions are tricky because they must match the embedded interpreter's
ABI. Test against the exact `pythonXX.dll` MO2 ships.

---

## 22. Hot reload, debugging, and logging

### Reloading a single plugin (MO2 2.4 alpha 6+)

```text
ModOrganizer.exe reload-plugin "Plugin Name"
```

Where `"Plugin Name"` matches the value of `name()`. Wire it into VS Code via
a task and the *Trigger Task on Save* extension to get automatic reload while
editing.

### Logging

MO2 surfaces `print(...)` and `logging` output to its log pane and to
`%LOCALAPPDATA%/ModOrganizer/<instance>/logs/mo_interface.log`. Prefer the
standard `logging` module:

```python
import logging
log = logging.getLogger(__name__)
log.info("Installer: archive %s claimed", archive)
```

Uncaught exceptions are caught by the proxy and logged with traceback, but
the failing call returns a sensible default (e.g. `False`) — so a buggy
`isArchiveSupported` won't crash MO2, it'll just silently decline.

### Common signs of trouble

| Symptom | Likely cause |
|---|---|
| `Boost.Python.ArgumentError: Python argument types in ... did not match C++ signature` on first method call | missing `super().__init__()` |
| `TypeError: 'NoneType' object is not iterable` in `init` | returned `None` instead of `True` |
| Plugin doesn't appear in Tools menu | `isActive()` returns `False`, or `init()` returned `False`, or `requirements()` not satisfied |
| `isinstance(obj, QWidget)` fails for a known widget | stub fakes inheritance; use `obj.isWidgetType()` or duck-typing instead |
| Dialog appears behind MO2 | forgot to pass `self._parentWidget()` as `parent` |
| Settings don't persist | mismatch between `name()` returned by plugin and the key used in `pluginSetting(...)` |

---

## 23. Common pitfalls

- **`super().__init__()` is mandatory** in every plugin subclass — even with
  no arguments. `boost::python` cannot synthesise the parent constructor.
- **`name()` is a stable identifier**, not a display string. If you localise
  it (or change it between releases) all stored settings vanish silently.
- **Don't reassign `name` in `install()`** — `GuessedString` is mutated via
  `name.update("...", mobase.GuessQuality.USER)`. A `name = "..."` rebind is
  invisible to MO2.
- **`tree.walk` callback must return a `WalkReturn` value** (or `None`, which
  is interpreted as `CONTINUE`). Returning a truthy/falsy value won't do
  what you mean.
- **One-pass walks beat multi-pass walks**: instead of three separate
  `tree.walk(...)`s for "is FOMOD?", "is UE4SS?", "has paks?", consolidate
  into one callback with three flags and `STOP` early.
- **Avoid `tree.remove(...)` while iterating** that part of the tree —
  capture entries into a list first.
- **`Path(entry.path()).parts[-3]`** is fragile across archive layouts. Walk
  upward via `entry.parent()` until you hit a known marker file/dir.
- **`isinstance(x, QObject)` and friends fail** for objects coming back from
  MO2 because the stubs only simulate Qt inheritance for IDE support. Real
  objects delegate to the underlying Qt instance through `__getattr__`.
- **`mobase` cannot be imported outside MO2.** Static analysis works only via
  `mobase-stubs`. Don't try to run plugin files standalone — use `if "mobase"
  not in sys.modules: import mock_mobase as mobase` for unit tests if you go
  that route.
- **The Python interpreter is shared** across all plugins. Don't pollute
  `sys.path` globally; restrict additions to your `lib/` folder.
- **Multiple inheritance must satisfy every base's abstract surface.** A
  `class X(IPluginTool, IPluginDiagnose)` must implement `display`,
  `displayName`, `tooltip`, `icon` *and* `activeProblems`,
  `shortDescription`, `fullDescription`, etc. Use `mypy` to catch gaps.

---

## 24. Worked example: a minimal `IPluginInstallerSimple`

This is a stripped-down skeleton that mirrors the kind of installer you'd
build for Palworld — tree triage, dialog, mutate-and-return.

```python
# plugins/myinstaller/__init__.py
import mobase
from .installer import MyInstaller

def createPlugin() -> mobase.IPlugin:
    return MyInstaller()
```

```python
# plugins/myinstaller/installer.py
from __future__ import annotations
import re
from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QWidget

from .ui.dialog import InstallerDialog


RE_DESCRIPTION = re.compile(r"^select(\d+)-description$")
RE_OPTION      = re.compile(r"^select(\d+)-option(\d+)$")


class MyInstaller(mobase.IPluginInstallerSimple):
    _organizer: mobase.IOrganizer
    _parent: QWidget | None = None

    def __init__(self):
        super().__init__()

    # --- IPlugin ---------------------------------------------------------
    def init(self, organizer):
        self._organizer = organizer
        return True

    def name(self):        return "My Palworld Installer"
    def author(self):      return "You"
    def description(self): return self._tr("Custom installer for Palworld pak/lua mods.")
    def version(self):     return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)
    def isActive(self):    return bool(self._organizer.pluginSetting(self.name(), "enabled"))

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting("enabled",      "Enable installer",            True),
            mobase.PluginSetting("priority",     "Priority (higher = first)",   120),
            mobase.PluginSetting("prefer_fomod", "Defer to FOMOD when present", True),
        ]

    # --- IPluginInstaller -----------------------------------------------
    def priority(self) -> int:
        return int(self._organizer.pluginSetting(self.name(), "priority"))

    def isManualInstaller(self) -> bool:
        return False

    def setParentWidget(self, parent: QWidget) -> None:
        self._parent = parent

    def isArchiveSupported(self, tree: mobase.IFileTree) -> bool:
        game = self._organizer.managedGame().gameName()
        if game not in ("Palworld", "Palworld Server"):
            return False

        prefer_fomod = bool(self._organizer.pluginSetting(self.name(), "prefer_fomod"))
        fomod_enabled = self._organizer.isPluginEnabled("FOMOD Installer")

        flags = {"fomod": False, "ue4ss": False, "pak": False, "lua": False}

        def visit(path: str, entry: mobase.FileTreeEntry):
            if entry.isFile():
                lower = entry.name().lower()
                if lower == "moduleconfig.xml" and path.lower().endswith("fomod"):
                    flags["fomod"] = True
                    return mobase.IFileTree.WalkReturn.STOP
                if lower == "ue4ss.dll":
                    flags["ue4ss"] = True
                    return mobase.IFileTree.WalkReturn.STOP
                if entry.suffix() == "pak":
                    flags["pak"] = True
                if lower == "main.lua":
                    flags["lua"] = True
            return mobase.IFileTree.WalkReturn.CONTINUE

        tree.walk(visit)

        if flags["fomod"] and fomod_enabled and prefer_fomod:
            return False
        if flags["ue4ss"]:
            return False
        return flags["pak"] or flags["lua"]

    def onInstallationStart(self, archive, reinstallation, current_mod):
        self._previous = {}
        if reinstallation and current_mod is not None:
            self._previous = dict(current_mod.pluginSettings(self.name()))

    def onInstallationEnd(self, result, new_mod):
        if result != mobase.InstallResult.SUCCESS:
            return
        for i, (desc, options) in enumerate(self._user_choices):
            new_mod.setPluginSetting(self.name(), f"select{i}-description", desc)
            for j, opt in enumerate(options):
                new_mod.setPluginSetting(self.name(), f"select{i}-option{j}", opt)

    def install(self, name, tree, version, nexus_id):
        # 1. Collect interesting entries from the tree.
        paks: list[mobase.FileTreeEntry] = []
        scripts: list[mobase.FileTreeEntry] = []
        jsons: list[mobase.FileTreeEntry] = []

        def collect(_path, entry):
            if entry.isFile():
                if entry.suffix() == "pak":
                    paks.append(entry)
                elif entry.name() == "main.lua":
                    scripts.append(entry)
                elif entry.suffix() == "json":
                    jsons.append(entry)
            return mobase.IFileTree.WalkReturn.CONTINUE
        tree.walk(collect)

        # 2. Show UI.
        dlg = InstallerDialog(self._parent, str(name), paks, scripts,
                              previous=self._previous)
        if dlg.exec() == 0:
            return mobase.InstallResult.CANCELED

        name.update(dlg.mod_name(), mobase.GuessQuality.USER)
        self._user_choices = dlg.user_choices()

        # 3. Apply.
        for entry, dest in dlg.pak_destinations().items():
            if dest == "SKIP":
                tree.remove(entry)
                continue
            target_dir = tree.addDirectory(f"Pal/Content/Paks/{dest}")
            tree.move(entry, f"{target_dir.path('/')}/{entry.name()}",
                      policy=mobase.IFileTree.InsertPolicy.REPLACE)

        for script in scripts:
            mod_dir = script.parent().parent().parent().name()  # …/<modname>/Scripts/main.lua
            target = tree.addDirectory(f"Pal/Binaries/Win64/Mods/{mod_dir}")
            target.merge(script.parent().parent(), overwrites=True)

        # 4. Strip everything that isn't an expected top-level dir.
        keep = {"Pal"}
        tree.removeIf(lambda e: e.parent() is tree and e.name() not in keep)

        return tree

    # --- helper ----------------------------------------------------------
    def _tr(self, t):
        return QCoreApplication.translate("MyInstaller", t)
```

---

## 25. Worked example: a `BasicGame` for Palworld

Lives at `plugins/basic_games/games/game_palworld.py`.

```python
# game_palworld.py
import os
from pathlib import Path

from PyQt6.QtCore import QDir, QFileInfo
import mobase

from ..basic_features.basic_save_game_info import BasicGameSaveGame
from ..basic_game import BasicGame


class PalworldSaveGame(BasicGameSaveGame):
    """One save = a folder named with the game-save id, holding Level.sav."""
    def getName(self) -> str:
        return self._filepath.parent.name


class PalworldGame(BasicGame):
    Name           = "Palworld Support Plugin"
    Author         = "You"
    Version        = "1.0.0"
    Description    = "Adds Palworld support to MO2."

    GameName       = "Palworld"
    GameShortName  = "palworld"
    GameNexusName  = "palworld"
    GameBinary     = "Pal/Binaries/Win64/Palworld-Win64-Shipping-Cmd.exe"
    GameDataPath   = "Pal/Content/Paks"
    GameSaveExtension = "sav"
    GameDocumentsDirectory = "%DOCUMENTS%/Palworld"
    GameSavesDirectory     = "%GAME_DOCUMENTS%/Saved/SaveGames"
    GameSteamId    = 1623730
    GameSupportURL = "https://github.com/you/mo2-palworld-plugin"

    def version(self):
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.FINAL)

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        # SaveGames/<userid>/<gamesaveid>/Level.sav
        saves: list[mobase.ISaveGame] = []
        root = Path(folder.absolutePath())
        if not root.is_dir():
            return saves
        for user_dir in root.iterdir():
            if not user_dir.is_dir():
                continue
            for save_dir in user_dir.iterdir():
                level = save_dir / "Level.sav"
                if level.is_file():
                    saves.append(PalworldSaveGame(level))
        return saves


def createPlugin() -> mobase.IPlugin:
    return PalworldGame()
```

The dedicated server is virtually identical — change `GameName`,
`GameShortName`, `GameSteamId`, and `GameBinary`.

---

## Sources

Primary documentation:
- [MO2 Python Plugin API documentation (root)](https://www.modorganizer.org/python-plugins-doc/)
- [Writing Plugins guide](https://www.modorganizer.org/python-plugins-doc/writing-plugins.html)
  ([RST source](https://www.modorganizer.org/python-plugins-doc/_sources/writing-plugins.rst.txt))
- [Type of Plugins guide](https://www.modorganizer.org/python-plugins-doc/plugin-types.html)
- [`mobase` API reference](https://www.modorganizer.org/python-plugins-doc/autoapi/mobase/index.html)
  ([RST source](https://www.modorganizer.org/python-plugins-doc/_sources/autoapi/mobase/index.rst.txt))
- [Setting up the environment](https://www.modorganizer.org/python-plugins-doc/setup-tools.html)
- [FAQ](https://www.modorganizer.org/python-plugins-doc/faq.html)
- [`mobase-stubs` on PyPI](https://pypi.org/project/mobase-stubs/)

Code repositories:
- [`ModOrganizer2/modorganizer-basic_games`](https://github.com/ModOrganizer2/modorganizer-basic_games) — meta-plugin and 100+ game definitions.
- [`ModOrganizer2/modorganizer-installer_wizard`](https://github.com/ModOrganizer2/modorganizer-installer_wizard) — production-quality `IPluginInstallerSimple`.
- [`Holt59/modorganizer-python_plugins`](https://github.com/Holt59/modorganizer-python_plugins) — minimal example tool / installer / game plugins.
- [`AnyOldName3/ModOrganizer2PythonPluginTests`](https://github.com/AnyOldName3/ModOrganizer2PythonPluginTests) — stub plugins for every interface.
- [`ModOrganizer2/pystubs-generation`](https://github.com/ModOrganizer2/pystubs-generation) — source of truth for `mobase` stubs.
- [`ModOrganizer2/modorganizer-plugin_python`](https://github.com/ModOrganizer2/modorganizer-plugin_python) — the C++ proxy that loads Python plugins.
- [`ModOrganizer2/modorganizer/wiki/Writing-Mod-Organizer-Plugins`](https://github.com/ModOrganizer2/modorganizer/wiki/Writing-Mod-Organizer-Plugins) — older but still useful wiki.
