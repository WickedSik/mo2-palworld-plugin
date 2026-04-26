"""Shared preset constants for PalworldInstaller.

Single source of truth for the pak destination presets consumed by both
the installer's routing SSOT (``_compute_pak_routing``) and the dialog's
combo-box options. Keeping the lists here prevents the parallel-table
drift that would otherwise creep in between ``installer.py`` and
``ui/dialog.py``.
"""
from __future__ import annotations


PAK_PRESETS: tuple[str, ...] = ("ROOT", "~mods", "LogicMods")
"""Routing destinations the silent path may emit without user confirmation."""

PAK_DEST_OPTIONS: tuple[str, ...] = (*PAK_PRESETS, "Custom", "SKIP")
"""Full set of combo-box entries shown by the dialog's per-group selector."""
