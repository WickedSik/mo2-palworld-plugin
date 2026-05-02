"""UnifiedUI install dialog for PalworldInstaller (M3).

Code review rules enforced in this file:

1. ONE SIGNAL, ONE SLOT. No Qt signal in this dialog connects to more than
   one slot. Verified manually: each combo's currentTextChanged connects
   only to the line-edit toggler for that row; the button box's accepted /
   rejected each connect to exactly one slot.

2. SINGLE RESOLUTION PATH for get_pak_locations(). Read combo first; if
   'Custom', return the line-edit text; else return the combo text. No
   fall-through to a default mid-resolution.

3. SINGLE SOURCE OF TRUTH for routing heuristics is in installer.py
   (_compute_pak_routing). This file does NOT encode any heuristic; it
   accepts the default destinations as constructor input.

4. GROUP-AWARE. Each pak row corresponds to one stem GROUP, not a single
   file. The decisions returned here are stem -> destination; the installer
   expands them across .pak + .utoc + .ucas + associated JSON dirs.
"""
from __future__ import annotations

from typing import List, Tuple

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..presets import PAK_DEST_OPTIONS


class UnifiedUI(QDialog):
    """Three-section install dialog for Palworld archives.

    Sections:
      1. Mod name      -- editable QComboBox seeded with the suggested name
                          and any derived <modname>s from script paths.
      2. Script mods   -- one QCheckBox per detected main.lua. Checked by
                          default when derivation is unambiguous.
      3. Pak groups    -- one row per .pak stem group. Label + destination
                          combo (ROOT / ~mods / LogicMods / Custom / SKIP)
                          + custom-path QLineEdit (enabled only on Custom).

    Public API (positional alignment with constructor inputs):
      - get_new_mod_name()    -> str
      - get_script_statuses() -> list[str]   ('INSTALL' or 'SKIP')
      - get_pak_locations()   -> dict[group_id, str]

    Pak rows are 3-tuples ``(group_id, default_destination, display_label)``.
    A ``default_destination`` that is one of ``ROOT`` / ``~mods`` /
    ``LogicMods`` selects the matching combo entry; anything else (a
    pre-arranged custom path supplied by the SSOT) flips the combo to
    ``Custom`` and pre-fills the line edit with that string.

    A read-only platform indicator at the top of the dialog shows the
    resolved platform from PluginSetting (``steam`` or ``xbox``). Per Q1
    in docs/rebuild.md §6, the dialog never offers a per-install override:
    platform is global per managed game.
    """

    def __init__(
        self,
        parent: QWidget | None,
        suggested_name: str,
        script_rows: List[Tuple[str, str, bool]],
        pak_rows: List[Tuple[str, str, str]],
        platform: str,
    ):
        super().__init__(parent)
        self.setWindowTitle("Palworld Mod Installer")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # --- Platform indicator (read-only) ------------------------------
        # Surfaces the resolved platform from PluginSetting so the user can
        # see which variant the installer will route to. Read-only by design
        # (Q1 resolution): per-install overrides would conflict with the
        # "global per managed game" principle in §5 of docs/rebuild.md.
        platform_label = QLabel(
            f"<b>Platform:</b> {platform.capitalize()} <i>(from settings)</i>"
        )
        layout.addWidget(platform_label)

        # --- Section 1: Mod name -----------------------------------------
        name_group = QGroupBox("Mod name")
        name_layout = QFormLayout(name_group)
        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.addItem(suggested_name)
        seen = {suggested_name}
        for derived_name, _display, _checked in script_rows:
            if derived_name and derived_name not in seen:
                self._name_combo.addItem(derived_name)
                seen.add(derived_name)
        self._name_combo.setCurrentIndex(0)
        name_layout.addRow("Name:", self._name_combo)
        layout.addWidget(name_group)

        # --- Section 2: Script mods --------------------------------------
        self._script_checkboxes: list[QCheckBox] = []
        if script_rows:
            scripts_group = QGroupBox("Script mods (main.lua)")
            scripts_layout = QVBoxLayout(scripts_group)
            for derived_name, display_path, default_checked in script_rows:
                cb = QCheckBox(f"{derived_name}  ({display_path})")
                cb.setChecked(default_checked)
                self._script_checkboxes.append(cb)
                scripts_layout.addWidget(cb)
            layout.addWidget(scripts_group)

        # --- Section 3: Pak groups ---------------------------------------
        self._pak_rows: dict[str, tuple[QComboBox, QLineEdit]] = {}
        if pak_rows:
            pak_group_box = QGroupBox("Pak file groups")
            pak_layout = QVBoxLayout(pak_group_box)
            for group_id, default_dest, display_label in pak_rows:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)

                row_layout.addWidget(QLabel(display_label))

                combo = QComboBox()
                for opt in PAK_DEST_OPTIONS:
                    combo.addItem(opt)

                line_edit = QLineEdit()
                line_edit.setPlaceholderText("custom/path/under/archive/root")

                # Resolve the default: a preset selects the combo entry;
                # anything else flips to Custom and pre-fills the line edit.
                preset_idx = combo.findText(default_dest)
                if preset_idx >= 0:
                    combo.setCurrentIndex(preset_idx)
                else:
                    combo.setCurrentIndex(combo.findText("Custom"))
                    line_edit.setText(default_dest)

                line_edit.setEnabled(combo.currentText() == "Custom")
                row_layout.addWidget(combo)
                row_layout.addWidget(line_edit, 1)

                # Rule 1: ONE SIGNAL, ONE SLOT. The combo's currentTextChanged
                # has exactly one listener -- the per-row line-edit toggler.
                combo.currentTextChanged.connect(
                    lambda value, le=line_edit: le.setEnabled(value == "Custom")
                )

                pak_layout.addWidget(row_widget)
                self._pak_rows[group_id] = (combo, line_edit)
            layout.addWidget(pak_group_box)

        # --- Buttons -----------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- Public API ------------------------------------------------------
    def get_new_mod_name(self) -> str:
        return self._name_combo.currentText()

    def get_script_statuses(self) -> List[str]:
        return [
            "INSTALL" if cb.isChecked() else "SKIP"
            for cb in self._script_checkboxes
        ]

    def get_pak_locations(self) -> dict[str, str]:
        # Rule 2: SINGLE RESOLUTION PATH. Combo first; if 'Custom', return
        # line-edit text; else return combo text. No fall-through. Keys
        # are group_ids -- the unique pak path supplied at construction.
        out: dict[str, str] = {}
        for group_id, (combo, line_edit) in self._pak_rows.items():
            value = combo.currentText()
            out[group_id] = line_edit.text() if value == "Custom" else value
        return out
