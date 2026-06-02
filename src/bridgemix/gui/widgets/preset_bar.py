"""
Preset save / load bar — sits at the top of the main window.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from bridgemix.preset.manager import load_preset, preset_dir, save_preset

if TYPE_CHECKING:
    from bridgemix.device.bridge_cast import BridgeCast


class PresetBar(QWidget):
    def __init__(self, bridge: "BridgeCast", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bridge = bridge
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)
        preset_lbl = QLabel("Device Settings:")
        preset_lbl.setStyleSheet("color: #7a7a82; font-size: 11px; font-weight: 500;")
        row.addWidget(preset_lbl)

        btn_save = QPushButton("Save…")
        btn_save.clicked.connect(self._save)
        btn_load = QPushButton("Load…")
        btn_load.clicked.connect(self._load)
        row.addWidget(btn_save)
        row.addWidget(btn_load)

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Preset",
            str(preset_dir()),
            "JSON Presets (*.json)",
        )
        if not path:
            return
        save_preset(Path(path), self._bridge.state)
        QMessageBox.information(self, "Saved", f"Preset saved to {path}")

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Preset",
            str(preset_dir()),
            "JSON Presets (*.json)",
        )
        if not path:
            return
        try:
            params = load_preset(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", str(exc))
            return
        for name, value in params.items():
            self._bridge.set_parameter(name, value)
        QMessageBox.information(self, "Loaded", f"Loaded {len(params)} parameters from {path}")
