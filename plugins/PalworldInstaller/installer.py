from __future__ import annotations

from typing import List

import mobase
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QWidget


class PalworldInstaller(mobase.IPluginInstallerSimple):
    _organizer: mobase.IOrganizer
    _parent: QWidget | None = None

    def __init__(self):
        super().__init__()

    # --- IPlugin ---------------------------------------------------------
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def name(self) -> str:
        return "PalworldInstaller"

    def localizedName(self) -> str:
        return self._tr("Palworld Installer")

    def author(self) -> str:
        return "WickedSik"

    def description(self) -> str:
        return self._tr(
            "Custom installer for Palworld pak/lua mods. "
            "Scaffolding only — does not yet claim archives."
        )

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.PRE_ALPHA)

    def settings(self) -> List[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "enabled",
                "check to enable this plugin",
                True,
            ),
            mobase.PluginSetting(
                "prefer_fomod",
                "prefer FOMOD installer when possible",
                True,
            ),
            mobase.PluginSetting(
                "priority",
                "priority of this installer",
                120,
            ),
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

    def isActive(self) -> bool:
        return bool(self._organizer.pluginSetting(self.name(), "enabled"))

    # --- IPluginInstaller ------------------------------------------------
    def priority(self) -> int:
        return int(self._organizer.pluginSetting(self.name(), "priority"))

    def isManualInstaller(self) -> bool:
        return False

    def setParentWidget(self, parent: QWidget) -> None:
        self._parent = parent

    # --- IPluginInstallerSimple -----------------------------------------
    def isArchiveSupported(self, tree: mobase.IFileTree) -> bool:
        return False

    def install(
        self,
        name: mobase.GuessedString,
        tree: mobase.IFileTree,
        version: str,
        nexus_id: int,
    ) -> mobase.InstallResult:
        return mobase.InstallResult.NOT_ATTEMPTED

    # --- helper ----------------------------------------------------------
    def _tr(self, txt: str) -> str:
        return QCoreApplication.translate("PalworldInstaller", txt)
