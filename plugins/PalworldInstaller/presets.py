"""Shared preset constants for PalworldInstaller.

The one place that defines the pak destination presets. Both the
installer's routing logic (``_compute_pak_routing``) and the dialog's
combo-box options read from here. Keeping the lists in one place stops
``installer.py`` and ``ui/dialog.py`` from drifting apart.
"""
from __future__ import annotations


PAK_PRESETS: tuple[str, ...] = ("ROOT", "~mods", "LogicMods")
"""Routing destinations the silent path may use without asking the user."""

PAK_DEST_OPTIONS: tuple[str, ...] = (*PAK_PRESETS, "Custom", "SKIP")
"""All combo-box entries shown by the dialog's per-group selector."""
