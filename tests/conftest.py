"""Pytest conftest: patches sys.modules so plugin imports resolve without
mobase or PyQt6 installed.

Must run before any test module triggers top-level imports from the plugin.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import tests.mobase_mock as mobase_mock

# --- Patch mobase -----------------------------------------------------------

sys.modules["mobase"] = mobase_mock

# --- Patch PyQt6 ------------------------------------------------------------

_pyqt6 = ModuleType("PyQt6")
sys.modules["PyQt6"] = _pyqt6

_qtwidgets = ModuleType("PyQt6.QtWidgets")
for _widget_name in (
    "QCheckBox",
    "QComboBox",
    "QDialog",
    "QDialogButtonBox",
    "QFormLayout",
    "QFrame",
    "QGroupBox",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QScrollArea",
    "QVBoxLayout",
    "QWidget",
):
    setattr(_qtwidgets, _widget_name, MagicMock())

# QDialog.DialogCode.Accepted must be resolvable
_dialog_mock = MagicMock()
_dialog_mock.DialogCode.Accepted = 1
_qtwidgets.QDialog = _dialog_mock
sys.modules["PyQt6.QtWidgets"] = _qtwidgets

_qtcore = ModuleType("PyQt6.QtCore")
_qtcore.QCoreApplication = MagicMock()
_qtcore.Qt = MagicMock()
sys.modules["PyQt6.QtCore"] = _qtcore

# --- Fixtures ----------------------------------------------------------------

import pytest  # noqa: E402


@pytest.fixture
def mock_organizer():
    """Returns a mock IOrganizer with configurable plugin settings."""
    org = mobase_mock.IOrganizer()
    org._settings["PalworldInstaller"] = {
        "enabled": True,
        "prefer_fomod": True,
        "priority": 120,
        "palworld_platform": "steam",
        "palworld_server_platform": "steam",
        "recognizer.palschema.enabled": True,
        "recognizer.altermatic.enabled": True,
        "recognizer.ue4ss_plugin.enabled": True,
        "force_dialog": False,
    }
    return org


@pytest.fixture
def make_installer(mock_organizer):
    """Returns a configured PalworldInstaller instance with mocked base class."""
    from plugins.PalworldInstaller.installer import PalworldInstaller

    installer = PalworldInstaller()
    installer._organizer = mock_organizer
    return installer
