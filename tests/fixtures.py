"""Hardcoded test-mod directory structures derived from _assets/test-mods/.

Each constant is a nested dict representing an archive layout. Keys ending
with "/" are directories; all other keys are files. Values for files are
the FILE sentinel; values for directories are nested dicts.

Source: _assets/test-mods/ (gitignored — contains real multi-MB .pak binaries).
Last synced: 2026-05-24.
"""
from tests.mobase_mock import FILE

# --- SexyMimog: single _P pak at root ----------------------------------------

SEXY_MIMOG = {
    "SexyMimog_NSFW_Nude+Armors_P.pak": FILE,
}

# --- ScrollTest20Paks: 20 paks (mix of _P and Logic) + 3 script mods ---------

SCROLL_TEST_20_PAKS = {
    "Aurora_P.pak": FILE,
    "Borealis_P.pak": FILE,
    "Cinder_P.pak": FILE,
    "Dusk_P.pak": FILE,
    "Ember_P.pak": FILE,
    "Frost_P.pak": FILE,
    "Glimmer_P.pak": FILE,
    "Halcyon_P.pak": FILE,
    "Iris_P.pak": FILE,
    "Jade_P.pak": FILE,
    "KrakenLogic.pak": FILE,
    "LeviathanLogic.pak": FILE,
    "MimicLogic.pak": FILE,
    "NebulaLogic.pak": FILE,
    "OracleLogic.pak": FILE,
    "PhoenixLogic.pak": FILE,
    "QuasarLogic.pak": FILE,
    "RavenLogic.pak": FILE,
    "SerpentLogic.pak": FILE,
    "TitanLogic.pak": FILE,
    "ScriptModAlpha/": {
        "Scripts/": {"main.lua": FILE},
    },
    "ScriptModBeta/": {
        "Scripts/": {"main.lua": FILE},
    },
    "ScriptModGamma/": {
        "Scripts/": {"main.lua": FILE},
    },
}

# --- ASD_MercyBlacklist: {Steam}/{Gamepass} platform variants ----------------
# Xbox/Gamepass variant includes .utoc/.ucas companions.
# Both have nested Palworld/Pal/Content/Paks/LogicMods/ wrapper.

ASD_MERCY_BLACKLIST = {
    "{Steam}/": {
        "Palworld/": {
            "Pal/": {
                "Content/": {
                    "Paks/": {
                        "LogicMods/": {
                            "ASD_MercyBlacklist.pak": FILE,
                            "Settings/": {
                                "ASD_MercyBlacklist.json": FILE,
                            },
                        },
                    },
                },
            },
        },
    },
    "{Gamepass}/": {
        "Palworld/": {
            "Pal/": {
                "Content/": {
                    "Paks/": {
                        "LogicMods/": {
                            "ASD_MercyBlacklist.pak": FILE,
                            "ASD_MercyBlacklist.utoc": FILE,
                            "ASD_MercyBlacklist.ucas": FILE,
                            "Settings/": {
                                "ASD_MercyBlacklist.json": FILE,
                            },
                        },
                    },
                },
            },
        },
    },
}

# --- Altermatic: (STEAM)/(XBOX) variants with LogicMods + ~Mods/SwapJSON ----

ALTERMATIC = {
    "Altermatic - Metadata.txt": FILE,
    "Altermatic - Changelog.txt": FILE,
    "Altermatic - ReadMe.txt": FILE,
    "JSON_Templates/": {
        "AllGlassesCattiva.json": FILE,
        "_Altermatic_TemplateSimple.json": FILE,
        "_Altermatic_TemplateWithExplanations.json": FILE,
    },
    "(STEAM)/": {
        "LogicMods/": {
            "Altermatic.pak": FILE,
        },
        "~Mods/": {
            "SwapJSON/": {
                "__Create_Load_List__MO.bat": FILE,
                "_LoadList.json": FILE,
                "__Create_Load_List__.bat": FILE,
                "_LoadList_Example.json": FILE,
            },
        },
    },
    "(XBOX)/": {
        "LogicMods/": {
            "Altermatic.pak": FILE,
            "Altermatic.utoc": FILE,
            "Altermatic.ucas": FILE,
        },
        "~Mods/": {
            "SwapJSON/": {
                "__Create_Load_List__MO.bat": FILE,
                "_LoadList.json": FILE,
                "__Create_Load_List__.bat": FILE,
                "_LoadList_Example.json": FILE,
            },
        },
    },
}

# --- PalSchema (Okaetsu): UE4SS plugin layout --------------------------------

PALSCHEMA_OKAETSU = {
    "Binaries/": {
        "Win64/": {
            "ue4ss/": {
                "Mods/": {
                    "PalSchema/": {
                        "enabled.txt": FILE,
                        "dlls/": {
                            "main.dll": FILE,
                        },
                    },
                },
            },
        },
    },
}

# --- LevelShield: Lua script mod with extra files ----------------------------

LEVEL_SHIELD = {
    "Level Shield/": {
        "enabled.txt": FILE,
        "Scripts/": {
            "main.lua": FILE,
            "config.lua": FILE,
            "constructors/": {
                "Fguid.lua": FILE,
            },
        },
    },
}
