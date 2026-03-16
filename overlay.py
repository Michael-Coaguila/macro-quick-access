"""
overlay.py — Ventana flotante principal + ProfileManager + ShortcutButton
"""

import copy
import json
import logging
import math
import os
import subprocess
import webbrowser

import pyautogui
from PyQt5.QtCore import Qt, QTimer, QPoint, QRect, QPropertyAnimation, QEasingCurve, QObject, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QFont, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QGridLayout, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QSizePolicy, QFrame
)

_log = logging.getLogger(__name__)

# ── Estilos compartidos ──────────────────────────────────────────────────────
_TAB_STYLE_ON = """QPushButton {
    background: #2980B9; color: white;
    border-radius: 5px; font-size: 11px; font-weight: bold; border: none;
}"""
_TAB_STYLE_OFF = """QPushButton {
    background: #333; color: #aaa;
    border-radius: 5px; font-size: 11px; border: none;
} QPushButton:pressed { background: #444; }"""

# ──────────────────────────────────────────────────────────────────────────────
# Win32 helpers
# ──────────────────────────────────────────────────────────────────────────────
try:
    import win32gui
    import win32con
    import win32api
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Perfiles predeterminados
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_PROFILES = {
    "active_profile": "General",
    "window_pos": [80, 80],
    "window_size": [300, 280],
    "window_opacity": 0.92,
    "button_size": [85, 62],
    "profiles": {
        "General": {
            "buttons_per_page": 9,
            "process": "",
            "buttons": [
                {"label": "Copiar",       "hotkey": "ctrl+c",        "color": "#2980B9"},
                {"label": "Pegar",        "hotkey": "ctrl+v",        "color": "#2980B9"},
                {"label": "Cortar",       "hotkey": "ctrl+x",        "color": "#2980B9"},
                {"label": "Deshacer",     "hotkey": "ctrl+z",        "color": "#E67E22"},
                {"label": "Rehacer",      "hotkey": "ctrl+y",        "color": "#E67E22"},
                {"label": "Guardar",      "hotkey": "ctrl+s",        "color": "#27AE60"},
                {"label": "Guardar Todo", "hotkey": "ctrl+shift+s",  "color": "#27AE60"},
                {"label": "Selec. Todo",  "hotkey": "ctrl+a",        "color": "#8E44AD"},
                {"label": "Buscar",       "hotkey": "ctrl+f",        "color": "#8E44AD"},
                {"label": "Cambiar App",  "hotkey": "alt+tab",       "color": "#C0392B"},
                {"label": "Cerrar",       "hotkey": "alt+f4",        "color": "#C0392B"},
                {"label": "Escritorio",   "hotkey": "win+d",         "color": "#7F8C8D"},
            ]
        },
        "VS Code": {
            "buttons_per_page": 9,
            "process": "code.exe",
            "buttons": [
                {"label": "Terminal",     "hotkey": "ctrl+grave",    "color": "#16A085"},
                {"label": "Paleta Cmd",   "hotkey": "ctrl+shift+p",  "color": "#2980B9"},
                {"label": "Ir Archivo",   "hotkey": "ctrl+p",        "color": "#2980B9"},
                {"label": "Comentar",     "hotkey": "ctrl+slash",    "color": "#8E44AD"},
                {"label": "Formatear",    "hotkey": "shift+alt+f",   "color": "#8E44AD"},
                {"label": "Ir Definición","hotkey": "f12",           "color": "#E74C3C"},
                {"label": "Renombrar",    "hotkey": "f2",            "color": "#E74C3C"},
                {"label": "Panel Lateral","hotkey": "ctrl+b",        "color": "#27AE60"},
                {"label": "Dividir",      "hotkey": "ctrl+backslash","color": "#27AE60"},
                {"label": "Multi Cursor", "hotkey": "ctrl+alt+down", "color": "#F39C12"},
            ]
        },
        "Navegador": {
            "buttons_per_page": 9,
            "process": "",
            "buttons": [
                {"label": "Nueva Pesta.", "hotkey": "ctrl+t",        "color": "#2980B9"},
                {"label": "Cerrar Pesta.","hotkey": "ctrl+w",        "color": "#E74C3C"},
                {"label": "Recuperar",   "hotkey": "ctrl+shift+t",   "color": "#27AE60"},
                {"label": "Sig. Pesta.", "hotkey": "ctrl+tab",       "color": "#8E44AD"},
                {"label": "Ant. Pesta.", "hotkey": "ctrl+shift+tab", "color": "#8E44AD"},
                {"label": "Actualizar",  "hotkey": "f5",             "color": "#16A085"},
                {"label": "Barra URL",   "hotkey": "ctrl+l",         "color": "#F39C12"},
                {"label": "Herram. Dev.","hotkey": "f12",            "color": "#C0392B"},
                {"label": "Zoom +",      "hotkey": "ctrl+plus",      "color": "#27AE60"},
                {"label": "Zoom -",      "hotkey": "ctrl+minus",     "color": "#E74C3C"},
            ]
        }
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# ProfileManager
# ──────────────────────────────────────────────────────────────────────────────
class ProfileManager:
    """Carga y guarda perfiles desde profiles.json."""

    def __init__(self):
        base = os.path.dirname(os.path.abspath(__file__))
        self._path = os.path.join(base, "profiles.json")
        self._data = {}
        self.load()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        if not self._data:
            self._data = copy.deepcopy(DEFAULT_PROFILES)
            self.save()

    def save(self):
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception as e:
            _log.error("ProfileManager: error guardando perfiles: %s", e)

    def export_data(self) -> dict:
        """Retorna una copia profunda de todos los datos para exportar."""
        return copy.deepcopy(self._data)

    # ── Perfiles ──────────────────────────────────────────────────────────────

    def get_profile_names(self):
        return list(self._data.get("profiles", {}).keys())

    def get_active_profile(self):
        return self._data.get("active_profile", "General")

    def set_active_profile(self, name: str):
        self._data["active_profile"] = name
        self.save()

    def get_buttons(self, profile: str):
        return self._data.get("profiles", {}).get(profile, {}).get("buttons", [])

    def set_buttons(self, profile: str, buttons: list):
        if profile not in self._data["profiles"]:
            self._data["profiles"][profile] = {}
        self._data["profiles"][profile]["buttons"] = buttons
        self.save()

    def get_buttons_per_page(self, profile: str) -> int:
        return self._data.get("profiles", {}).get(profile, {}).get("buttons_per_page", 9)

    def set_buttons_per_page(self, profile: str, value: int):
        if profile in self._data["profiles"]:
            self._data["profiles"][profile]["buttons_per_page"] = max(1, value)
            self.save()

    # S2 — proceso para auto-switch
    def get_profile_process(self, profile: str) -> str:
        return self._data.get("profiles", {}).get(profile, {}).get("process", "")

    def set_profile_process(self, profile: str, process: str):
        if profile in self._data.get("profiles", {}):
            self._data["profiles"][profile]["process"] = process
            self.save()

    # ── Ventana ───────────────────────────────────────────────────────────────

    def get_window_pos(self):
        return tuple(self._data.get("window_pos", [80, 80]))

    def save_window_pos(self, x: int, y: int):
        self._data["window_pos"] = [x, y]
        self.save()

    def get_window_size(self) -> tuple:
        s = self._data.get("window_size", [300, 280])
        return (int(s[0]), int(s[1]))

    def save_window_size(self, w: int, h: int):
        self._data["window_size"] = [w, h]
        self.save()

    def get_edit_size(self) -> tuple:
        """Tamaño de ventana en modo edición (independiente del modo uso)."""
        s = self._data.get("edit_size", [330, 500])
        return (int(s[0]), int(s[1]))

    def save_edit_size(self, w: int, h: int):
        self._data["edit_size"] = [w, h]
        self.save()

    def get_opacity(self) -> float:
        return float(self._data.get("window_opacity", 0.92))

    def set_opacity(self, value: float):
        self._data["window_opacity"] = round(max(0.30, min(1.0, value)), 2)
        self.save()

    def get_button_size(self) -> tuple:
        s = self._data.get("button_size", [85, 62])
        return (int(s[0]), int(s[1]))

    def set_button_size(self, w: int, h: int):
        self._data["button_size"] = [w, h]
        self.save()

    # ── CRUD perfiles ──────────────────────────────────────────────────────────

    def add_profile(self, name: str):
        if name and name not in self._data["profiles"]:
            self._data["profiles"][name] = {"buttons_per_page": 9, "process": "", "buttons": []}
            self.save()

    def rename_profile(self, old: str, new: str):
        if old in self._data["profiles"] and new and new not in self._data["profiles"]:
            self._data["profiles"][new] = self._data["profiles"].pop(old)
            if self._data.get("active_profile") == old:
                self._data["active_profile"] = new
            self.save()

    def delete_profile(self, name: str):
        profiles = self._data["profiles"]
        if name in profiles and len(profiles) > 1:
            del profiles[name]
            if self._data.get("active_profile") == name:
                self._data["active_profile"] = next(iter(profiles))
            self.save()

    # ── Perfil base (pestaña siempre visible) ─────────────────────────────────

    def get_pinned_profile(self) -> str:
        return self._data.get("pinned_profile", "")

    def set_pinned_profile(self, name: str):
        self._data["pinned_profile"] = name
        self.save()


# ──────────────────────────────────────────────────────────────────────────────
# ShortcutButton  (S1: subtítulo de hotkey via QLabel; S6: send_fn sin argumentos)
# ──────────────────────────────────────────────────────────────────────────────
class ShortcutButton(QPushButton):
    """
    Botón táctil individual.
    Usa dos QLabel internos (label en blanco + hotkey en gris) en lugar de
    HTML en setText(), que en algunas versiones de Qt5 se renderiza como texto plano.
    """

    def __init__(self, label: str, hotkey: str, color: str, send_fn, size=(85, 62)):
        super().__init__()
        self._color = color   # B1: guardar color original para restaurar tras flash
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedHeight(size[1])
        self.setMinimumWidth(35)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        font_size = max(8, min(13, int(size[1] * 0.18)))
        sub_size  = max(7, font_size - 3)

        # Layout vertical con label principal + subtítulo hotkey
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 3, 4, 3)
        vbox.setSpacing(1)

        lbl_w = QLabel(label)
        lbl_w.setAlignment(Qt.AlignCenter)
        lbl_w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        lbl_w.setStyleSheet(
            f"background: transparent; color: white; border: none; "
            f"font-size: {font_size}px; font-weight: bold;"
        )
        vbox.addWidget(lbl_w)

        if hotkey:
            hk_w = QLabel(hotkey)
            hk_w.setAlignment(Qt.AlignCenter)
            hk_w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            hk_w.setStyleSheet(
                f"background: transparent; color: #bbbbbb; border: none; "
                f"font-size: {sub_size}px; font-weight: normal;"
            )
            vbox.addWidget(hk_w)

        self._apply_style(color)

        # B1: conectar a _on_click para ejecutar flash + acción
        self.clicked.connect(lambda: self._on_click(send_fn))

    def _on_click(self, send_fn):
        """B1: flash visual de confirmación + ejecutar acción."""
        self._flash()
        send_fn()

    def _flash(self):
        """B1: destello blanco breve (~180 ms) que confirma el toque."""
        self.setStyleSheet("""QPushButton {
            background-color: rgba(255, 255, 255, 0.85);
            border-radius: 8px; border: none;
        }""")
        QTimer.singleShot(180, lambda: self._apply_style(self._color))

    def _apply_style(self, color: str):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 8px;
                border: none;
            }}
            QPushButton:pressed {{
                background-color: {self._darken(color)};
            }}
        """)

    @staticmethod
    def _darken(hex_color: str, factor: float = 0.72) -> str:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"


# ──────────────────────────────────────────────────────────────────────────────
# ResizeHandle
# ──────────────────────────────────────────────────────────────────────────────
class ResizeHandle(QLabel):
    """
    Asa de redimensionamiento en la esquina inferior-derecha.
    Se posiciona de forma absoluta (no en ningún layout).
    """

    def __init__(self, parent):
        super().__init__("⊿", parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "color: #555; font-size: 14px; background: transparent;"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window()._start_resize(event.globalPos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.window()._do_resize(event.globalPos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.window()._end_resize()
        super().mouseReleaseEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# CollapsedIconWidget
# ──────────────────────────────────────────────────────────────────────────────
class CollapsedIconWidget(QWidget):
    """Icono cuadrado del overlay colapsado.
    Maneja su propio arrastre (para mover la ventana) y toque/clic para expandir.
    Si existe 'icon_collapsed.png' en la carpeta del proyecto lo usa como icono;
    de lo contrario pinta una cuadrícula 3×3 de mini-teclas como fallback."""

    expand_requested = pyqtSignal()

    SIZE = 72

    # Intentar cargar el pixmap una sola vez (caché de clase)
    _pixmap_cache: "QPixmap | None" = None
    _pixmap_loaded: bool = False

    # Colores fallback — mini-teclas (misma paleta que los botones del overlay)
    _KEY_COLORS = [
        "#2980B9", "#27AE60", "#8E44AD",
        "#E67E22", "#2980B9", "#27AE60",
        "#C0392B", "#8E44AD", "#E67E22",
    ]

    @classmethod
    def _load_pixmap(cls):
        """Carga icon_collapsed.png desde la carpeta del proyecto (una sola vez)."""
        if cls._pixmap_loaded:
            return
        cls._pixmap_loaded = True
        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "icon_collapsed.png")
        if os.path.exists(img_path):
            px = QPixmap(img_path)
            cls._pixmap_cache = px if not px.isNull() else None

    def __init__(self, parent=None):
        super().__init__(parent)
        CollapsedIconWidget._load_pixmap()
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Expandir (toca o arrastra)")
        self._press_pos = None
        self._drag_pos = None
        self._drag_started = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.SIZE

        # Clip redondeado para que la imagen respete las esquinas
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, s, s, 16, 16)
        p.setClipPath(clip)

        if self._pixmap_cache is not None:
            # ── Modo imagen: escalar y centrar el pixmap ──────────────────────
            p.drawPixmap(0, 0, s, s, self._pixmap_cache)
        else:
            # ── Fallback: cuadrícula pintada de mini-teclas ───────────────────
            bg = QPainterPath()
            bg.addRoundedRect(0, 0, s, s, 16, 16)
            p.fillPath(bg, QColor("#1b2535"))

            p.setClipping(False)
            p.setPen(QPen(QColor("#3d5a7a"), 1.5))
            p.drawPath(bg)

            key_w, key_h = 16, 12
            gap = 3
            total_w = 3 * key_w + 2 * gap
            total_h = 3 * key_h + 2 * gap
            ox = (s - total_w) // 2
            oy = (s - total_h) // 2

            p.setPen(Qt.NoPen)
            for i, color in enumerate(self._KEY_COLORS):
                row, col = divmod(i, 3)
                x = ox + col * (key_w + gap)
                y = oy + row * (key_h + gap)

                shadow = QPainterPath()
                shadow.addRoundedRect(x, y + 2, key_w, key_h, 2.5, 2.5)
                sc = QColor(color).darker(160)
                sc.setAlpha(120)
                p.fillPath(shadow, sc)

                kp = QPainterPath()
                kp.addRoundedRect(x, y, key_w, key_h, 2.5, 2.5)
                p.fillPath(kp, QColor(color))

                hi = QPainterPath()
                hi.addRoundedRect(x + 1, y + 1, key_w - 2, 3, 1.5, 1.5)
                lc = QColor(color).lighter(170)
                lc.setAlpha(80)
                p.fillPath(hi, lc)

        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._drag_pos = event.globalPos() - self.window().frameGeometry().topLeft()
            self._drag_started = False

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            delta = event.pos() - self._press_pos
            if not self._drag_started and (abs(delta.x()) > 6 or abs(delta.y()) > 6):
                self._drag_started = True
            if self._drag_started:
                self.window().move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._drag_started:
                # Guardar posición nueva
                win = self.window()
                if hasattr(win, '_pm'):
                    win._pm.save_window_pos(win.x(), win.y())
            else:
                # Sin arrastre → expandir
                self.expand_requested.emit()
            self._press_pos = None
            self._drag_pos = None
            self._drag_started = False


# ──────────────────────────────────────────────────────────────────────────────
# SwipeFilter
# ──────────────────────────────────────────────────────────────────────────────
class SwipeFilter(QObject):
    """Event filter instalado en QApplication para detectar swipes horizontales
    sobre el grid de botones y sus hijos, emitiendo swipe_left / swipe_right."""

    swipe_left  = pyqtSignal()   # deslizar hacia la izquierda → página siguiente
    swipe_right = pyqtSignal()   # deslizar hacia la derecha  → página anterior

    MIN_DISTANCE = 60   # px mínimos para considerar un swipe
    MAX_VERTICAL  = 0.6 # ratio vertical/horizontal máximo permitido

    def __init__(self, watched: QWidget, parent=None):
        super().__init__(parent)
        self._watched = watched
        self._start = None

    def _is_descendant(self, obj) -> bool:
        w = obj
        while w is not None:
            if w is self._watched:
                return True
            parent_fn = getattr(w, "parent", None)
            w = parent_fn() if callable(parent_fn) else None
        return False

    def eventFilter(self, obj, event):
        from PyQt5.QtCore import QEvent
        if not self._is_descendant(obj):
            return False
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._start = event.globalPos()
        elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self._start is not None:
                dx = event.globalPos().x() - self._start.x()
                dy = event.globalPos().y() - self._start.y()
                is_swipe = (abs(dx) >= self.MIN_DISTANCE
                            and abs(dy) < abs(dx) * self.MAX_VERTICAL)
                self._start = None
                if is_swipe:
                    (self.swipe_left if dx < 0 else self.swipe_right).emit()
                    return True   # consumir el release para no disparar el botón
        return False


# ──────────────────────────────────────────────────────────────────────────────
# ToastNotification
# ──────────────────────────────────────────────────────────────────────────────
class ToastNotification(QWidget):
    """Aviso temporal no-modal que aparece en la esquina inferior del overlay
    y desaparece automáticamente después de 2.5 segundos."""

    def __init__(self, parent: QWidget, message: str, level: str = "error"):
        super().__init__(parent,
                         Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        color = "#C0392B" if level == "error" else "#E67E22"
        icon  = "✗" if level == "error" else "⚠"

        lbl = QLabel(f"{icon}  {message}", self)
        lbl.setStyleSheet(f"""
            QLabel {{
                background: {color}; color: white;
                border-radius: 8px; padding: 8px 14px;
                font-size: 12px; font-weight: bold;
            }}
        """)
        lbl.adjustSize()
        self.resize(lbl.size())

        # Posicionar en esquina inferior-izquierda del padre
        pr = parent.geometry()
        self.move(pr.x() + 8, pr.y() + pr.height() - self.height() - 8)
        self.show()

        QTimer.singleShot(2500, self.close)


# ──────────────────────────────────────────────────────────────────────────────
# OverlayWindow
# ──────────────────────────────────────────────────────────────────────────────
class OverlayWindow(QWidget):
    """
    Ventana flotante principal.
    Tres modos: "use" | "edit" | "collapsed"
    """

    COLUMNS = 3

    def __init__(self, profile_manager: ProfileManager):
        super().__init__()
        self._pm = profile_manager

        # Estado de arrastre (drag para mover)
        self._drag_pos = None

        # Estado de redimensionado
        self._resizing = False
        self._resize_start = QPoint()
        self._resize_start_size = (0, 0)

        # (sin timer de resize: el reload lo hace _end_resize directamente)

        # S9 — Animación de colapso/expansión
        self._anim = None

        # S2 — Auto-switch por proceso activo
        self._auto_switch_cooldown = False
        self._last_fg_process = ""
        self._process_timer = QTimer(self)
        self._process_timer.setInterval(1500)
        self._process_timer.timeout.connect(self._check_foreground_process)
        self._process_timer.start()

        self._edit_panel = None
        self._mode = "use"
        self._pre_collapse_mode = "use"   # modo antes de colapsar, para restaurarlo al expandir
        self._current_page = 0
        self._total_pages = 1              # carrusel: actualizado en _load_profile
        self._viewing_pinned = False       # True = mostrando pestaña del perfil base
        self._last_grid_rows = 1           # D1: filas del grid en la última carga

        self.setWindowFlags(
            Qt.Tool
            | Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._build_ui()

        # (el resize handle se crea dentro de _build_ui, integrado en _nav_bar)

        # Arrancar siempre con ancho compacto; _fit_height recalcula la altura
        _startup_w = self.COLUMNS * 68 + 22   # ≈ 226 px (3 col × 68 + márgenes)
        self.resize(_startup_w, 300)

        self._load_profile(self._pm.get_active_profile())
        self._update_tab_bar()   # sincronizar tab bar y pin button con el estado guardado

        pos = self._pm.get_window_pos()
        self.move(pos[0], pos[1])

        # Aplicar opacidad guardada (afecta TODO el overlay, no solo el fondo)
        self.setWindowOpacity(self._pm.get_opacity())

    # ── Construcción UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 5, 5)
        outer.setSpacing(0)

        self._container = QWidget(self)
        self._container.setObjectName("container")
        outer.addWidget(self._container)

        # Guardar referencia al layout exterior para ajustar márgenes al colapsar
        self._outer_layout = outer

        self._main_layout = QVBoxLayout(self._container)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        # Icono colapsado — visible solo en modo colapsado
        self._expand_btn = CollapsedIconWidget()
        self._expand_btn.expand_requested.connect(self.expand)
        self._expand_btn.hide()
        self._main_layout.addWidget(self._expand_btn, alignment=Qt.AlignCenter)

        # Barra superior
        self._top_bar = self._build_top_bar()
        self._main_layout.addWidget(self._top_bar)

        # S8 — Label con nombre del perfil activo (solo visible en modo edición)
        self._profile_name_label = QLabel(self._pm.get_active_profile())
        self._profile_name_label.hide()   # oculto por defecto desde el inicio
        self._profile_name_label.setAlignment(Qt.AlignCenter)
        self._profile_name_label.setStyleSheet(
            "color: #4a90d9; font-size: 13px; font-weight: bold; padding: 2px 0;"
        )
        self._main_layout.addWidget(self._profile_name_label)

        # Área de contenido
        self._content_area = QWidget()
        self._content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(0, 4, 0, 0)
        self._content_layout.setSpacing(0)
        self._main_layout.addWidget(self._content_area, 1)

        # Grid de botones (modo uso)
        self._btn_widget = QWidget()
        self._btn_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._btn_grid = QGridLayout(self._btn_widget)
        self._btn_grid.setSpacing(5)
        self._btn_grid.setContentsMargins(0, 0, 0, 0)
        self._content_layout.addWidget(self._btn_widget)

        # B2: filtro de swipe horizontal para paginar
        self._swipe_filter = SwipeFilter(self._btn_widget, parent=self)
        QApplication.instance().installEventFilter(self._swipe_filter)
        self._swipe_filter.swipe_left.connect(
            lambda: self._next_page() if self._next_btn.isEnabled() else None)
        self._swipe_filter.swipe_right.connect(
            lambda: self._prev_page() if self._prev_btn.isEnabled() else None)

        # Tab bar para perfil base — oculta hasta que se configure un pin
        self._tab_bar = self._build_tab_bar()
        self._main_layout.addWidget(self._tab_bar)

        # Barra de navegación — siempre visible en modo uso (tiene botón ＋)
        self._nav_bar = QWidget()
        nav_h = QHBoxLayout(self._nav_bar)
        nav_h.setContentsMargins(0, 2, 0, 0)
        nav_h.setSpacing(4)

        # ── Controles de vista: opacidad + tamaño (movidos de la top bar) ────
        self._dim_btn = self._make_icon_btn("◐", "#444", tooltip="Menos opacidad",
                                            size=(20, 20))
        self._dim_btn.clicked.connect(lambda: self._adjust_opacity(-0.08))
        nav_h.addWidget(self._dim_btn)

        self._bright_btn = self._make_icon_btn("●", "#444", tooltip="Más opacidad",
                                               size=(20, 20))
        self._bright_btn.clicked.connect(lambda: self._adjust_opacity(+0.08))
        nav_h.addWidget(self._bright_btn)

        self._size_dn_btn = self._make_icon_btn("A−", "#444", tooltip="Botones más pequeños",
                                                size=(22, 20))
        self._size_dn_btn.clicked.connect(lambda: self._resize_buttons(-10))
        nav_h.addWidget(self._size_dn_btn)

        self._size_up_btn = self._make_icon_btn("A+", "#444", tooltip="Botones más grandes",
                                                size=(22, 20))
        self._size_up_btn.clicked.connect(lambda: self._resize_buttons(+10))
        nav_h.addWidget(self._size_up_btn)

        # Separador visual entre controles de vista y navegación de páginas
        _sep = QFrame()
        _sep.setFrameShape(QFrame.VLine)
        _sep.setFixedWidth(1)
        _sep.setStyleSheet("background: #444;")
        nav_h.addWidget(_sep)

        # B3: botón ＋ de acceso rápido
        self._quick_add_btn = self._make_icon_btn("＋", "#27AE60",
                                                   tooltip="Añadir atajo rápido",
                                                   size=(20, 20))
        self._quick_add_btn.clicked.connect(self._quick_add_shortcut)
        nav_h.addWidget(self._quick_add_btn)

        self._prev_btn = self._make_icon_btn("◀", "#444", tooltip="Página anterior",
                                             size=(20, 20))
        self._prev_btn.clicked.connect(self._prev_page)
        self._page_label = QLabel("1 / 1")
        self._page_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        self._page_label.setAlignment(Qt.AlignCenter)
        self._next_btn = self._make_icon_btn("▶", "#444", tooltip="Página siguiente",
                                             size=(20, 20))
        self._next_btn.clicked.connect(self._next_page)
        nav_h.addWidget(self._prev_btn)
        nav_h.addWidget(self._page_label, 1)
        nav_h.addWidget(self._next_btn)

        # Handle de resize dentro del nav_bar (esquina inferior-derecha natural)
        self._resize_handle = ResizeHandle(self._nav_bar)
        nav_h.addWidget(self._resize_handle)

        self._nav_bar.show()   # siempre visible en uso (el ＋ siempre está)
        self._main_layout.addWidget(self._nav_bar)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(32)
        bar.setCursor(Qt.SizeAllCursor)
        h = QHBoxLayout(bar)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(3)

        # Ícono drag
        drag_lbl = QLabel("≡")
        drag_lbl.setStyleSheet("color: #888888; font-size: 14px;")
        drag_lbl.setFixedWidth(16)
        h.addWidget(drag_lbl)

        # Combobox de perfil
        self._profile_combo = QComboBox()
        self._profile_combo.setFocusPolicy(Qt.NoFocus)
        self._profile_combo.addItems(self._pm.get_profile_names())
        self._profile_combo.setCurrentText(self._pm.get_active_profile())
        self._profile_combo.setStyleSheet("""
            QComboBox {
                background: #3a3a3a; color: white;
                border: 1px solid #555; border-radius: 5px;
                padding: 2px 6px; font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #2d2d2d; color: white;
                selection-background-color: #4a90d9;
            }
        """)
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        # S2: detectar selección manual para activar cooldown de auto-switch
        self._profile_combo.activated.connect(self._on_manual_profile_change)
        h.addWidget(self._profile_combo, 1)

        # ── Perfil base (pin) ─────────────────────────────────────────────────
        self._pin_btn = self._make_icon_btn("📌", "#444", tooltip="Perfil base siempre visible")
        self._pin_btn.setFixedSize(26, 26)
        self._pin_btn.clicked.connect(self._toggle_pinned_profile)
        h.addWidget(self._pin_btn)

        # ── Editar / Listo (mismo slot, se alternan según el modo) ────────────
        self._edit_btn = self._make_icon_btn("✏", "#555555", tooltip="Editar atajos")
        self._edit_btn.clicked.connect(self.enter_edit_mode)
        h.addWidget(self._edit_btn)

        self._done_btn = self._make_icon_btn("✓", "#27AE60", tooltip="Volver al modo uso")
        self._done_btn.clicked.connect(self.enter_use_mode)
        self._done_btn.hide()   # oculto en modo uso
        h.addWidget(self._done_btn)

        # ── Colapsar ──────────────────────────────────────────────────────────
        collapse_btn = self._make_icon_btn("⊟", "#555555", tooltip="Plegar a ícono")
        collapse_btn.clicked.connect(self.collapse)
        h.addWidget(collapse_btn)

        # ── Ocultar (bandeja) ─────────────────────────────────────────────────
        hide_btn = self._make_icon_btn("✕", "#555555", tooltip="Ocultar (bandeja)")
        hide_btn.clicked.connect(self.hide)
        h.addWidget(hide_btn)

        self._update_pin_btn_visual()   # restaurar estado visual del pin al iniciar
        return bar

    @staticmethod
    def _make_icon_btn(text: str, color: str, tooltip: str = "",
                       size: tuple = (24, 24)) -> QPushButton:
        btn = QPushButton(text)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedSize(*size)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border-radius: 5px;
                font-size: 11px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:pressed {{ background: #2a2a2a; }}
        """)
        return btn

    # ── Carga de perfil con paginación (S6: _execute_button; S7: separadores) ─

    def _load_profile(self, profile: str):
        # Limpiar grid — setParent(None) quita el widget del layout de inmediato
        # (a diferencia de solo deleteLater), lo que permite que el layout
        # recalcule su tamaño mínimo antes de que _fit_height llame a resize()
        while self._btn_grid.count():
            item = self._btn_grid.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()

        all_buttons = self._pm.get_buttons(profile)
        per_page = self._pm.get_buttons_per_page(profile)
        total_pages = max(1, math.ceil(len(all_buttons) / per_page)) if all_buttons else 1
        self._total_pages = total_pages                          # carrusel
        self._current_page = self._current_page % total_pages   # wrap en lugar de clamp

        start = self._current_page * per_page
        page_buttons = all_buttons[start: start + per_page]

        _, btn_h = self._pm.get_button_size()

        # S7: bucle con tracking de row/col para manejar separadores
        row, col = 0, 0
        for btn_data in page_buttons:
            btn_type = btn_data.get("type", "hotkey")

            if btn_type == "separator":
                # Separador: ocupa fila completa
                if col > 0:
                    row += 1
                    col = 0
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("color: #555555; background-color: #555555;")
                sep.setFixedHeight(2)
                self._btn_grid.addWidget(sep, row, 0, 1, self.COLUMNS)
                row += 1
            else:
                # S6: mostrar hotkey o action como subtítulo según tipo
                if btn_type in ("url", "app"):
                    display_sub = btn_data.get("action", "")
                else:
                    display_sub = btn_data.get("hotkey", "")

                btn = ShortcutButton(
                    label=btn_data.get("label", ""),
                    hotkey=display_sub,
                    color=btn_data.get("color", "#4a90d9"),
                    # S6: lambda que captura btn_data completo
                    send_fn=lambda bd=btn_data: self._execute_button(bd),
                    size=(55, btn_h),
                )
                self._btn_grid.addWidget(btn, row, col)
                col += 1
                if col >= self.COLUMNS:
                    col = 0
                    row += 1

        # D1: guardar filas reales del grid para auto-fit de altura
        actual_rows = row + (1 if col > 0 else 0)
        self._last_grid_rows = max(1, actual_rows)

        # Asegurar columnas de igual ancho
        for c in range(self.COLUMNS):
            self._btn_grid.setColumnStretch(c, 1)

        # Paginación — nav_bar siempre visible; mostrar controles solo si hay >1 página
        has_pages = total_pages > 1
        self._prev_btn.setVisible(has_pages)
        self._page_label.setVisible(has_pages)
        self._next_btn.setVisible(has_pages)
        if has_pages:
            self._page_label.setText(f"{self._current_page + 1} / {total_pages}")

        # D1: auto-ajustar altura al contenido real
        self._fit_height(self._last_grid_rows)

    def _fit_height(self, grid_rows: int):
        """D1: Redimensiona la ventana a la altura exacta del contenido visible."""
        if self._mode != "use":
            return
        _, btn_h = self._pm.get_button_size()
        GRID_SPACING = 5
        OUTER_V     = 10   # 5+5 outer margins (D4)
        INNER_V     = 8    # 4+4 inner margins (D4)
        TOP_BAR     = 32
        CONTENT_TOP = 4    # content_layout top margin
        NAV_H       = 22   # 20px botones + 2px margen superior (D3)
        SPACING     = 8    # 4px × 2 gaps visibles (top_bar↔content, content↔nav)

        grid_h = grid_rows * btn_h + max(0, grid_rows - 1) * GRID_SPACING
        tab_h  = 34 if self._tab_bar.isVisible() else 0  # 30px + 4px spacing extra
        total  = OUTER_V + INNER_V + TOP_BAR + CONTENT_TOP + grid_h + NAV_H + SPACING + tab_h + 2

        new_h = max(100, total)
        # Quitar restricciones de altura para permitir reducir el tamaño
        # cuando se cambia a un perfil con menos filas que el anterior
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)   # QWIDGETSIZE_MAX
        self.resize(self.width(), new_h)
        self._pm.save_window_size(self.width(), new_h)

    def _on_profile_changed(self, name: str):
        if name:
            self._current_page = 0
            self._pm.set_active_profile(name)
            self._update_tab_bar()                   # actualizar etiqueta de la pestaña activa
            if not self._viewing_pinned:             # solo recargar el grid si estamos en la pestaña activa
                self._load_profile(name)
                # S8: actualizar label de perfil
                self._profile_name_label.setText(name)

    # ── S6: ejecutar botón según tipo ────────────────────────────────────────

    def _execute_button(self, btn_data: dict):
        t = btn_data.get("type", "hotkey")
        if t == "url":
            try:
                webbrowser.open(btn_data.get("action", ""))
            except Exception as e:
                _log.warning("Error abriendo URL '%s': %s", btn_data.get("action", ""), e)
                ToastNotification(self, "No se pudo abrir la URL")
        elif t == "app":
            try:
                subprocess.Popen(btn_data.get("action", ""), shell=True)
            except Exception as e:
                _log.warning("Error lanzando app '%s': %s", btn_data.get("action", ""), e)
                ToastNotification(self, "No se pudo lanzar la app")
        else:
            # Hotkey (comportamiento original)
            self.send_hotkey(btn_data.get("hotkey", btn_data.get("action", "")))

    # ── Paginación ────────────────────────────────────────────────────────────

    def _prev_page(self):
        total = getattr(self, '_total_pages', 1)
        self._current_page = (self._current_page - 1) % total   # carrusel
        self._load_profile(self._current_viewed_profile())

    def _next_page(self):
        total = getattr(self, '_total_pages', 1)
        self._current_page = (self._current_page + 1) % total   # carrusel
        self._load_profile(self._current_viewed_profile())

    def _current_viewed_profile(self) -> str:
        """Retorna el perfil que se está mostrando actualmente en el grid."""
        if self._viewing_pinned:
            return self._pm.get_pinned_profile()
        return self._pm.get_active_profile()

    # ── Opacidad ──────────────────────────────────────────────────────────────

    def _adjust_opacity(self, delta: float):
        if self._mode != "use":
            return   # La opacidad solo se ajusta en modo uso
        new_val = self._pm.get_opacity() + delta
        self._pm.set_opacity(new_val)
        self.setWindowOpacity(self._pm.get_opacity())

    # ── Altura de botones (A+/A−) ─────────────────────────────────────────────

    def _resize_buttons(self, delta: int):
        """A+/A− cambia solo la altura de los botones; el ancho se controla con el handle ⊿."""
        _, h = self._pm.get_button_size()
        new_h = max(40, min(110, h + int(delta * 0.72)))
        self._pm.set_button_size(55, new_h)
        self._load_profile(self._current_viewed_profile())

    # ── Envío de hotkey ───────────────────────────────────────────────────────

    def send_hotkey(self, hotkey_string: str):
        keys = [k.strip() for k in hotkey_string.lower().split("+")]
        key_map = {
            "grave": "`", "slash": "/", "backslash": "\\",
            "plus": "+", "minus": "-",
        }
        mapped = [key_map.get(k, k) for k in keys]

        if "win" in mapped:
            QTimer.singleShot(60, lambda: self._send_win_combo(mapped))
        else:
            QTimer.singleShot(60, lambda: pyautogui.hotkey(*mapped))

    @staticmethod
    def _send_win_combo(keys: list):
        if not WIN32_AVAILABLE:
            return
        other = [k for k in keys if k != "win"]
        try:
            win32api.keybd_event(win32con.VK_LWIN, 0, 0, 0)
            for k in other:
                pyautogui.press(k)
            win32api.keybd_event(win32con.VK_LWIN, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception as e:
            _log.warning("Error enviando combinación Win32: %s", e)

    # ── Modos ─────────────────────────────────────────────────────────────────

    def collapse(self):
        """Plegar el overlay a un ícono flotante con animación suave (S9)."""
        # Detener animación previa si existe
        if self._anim is not None:
            self._anim.stop()

        # Registrar geometría actual (expandida) antes de modificar nada
        start_rect = self.geometry()

        # Ejecutar el colapso normal: ocultar contenido, mostrar expand_btn
        self._top_bar.hide()
        self._content_area.hide()
        self._nav_bar.hide()   # oculta también el handle ⊿ que vive dentro
        self._tab_bar.hide()
        self._profile_name_label.hide()   # S8
        self._expand_btn.show()
        self._pre_collapse_mode = self._mode   # recordar qué modo estaba activo
        self._mode = "collapsed"
        self._process_timer.stop()   # A1: no auto-switch en modo colapsado
        self.setWindowOpacity(1.0)
        self.update()   # forzar repintado para que paintEvent salte el fondo

        # Eliminar márgenes del layout para que el icono quede ajustado y cuadrado
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Obtener el tamaño colapsado con adjustSize y registrarlo
        self.adjustSize()
        end_rect = self.geometry()

        # Restaurar la geometría expandida para comenzar la animación desde ahí
        self.setGeometry(start_rect)

        # S9: animar de expandido a colapsado
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(160)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim = anim
        anim.start()

    def expand(self):
        """Expandir desde el ícono al overlay completo con animación suave (S9).
        Restaura el modo que estaba activo antes del colapso (uso o edición)."""
        # Detener animación previa si existe
        if self._anim is not None:
            self._anim.stop()

        # D1: capturar geometría colapsada ANTES de que _load_profile() pueda llamar resize()
        start_rect = self.geometry()

        # Restaurar márgenes del layout (se zeraron al colapsar)
        self._outer_layout.setContentsMargins(5, 5, 5, 5)
        self._main_layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout.setSpacing(4)

        # Mostrar contenido inmediatamente para que sea visible durante la animación
        self._expand_btn.hide()
        self.update()   # repintar fondo del overlay ahora que ya no estamos en "collapsed"
        self._top_bar.show()
        self._content_area.show()
        # (el resize handle se muestra con nav_bar en cada rama)

        screen = QApplication.primaryScreen().availableGeometry()

        if self._pre_collapse_mode == "edit":
            # ── Restaurar modo edición ────────────────────────────────────────
            self._mode = "edit"
            self.setWindowOpacity(1.0)

            # Asegurarse de que el panel de edición esté visible
            if self._edit_panel is not None:
                self._edit_panel.show()
            self._btn_widget.hide()
            self._profile_name_label.hide()
            self._edit_btn.hide()
            self._dim_btn.hide()
            self._bright_btn.hide()
            self._size_dn_btn.hide()
            self._size_up_btn.hide()
            self._pin_btn.hide()
            self._quick_add_btn.hide()
            self._prev_btn.hide()
            self._page_label.hide()
            self._next_btn.hide()
            self._done_btn.show()
            self._profile_combo.setEnabled(False)
            self._nav_bar.show()   # visible para el handle ⊿

            target_w, target_h = self._pm.get_edit_size()
            new_x = max(screen.left(), min(self.x(), screen.right() - target_w))
            new_y = max(screen.top(), min(self.y(), screen.bottom() - target_h))

        else:
            # ── Restaurar modo uso ────────────────────────────────────────────
            self._mode = "use"
            self._process_timer.start()   # A1: reanudar auto-switch al expandir en uso
            self.setWindowOpacity(self._pm.get_opacity())

            # Asegurarse de que el panel de uso esté visible
            if self._edit_panel:
                self._edit_panel.hide()
            self._btn_widget.show()
            self._edit_btn.show()
            self._done_btn.hide()
            self._dim_btn.show()
            self._bright_btn.show()
            self._size_dn_btn.show()
            self._size_up_btn.show()
            self._quick_add_btn.show()   # B3: mostrar ＋ al expandir en uso
            self._update_pin_btn_visual()
            self._profile_combo.setEnabled(True)
            self._viewing_pinned = False
            active = self._pm.get_active_profile()
            self._profile_name_label.hide()  # D2: ocultar label en uso
            self._nav_bar.show()   # B3: nav_bar siempre visible en uso
            self._load_profile(active)   # D1: llama _fit_height() → resize() + set_window_size()
            self._update_tab_bar()

            target_w, target_h = self._pm.get_window_size()  # D1: tamaño auto-fit ya guardado
            new_x = max(screen.left(), min(self.x(), screen.right() - target_w))
            new_y = max(screen.top(), min(self.y(), screen.bottom() - target_h))
            self._pm.save_window_pos(new_x, new_y)

        # S9: animar de colapsado a expandido (start_rect capturado al inicio antes de resize)
        end_rect = QRect(new_x, new_y, target_w, target_h)

        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(160)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim = anim
        anim.start()

    def enter_edit_mode(self):
        from edit_panel import EditPanel
        self._process_timer.stop()   # A1: no auto-switch en modo edición
        # Guardar tamaño actual (uso) y restaurar el del modo edición
        self._pm.save_window_size(self.width(), self.height())

        # Si aún no se ha guardado un tamaño de edición, calcularlo
        # automáticamente: 90% de la altura de pantalla, ancho basado en contenido
        if "edit_size" not in self._pm._data:
            screen = QApplication.primaryScreen().availableGeometry()
            auto_h = int(screen.height() * 0.90)
            auto_w = max(340, min(400, int(screen.width() * 0.22)))
            self._pm.save_edit_size(auto_w, auto_h)

        edit_w, edit_h = self._pm.get_edit_size()

        self._btn_widget.hide()
        self._tab_bar.hide()
        self._profile_name_label.hide()   # S8
        if self._edit_panel is None:
            self._edit_panel = EditPanel(self._pm, self)
            self._content_layout.addWidget(self._edit_panel)
        else:
            self._edit_panel.reload()
            self._edit_panel.show()
        self._edit_btn.hide()
        self._profile_combo.setEnabled(False)
        # Ocultar controles irrelevantes en edición, mostrar botón volver
        self._dim_btn.hide()
        self._bright_btn.hide()
        self._size_dn_btn.hide()
        self._size_up_btn.hide()
        self._pin_btn.hide()
        self._quick_add_btn.hide()   # B3: ocultar ＋ en modo edición
        self._prev_btn.hide()
        self._page_label.hide()
        self._next_btn.hide()
        # nav_bar se mantiene visible en edición para que el handle ⊿ sea accesible
        self._nav_bar.show()
        self._done_btn.show()
        self._mode = "edit"
        self.setWindowOpacity(1.0)   # Edición siempre completamente opaca
        self.resize(edit_w, edit_h)

    def enter_use_mode(self):
        # Guardar tamaño actual (edición) y restaurar el del modo uso
        self._pm.save_edit_size(self.width(), self.height())

        if self._edit_panel:
            self._edit_panel.hide()
        self._btn_widget.show()
        self._edit_btn.show()
        self._done_btn.hide()
        self._dim_btn.show()
        self._bright_btn.show()
        self._size_dn_btn.show()
        self._size_up_btn.show()
        self._pin_btn.show()
        self._quick_add_btn.show()   # B3: mostrar ＋ al volver a modo uso
        self._update_pin_btn_visual()
        self._profile_combo.setEnabled(True)
        self._mode = "use"
        # Restaurar ancho de uso (guardado en enter_edit_mode) antes de _load_profile
        # para que _fit_height use el ancho correcto y no el del modo edición
        _use_w, _ = self._pm.get_window_size()
        self.resize(_use_w, self.height())
        # Refrescar combobox
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(self._pm.get_profile_names())
        active = self._pm.get_active_profile()
        self._profile_combo.setCurrentText(active)
        self._profile_combo.blockSignals(False)
        self._current_page = 0
        self._viewing_pinned = False
        self._nav_bar.show()   # B3: nav_bar siempre visible en uso
        self._load_profile(active)
        # D2: ocultar label de perfil en uso (el combo ya lo muestra)
        self._profile_name_label.hide()
        self._update_tab_bar()
        self.setWindowOpacity(self._pm.get_opacity())
        # D1: altura ya ajustada por _fit_height() dentro de _load_profile()
        self._process_timer.start()   # A1: reanudar auto-switch al volver a uso

    def reload_overlay(self):
        self.enter_use_mode()

    # ── S2: Auto-switch por proceso activo ───────────────────────────────────

    def _get_foreground_process(self) -> str:
        """Obtiene el nombre del ejecutable de la ventana en primer plano."""
        if not WIN32_AVAILABLE:
            return ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            # Ignorar si la ventana en foco es el propio overlay
            if hwnd == int(self.winId()):
                return self._last_fg_process
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            handle = win32api.OpenProcess(0x0410, False, pid)
            name = win32process.GetModuleFileNameEx(handle, 0)
            win32api.CloseHandle(handle)
            return os.path.basename(name).lower()
        except Exception:
            return ""

    def _check_foreground_process(self):
        """Compara el proceso activo con los perfiles configurados y cambia si coincide."""
        if self._mode != "use" or self._auto_switch_cooldown:
            return
        proc = self._get_foreground_process()
        if not proc or proc == self._last_fg_process:
            return
        self._last_fg_process = proc
        for name in self._pm.get_profile_names():
            configured = self._pm.get_profile_process(name).strip().lower()
            if configured and configured == proc:
                if name != self._pm.get_active_profile():
                    self._profile_combo.setCurrentText(name)  # dispara _on_profile_changed
                break

    def _on_manual_profile_change(self, index: int):
        """Activa cooldown de 3 s para el auto-switch cuando el usuario cambia perfil manualmente."""
        self._auto_switch_cooldown = True
        QTimer.singleShot(3000, lambda: setattr(self, "_auto_switch_cooldown", False))

    # ── Pestaña de perfil base ────────────────────────────────────────────────

    def _build_tab_bar(self) -> QWidget:
        """Construye el mini tab bar con pestaña activa y pestaña del perfil base."""
        bar = QWidget()
        bar.setFixedHeight(30)
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 2, 0, 0)
        h.setSpacing(3)

        self._tab_active_btn = QPushButton("")
        self._tab_active_btn.setFocusPolicy(Qt.NoFocus)
        self._tab_active_btn.clicked.connect(lambda: self._on_tab_click("active"))

        self._tab_pinned_btn = QPushButton("")
        self._tab_pinned_btn.setFocusPolicy(Qt.NoFocus)
        self._tab_pinned_btn.clicked.connect(lambda: self._on_tab_click("pinned"))

        for btn in (self._tab_active_btn, self._tab_pinned_btn):
            btn.setFixedHeight(26)
            h.addWidget(btn, 1)

        bar.hide()   # oculto hasta que se configure un pin
        return bar

    def _update_tab_bar(self):
        """Actualiza etiquetas, colores y visibilidad del tab bar."""
        pinned = self._pm.get_pinned_profile()
        if not pinned:
            self._tab_bar.hide()
            return

        active = self._pm.get_active_profile()
        self._tab_active_btn.setText(active)
        self._tab_pinned_btn.setText(pinned)

        if self._viewing_pinned:
            self._tab_active_btn.setStyleSheet(_TAB_STYLE_OFF)
            self._tab_pinned_btn.setStyleSheet(_TAB_STYLE_ON)
        else:
            self._tab_active_btn.setStyleSheet(_TAB_STYLE_ON)
            self._tab_pinned_btn.setStyleSheet(_TAB_STYLE_OFF)

        self._tab_bar.show()

    def _on_tab_click(self, which: str):
        """Cambia la pestaña visible sin afectar el perfil activo del sistema."""
        if which == "pinned":
            self._viewing_pinned = True
            profile = self._pm.get_pinned_profile()
        else:
            self._viewing_pinned = False
            profile = self._pm.get_active_profile()

        self._current_page = 0
        self._load_profile(profile)
        self._profile_name_label.setText(profile)
        self._update_tab_bar()

    def _toggle_pinned_profile(self):
        """Cicla entre: sin pin → cada perfil distinto al activo → sin pin."""
        names = self._pm.get_profile_names()
        current_pin = self._pm.get_pinned_profile()
        active = self._pm.get_active_profile()
        candidates = [""] + [n for n in names if n != active]
        idx = candidates.index(current_pin) if current_pin in candidates else 0
        next_pin = candidates[(idx + 1) % len(candidates)]

        self._pm.set_pinned_profile(next_pin)

        # Si se quita el pin, volver a mostrar la pestaña activa
        if not next_pin:
            self._viewing_pinned = False
            self._load_profile(active)
            self._profile_name_label.setText(active)

        self._update_pin_btn_visual()
        self._update_tab_bar()

    def _update_pin_btn_visual(self):
        """Actualiza color y tooltip del botón 📌 según si hay perfil base configurado."""
        pinned = self._pm.get_pinned_profile()
        color = "#1a5276" if pinned else "#444"
        tip = (f"Perfil base: {pinned} (toca para cambiar)"
               if pinned else "Perfil base: sin configurar (toca para activar)")
        self._pin_btn.setStyleSheet(f"""QPushButton {{
            background: {color}; color: white; border-radius: 5px;
            font-size: 11px; border: none;
        }} QPushButton:pressed {{ background: #2a2a2a; }}""")
        self._pin_btn.setToolTip(tip)

    def _quick_add_shortcut(self):
        """B3: abre ShortcutEditDialog para añadir un atajo rápidamente al perfil actual."""
        from edit_panel import ShortcutEditDialog
        dlg = ShortcutEditDialog(parent=None)
        if dlg.exec_() == dlg.Accepted:
            data = dlg.get_data()
            profile = self._current_viewed_profile()
            buttons = self._pm.get_buttons(profile)
            buttons.append(data)
            self._pm.set_buttons(profile, buttons)
            self._load_profile(profile)

    # ── Redimensionamiento de ventana ─────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # El timer ya no dispara recargas: el reload por resize del usuario
        # lo hace _end_resize directamente, sin riesgo de loop.

    # ── Pintar fondo redondeado ───────────────────────────────────────────────

    def paintEvent(self, event):
        # En modo colapsado el CollapsedIconWidget pinta todo — no dibujar fondo
        if self._mode == "collapsed":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        rect = self.rect().adjusted(4, 4, -4, -4)
        path.addRoundedRect(float(rect.x()), float(rect.y()),
                            float(rect.width()), float(rect.height()), 12.0, 12.0)
        painter.fillPath(path, QColor(22, 22, 28, 230))
        painter.setPen(QColor(80, 80, 90, 120))
        painter.drawPath(path)

    # ── Helpers de resize (llamados desde ResizeHandle) ───────────────────────

    def _start_resize(self, global_pos: QPoint):
        self._resizing = True
        self._resize_start = global_pos
        self._resize_start_size = (self.width(), self.height())

    def _do_resize(self, global_pos: QPoint):
        if not self._resizing:
            return
        delta = global_pos - self._resize_start
        new_w = max(155,self._resize_start_size[0] + delta.x())
        new_h = max(150, self._resize_start_size[1] + delta.y())
        self.resize(new_w, new_h)

    def _end_resize(self):
        if self._resizing:
            if self._mode == "edit":
                self._pm.save_edit_size(self.width(), self.height())
            else:
                self._pm.save_window_size(self.width(), self.height())
                # Recargar el grid con el nuevo ancho (sin timer — llamada directa)
                if self._mode == "use":
                    self._load_profile(self._current_viewed_profile())
            self._resizing = False

    # ── Drag para mover ───────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            in_top_bar = (self._top_bar.isVisible() and
                          self._top_bar.geometry().contains(event.pos()))
            if in_top_bar or self._mode == "collapsed":
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if self._drag_pos is not None:
                self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._pm.save_window_pos(self.x(), self.y())
            self._drag_pos = None

    # ── Fix Win32 para touchscreen ────────────────────────────────────────────

    def hideEvent(self, event):
        super().hideEvent(event)
        self._process_timer.stop()   # A1: no auto-switch mientras está oculto

    def showEvent(self, event):
        super().showEvent(event)
        # Re-aplicar opacidad correcta según modo al mostrarse
        if self._mode == "use":
            self.setWindowOpacity(self._pm.get_opacity())
            self._process_timer.start()   # A1: reanudar auto-switch al hacerse visible
        else:
            self.setWindowOpacity(1.0)
        if WIN32_AVAILABLE:
            try:
                hwnd = int(self.winId())
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                win32gui.SetWindowLong(
                    hwnd, win32con.GWL_EXSTYLE,
                    style | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
                )
            except Exception as e:
                _log.warning("showEvent Win32: %s", e)
