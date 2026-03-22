"""
edit_panel.py — Panel de edición embebido en el overlay.
Permite gestionar perfiles y atajos con una interfaz táctil amigable.
"""

import copy
import json
import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
_log = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QLineEdit, QColorDialog,
    QDialogButtonBox, QScrollArea, QFrame, QSizePolicy, QInputDialog,
    QMessageBox, QComboBox, QFileDialog
)


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades de estilo
# ──────────────────────────────────────────────────────────────────────────────
BTN_STYLE_PRIMARY = """
    QPushButton {
        background: #2980B9;
        color: white;
        border-radius: 7px;
        font-size: 12px;
        font-weight: bold;
        padding: 6px 10px;
        border: none;
    }
    QPushButton:pressed { background: #1a5f8a; }
    QPushButton:disabled { background: #555; color: #999; }
"""

BTN_STYLE_SUCCESS = """
    QPushButton {
        background: #27AE60;
        color: white;
        border-radius: 7px;
        font-size: 12px;
        font-weight: bold;
        padding: 6px 10px;
        border: none;
    }
    QPushButton:pressed { background: #1e8449; }
"""

BTN_STYLE_DANGER = """
    QPushButton {
        background: #C0392B;
        color: white;
        border-radius: 7px;
        font-size: 11px;
        font-weight: bold;
        padding: 4px 8px;
        border: none;
    }
    QPushButton:pressed { background: #922b21; }
"""

BTN_STYLE_NEUTRAL = """
    QPushButton {
        background: #555;
        color: white;
        border-radius: 7px;
        font-size: 11px;
        font-weight: bold;
        padding: 4px 8px;
        border: none;
    }
    QPushButton:pressed { background: #333; }
"""

BTN_STYLE_EXPORT = """
    QPushButton {
        background: #5d6d7e;
        color: white;
        border-radius: 7px;
        font-size: 11px;
        font-weight: bold;
        padding: 4px 8px;
        border: none;
    }
    QPushButton:pressed { background: #3d4d5e; }
"""

LABEL_STYLE = "color: #cccccc; font-size: 11px;"
TITLE_STYLE = "color: #ffffff; font-size: 12px; font-weight: bold;"

SCROLL_STYLE = """
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical {
        background: #2a2a2a; width: 8px; border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #555; border-radius: 4px; min-height: 20px;
    }
"""

ITEM_FRAME_STYLE = """
    QFrame {
        background: #2a2a36;
        border-radius: 7px;
        border: 1px solid #444;
    }
"""

INPUT_STYLE = """
    QLineEdit {
        background: #2d2d3a;
        color: white;
        border: 1px solid #555;
        border-radius: 6px;
        padding: 5px 8px;
        font-size: 12px;
    }
    QLineEdit:focus { border-color: #4a90d9; }
"""

COMBO_STYLE = """
    QComboBox {
        background: #3a3a3a; color: white;
        border: 1px solid #555; border-radius: 6px;
        padding: 4px 8px; font-size: 12px;
    }
    QComboBox::drop-down { border: none; }
    QComboBox QAbstractItemView {
        background: #2d2d2d; color: white;
        selection-background-color: #4a90d9;
    }
"""

MOD_BTN_STYLE = """
    QPushButton {
        background: #3a3a3a; color: #aaa;
        border: 1px solid #555; border-radius: 5px;
        font-size: 11px; font-weight: bold; padding: 2px 6px;
    }
    QPushButton:checked {
        background: #2471a3; color: white; border-color: #4a90d9;
    }
    QPushButton:hover { background: #4a4a4a; }
    QPushButton:checked:hover { background: #1a6090; }
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de diálogo — siempre aparecen encima del overlay (WindowStaysOnTopHint)
# ──────────────────────────────────────────────────────────────────────────────
def _create_msgbox(title: str, text: str, icon, buttons) -> QMessageBox:
    """Base común para todos los helpers de diálogo.
    NO se pasa parent al constructor: evita heredar WA_TranslucentBackground
    del OverlayWindow, que haría el fondo negro.
    """
    box = QMessageBox()
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(icon)
    box.setStandardButtons(buttons)
    box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    box.setAttribute(Qt.WA_TranslucentBackground, False)
    return box


def _dlg_question(parent, title: str, text: str) -> int:
    return _create_msgbox(title, text, QMessageBox.Question,
                          QMessageBox.Yes | QMessageBox.No).exec_()


def _dlg_info(parent, title: str, text: str):
    _create_msgbox(title, text, QMessageBox.Information, QMessageBox.Ok).exec_()


def _dlg_warning(parent, title: str, text: str):
    _create_msgbox(title, text, QMessageBox.Warning, QMessageBox.Ok).exec_()


def _dlg_critical(parent, title: str, text: str):
    _create_msgbox(title, text, QMessageBox.Critical, QMessageBox.Ok).exec_()


def _dlg_get_text(parent, title: str, label: str, default: str = "") -> tuple:
    """
    Equivalente a QInputDialog.getText visible sobre el overlay.
    Sin parent para evitar heredar WA_TranslucentBackground.
    """
    dlg = QInputDialog()
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setTextValue(default)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setAttribute(Qt.WA_TranslucentBackground, False)
    ok = (dlg.exec_() == QDialog.Accepted)
    return dlg.textValue(), ok


# ──────────────────────────────────────────────────────────────────────────────
# DragHandle — asa táctil para reordenar atajos arrastrando
# ──────────────────────────────────────────────────────────────────────────────
class DragHandle(QLabel):
    """
    Asa de arrastre vertical (≡). Captura mouse press/move/release
    y delega al EditPanel para que gestione el estado de drag.
    grabMouse() asegura que los eventos llegan aunque el dedo salga del widget.
    """

    def __init__(self, item_index: int, parent_item, edit_panel):
        super().__init__("≡", parent_item)
        self._ep = edit_panel
        self._index = item_index
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(28, 40)
        self.setCursor(Qt.SizeVerCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "color: #666; font-size: 16px; font-weight: bold; "
            "background: transparent; border-radius: 4px;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.grabMouse()
            self._ep._on_drag_start(self._index, event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self._ep._on_drag_move(event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.releaseMouse()
            self._ep._on_drag_release()
        super().mouseReleaseEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# _DropContainer — contenedor de la lista con indicador visual de drop
# ──────────────────────────────────────────────────────────────────────────────
class _DropContainer(QWidget):
    """
    Reemplaza el QWidget simple de _list_container.
    Sobrescribe paintEvent para dibujar la línea azul de inserción
    durante el drag & drop.
    """

    def __init__(self, edit_panel_ref, parent=None):
        super().__init__(parent)
        self._ep = edit_panel_ref
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        super().paintEvent(event)
        if not getattr(self._ep, '_drag_active', False):
            return
        idx = self._ep._drag_current_index
        n = self._ep._list_layout.count() - 1   # -1 por addStretch al final
        if idx < 0 or n <= 0:
            return

        # Calcular la Y donde se dibuja el indicador de inserción
        if idx == 0:
            y = 2
        elif idx >= n:
            last_item = self._ep._list_layout.itemAt(n - 1)
            if last_item and last_item.widget():
                lw = last_item.widget()
                y = lw.y() + lw.height() + 2
            else:
                return
        else:
            wa_item = self._ep._list_layout.itemAt(idx - 1)
            wb_item = self._ep._list_layout.itemAt(idx)
            if not (wa_item and wb_item and wa_item.widget() and wb_item.widget()):
                return
            wa, wb = wa_item.widget(), wb_item.widget()
            y = (wa.y() + wa.height() + wb.y()) // 2

        # Dibujar línea azul con círculos en los extremos
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#4a90d9"), 2))
        painter.drawLine(12, y, self.width() - 12, y)
        painter.setBrush(QColor("#4a90d9"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, y - 4, 8, 8)
        painter.drawEllipse(self.width() - 12, y - 4, 8, 8)


# ──────────────────────────────────────────────────────────────────────────────
# ShortcutEditDialog — diálogo para agregar/editar un atajo  (S6: tipo URL/App)
# ──────────────────────────────────────────────────────────────────────────────
class ShortcutEditDialog(QDialog):
    """Diálogo táctil para crear o editar un atajo (hotkey, URL o App)."""

    # Mapeo tipo interno → índice del combo
    _TYPE_TO_IDX = {"hotkey": 0, "url": 1, "app": 2}
    _IDX_TO_TYPE = {0: "hotkey", 1: "url", 2: "app"}

    # VK codes de Windows para modificadores lado derecho
    _RIGHT_VK = {0xA1: "shiftright", 0xA3: "ctrlright", 0xA5: "altright"}

    # Orden canónico al reconstruir el string de atajo (Win primero, como es convención)
    _MOD_ORDER = ["win", "ctrl", "ctrlright", "alt", "altright", "shift", "shiftright"]
    # Pares mutuamente excluyentes (izquierdo ↔ derecho)
    _MOD_PAIRS = [("ctrl", "ctrlright"), ("alt", "altright"), ("shift", "shiftright")]

    def __init__(self, parent=None, label="", hotkey="", color="#2980B9",
                 btn_type="hotkey", action=""):
        super().__init__(parent)
        self._color = color
        self._recording = False
        self._mod_btns: dict = {}
        self._mod_active: dict = {m: False for m in self._MOD_ORDER}

        self.setWindowTitle("Configurar Botón")
        self.setModal(True)
        self.setMinimumWidth(340)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)   # evita fondo negro
        self.setStyleSheet("""
            QDialog {
                background: #1e1e2a;
                color: white;
            }
            QLabel { color: #cccccc; font-size: 12px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Tipo de botón (S6) ────────────────────────────────────────────────
        layout.addWidget(QLabel("Tipo de botón:"))
        self._type_combo = QComboBox()
        self._type_combo.setFocusPolicy(Qt.NoFocus)
        self._type_combo.addItems(["⌨ Hotkey", "🌐 URL", "📂 App / Comando"])
        self._type_combo.setCurrentIndex(self._TYPE_TO_IDX.get(btn_type, 0))
        self._type_combo.setStyleSheet(COMBO_STYLE)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self._type_combo)

        # ── Etiqueta ──────────────────────────────────────────────────────────
        layout.addWidget(QLabel("Etiqueta del botón:"))
        self._label_edit = QLineEdit(label)
        self._label_edit.setPlaceholderText("ej: Copiar")
        self._label_edit.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self._label_edit)

        # ── Campo de acción / hotkey ───────────────────────────────────────────
        self._action_label = QLabel("Combinación de teclas:")
        layout.addWidget(self._action_label)

        # Fila: campo de texto editable + botón limpiar
        hotkey_row = QHBoxLayout()
        initial_value = hotkey if btn_type == "hotkey" else action
        self._hotkey_edit = QLineEdit(initial_value)
        self._hotkey_edit.setStyleSheet(INPUT_STYLE)
        hotkey_row.addWidget(self._hotkey_edit, 1)
        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(30, 36)
        clear_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        clear_btn.setFocusPolicy(Qt.NoFocus)
        clear_btn.setToolTip("Limpiar atajo")
        clear_btn.clicked.connect(self._clear_hotkey)
        hotkey_row.addWidget(clear_btn)
        layout.addLayout(hotkey_row)

        # ── Compositor visual (modificadores + selector de tecla) ──────────────
        self._mod_widget = QWidget()
        mod_vbox = QVBoxLayout(self._mod_widget)
        mod_vbox.setContentsMargins(0, 4, 0, 0)
        mod_vbox.setSpacing(4)

        # Fila 1: modificadores estándar
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        for mod, lbl in [("ctrl", "Ctrl"), ("alt", "Alt"), ("shift", "Shift"), ("win", "Win")]:
            row1.addWidget(self._make_mod_btn(mod, lbl))
        mod_vbox.addLayout(row1)

        # Fila 2: modificadores lado derecho
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        for mod, lbl in [("altright", "AltGr"), ("shiftright", "RShift"), ("ctrlright", "RCtrl")]:
            row2.addWidget(self._make_mod_btn(mod, lbl))
        row2.addStretch()
        mod_vbox.addLayout(row2)

        # Fila 3: selector de tecla + botón grabar
        key_row = QHBoxLayout()
        key_row.setSpacing(4)
        self._key_picker = QComboBox()
        self._key_picker.setFocusPolicy(Qt.NoFocus)
        self._key_picker.setStyleSheet(COMBO_STYLE)
        self._key_picker.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._populate_key_picker()
        self._key_picker.currentIndexChanged.connect(self._rebuild_hotkey)
        key_row.addWidget(self._key_picker, 1)

        self._record_btn = QPushButton("🔴 Grabar")
        self._record_btn.setFocusPolicy(Qt.StrongFocus)
        self._record_btn.setFixedHeight(36)
        self._record_btn.setMinimumWidth(80)
        self._record_btn.setStyleSheet(BTN_STYLE_DANGER)
        self._record_btn.setToolTip("Presiona la combinación en tu teclado físico")
        self._record_btn.clicked.connect(self._toggle_recording)
        key_row.addWidget(self._record_btn)
        mod_vbox.addLayout(key_row)

        layout.addWidget(self._mod_widget)

        self._record_hint = QLabel("")
        self._record_hint.setStyleSheet("color: #f39c12; font-size: 11px; font-style: italic;")
        layout.addWidget(self._record_hint)

        # Inicializar toggles si el valor inicial es un hotkey
        if btn_type == "hotkey" and initial_value:
            self._parse_hotkey_to_ui(initial_value)

        # ── Color ──────────────────────────────────────────────────────────────
        layout.addWidget(QLabel("Color del botón:"))
        color_row = QHBoxLayout()
        self._color_preview = QPushButton()
        self._color_preview.setFixedSize(40, 36)
        self._color_preview.setFocusPolicy(Qt.NoFocus)
        self._color_preview.setToolTip("Toca para cambiar el color")
        self._color_preview.clicked.connect(self._pick_color)
        color_row.addWidget(self._color_preview)
        self._color_label = QLabel(color)
        self._color_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        color_row.addWidget(self._color_label)
        color_row.addStretch()

        # Preview del botón resultante
        self._preview_btn = QPushButton(label or "Ejemplo")
        self._preview_btn.setFocusPolicy(Qt.NoFocus)
        self._preview_btn.setFixedSize(90, 58)
        self._preview_btn.setEnabled(False)
        color_row.addWidget(self._preview_btn)

        layout.addLayout(color_row)
        self._update_color_ui(color)

        # Conectar actualizaciones del preview
        self._label_edit.textChanged.connect(self._update_preview_label)
        self._hotkey_edit.textChanged.connect(self._update_preview_hotkey)

        # ── Botones OK/Cancelar ────────────────────────────────────────────────
        layout.addSpacing(4)
        ok_btn = QPushButton("✔  Guardar")
        ok_btn.setStyleSheet(BTN_STYLE_SUCCESS)
        ok_btn.setMinimumHeight(38)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        cancel_btn.setMinimumHeight(38)
        ok_btn.clicked.connect(self._on_accept)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(ok_btn)
        layout.addWidget(cancel_btn)

        # Aplicar estado visual del tipo inicial
        self._on_type_changed(self._TYPE_TO_IDX.get(btn_type, 0))

    # ── Cambio de tipo (S6) ───────────────────────────────────────────────────

    def _on_type_changed(self, index: int):
        """Actualiza etiqueta, placeholder y visibilidad del compositor de hotkey."""
        labels       = ["Combinación de teclas:", "URL:", "Comando o ruta del ejecutable:"]
        placeholders = [
            "ej: ctrl+c  o  ctrl+shift+p",
            "ej: https://google.com",
            "ej: code   o   C:\\Apps\\prog.exe",
        ]
        self._action_label.setText(labels[index])
        self._hotkey_edit.setPlaceholderText(placeholders[index])
        # El compositor visual (modificadores + selector) solo aplica a Hotkey
        self._mod_widget.setVisible(index == 0)
        if index != 0:
            self._recording = False
            self._record_hint.setText("")

    # ── Grabación de tecla ────────────────────────────────────────────────────

    def _toggle_recording(self):
        self._recording = not self._recording
        self._right_mods_held = set()
        self._right_mods_order = []
        if self._recording:
            self._record_btn.setText("⏹ Grabando…")
            self._record_btn.setStyleSheet("""
                QPushButton {
                    background: #f39c12; color: white; border-radius: 7px;
                    font-size: 12px; font-weight: bold; padding: 6px 10px; border: none;
                }
            """)
            self._record_hint.setText("Ahora presiona la combinación de teclas en tu teclado...")
            self._hotkey_edit.clear()
            self.setFocus()
        else:
            self._record_btn.setText("🔴 Grabar")
            self._record_btn.setStyleSheet(BTN_STYLE_DANGER)
            self._record_hint.setText("")

    def event(self, event):
        """Override para capturar Tab y teclas especiales (y KeyRelease) durante la grabación."""
        from PyQt5.QtCore import QEvent
        if self._recording:
            if event.type() == QEvent.KeyPress:
                self.keyPressEvent(event)
                event.accept()
                return True
            if event.type() == QEvent.KeyRelease:
                self._on_key_release_recording(event)
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        if not self._recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        vk  = event.nativeVirtualKey()

        # Modificador presionado → acumular si es lado derecho, ignorar si es izquierdo
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_AltGr, Qt.Key_Meta):
            if vk in self._RIGHT_VK and vk not in self._right_mods_held:
                self._right_mods_held.add(vk)
                self._right_mods_order.append(vk)
            return

        if key == Qt.Key_unknown:
            return

        # Tecla principal presionada → finalizar combo
        mods = event.modifiers()
        parts = []
        if mods & Qt.ControlModifier:
            parts.append("ctrlright" if 0xA3 in self._right_mods_held else "ctrl")
        if mods & Qt.AltModifier:
            parts.append("altright"  if 0xA5 in self._right_mods_held else "alt")
        if mods & Qt.ShiftModifier:
            parts.append("shiftright" if 0xA1 in self._right_mods_held else "shift")
        if mods & Qt.MetaModifier:
            parts.append("win")

        key_name = self._qt_key_to_str(key)
        if key_name:
            parts.append(key_name)

        if parts:
            self._finish_recording("+".join(parts))

    def _on_key_release_recording(self, event):
        """Finaliza la grabación cuando se suelta un modificador-derecha sin haber pulsado otra tecla."""
        vk = event.nativeVirtualKey()
        if vk not in self._RIGHT_VK or vk not in self._right_mods_held:
            return
        self._right_mods_held.discard(vk)
        # Si ya no queda ningún modificador → grabar el combo de mods solos
        remaining = event.modifiers() & (Qt.ControlModifier | Qt.AltModifier |
                                         Qt.ShiftModifier | Qt.MetaModifier)
        if not self._right_mods_held and not remaining:
            parts = [self._RIGHT_VK[v] for v in self._right_mods_order if v in self._RIGHT_VK]
            if parts:
                self._finish_recording("+".join(parts))

    def _finish_recording(self, hotkey: str):
        self._recording = False
        self._right_mods_held = set()
        self._right_mods_order = []
        self._record_btn.setText("🔴 Grabar")
        self._record_btn.setStyleSheet(BTN_STYLE_DANGER)
        self._record_hint.setText(f"Grabado: {hotkey}")
        self._parse_hotkey_to_ui(hotkey)  # sincroniza toggles y selector

    @staticmethod
    def _qt_key_to_str(key: int) -> str:
        mapping = {
            Qt.Key_A: "a", Qt.Key_B: "b", Qt.Key_C: "c", Qt.Key_D: "d",
            Qt.Key_E: "e", Qt.Key_F: "f", Qt.Key_G: "g", Qt.Key_H: "h",
            Qt.Key_I: "i", Qt.Key_J: "j", Qt.Key_K: "k", Qt.Key_L: "l",
            Qt.Key_M: "m", Qt.Key_N: "n", Qt.Key_O: "o", Qt.Key_P: "p",
            Qt.Key_Q: "q", Qt.Key_R: "r", Qt.Key_S: "s", Qt.Key_T: "t",
            Qt.Key_U: "u", Qt.Key_V: "v", Qt.Key_W: "w", Qt.Key_X: "x",
            Qt.Key_Y: "y", Qt.Key_Z: "z",
            Qt.Key_0: "0", Qt.Key_1: "1", Qt.Key_2: "2", Qt.Key_3: "3",
            Qt.Key_4: "4", Qt.Key_5: "5", Qt.Key_6: "6", Qt.Key_7: "7",
            Qt.Key_8: "8", Qt.Key_9: "9",
            Qt.Key_F1: "f1", Qt.Key_F2: "f2", Qt.Key_F3: "f3", Qt.Key_F4: "f4",
            Qt.Key_F5: "f5", Qt.Key_F6: "f6", Qt.Key_F7: "f7", Qt.Key_F8: "f8",
            Qt.Key_F9: "f9", Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
            Qt.Key_Tab: "tab", Qt.Key_Return: "enter", Qt.Key_Enter: "enter",
            Qt.Key_Escape: "esc", Qt.Key_Space: "space", Qt.Key_Delete: "delete",
            Qt.Key_Backspace: "backspace", Qt.Key_Insert: "insert",
            Qt.Key_Home: "home", Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup", Qt.Key_PageDown: "pagedown",
            Qt.Key_Left: "left", Qt.Key_Right: "right",
            Qt.Key_Up: "up", Qt.Key_Down: "down",
            Qt.Key_Print: "printscreen", Qt.Key_Pause: "pause",
            Qt.Key_QuoteLeft: "grave",
            Qt.Key_Slash: "slash", Qt.Key_Backslash: "backslash",
            Qt.Key_Plus: "plus", Qt.Key_Minus: "minus",
            Qt.Key_Equal: "=", Qt.Key_BracketLeft: "[", Qt.Key_BracketRight: "]",
            Qt.Key_Semicolon: ";", Qt.Key_Apostrophe: "'", Qt.Key_Comma: ",",
            Qt.Key_Period: ".", Qt.Key_NumberSign: "#",
        }
        return mapping.get(key, "")

    # ── Compositor visual de hotkeys ──────────────────────────────────────────

    def _make_mod_btn(self, mod: str, label: str) -> QPushButton:
        """Crea un botón de modificador checkable y lo registra en _mod_btns."""
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedHeight(28)
        btn.setStyleSheet(MOD_BTN_STYLE)
        btn.clicked.connect(lambda checked, m=mod: self._on_mod_toggle(m, checked))
        self._mod_btns[mod] = btn
        return btn

    def _on_mod_toggle(self, mod: str, checked: bool):
        """Activa/desactiva un modificador; desactiva el par opuesto si aplica."""
        for a, b in self._MOD_PAIRS:
            if mod == a and checked:
                self._set_mod(b, False)
            elif mod == b and checked:
                self._set_mod(a, False)
        self._mod_active[mod] = checked
        self._rebuild_hotkey()

    def _set_mod(self, mod: str, active: bool):
        """Actualiza estado y botón de un modificador sin disparar rebuild."""
        self._mod_active[mod] = active
        btn = self._mod_btns.get(mod)
        if btn:
            btn.setChecked(active)

    def _populate_key_picker(self):
        """Rellena el selector de tecla con grupos de opciones."""
        self._key_picker.addItem("— tecla —", "")
        groups = [
            ("Letras",    [(c.upper(), c) for c in "abcdefghijklmnopqrstuvwxyz"]),
            ("Números",   [(str(i), str(i)) for i in range(10)]),
            ("Función",   [(f"F{i}", f"f{i}") for i in range(1, 13)]),
            ("Flechas",   [("← Izq", "left"), ("→ Der", "right"),
                            ("↑ Arr", "up"),  ("↓ Abj", "down")]),
            ("Numpad",    [(f"Num {i}", f"num{i}") for i in range(10)] + [
                            ("Num +", "num+"), ("Num −", "num-"),
                            ("Num *", "num*"), ("Num /", "num/")]),
            ("Especiales", [
                ("Space",      "space"),    ("Tab",        "tab"),
                ("Enter",      "enter"),    ("Esc",        "esc"),
                ("Supr",       "delete"),   ("Retroceso",  "backspace"),
                ("Inicio",     "home"),     ("Fin",        "end"),
                ("Re Pág",     "pageup"),   ("Av Pág",     "pagedown"),
                ("Insert",     "insert"),   ("Impr Pant",  "printscreen"),
                ("Pausa",      "pause"),
            ]),
            ("Símbolo",   [
                (".",  "."), (",",  ","),  (";", ";"), ("'", "'"),
                ("-",  "minus"), ("+", "plus"), ("=", "="),
                ("[",  "["),  ("]",  "]"),
                ("` (grave)", "grave"), ("/  (slash)", "slash"),
                ("\\ (backslash)", "backslash"),
            ]),
        ]
        model = self._key_picker.model()
        for group_name, items in groups:
            self._key_picker.addItem(f"── {group_name} ──", None)
            model.item(self._key_picker.count() - 1).setEnabled(False)
            for display, value in items:
                self._key_picker.addItem(display, value)

    def _rebuild_hotkey(self):
        """Reconstruye el campo de texto a partir del estado de modificadores + selector."""
        if self._type_combo.currentIndex() != 0:
            return
        parts = [m for m in self._MOD_ORDER if self._mod_active.get(m)]
        key = self._key_picker.currentData()
        if key:
            parts.append(key)
        self._hotkey_edit.setText("+".join(parts))

    def _parse_hotkey_to_ui(self, hotkey_str: str):
        """Parsea un string de atajo y actualiza los toggles y el selector."""
        # Resetear estado actual sin disparar rebuild
        for m in self._MOD_ORDER:
            self._set_mod(m, False)
        # Bloquear señal del picker durante el parse para no disparar rebuild prematuro
        self._key_picker.blockSignals(True)
        self._key_picker.setCurrentIndex(0)
        self._key_picker.blockSignals(False)

        parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
        key_found = False
        for part in parts:
            if part in self._mod_active:
                self._set_mod(part, True)
            else:
                # Buscar en el picker
                for i in range(self._key_picker.count()):
                    if self._key_picker.itemData(i) == part:
                        self._key_picker.blockSignals(True)
                        self._key_picker.setCurrentIndex(i)
                        self._key_picker.blockSignals(False)
                        key_found = True
                        break
        # Actualizar el campo de texto con el estado final
        self._rebuild_hotkey()
        # Si el campo quedó vacío pero había texto original, restaurarlo
        if not self._hotkey_edit.text() and hotkey_str:
            self._hotkey_edit.setText(hotkey_str)

    def _clear_hotkey(self):
        """Limpia el atajo y resetea todos los controles."""
        self._hotkey_edit.clear()
        for m in list(self._mod_active):
            self._set_mod(m, False)
        self._key_picker.blockSignals(True)
        self._key_picker.setCurrentIndex(0)
        self._key_picker.blockSignals(False)
        self._record_hint.setText("")

    # ── Color ──────────────────────────────────────────────────────────────────

    def _pick_color(self):
        # Sin parent para evitar heredar WA_TranslucentBackground del overlay
        color = QColorDialog.getColor(QColor(self._color), None, "Elegir color del botón")
        if color.isValid():
            self._color = color.name()
            self._update_color_ui(self._color)

    def _update_color_ui(self, color: str):
        self._color_preview.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                border-radius: 6px;
                border: 2px solid #888;
            }}
        """)
        self._color_label.setText(color)
        self._update_preview_style()

    def _update_preview_style(self):
        lbl = self._label_edit.text() or "Ejemplo"
        self._preview_btn.setText(lbl)
        self._preview_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._color};
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 8px;
                border: none;
            }}
        """)

    def _update_preview_label(self, text: str):
        self._preview_btn.setText(text or "Ejemplo")

    def _update_preview_hotkey(self, text: str):
        pass  # podría usarse para preview extra

    # ── Aceptar ────────────────────────────────────────────────────────────────

    def _on_accept(self):
        if not self._label_edit.text().strip():
            self._label_edit.setStyleSheet(INPUT_STYLE + "QLineEdit { border-color: #E74C3C; }")
            return
        if not self._hotkey_edit.text().strip():
            self._hotkey_edit.setStyleSheet(INPUT_STYLE + "QLineEdit { border-color: #E74C3C; }")
            return
        self.accept()

    def get_data(self) -> dict:
        """Retorna el dict del botón según el tipo seleccionado."""
        idx = self._type_combo.currentIndex()
        label = self._label_edit.text().strip()
        color = self._color
        value = self._hotkey_edit.text().strip()

        if idx == 1:   # URL
            return {"label": label, "type": "url", "action": value, "color": color}
        elif idx == 2: # App
            return {"label": label, "type": "app", "action": value, "color": color}
        else:          # Hotkey (sin campo "type" para compatibilidad con perfiles existentes)
            return {"label": label, "hotkey": value.lower(), "color": color}


# ──────────────────────────────────────────────────────────────────────────────
# ShortcutItemWidget — fila individual en el panel de edición  (S6: URL/App; S7: separator)
# ──────────────────────────────────────────────────────────────────────────────
class ShortcutItemWidget(QFrame):
    """
    Representa un ítem en la lista del panel de edición.
    Puede ser: hotkey normal, URL, App, o separador visual.
    """

    edit_requested      = pyqtSignal(int)
    duplicate_requested = pyqtSignal(int)
    delete_requested    = pyqtSignal(int)

    def __init__(self, index: int, data: dict, edit_panel=None, parent=None):
        super().__init__(parent)
        self._index = index
        self._data = data
        self._is_separator = (data.get("type") == "separator")

        if self._is_separator:
            self._build_separator_ui()
        else:
            self._build_normal_ui(data, edit_panel)

    def _build_separator_ui(self):
        """UI simplificada para un separador: línea + etiqueta + botón eliminar."""
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.setFixedHeight(28)

        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(6)

        # Línea decorativa
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #555555; background-color: #555555;")
        line.setFixedHeight(2)
        h.addWidget(line, 1)

        lbl = QLabel("── Separador ──")
        lbl.setStyleSheet("color: #666666; font-size: 10px;")
        h.addWidget(lbl)

        del_btn = QPushButton("🗑")
        del_btn.setFocusPolicy(Qt.NoFocus)
        del_btn.setFixedSize(28, 22)
        del_btn.setStyleSheet(BTN_STYLE_DANGER)
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._index))
        h.addWidget(del_btn)

    def _build_normal_ui(self, data: dict, edit_panel):
        """UI completa para un botón normal (hotkey, URL o App)."""
        self.setStyleSheet(ITEM_FRAME_STYLE)
        self.setFixedHeight(46)

        h = QHBoxLayout(self)
        h.setContentsMargins(4, 4, 8, 4)
        h.setSpacing(6)

        # Asa de drag
        if edit_panel is not None:
            self._drag_handle = DragHandle(self._index, self, edit_panel)
            h.addWidget(self._drag_handle)

        # Swatch de color
        swatch = QLabel("  ")
        swatch.setFixedSize(16, 28)
        swatch.setStyleSheet(f"""
            background: {data.get('color', '#4a90d9')};
            border-radius: 4px;
        """)
        h.addWidget(swatch)

        # Etiqueta principal
        lbl = QLabel(data.get("label", ""))
        lbl.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        lbl.setMinimumWidth(80)
        h.addWidget(lbl, 1)

        # Subtítulo: hotkey, URL (🌐) o App (📂)  — S6
        btn_type = data.get("type", "hotkey")
        if btn_type == "url":
            sub_text = f"🌐 {data.get('action', '')}"
        elif btn_type == "app":
            sub_text = f"📂 {data.get('action', '')}"
        else:
            sub_text = data.get("hotkey", "")

        hk = QLabel(sub_text)
        hk.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        hk.setMinimumWidth(90)
        h.addWidget(hk)

        # Botón Editar
        edit_btn = QPushButton("✏")
        edit_btn.setFocusPolicy(Qt.NoFocus)
        edit_btn.setFixedSize(32, 32)
        edit_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        edit_btn.setToolTip("Editar")
        edit_btn.clicked.connect(lambda: self.edit_requested.emit(self._index))
        h.addWidget(edit_btn)

        # Botón Duplicar
        dup_btn = QPushButton("📋")
        dup_btn.setFocusPolicy(Qt.NoFocus)
        dup_btn.setFixedSize(32, 32)
        dup_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        dup_btn.setToolTip("Duplicar atajo")
        dup_btn.clicked.connect(lambda: self.duplicate_requested.emit(self._index))
        h.addWidget(dup_btn)

        # Botón Eliminar
        del_btn = QPushButton("🗑")
        del_btn.setFocusPolicy(Qt.NoFocus)
        del_btn.setFixedSize(32, 32)
        del_btn.setStyleSheet(BTN_STYLE_DANGER)
        del_btn.setToolTip("Eliminar")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self._index))
        h.addWidget(del_btn)

    def set_drag_lifted(self, lifted: bool):
        """Estilo visual de elevación durante drag & drop (ignorado en separadores)."""
        if self._is_separator:
            return
        if lifted:
            self.setStyleSheet("""
                QFrame {
                    background: #3d3d52;
                    border-radius: 7px;
                    border: 1px solid #6a6aaa;
                }
            """)
        else:
            self.setStyleSheet(ITEM_FRAME_STYLE)


# ──────────────────────────────────────────────────────────────────────────────
# EditPanel — panel de edición embebido
# ──────────────────────────────────────────────────────────────────────────────
class EditPanel(QWidget):
    """Panel de configuración que se monta dentro del OverlayWindow."""

    def __init__(self, profile_manager, overlay_window):
        super().__init__(overlay_window)
        self._pm = profile_manager
        self._overlay = overlay_window
        self._current_profile = self._pm.get_active_profile()

        self.setStyleSheet("background: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Estado de drag & drop
        self._drag_active = False
        self._drag_source_index = -1
        self._drag_current_index = -1
        self._drag_widget_ref = None

        self._build_ui()
        self._refresh_list()

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(6)

        # ── Fila 1: Volver + selector de perfil ───────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        back_btn = QPushButton("◀ Listo")
        back_btn.setFocusPolicy(Qt.NoFocus)
        back_btn.setMinimumHeight(34)
        back_btn.setStyleSheet(BTN_STYLE_SUCCESS)
        back_btn.clicked.connect(self._on_back)
        row1.addWidget(back_btn)

        self._profile_combo = QComboBox()
        self._profile_combo.setFocusPolicy(Qt.NoFocus)
        self._profile_combo.setMinimumHeight(34)
        self._profile_combo.setStyleSheet("""
            QComboBox {
                background: #3a3a3a; color: white;
                border: 1px solid #555; border-radius: 6px;
                padding: 2px 8px; font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #2d2d2d; color: white;
                selection-background-color: #4a90d9;
            }
        """)
        self._profile_combo.currentTextChanged.connect(self._on_profile_selected)
        row1.addWidget(self._profile_combo, 1)

        main.addLayout(row1)

        # ── Fila 2: Gestión de perfiles ───────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(4)

        new_p_btn = QPushButton("＋ Perfil")
        new_p_btn.setFocusPolicy(Qt.NoFocus)
        new_p_btn.setMinimumHeight(30)
        new_p_btn.setStyleSheet(BTN_STYLE_PRIMARY)
        new_p_btn.clicked.connect(self._new_profile)
        row2.addWidget(new_p_btn)

        ren_p_btn = QPushButton("✏ Renombrar")
        ren_p_btn.setFocusPolicy(Qt.NoFocus)
        ren_p_btn.setMinimumHeight(30)
        ren_p_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        ren_p_btn.clicked.connect(self._rename_profile)
        row2.addWidget(ren_p_btn)

        dup_p_btn = QPushButton("📋 Duplicar")
        dup_p_btn.setFocusPolicy(Qt.NoFocus)
        dup_p_btn.setMinimumHeight(30)
        dup_p_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        dup_p_btn.setToolTip("Crear una copia de este perfil con todos sus atajos")
        dup_p_btn.clicked.connect(self._duplicate_profile)
        row2.addWidget(dup_p_btn)

        del_p_btn = QPushButton("🗑")
        del_p_btn.setFocusPolicy(Qt.NoFocus)
        del_p_btn.setFixedWidth(38)
        del_p_btn.setMinimumHeight(30)
        del_p_btn.setStyleSheet(BTN_STYLE_DANGER)
        del_p_btn.clicked.connect(self._delete_profile)
        row2.addWidget(del_p_btn)

        main.addLayout(row2)

        # ── Fila 2b: Atajos por página ────────────────────────────────────────
        row2b = QHBoxLayout()
        row2b.setSpacing(4)

        per_page_lbl = QLabel("Atajos por página:")
        per_page_lbl.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        row2b.addWidget(per_page_lbl)
        row2b.addStretch()

        pp_dn = QPushButton("−")
        pp_dn.setFocusPolicy(Qt.NoFocus)
        pp_dn.setFixedSize(28, 26)
        pp_dn.setStyleSheet(BTN_STYLE_NEUTRAL)
        pp_dn.clicked.connect(lambda: self._change_buttons_per_page(-1))
        row2b.addWidget(pp_dn)

        self._per_page_label = QLabel("9")
        self._per_page_label.setFixedWidth(26)
        self._per_page_label.setAlignment(Qt.AlignCenter)
        self._per_page_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        row2b.addWidget(self._per_page_label)

        pp_up = QPushButton("＋")
        pp_up.setFocusPolicy(Qt.NoFocus)
        pp_up.setFixedSize(28, 26)
        pp_up.setStyleSheet(BTN_STYLE_NEUTRAL)
        pp_up.clicked.connect(lambda: self._change_buttons_per_page(+1))
        row2b.addWidget(pp_up)

        main.addLayout(row2b)

        # ── Fila 2c: Auto-switch de proceso (S2) ──────────────────────────────
        row2c = QHBoxLayout()
        row2c.setSpacing(6)

        proc_lbl = QLabel("Auto-switch proceso:")
        proc_lbl.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        row2c.addWidget(proc_lbl)

        self._process_edit = QLineEdit()
        self._process_edit.setPlaceholderText("ej: code.exe  (vacío = desactivado)")
        self._process_edit.setStyleSheet(INPUT_STYLE)
        self._process_edit.setMinimumHeight(28)
        self._process_edit.textChanged.connect(self._on_process_changed)
        row2c.addWidget(self._process_edit, 1)

        main.addLayout(row2c)

        # ── Fila 2d: Exportar / Importar perfiles (S3) ────────────────────────
        row2d = QHBoxLayout()
        row2d.setSpacing(4)

        export_btn = QPushButton("📤 Exportar")
        export_btn.setFocusPolicy(Qt.NoFocus)
        export_btn.setMinimumHeight(28)
        export_btn.setStyleSheet(BTN_STYLE_EXPORT)
        export_btn.setToolTip("Guardar todos los perfiles en un archivo JSON")
        export_btn.clicked.connect(self._export_profiles)
        row2d.addWidget(export_btn)

        import_btn = QPushButton("📥 Importar")
        import_btn.setFocusPolicy(Qt.NoFocus)
        import_btn.setMinimumHeight(28)
        import_btn.setStyleSheet(BTN_STYLE_EXPORT)
        import_btn.setToolTip("Cargar y fusionar perfiles desde un archivo JSON")
        import_btn.clicked.connect(self._import_profiles)
        row2d.addWidget(import_btn)

        row2d.addStretch()
        main.addLayout(row2d)

        # ── Separador ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #444;")
        main.addWidget(sep)

        # ── Lista de atajos con scroll ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLL_STYLE)
        scroll.setMinimumHeight(150)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._list_container = _DropContainer(self)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        main.addWidget(scroll, 1)

        # ── Fila inferior: agregar / separador / mover ────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(4)

        add_btn = QPushButton("＋ Atajo")
        add_btn.setFocusPolicy(Qt.NoFocus)
        add_btn.setMinimumHeight(36)
        add_btn.setStyleSheet(BTN_STYLE_PRIMARY)
        add_btn.clicked.connect(self._add_shortcut)
        row3.addWidget(add_btn, 1)

        sep_btn = QPushButton("── Sep")       # S7: añadir separador visual
        sep_btn.setFocusPolicy(Qt.NoFocus)
        sep_btn.setMinimumHeight(36)
        sep_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        sep_btn.setToolTip("Agregar separador visual al grid")
        sep_btn.clicked.connect(self._add_separator)
        row3.addWidget(sep_btn)

        up_btn = QPushButton("↑")
        up_btn.setFocusPolicy(Qt.NoFocus)
        up_btn.setFixedSize(34, 36)
        up_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        up_btn.setToolTip("Mover arriba")
        up_btn.clicked.connect(self._move_up)
        row3.addWidget(up_btn)

        down_btn = QPushButton("↓")
        down_btn.setFocusPolicy(Qt.NoFocus)
        down_btn.setFixedSize(34, 36)
        down_btn.setStyleSheet(BTN_STYLE_NEUTRAL)
        down_btn.setToolTip("Mover abajo")
        down_btn.clicked.connect(self._move_down)
        row3.addWidget(down_btn)

        main.addLayout(row3)

        self._selected_index = -1

    # ── Carga / refresco ──────────────────────────────────────────────────────

    def reload(self):
        self._current_profile = self._pm.get_active_profile()
        self._refresh_combos()
        self._refresh_list()

    def _refresh_combos(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(self._pm.get_profile_names())
        self._profile_combo.setCurrentText(self._current_profile)
        self._profile_combo.blockSignals(False)

    def _change_buttons_per_page(self, delta: int):
        current = self._pm.get_buttons_per_page(self._current_profile)
        new_val = max(1, min(50, current + delta))
        self._pm.set_buttons_per_page(self._current_profile, new_val)
        self._per_page_label.setText(str(new_val))

    def _refresh_list(self):
        self._refresh_combos()

        # Actualizar contador de atajos por página
        self._per_page_label.setText(
            str(self._pm.get_buttons_per_page(self._current_profile))
        )

        # S2: Actualizar campo de proceso sin disparar la señal
        self._process_edit.blockSignals(True)
        self._process_edit.setText(
            self._pm.get_profile_process(self._current_profile)
        )
        self._process_edit.blockSignals(False)

        # Limpiar lista
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        buttons = self._pm.get_buttons(self._current_profile)
        for i, btn_data in enumerate(buttons):
            widget = ShortcutItemWidget(i, btn_data, self)
            widget.edit_requested.connect(self._edit_shortcut)
            widget.duplicate_requested.connect(self._duplicate_shortcut)
            widget.delete_requested.connect(self._delete_shortcut)
            self._list_layout.insertWidget(i, widget)

        self._selected_index = -1

    # ── S2: Auto-switch proceso ────────────────────────────────────────────────

    def _on_process_changed(self, text: str):
        """Guarda el proceso de auto-switch del perfil actual."""
        self._pm.set_profile_process(self._current_profile, text.strip().lower())

    # ── S3: Exportar / Importar perfiles ──────────────────────────────────────

    def _export_profiles(self):
        """Exportar todos los perfiles a un archivo JSON."""
        dlg = QFileDialog()   # sin parent — evita heredar WA_TranslucentBackground
        dlg.setWindowTitle("Exportar perfiles")
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setNameFilter("JSON (*.json)")
        dlg.setDefaultSuffix("json")
        dlg.selectFile("perfiles_backup.json")
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dlg.setAttribute(Qt.WA_TranslucentBackground, False)
        if dlg.exec_() != QDialog.Accepted:
            return
        path = dlg.selectedFiles()[0]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._pm.export_data(), f, ensure_ascii=False, indent=2)
            _dlg_info(self, "Exportar perfiles", f"Perfiles guardados correctamente en:\n{path}")
        except Exception as e:
            _dlg_critical(self, "Error al exportar", f"No se pudo guardar el archivo:\n{e}")

    def _import_profiles(self):
        """Importar y fusionar perfiles desde un archivo JSON."""
        dlg = QFileDialog()   # sin parent — evita heredar WA_TranslucentBackground
        dlg.setWindowTitle("Importar perfiles")
        dlg.setAcceptMode(QFileDialog.AcceptOpen)
        dlg.setNameFilter("JSON (*.json)")
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dlg.setAttribute(Qt.WA_TranslucentBackground, False)
        if dlg.exec_() != QDialog.Accepted:
            return
        path = dlg.selectedFiles()[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "profiles" not in data or not isinstance(data["profiles"], dict):
                _dlg_warning(
                    self, "Importar perfiles",
                    'El archivo no contiene perfiles válidos (falta clave "profiles").'
                )
                return
            incoming = data["profiles"]
            for name, profile_data in incoming.items():
                self._pm._data["profiles"][name] = profile_data
            self._pm.save()
            self._refresh_list()
            _dlg_info(self, "Importar perfiles",
                      f"Se importaron {len(incoming)} perfil(es) correctamente.")
        except Exception as e:
            _dlg_critical(self, "Error al importar", f"No se pudo leer el archivo:\n{e}")

    # ── Gestión de perfiles ───────────────────────────────────────────────────

    def _on_profile_selected(self, name: str):
        if name:
            self._current_profile = name
            self._pm.set_active_profile(name)
            self._refresh_list()

    def _new_profile(self):
        name, ok = _dlg_get_text(self, "Nuevo Perfil", "Nombre del nuevo perfil:")
        if ok and name.strip():
            name = name.strip()
            if name in self._pm.get_profile_names():
                _dlg_warning(self, "Error", f'Ya existe un perfil llamado "{name}".')
                return
            self._pm.add_profile(name)
            self._current_profile = name
            self._pm.set_active_profile(name)
            self._refresh_list()

    def _rename_profile(self):
        old = self._current_profile
        new_name, ok = _dlg_get_text(self, "Renombrar Perfil", f'Nuevo nombre para "{old}":')
        if ok and new_name.strip():
            new_name = new_name.strip()
            if new_name in self._pm.get_profile_names():
                _dlg_warning(self, "Error", f'Ya existe un perfil llamado "{new_name}".')
                return
            self._pm.rename_profile(old, new_name)
            self._current_profile = new_name
            self._refresh_list()

    def _duplicate_profile(self):
        src = self._current_profile
        new_name, ok = _dlg_get_text(
            self, "Duplicar perfil",
            f'Nombre para la copia de "{src}":',
            default=f"{src} (copia)"
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if new_name in self._pm.get_profile_names():
            _dlg_warning(self, "Nombre ya existe",
                         f'Ya existe un perfil llamado "{new_name}".')
            return
        self._pm.duplicate_profile(src, new_name)
        self._current_profile = new_name
        self._refresh_combos()
        self._refresh_list()
        self._notify_host()

    def _delete_profile(self):
        profiles = self._pm.get_profile_names()
        if len(profiles) <= 1:
            _dlg_info(self, "Info", "Debe existir al menos un perfil.")
            return
        reply = _dlg_question(
            self, "Eliminar Perfil",
            f'¿Eliminar el perfil "{self._current_profile}" y todos sus atajos?',
        )
        if reply == QMessageBox.Yes:
            self._pm.delete_profile(self._current_profile)
            self._current_profile = self._pm.get_active_profile()
            self._refresh_list()

    # ── Gestión de atajos ──────────────────────────────────────────────────────

    def _add_shortcut(self):
        """Agregar un nuevo botón (hotkey, URL o App)."""
        dlg = ShortcutEditDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            buttons = self._pm.get_buttons(self._current_profile)
            buttons.append(data)
            self._pm.set_buttons(self._current_profile, buttons)
            self._refresh_list()

    def _add_separator(self):
        """S7: Agregar un separador visual al final del perfil actual."""
        buttons = self._pm.get_buttons(self._current_profile)
        buttons.append({"type": "separator", "label": ""})
        self._pm.set_buttons(self._current_profile, buttons)
        self._refresh_list()

    def _edit_shortcut(self, index: int):
        """Editar un botón existente (S6: pasa tipo y acción al diálogo)."""
        self._selected_index = index
        buttons = self._pm.get_buttons(self._current_profile)
        if index >= len(buttons):
            return
        existing = buttons[index]
        # No debería llamarse en separadores (no tienen botón editar), pero por seguridad:
        if existing.get("type") == "separator":
            return
        dlg = ShortcutEditDialog(
            self,
            label=existing.get("label", ""),
            hotkey=existing.get("hotkey", ""),
            color=existing.get("color", "#2980B9"),
            btn_type=existing.get("type", "hotkey"),
            action=existing.get("action", ""),
        )
        if dlg.exec_() == QDialog.Accepted:
            buttons[index] = dlg.get_data()
            self._pm.set_buttons(self._current_profile, buttons)
            self._refresh_list()

    def _delete_shortcut(self, index: int):
        buttons = self._pm.get_buttons(self._current_profile)
        if index >= len(buttons):
            return
        item = buttons[index]
        if item.get("type") == "separator":
            lbl = "este separador"
        else:
            lbl = item.get("label") or "este atajo"
        reply = _dlg_question(self, "Eliminar", f'¿Eliminar "{lbl}"?')
        if reply == QMessageBox.Yes:
            buttons.pop(index)
            self._pm.set_buttons(self._current_profile, buttons)
            self._refresh_list()

    def _duplicate_shortcut(self, index: int):
        """Crea una copia del botón en `index` e inserta inmediatamente después."""
        buttons = self._pm.get_buttons(self._current_profile)
        if 0 <= index < len(buttons):
            buttons.insert(index + 1, copy.deepcopy(buttons[index]))
            self._pm.set_buttons(self._current_profile, buttons)
            self._refresh_list()
            self._notify_host()

    def _move_up(self):
        if self._selected_index <= 0:
            return
        buttons = self._pm.get_buttons(self._current_profile)
        i = self._selected_index
        buttons[i - 1], buttons[i] = buttons[i], buttons[i - 1]
        self._pm.set_buttons(self._current_profile, buttons)
        self._selected_index = i - 1
        self._refresh_list()

    def _move_down(self):
        buttons = self._pm.get_buttons(self._current_profile)
        i = self._selected_index
        if i < 0 or i >= len(buttons) - 1:
            return
        buttons[i + 1], buttons[i] = buttons[i], buttons[i + 1]
        self._pm.set_buttons(self._current_profile, buttons)
        self._selected_index = i + 1
        self._refresh_list()

    # ── Drag & Drop ───────────────────────────────────────────────────────────

    def _on_drag_start(self, source_index: int, global_pos):
        self._drag_active = True
        self._drag_source_index = source_index
        self._drag_current_index = source_index
        self._drag_widget_ref = self._get_item_widget(source_index)
        if self._drag_widget_ref:
            self._drag_widget_ref.set_drag_lifted(True)
        self._list_container.update()

    def _on_drag_move(self, global_pos):
        if not self._drag_active:
            return
        local_y = self._list_container.mapFromGlobal(global_pos).y()
        new_target = self._compute_drop_index(local_y)
        if new_target != self._drag_current_index:
            self._drag_current_index = new_target
            self._list_container.update()

    def _compute_drop_index(self, local_y: int) -> int:
        """Calcula el índice de inserción según la posición Y del cursor."""
        n = self._list_layout.count() - 1   # -1 por el addStretch al final
        for i in range(n):
            item = self._list_layout.itemAt(i)
            if item and item.widget():
                mid_y = item.widget().y() + item.widget().height() // 2
                if local_y < mid_y:
                    return i
        return max(0, n)

    def _on_drag_release(self):
        if not self._drag_active:
            return
        src = self._drag_source_index
        dst = self._drag_current_index
        # Restaurar estilo normal del ítem arrastrado
        if self._drag_widget_ref:
            self._drag_widget_ref.set_drag_lifted(False)
            self._drag_widget_ref = None
        self._drag_active = False
        self._drag_source_index = -1
        # dst == src+1 significa "insertar justo después de src" = sin movimiento
        if dst != src and dst != src + 1:
            buttons = self._pm.get_buttons(self._current_profile)
            item = buttons.pop(src)
            insert_at = dst if dst <= src else dst - 1
            buttons.insert(insert_at, item)
            self._pm.set_buttons(self._current_profile, buttons)
        self._drag_current_index = -1
        self._list_container.update()
        self._refresh_list()

    def _get_item_widget(self, index: int):
        """Devuelve el ShortcutItemWidget en la posición dada del layout."""
        item = self._list_layout.itemAt(index)
        return item.widget() if item else None

    # ── Volver al modo uso ─────────────────────────────────────────────────────

    def _on_back(self):
        self._overlay.reload_overlay()
