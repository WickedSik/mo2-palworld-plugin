from pathlib import Path
import os
from typing import List

import mobase
from PyQt6.QtCore import QDir
from PyQt6.QtCore import qInfo

from ..basic_features import BasicGameSaveGameInfo
from ..basic_features.basic_save_game_info import BasicGameSaveGame
from ..basic_game import BasicGame

class PalworldGame(BasicGame):
    Name = "Palworld"
    Author = "WickedSik"
    Version = "0.0.1"
    Description = "Palworld installer with support for multi-platform packages"
    GameNexusId = 658
    GameSteamId = [1623730]

    GameName = "Palworld"
    GameShortName = "palworld"
    GameNexusName = "palworld"
    GameBinary = "palworld.exe"
    GameDataPath = "Pal"
    GameSaveExtension = "sav"
    GameDocumentsDirectory = "%localappdata%/Pal/Saved/Config/Windows/"
    GameSavesDirectory = "%localappdata%/Pal/Saved/SaveGames/"

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        self._featureMap[mobase.SaveGameInfo] = BasicGameSaveGameInfo(
            lambda s: Path(s or "", "level.sav")
        )
        return True
  

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        saves = []
        save_path = os.path.expandvars(self.GameSavesDirectory)

        for user_dir in Path(save_path).iterdir():
            if user_dir.is_dir():
                for game_save_dir in user_dir.iterdir():
                    if game_save_dir.is_dir():
                        save_file = game_save_dir / "level.sav"
                        if save_file.exists():
                            saves.append(BasicGameSaveGame(game_save_dir))
        
        return saves
