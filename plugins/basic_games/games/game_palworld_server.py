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
    Name = "Palworld Server"
    Author = "WickedSik"
    Version = "0.0.1"
    GameNexusId = 658
    GameSteamId = [2394010]

    GameName = "Palworld Server"
    GameShortName = "palworld_server"
    GameNexusName = "palworld"
    GameBinary = "PalServer.exe"
    GameDataPath = "Pal"
    GameSaveExtension = "sav"
    GameDocumentsDirectory = "%GAME_PATH%/Pal/Saved/Config/WindowsServer"
    GameSavesDirectory = "%GAME_PATH%/Pal/Saved/SaveGames/"

    def init(self, organizer: mobase.IOrganizer) -> bool:
        super().init(organizer)
        organizer.gameFeatures().registerFeature(
            self,
            BasicGameSaveGameInfo(lambda s: Path(s or "", "level.sav")),
            0,
            replace=True,
        )
        return True
  

    def listSaves(self, folder: QDir) -> list[mobase.ISaveGame]:
        saves = []
        for user_dir in Path(folder.absolutePath()).iterdir():
            if user_dir.is_dir():  # Assuming this is the Steam user ID directory
                for game_save_dir in user_dir.iterdir():
                    if game_save_dir.is_dir():  # This should be the random game save ID directory
                        save_file = game_save_dir / "level.sav"
                        if save_file.exists():
                            saves.append(BasicGameSaveGame(game_save_dir))
        
        return saves
