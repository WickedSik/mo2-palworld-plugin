from __future__ import annotations

from ._base import ModRecognizer
from .altermatic import AltermaticRecognizer
from .lua_script import LuaScriptRecognizer
from .noop import NoopRecognizer
from .pak import PakRecognizer
from .palschema import PalSchemaRecognizer
from .ue4ss import Ue4ssSkipRecognizer
from .ue4ss_plugin import Ue4ssPluginRecognizer

RECOGNIZERS: list[ModRecognizer] = [
    Ue4ssSkipRecognizer(),
    Ue4ssPluginRecognizer(),
    PalSchemaRecognizer(),
    AltermaticRecognizer(),
    LuaScriptRecognizer(),
    PakRecognizer(),
    NoopRecognizer(),
]

RECOGNIZERS.sort(key=lambda r: r.priority)

_names = [r.name for r in RECOGNIZERS]
if len(_names) != len(set(_names)):
    _dupes = [n for n in _names if _names.count(n) > 1]
    raise RuntimeError(
        f"Duplicate recognizer names in registry: {sorted(set(_dupes))}"
    )
