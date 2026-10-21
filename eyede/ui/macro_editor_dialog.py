"""IDEye - Custom Macro Editor dialog (Phase 8.2)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

try:
    from eyede.core.macro_manager import MacroManager
except ImportError:  # pragma: no cover
    from core.macro_manager import MacroManager


MODE_LABELS = (
    ("coding", "Código"),
    ("writing", "Redacción"),
    ("terminal", "Terminal / Git"),
    ("data_math", "Datos / LaTeX"),
    ("navigation", "Navegación"),
    ("sniper", "FreeLook / Ratón"),
)


class CustomMacroDialog(QDialog):
    """Dark-themed editor for the nine cells of any active mode."""

    def __init__(
        self,
        macro_manager: MacroManager,
        mode_manager: Optional[Any] = None,
        on_apply: Optional[Callable[[str], None]] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.macro_manager = macro_manager
        self.mode_manager = mode_manager
        self.on_apply = on_apply
        self._buttons: Dict[int, QPushButton] = {}
        self._selected_cell: int = 0

        self.setWindowTitle("IDEye - Editor de Macros")
        self.setMinimumSize(680, 520)
        self.setStyleSheet(
            """
            QDialog { background: #0b0f19; color: #e2e8f0; }
            QLabel { color: #cbd5e1; }
            QLineEdit, QTextEdit, QComboBox {
                background: #111827; color: #f8fafc; border: 1px solid #334155;
                border-radius: 6px; padding: 6px;
            }
            QComboBox QAbstractItemView { background: #111827; color: #f8fafc; }
            QPushButton {
                background: #1e293b; color: #e2e8f0; border: 1px solid #475569;
                border-radius: 6px; padding: 8px;
            }
            QPushButton:hover { border-color: #38bdf8; }
            QPushButton#cellActive { border: 2px solid #f43f5e; background: #2a1018; }
            QPushButton#cellProtected { color: #64748b; }
            QPushButton#saveButton { background: #065f46; border-color: #10b981; font-weight: bold; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("EDITOR DE MACROS PERSONALIZADAS")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        root.addWidget(title)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Modo:"))
        self.combo_mode = QComboBox(self)
        for mode_id, label in MODE_LABELS:
            self.combo_mode.addItem(label, mode_id)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.combo_mode, stretch=1)
        root.addLayout(mode_row)

        self.grid = QGridLayout()
        self.grid.setSpacing(6)
        for idx in range(9):
            btn = QPushButton(f"Celda {idx + 1}", self)
            btn.setMinimumHeight(54)
            btn.clicked.connect(lambda _checked=False, i=idx: self._select_cell(i))
            if idx in MacroManager.PROTECTED_CELLS:
                btn.setObjectName("cellProtected")
                btn.setEnabled(False)
                btn.setText("PAUSA" if idx == 4 else "VOLVER")
            self._buttons[idx] = btn
            self.grid.addWidget(btn, idx // 3, idx % 3)
        root.addLayout(self.grid)

        form = QVBoxLayout()
        form.addWidget(QLabel("Título"))
        self.edit_label = QLineEdit(self)
        form.addWidget(self.edit_label)
        form.addWidget(QLabel("Subtítulo"))
        self.edit_subtitle = QLineEdit(self)
        form.addWidget(self.edit_subtitle)
        form.addWidget(QLabel("Tipo de acción"))
        self.combo_action = QComboBox(self)
        self.combo_action.addItem("Snippet de texto", "snippet")
        self.combo_action.addItem("Comando de terminal", "command")
        self.combo_action.addItem("Atajo OS", "key")
        form.addWidget(self.combo_action)
        form.addWidget(QLabel("Contenido / Payload"))
        self.edit_payload = QTextEdit(self)
        self.edit_payload.setMinimumHeight(90)
        form.addWidget(self.edit_payload)
        root.addLayout(form)

        actions = QHBoxLayout()
        self.btn_save = QPushButton("Guardar y aplicar", self)
        self.btn_save.setObjectName("saveButton")
        self.btn_save.clicked.connect(self._save_current)
        actions.addWidget(self.btn_save)
        self.btn_clear = QPushButton("Restaurar celda", self)
        self.btn_clear.clicked.connect(self._clear_current)
        actions.addWidget(self.btn_clear)
        root.addLayout(actions)

        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("color: #94a3b8;")
        root.addWidget(self.lbl_status)

        self._on_mode_changed()

    # ------------------------------------------------------------------
    def _current_mode(self) -> str:
        return str(self.combo_mode.currentData() or "coding")

    def _default_node(self, mode_id: str):
        if self.mode_manager is not None:
            try:
                mode = self.mode_manager.get_mode(mode_id)
                return mode.get_root_menu()
            except Exception:
                pass
        return None

    def _on_mode_changed(self) -> None:
        self._selected_cell = 0
        self._refresh_grid()
        self._select_cell(0)

    def _refresh_grid(self) -> None:
        mode = self._current_mode()
        cells = self.macro_manager.get_cells(mode)
        default = self._default_node(mode)
        for idx, btn in self._buttons.items():
            if idx in MacroManager.PROTECTED_CELLS:
                continue
            if str(idx) in cells:
                btn.setText(f"{idx + 1}: {cells[str(idx)]['label']}")
            elif default is not None and idx < len(default.items):
                btn.setText(default.items[idx].label)
            else:
                btn.setText(f"Celda {idx + 1}")

    def _select_cell(self, idx: int) -> None:
        if idx in MacroManager.PROTECTED_CELLS:
            return
        self._selected_cell = idx
        for i, btn in self._buttons.items():
            btn.setObjectName("cellActive" if i == idx else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        mode = self._current_mode()
        cells = self.macro_manager.get_cells(mode)
        cell = cells.get(str(idx))
        if cell is None:
            default = self._default_node(mode)
            if default is not None and idx < len(default.items):
                item = default.items[idx]
                self.edit_label.setText(item.label)
                self.edit_subtitle.setText(item.hint)
                self.edit_payload.setPlainText(item.snippet or item.key_name or "")
                self.combo_action.setCurrentIndex(max(0, self.combo_action.findData("snippet")))
            else:
                self.edit_label.setText(f"Celda {idx + 1}")
                self.edit_subtitle.clear()
                self.edit_payload.clear()
        else:
            self.edit_label.setText(cell.get("label", ""))
            self.edit_subtitle.setText(cell.get("subtitle", ""))
            self.edit_payload.setPlainText(cell.get("payload", ""))
            index = self.combo_action.findData(cell.get("action_type", "snippet"))
            self.combo_action.setCurrentIndex(max(0, index))

    def _save_current(self) -> None:
        data = {
            "label": self.edit_label.text().strip(),
            "subtitle": self.edit_subtitle.text().strip(),
            "icon": "code",
            "action_type": self.combo_action.currentData() or "snippet",
            "payload": self.edit_payload.toPlainText(),
        }
        if not data["label"]:
            self.lbl_status.setText("El título no puede estar vacío.")
            return
        ok = self.macro_manager.save_macro(
            self._current_mode(), self._selected_cell, data
        )
        self.lbl_status.setText("Guardado y aplicado." if ok else "No se pudo guardar.")
        if ok:
            self._refresh_grid()
            if self.on_apply is not None:
                self.on_apply(self._current_mode())

    def _clear_current(self) -> None:
        self.macro_manager.delete_macro(self._current_mode(), self._selected_cell)
        self._refresh_grid()
        self._select_cell(self._selected_cell)
        self.lbl_status.setText("Celda restaurada al valor por defecto.")
        if self.on_apply is not None:
            self.on_apply(self._current_mode())
