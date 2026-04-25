import mobase

from .installer import PalworldInstaller


def createPlugin() -> mobase.IPlugin:
    return PalworldInstaller()
