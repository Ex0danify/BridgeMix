"""
Reusable bank-slot selector with Load / Write / Save / Revert actions.

File loading handles both BridgeMix-exported format and all Roland native
formats (.brdgcProfile, .brdgcEfx, .brdgcBackup).  Parsed parameters are
emitted via signals; the parent panel connects those signals to the
appropriate bridge calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_LOAD_FILTER = (
    "Roland / BridgeMix (*.brdgcProfile *.brdgcEfx *.brdgcBackup *.json);;"
    "All Files (*)"
)


class ProfileWidget(QGroupBox):
    """Slot-selector + action buttons for a 5-slot bank.

    Parameters
    ----------
    title:
        Group-box header text (e.g. "VOICE FX PRESETS", "PROFILE BANK").
    num_slots:
        Number of slots displayed in the list (default 5).
    load_filter:
        File-dialog filter string for the Load button.

    Signals
    -------
    slot_selected(int)
        User clicked a different slot row (0-based).
    params_loaded(int, dict)
        File was loaded and parsed; carries the **target** slot (0-based) and
        the ``{registry_name: value}`` dict extracted from the file for that
        slot.  The parent applies these via ``bridge.set_parameter()``.
    write_requested(int, str)
        User confirmed Write; carries the slot (0-based) and the name they
        entered.  The parent sequences the name write + slot commit.
    save_requested(int)
        User clicked Save; carries the slot (0-based).  The parent is
        responsible for opening a file dialog, calling
        ``bridge.export_*(slot)``, and writing the file.
    revert_requested(int)
        User confirmed Revert; carries the slot (0-based).  The parent calls
        the appropriate reset method.
    """

    slot_selected     = pyqtSignal(int)
    params_loaded     = pyqtSignal(int, dict)
    write_requested   = pyqtSignal(int, str)
    save_requested    = pyqtSignal(int)
    revert_requested  = pyqtSignal(int)
    library_requested = pyqtSignal()   # only emitted when show_library=True

    def __init__(
        self,
        title: str = "BANK",
        num_slots: int = 5,
        load_filter: str = _DEFAULT_LOAD_FILTER,
        show_library: bool = False,
        show_revert: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._load_filter = load_filter
        self._num_slots = num_slots
        self._busy = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 8)
        outer.setSpacing(6)

        # ── slot list ─────────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setStyleSheet(
            "QListWidget::item { padding: 2px 8px; font-size: 12px; }"
        )
        for i in range(num_slots):
            self._list.addItem(QListWidgetItem(f"{i + 1}  Slot {i + 1}"))
        self._list.setCurrentRow(0)

        row_h = self._list.sizeHintForRow(0)
        if row_h <= 0:
            row_h = 22
        fw = self._list.frameWidth()
        self._list.setFixedHeight(row_h * num_slots + fw * 2)
        self._list.currentRowChanged.connect(self._on_row_changed)
        outer.addWidget(self._list)

        # ── action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_load    = QPushButton("Load")
        self._btn_write   = QPushButton("Write")
        self._btn_save    = QPushButton("Save")
        self._btn_revert  = QPushButton("Revert")
        self._btn_library = QPushButton("Library")

        buttons = [self._btn_load, self._btn_write, self._btn_save]
        if show_revert:
            buttons.append(self._btn_revert)
        else:
            self._btn_revert.hide()
        if show_library:
            buttons.append(self._btn_library)
        else:
            self._btn_library.hide()

        for btn in buttons:
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn_row.addWidget(btn)

        self._btn_load.clicked.connect(self._on_load)
        self._btn_write.clicked.connect(self._on_write)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_revert.clicked.connect(self._on_revert)
        self._btn_library.clicked.connect(lambda: self.library_requested.emit())

        outer.addLayout(btn_row)

    # ── public API ────────────────────────────────────────────────────────────

    def set_slot_names(self, names: list[str]) -> None:
        """Update slot list display names (call with bridge-supplied names)."""
        for i, name in enumerate(names[: self._num_slots]):
            item = self._list.item(i)
            if item:
                item.setText(f"{i + 1}  {name}")

    def set_current_slot(self, slot: int) -> None:
        """Programmatically select a row (0-based) without emitting slot_selected."""
        self._busy = True
        self._list.setCurrentRow(slot)
        self._busy = False

    def current_slot(self) -> int:
        """Return the currently selected slot index (0-based)."""
        return self._list.currentRow()

    def slot_display_name(self, slot: int) -> str:
        """Return the human-readable name for a slot (strips the row-number prefix)."""
        item = self._list.item(slot)
        if item:
            return item.text().split("  ", 1)[-1]
        return f"Slot {slot + 1}"

    # ── slot selection ────────────────────────────────────────────────────────

    def _on_row_changed(self, row: int) -> None:
        if row >= 0 and not self._busy:
            self.slot_selected.emit(row)

    # ── Load ──────────────────────────────────────────────────────────────────

    def _on_load(self) -> None:
        slot = self._list.currentRow()
        if slot < 0:
            return

        path_str, _ = QFileDialog.getOpenFileName(
            self, "Load from File", "", self._load_filter
        )
        if not path_str:
            return

        path = Path(path_str)
        try:
            raw: dict = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", f"Could not read file:\n{exc}")
            return

        # ── BridgeMix native format ───────────────────────────────────────────
        if raw.get("ExportApp") == "BridgeMix":
            params = raw.get("parameters", {})
            if not params:
                QMessageBox.warning(
                    self, "Nothing Loaded", "No parameters found in file."
                )
                return
            self.params_loaded.emit(slot, dict(params))
            return

        # ── Roland native format ──────────────────────────────────────────────
        if raw.get("ExportModelName") != "BRIDGECAST":
            QMessageBox.warning(
                self,
                "Incompatible Format",
                "This file does not appear to be a Roland BridgeCast export.\n\n"
                "Supported formats: .brdgcProfile, .brdgcEfx, .brdgcBackup, "
                "or a BridgeMix JSON file.",
            )
            return

        try:
            from bridgemix.preset.roland_map import parse_roland_file_dict

            slots_data = parse_roland_file_dict(raw)
        except Exception as exc:
            QMessageBox.critical(self, "Parse Failed", str(exc))
            return

        # Roland files use 1-based slot numbers; slot 0 = bare live-state keys
        # (backup only).  Prefer the slot that matches the selected row; fall
        # back to the live-state slot 0 (e.g. loading from a backup file).
        roland_slot = slot + 1
        params = slots_data.get(roland_slot) or slots_data.get(0) or {}

        if not params:
            available = sorted(slots_data.keys())
            QMessageBox.warning(
                self,
                "No Data for Slot",
                f"No data found for Roland slot {roland_slot} in this file.\n"
                f"Available slots in file: {available}",
            )
            return

        self.params_loaded.emit(slot, params)

    # ── Write ─────────────────────────────────────────────────────────────────

    def _on_write(self) -> None:
        slot = self._list.currentRow()
        if slot < 0:
            return
        current_name = self.slot_display_name(slot)
        name, ok = QInputDialog.getText(
            self,
            f"Write to Slot {slot + 1}",
            "Slot name (max 18 characters):",
            text=current_name,
        )
        if not ok:
            return
        self.write_requested.emit(slot, name.strip()[:18])

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        slot = self._list.currentRow()
        if slot >= 0:
            self.save_requested.emit(slot)

    # ── Revert ────────────────────────────────────────────────────────────────

    def _on_revert(self) -> None:
        slot = self._list.currentRow()
        if slot < 0:
            return
        name = self.slot_display_name(slot)
        reply = QMessageBox.question(
            self,
            "Reset to Factory Defaults",
            f'Reset "{name}" (slot {slot + 1}) to factory defaults?\n\n'
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.revert_requested.emit(slot)
