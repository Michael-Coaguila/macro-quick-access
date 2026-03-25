"""
main.py — Macro Quick Access
Overlay táctil de atajos de teclado para usuarios con movilidad reducida.

Uso:
    python main.py

Dependencias:
    pip install PyQt5 pyautogui pywin32 pynput
"""

import logging
import os
import sys

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt5.QtCore import Qt, QObject, pyqtSignal

from overlay import OverlayWindow, ProfileManager


# ──────────────────────────────────────────────────────────────────────────────
# Logging centralizado
# ──────────────────────────────────────────────────────────────────────────────
def _setup_logging():
    if getattr(sys, 'frozen', False):
        log_dir = os.path.dirname(sys.executable)
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(log_dir, "macro_quick_access.log")
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8", mode="a"),
            logging.StreamHandler(),
        ],
    )

# pynput es opcional: si no está instalado, el hotkey global simplemente no funciona
try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("[Warning] pynput no instalado. El hotkey global Ctrl+Shift+M no estará disponible.")
    print("          Instalar con: pip install pynput")


# ──────────────────────────────────────────────────────────────────────────────
# Ícono generado en memoria (no requiere archivo externo)
# ──────────────────────────────────────────────────────────────────────────────
def _make_tray_icon() -> QIcon:
    """Genera un ícono de bandeja de 32×32px con una "M" de Macro."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Fondo redondeado
    painter.setBrush(QColor("#2980B9"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(2, 2, 28, 28, 7, 7)

    # Letra M
    painter.setPen(QColor("white"))
    font = painter.font()
    font.setPointSize(14)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "M")
    painter.end()

    return QIcon(pixmap)


# ──────────────────────────────────────────────────────────────────────────────
# S4 — GlobalHotkeyListener (Ctrl+Shift+M para mostrar/ocultar el overlay)
# ──────────────────────────────────────────────────────────────────────────────
class GlobalHotkeyListener(QObject):
    """
    Escucha el hotkey global Ctrl+Shift+M en el hilo de pynput.

    Usa pyqtSignal para despachar el callback al hilo principal de Qt de forma
    completamente thread-safe (emit() está garantizado como seguro desde cualquier hilo).
    Así el hook WH_KEYBOARD_LL retorna inmediatamente, sin bloquear.
    """

    # Señal emitida desde el hilo de pynput — Qt la encola automáticamente al hilo principal
    _toggle_signal = pyqtSignal()

    def __init__(self, callback):
        super().__init__()
        self._pressed = set()
        # Conectar la señal al callback del hilo principal
        self._toggle_signal.connect(callback)
        self._listener = pynput_keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )

    def start(self):
        """Arranca el listener (pynput.Listener ya es un Thread interno)."""
        self._listener.start()

    def stop(self):
        """Detiene el listener al salir de la aplicación."""
        try:
            self._listener.stop()
        except Exception:
            pass

    def _on_press(self, key):
        self._pressed.add(key)
        if self._is_combo_active():
            # emit() desde cualquier hilo → Qt lo encola al hilo principal (QueuedConnection)
            self._toggle_signal.emit()

    def _on_release(self, key):
        self._pressed.discard(key)

    def _is_combo_active(self) -> bool:
        """Detecta Ctrl+Shift+M (cualquier variante izq/der de Ctrl y Shift)."""
        has_ctrl = any(
            k in self._pressed
            for k in (pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r)
        )
        has_shift = any(
            k in self._pressed
            for k in (pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_r)
        )
        has_m = pynput_keyboard.KeyCode.from_char('m') in self._pressed
        return has_ctrl and has_shift and has_m


# ──────────────────────────────────────────────────────────────────────────────
# TrayApp
# ──────────────────────────────────────────────────────────────────────────────
class TrayApp:
    def __init__(self, app: QApplication):
        self._app = app
        self._pm = ProfileManager()
        self._overlay = OverlayWindow(self._pm)

        self._tray = QSystemTrayIcon(_make_tray_icon(), app)
        self._tray.setToolTip("Macro Quick Access")
        self._build_tray_menu()
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._overlay.show()

        # S4: hotkey global Ctrl+Shift+M
        self._hotkey_listener = None
        if PYNPUT_AVAILABLE:
            self._hotkey_listener = GlobalHotkeyListener(self._toggle_overlay)
            self._hotkey_listener.start()

    def _build_tray_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e2a;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item { padding: 8px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #2980B9; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 8px; }
        """)

        show_action = QAction("👁  Mostrar / Ocultar  (Ctrl+Shift+M)", self._app)
        show_action.triggered.connect(self._toggle_overlay)
        menu.addAction(show_action)

        menu.addSeparator()

        quit_action = QAction("✖  Salir", self._app)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._toggle_overlay()

    def _toggle_overlay(self):
        if self._overlay.isVisible():
            self._overlay.hide()
        else:
            self._overlay.show()
            self._overlay.activateWindow()

    def _quit(self):
        if self._hotkey_listener is not None:
            self._hotkey_listener.stop()
        self._tray.hide()
        self._app.quit()


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
def main():
    _setup_logging()
    # Habilitar HiDPI para pantallas de alta resolución / táctiles
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Macro Quick Access")
    app.setQuitOnLastWindowClosed(False)   # CRÍTICO: ocultar el overlay no cierra la app

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("[Warning] No hay bandeja del sistema disponible. La app se ejecutará sin ícono.")

    tray_app = TrayApp(app)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
