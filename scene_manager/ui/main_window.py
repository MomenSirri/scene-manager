"""Scene Manager panel: its own frameless window owned by the 3ds Max main window.

Layout: icon rail | setups sidebar (folders tree or thumbnail grid, search, tag chips) | setup header
and module cards. When the panel is narrow the sidebar moves above the cards.
"""
import os
import traceback

from PySide6 import QtCore, QtGui, QtWidgets
from pymxs import runtime as rt

from .. import config, thumbnails
from ..core import registry, tokens
from ..core.manager import get_manager
from ..render import batch
from . import theme
from .cards import ModuleCard
from .flow import FlowLayout
from . import backdrop, icons, layout
from .board import CardBoard, sort_modules
from . import groups
from . import scene_tools  # M2: baseline + repair menu entries

ID_ROLE = QtCore.Qt.UserRole + 1
CARD_MIN_WIDTH = 300
NARROW = 800
_dock = None


def _max_main_window():
    try:
        from qtmax import GetQMaxMainWindow
        return GetQMaxMainWindow()
    except ImportError:
        return None


def show():
    """Open (or raise) Scene Manager: its own window floating above 3ds Max, like Scene Manager 3 (no docking)."""
    global _dock
    if _dock is None:
        _dock = AppWindow(_max_main_window())
    _dock.show()
    if _dock.isMinimized():
        _dock.showNormal()
    _dock.raise_()
    _dock.activateWindow()
    return _dock


WINDOW_QSS = """
#SMTitleBar QLabel#SMTitleText { color: #f5f5f7; font-size: 12px; font-weight: 600; }
#SMTitleBar QToolButton { border: none; border-radius: 6px; }
#SMTitleBar QToolButton:hover { background: #ffffff1a; }
#SMTitleBar QToolButton#SMTitleClose:hover { background: #ff453acc; }
"""
def _log_window(w):
    """Diagnostics for 'small windows flash on New Setup': every other window that opens while Scene Manager
    is up is written to ~/.scene_manager/windows.log with the Python call stack that opened it."""
    try:
        import datetime
        stack = "".join(traceback.format_stack(limit=14)[:-2])
        line = "%s  %s  name=%r  title=%r  flags=%s  parent=%s\n%s\n" % (
            datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3], type(w).__name__, w.objectName(),
            w.windowTitle(), int(w.windowFlags()), type(w.parentWidget()).__name__ if w.parentWidget() else None, stack)
        config.HOME.mkdir(parents=True, exist_ok=True)
        with open(config.HOME / "windows.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


EDGE = 5  # px around the window that resize it


def _backdrop_host(widget):
    """The widget whose size the backdrop is painted for: the whole window, so title bar and panel share one pattern."""
    return widget.window() if widget.window() is not None else widget


class _EdgeGrip(QtWidgets.QWidget):
    """Invisible strip on one edge or corner of the window: shows the resize cursor and starts a system resize.
    Eight of these replace an application-wide event filter, so nothing of ours runs for 3ds Max's own events."""

    @staticmethod
    def _cursor(edges):
        L, R, T, B = QtCore.Qt.LeftEdge, QtCore.Qt.RightEdge, QtCore.Qt.TopEdge, QtCore.Qt.BottomEdge
        if edges in (L | T, R | B):
            return QtCore.Qt.SizeFDiagCursor
        if edges in (R | T, L | B):
            return QtCore.Qt.SizeBDiagCursor
        return QtCore.Qt.SizeHorCursor if edges in (L, R) else QtCore.Qt.SizeVerCursor

    def __init__(self, win, edges):
        super().__init__(win)
        self.edges = edges
        self.edges = QtCore.Qt.Edges(edges)
        self.corner = edges not in (QtCore.Qt.LeftEdge, QtCore.Qt.RightEdge, QtCore.Qt.TopEdge, QtCore.Qt.BottomEdge)
        self.setCursor(self._cursor(edges))

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            h = self.window().windowHandle()
            if h is not None:
                h.startSystemResize(self.edges)
        e.accept()


class _WindowLogger(QtCore.QObject):
    """Diagnostics, off by default (config "debug_windows": true): logs every window that opens."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QWidget) and obj.isWindow() \
                and obj is not self.win:
            _log_window(obj)
        return False


class AppWindow(QtWidgets.QWidget):
    """Frameless top-level window with our own title bar. Owned by the 3ds Max main window, so it stays above
    Max (not above other programs) and minimises with it. Moves, snaps and resizes through the system."""

    def __init__(self, owner=None):
        super().__init__(owner, QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.setObjectName("SceneManagerWindow")
        self.setWindowTitle("Scene Manager")
        self.setWindowIcon(icons.tinted("setups", "#64d2ff"))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.setMinimumSize(560, 380)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)  # 1 px outline
        lay.setSpacing(0)
        self.title_bar = TitleBar(self)
        self.title_bar.setStyleSheet(theme.rgba(WINDOW_QSS))
        lay.addWidget(self.title_bar)
        self.panel = Panel(self)
        lay.addWidget(self.panel, 1)
        L, R, T, B = QtCore.Qt.LeftEdge, QtCore.Qt.RightEdge, QtCore.Qt.TopEdge, QtCore.Qt.BottomEdge
        self._grips = [_EdgeGrip(self, e) for e in (L, R, T, B, L | T, R | T, L | B, R | B)]
        self._gt = QtCore.QTimer(self, singleShot=True, interval=400, timeout=self._save_geometry)
        cfg = config.load()
        self._restore_geometry(cfg.get("window_geometry"))
        if cfg.get("debug_windows"):
            self._logger = _WindowLogger(self)
            QtWidgets.QApplication.instance().installEventFilter(self._logger)
        _keep_typing_out_of_max(self)

    def widget(self):  # same call as the old dock, used by tests and scripts
        return self.panel

    def _restore_geometry(self, g):
        """Saved place and size, unless the monitor it was on is gone: then centre on the current screen."""
        rect = QtCore.QRect(*g) if g and len(g) == 4 else None
        screens = QtGui.QGuiApplication.screens()
        if rect is not None and any(sc.availableGeometry().intersects(rect.adjusted(40, 10, -40, -40)) for sc in screens):
            self.setGeometry(rect)
            return
        self.resize(1180, 720)
        owner = self.parentWidget()
        sc = (owner.screen() if owner is not None else None) or QtGui.QGuiApplication.primaryScreen()
        if sc is not None:
            a = sc.availableGeometry()
            self.resize(min(1180, a.width() - 80), min(720, a.height() - 80))
            self.move(a.center() - self.rect().center())

    # ---- resize from the edges (system resize keeps it smooth and snaps on Windows) ----
    def _place_grips(self):
        w, h, e = self.width(), self.height(), EDGE
        c = e * 2  # corners are a bit larger, easier to hit
        geo = (
            (0, c, e, h - 2 * c), (w - e, c, e, h - 2 * c), (c, 0, w - 2 * c, e), (c, h - e, w - 2 * c, e),
            (0, 0, c, c), (w - c, 0, c, c), (0, h - c, c, c), (w - c, h - c, c, c))
        show = not (self.isMaximized() or self.isFullScreen())
        for g, r in zip(self._grips, geo):
            if g.corner:
                # an L-shaped corner: only the outer band takes the mouse, the inside stays clickable
                g.setMask(QtGui.QRegion(0, 0, c, c) - QtGui.QRegion(
                    e if g.edges & QtCore.Qt.LeftEdge else 0, e if g.edges & QtCore.Qt.TopEdge else 0, c - e, c - e))
            g.setGeometry(*r)
            g.setVisible(show)
            g.raise_()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        if getattr(self.panel, "glass", True):
            p.drawPixmap(0, 0, backdrop.pixmap(self.width(), self.height(), self.devicePixelRatioF(),
                                               getattr(self.panel, "scheme", backdrop.DEFAULT_SCHEME)))
        else:
            p.fillRect(self.rect(), QtGui.QColor(theme.BG))
        p.setPen(QtGui.QColor(255, 255, 255, 36))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()

    def _save_geometry(self):
        if not self.isMaximized() and not self.isMinimized():
            g = self.geometry()
            geo = [g.x(), g.y(), g.width(), g.height()]
            if config.load().get("window_geometry") != geo:
                config.update(window_geometry=geo)

    def moveEvent(self, e):
        super().moveEvent(e)
        self._gt.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_grips()
        self._gt.start()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QtCore.QEvent.WindowStateChange and hasattr(self, "_grips"):
            self._place_grips()
            self.title_bar.sync_max_button()
        elif e.type() == QtCore.QEvent.ActivationChange and self.isActiveWindow() and hasattr(self, "panel"):
            self.panel.on_window_activated()

    def closeEvent(self, e):
        self._gt.stop()
        self._save_geometry()
        self.panel.save_view_state()
        super().closeEvent(e)


def _keep_typing_out_of_max(window):
    """While one of our text fields has the focus, 3ds Max must not treat typed keys as its shortcuts."""
    try:
        import qtmax
        qtmax.DisableMaxAcceleratorsOnFocus(window, True)  # UNVERIFIED name: check `dir(qtmax)` in Max 2025/2026
    except Exception:
        pass


class TitleBar(QtWidgets.QWidget):
    """Our own title bar: drag to move, double-click to maximise; minimise, maximise and close buttons."""

    HEIGHT = 36

    def __init__(self, win):
        super().__init__(win)
        self.setObjectName("SMTitleBar")
        self.win = win
        self.setFixedHeight(self.HEIGHT)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 6, 0)
        lay.setSpacing(4)
        logo = QtWidgets.QLabel()
        logo.setPixmap(icons.tinted("setups", "#64d2ff").pixmap(16, 16))
        lay.addWidget(logo)
        lay.addSpacing(4)
        t = QtWidgets.QLabel("Scene Manager")
        t.setObjectName("SMTitleText")
        lay.addWidget(t)
        lay.addStretch(1)
        for name, tip, fn, obj in (("minimize", "Minimise", win.showMinimized, ""),
                                   ("maximize", "Maximise", self._toggle_max, ""),
                                   ("close", "Close", win.close, "SMTitleClose")):
            b = QtWidgets.QToolButton()
            if obj:
                b.setObjectName(obj)
            b.setIcon(icons.get(name, "#f5f5f7", "#a1a1a6"))
            b.setIconSize(QtCore.QSize(16, 16))
            b.setFixedSize(30, 26)
            b.setToolTip(tip)
            b.setFocusPolicy(QtCore.Qt.NoFocus)
            b.clicked.connect(fn)
            lay.addWidget(b)
            if name == "maximize":
                self.max_btn = b
        self._press = None

    def _toggle_max(self):
        self.win.showNormal() if self.win.isMaximized() else self.win.showMaximized()

    def sync_max_button(self):
        self.max_btn.setToolTip("Restore" if self.win.isMaximized() else "Maximise")

    # The move starts on the first drag step, not on the press, so a double-click still reaches us.
    def mousePressEvent(self, e):
        self._press = e.globalPosition().toPoint() if e.button() == QtCore.Qt.LeftButton else None

    def mouseMoveEvent(self, e):
        if self._press is not None and (e.globalPosition().toPoint() - self._press).manhattanLength() >= 4:
            self._press = None
            h = self.win.windowHandle()
            if h is not None:
                h.startSystemMove()

    def mouseReleaseEvent(self, e):
        self._press = None

    def mouseDoubleClickEvent(self, e):
        self._press = None
        if e.button() == QtCore.Qt.LeftButton:
            self._toggle_max()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        panel = self.win.panel if hasattr(self.win, "panel") else None
        if getattr(panel, "glass", True):
            off = self.mapTo(self.win, QtCore.QPoint(0, 0))
            p.drawPixmap(-off.x(), -off.y(), backdrop.pixmap(self.win.width(), self.win.height(), self.devicePixelRatioF(),
                                                           getattr(panel, "scheme", backdrop.DEFAULT_SCHEME)))
            p.fillRect(self.rect(), QtGui.QColor(10, 10, 12, 140))
        else:
            p.fillRect(self.rect(), QtGui.QColor(theme.RAIL))
        p.fillRect(QtCore.QRect(0, self.height() - 1, self.width(), 1), QtGui.QColor(255, 255, 255, 20))
        p.end()


def _guard(fn):
    def wrapper(self, *a, **k):
        try:
            return fn(self, *a, **k)
        except Exception as e:
            traceback.print_exc()
            QtWidgets.QMessageBox.warning(self, "Scene Manager", str(e))
    wrapper.__name__ = fn.__name__
    return wrapper


def _button(text, primary=False, tip=""):
    b = QtWidgets.QPushButton(text)
    b.setObjectName("SMPrimary" if primary else "SMButton")
    b.setToolTip(tip)
    return b


def _swatch(color, size=10):
    pm = QtGui.QPixmap(size, size + 6)
    pm.fill(QtCore.Qt.transparent)
    if color:
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setBrush(QtGui.QColor(color))
        p.setPen(QtCore.Qt.NoPen)
        p.drawRoundedRect(3, 1, 4, size + 4, 2, 2)
        p.end()
    return QtGui.QIcon(pm)


class Panel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SMPanel")
        cfg = config.load()
        self.glass = bool(cfg.get("glass_backdrop", True))
        self.scheme = cfg.get("backdrop_scheme", backdrop.DEFAULT_SCHEME)
        self.setPalette(theme.dark_palette())
        self.setAutoFillBackground(not self.glass)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, not self.glass)
        self.setStyleSheet(theme.stylesheet(self.glass))
        self.mgr = get_manager()
        self.selected = self.mgr.active_id
        self.checked = set()
        self.collapsed = set(cfg.get("collapsed_cards") or [])
        self.tag_filter = set()
        self._building = False
        self._board = None        # the CardBoard on screen; cards are updated in place, not rebuilt
        self._board_tok = None    # layout tokens the board was built with
        self._chips_sig = None
        self._queue_sig = None
        self._thumbs = {}         # setup id -> (thumbnail string, icon): decode each PNG once
        self._flash_text = ""
        self._flash_timer = QtCore.QTimer(self, singleShot=True, interval=5000, timeout=self.refresh_status)
        self._refresh_timer = QtCore.QTimer(self, singleShot=True, interval=0, timeout=self.refresh)
        self._resize_timer = QtCore.QTimer(self, singleShot=True, interval=120, timeout=self._after_resize)

        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_rail())
        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self._build_setups_page())
        self.pages.addWidget(self._build_render_page())
        self.pages.addWidget(self._build_claude_page())
        self.pages.addWidget(self._build_settings_page())
        right.addWidget(self.pages, 1)
        right.addWidget(self._build_status())
        root.addLayout(right, 1)

        self.mgr.add_listener(self.schedule_refresh)
        from ..bridge import commands
        commands._log_listeners.append(self._refresh_claude_log)
        self.destroyed.connect(lambda *_, m=self.mgr, fn=self.schedule_refresh: m.remove_listener(fn))
        self._install_shortcuts()
        self.refresh()

    def _install_shortcuts(self):
        """Keys work while the mouse focus is in the setups list; Ctrl+F works anywhere in the window."""
        def key(seq, fn, widget, ctx=QtCore.Qt.WidgetWithChildrenShortcut):
            a = QtGui.QAction(widget)
            a.setShortcut(QtGui.QKeySequence(seq))
            a.setShortcutContext(ctx)
            a.triggered.connect(fn)
            widget.addAction(a)

        for w in (self.tree, self.grid):
            key("Return", lambda: self.on_activate(self.selected), w)
            key("Enter", lambda: self.on_activate(self.selected), w)
            key("Delete", lambda: self.on_delete(), w)
            key("Ctrl+D", lambda: self.on_duplicate(), w)
            key("Ctrl+N", lambda: self.on_new_setup(), w)
            key("Ctrl+Shift+N", lambda: self.on_new_folder(), w)
        key("Ctrl+F", lambda: (self._on_page(0), self.search.setFocus(), self.search.selectAll()), self,
            QtCore.Qt.WidgetWithChildrenShortcut)

    def flash(self, text):
        """Status bar message that stays a few seconds (a plain setText is overwritten by the next refresh)."""
        self._flash_text = text
        self.status.setText(text)
        self._flash_timer.start()

    def on_window_activated(self):
        """Back from 3ds Max: the scene may have changed, so re-read it for the 'differs' dots."""
        if self.pages.currentIndex() == 0 and self._board is not None:
            self._refresh_timer.start()

    def save_view_state(self):
        cols = [m.key for i, m in enumerate(self.tree.cols, start=1) if not self.tree.isColumnHidden(i)]
        cfg = config.load()
        new = dict(tree_columns=cols, splitter=self.split.sizes() if self.split.orientation() == QtCore.Qt.Horizontal
                   else cfg.get("splitter"), collapsed_cards=sorted(self.collapsed))
        if any(cfg.get(k) != v for k, v in new.items()):
            config.update(**new)

    # ======================================================================
    # building
    # ======================================================================
    def _build_rail(self):
        """Left bar: pages (setups, render queue), module groups, then Claude and settings at the bottom."""
        rail = QtWidgets.QFrame()
        rail.setObjectName("SMRail")
        lay = QtWidgets.QVBoxLayout(rail)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(4)
        self.page_buttons = {}
        self.cat_buttons = {}

        def btn(icon_name, tip, active="#f5f5f7"):
            b = QtWidgets.QToolButton()
            b.setIcon(icons.get(icon_name, active))
            b.setIconSize(QtCore.QSize(icons.SIZE, icons.SIZE))
            b.setToolTip(tip)
            b.setCheckable(True)
            return b

        for idx, (icon_name, tip) in enumerate([("setups", "Setups: all modules"), ("render", "Render queue")]):
            b = btn(icon_name, tip)
            b.clicked.connect(lambda _=False, i=idx: self._on_page(i))
            self.page_buttons[idx] = b
            lay.addWidget(b)
        line = QtWidgets.QFrame()
        line.setObjectName("SMRailSep")
        line.setFixedHeight(1)
        lay.addWidget(line)
        self.add_rail_btn = btn("plus", "Add a module to this setup or folder", active=theme.ACCENT)
        self.add_rail_btn.setIcon(icons.get("plus", "#64d2ff", "#64d2ff"))
        self.add_rail_btn.setCheckable(False)
        self.add_rail_btn.clicked.connect(lambda: self._show_module_palette(self.add_rail_btn))
        lay.addWidget(self.add_rail_btn)
        for key, label, icon_name, tint in groups.GROUPS:
            b = btn(icon_name, "%s modules (click again for all)" % label, active=tint)
            b.setProperty("cat", key)
            b.clicked.connect(lambda on, k=key: self._on_category(k if on else None))
            self.cat_buttons[key] = b
            lay.addWidget(b)
        lay.addStretch(1)
        for idx, (icon_name, tip) in ((2, ("claude", "Claude")), (3, ("settings", "Settings"))):
            b = btn(icon_name, tip)
            b.clicked.connect(lambda _=False, i=idx: self._on_page(i))
            self.page_buttons[idx] = b
            lay.addWidget(b)
        self.page_buttons[0].setChecked(True)
        self.category = None
        return rail

    def _on_page(self, idx):
        for i, b in self.page_buttons.items():
            b.setChecked(i == idx)
        if idx == 0:
            self._on_category(None)
        else:
            for b in self.cat_buttons.values():
                b.setChecked(False)
        self.pages.setCurrentIndex(idx)
        if idx == 1:
            self.refresh_queue()

    def _on_category(self, key):
        """Show only one module group on the setups page (None = all)."""
        self.category = key
        for k, b in self.cat_buttons.items():
            b.setChecked(k == key)
        for i, b in self.page_buttons.items():
            b.setChecked(i == 0)
        self.pages.setCurrentIndex(0)
        self.refresh_cards()

    def _build_setups_page(self):
        self.split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.split.setChildrenCollapsible(False)

        # ---- sidebar ----
        side = QtWidgets.QFrame()
        side.setObjectName("SMSidebar")
        sl = QtWidgets.QVBoxLayout(side)
        sl.setContentsMargins(12, 12, 12, 8)
        sl.setSpacing(8)
        top = QtWidgets.QHBoxLayout()
        t = QtWidgets.QLabel("Setups")
        t.setObjectName("SMTitle")
        self.count_label = QtWidgets.QLabel()
        self.count_label.setObjectName("SMCount")
        top.addWidget(t)
        top.addWidget(self.count_label)
        top.addStretch(1)
        self.view_toggle = QtWidgets.QToolButton()
        self.view_toggle.setObjectName("SMPlain")
        self.view_toggle.setIcon(icons.get("grid", theme.ACCENT))
        self.view_toggle.setToolTip("Show thumbnails / show tree")
        self.view_toggle.setCheckable(True)
        self.view_toggle.toggled.connect(lambda on: (self.views.setCurrentIndex(1 if on else 0), self.refresh_tree()))
        top.addWidget(self.view_toggle)
        nf = QtWidgets.QToolButton()
        nf.setObjectName("SMPlain")
        nf.setIcon(icons.get("folder"))
        nf.setToolTip("New folder")
        nf.clicked.connect(lambda: self.on_new_folder())
        top.addWidget(nf)
        ns = _button("New Setup", primary=True, tip="New setup from the current scene")
        ns.clicked.connect(lambda: self.on_new_setup())
        top.addWidget(ns)
        sl.addLayout(top)

        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("SMSearch")
        self.search.setPlaceholderText("Search setups")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icons.get("search"), QtWidgets.QLineEdit.LeadingPosition)
        self.search.textChanged.connect(lambda *_: self.refresh_tree())
        sl.addWidget(self.search)
        self.chips_holder = QtWidgets.QWidget()
        self.chips = FlowLayout(self.chips_holder)
        sl.addWidget(self.chips_holder)

        self.views = QtWidgets.QStackedWidget()
        self.tree = SetupTree(self)
        self.tree.setObjectName("SMTree")
        self.grid = QtWidgets.QListWidget()
        self.grid.setObjectName("SMGrid")
        self.grid.setViewMode(QtWidgets.QListView.IconMode)
        self.grid.setIconSize(QtCore.QSize(*thumbnails.SIZE))
        self.grid.setResizeMode(QtWidgets.QListView.Adjust)
        self.grid.setMovement(QtWidgets.QListView.Static)
        self.grid.setSpacing(6)
        self.grid.setWordWrap(True)
        self.grid.currentItemChanged.connect(lambda cur, _: cur and self.select(cur.data(ID_ROLE)))
        self.grid.itemDoubleClicked.connect(lambda it: self.on_activate(it.data(ID_ROLE)))
        self.grid.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(
            lambda pos: self._context_menu(self.grid.itemAt(pos) and self.grid.itemAt(pos).data(ID_ROLE),
                                           self.grid.viewport().mapToGlobal(pos)))
        self.views.addWidget(self.tree)
        self.views.addWidget(self.grid)
        sl.addWidget(self.views, 1)
        self.split.addWidget(side)

        # ---- detail ----
        detail = QtWidgets.QWidget()
        detail.setObjectName("SMDetail")
        dl = QtWidgets.QVBoxLayout(detail)
        dl.setContentsMargins(16, 12, 16, 8)
        dl.setSpacing(10)
        head = QtWidgets.QHBoxLayout()
        self.thumb = QtWidgets.QToolButton()
        self.thumb.setToolTip("Click to grab the active viewport as thumbnail")
        self.thumb.setIconSize(QtCore.QSize(112, 63))
        self.thumb.setFixedSize(116, 67)
        self.thumb.setObjectName("SMPlain")
        self.thumb.setAutoRaise(True)
        self.thumb.clicked.connect(self.on_thumbnail)
        head.addWidget(self.thumb)
        names = QtWidgets.QVBoxLayout()
        names.setSpacing(0)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setMinimumWidth(120)
        self.name_edit.setObjectName("SMName")
        self.name_edit.editingFinished.connect(self._on_name_edited)
        self.desc_edit = QtWidgets.QLineEdit()
        self.desc_edit.setObjectName("SMDesc")
        self.desc_edit.setPlaceholderText("Add a description")
        self.desc_edit.editingFinished.connect(lambda: self._edit_field("description", self.desc_edit.text()))
        self.tags_edit = QtWidgets.QLineEdit()
        self.tags_edit.setObjectName("SMTags")
        self.tags_edit.setPlaceholderText("Tags, comma separated")
        self.tags_edit.editingFinished.connect(
            lambda: self._edit_field("tags", [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]))
        names.addWidget(self.name_edit)
        names.addWidget(self.desc_edit)
        names.addWidget(self.tags_edit)
        head.addLayout(names, 1)
        self.time_label = QtWidgets.QLabel()
        self.time_label.setObjectName("SMMuted")
        head.addWidget(self.time_label)
        self.apply_btn = _button("Activate", primary=True, tip="Apply this setup to the scene (double-click in the list)")
        self.apply_btn.clicked.connect(lambda: self.on_activate(self.selected))
        head.addWidget(self.apply_btn)
        self.render_btn = _button("Render", tip="Render this setup, or every setup in this folder")
        self.render_btn.clicked.connect(lambda: self.on_render([self.selected]))
        head.addWidget(self.render_btn)
        more = QtWidgets.QToolButton()
        more.setObjectName("SMCardBtn")
        more.setIcon(icons.get("more", theme.LABEL_2, theme.LABEL_2))
        more.setIconSize(QtCore.QSize(18, 18))
        more.setFixedSize(30, 30)
        more.setToolTip("More")
        more.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        self.more_menu = QtWidgets.QMenu(more)
        more.setMenu(self.more_menu)
        self.more_menu.aboutToShow.connect(lambda: self._fill_item_menu(self.more_menu, self.selected))
        head.addWidget(more)
        dl.addLayout(head)

        self.folder_note = QtWidgets.QLabel()
        self.folder_note.setObjectName("SMMuted")
        self.folder_note.setWordWrap(True)

        self.layout_btn = QtWidgets.QToolButton()
        self.layout_btn.setObjectName("SMPlain")
        self.layout_btn.setText("Layout")
        self.layout_btn.setToolTip("Card spacing, alignment and size")
        self.layout_btn.clicked.connect(self._show_layout_popover)
        note_row = QtWidgets.QHBoxLayout()
        note_row.addWidget(self.folder_note, 1)
        note_row.addWidget(self.layout_btn, 0, QtCore.Qt.AlignTop)
        dl.addLayout(note_row)

        self.card_scroll = QtWidgets.QScrollArea()
        self.card_scroll.setWidgetResizable(True)
        self.card_scroll.viewport().setAutoFillBackground(False)
        self.card_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        dl.addWidget(self.card_scroll, 1)
        self.split.addWidget(detail)
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)  # extra width goes to the cards
        sizes = config.load().get("splitter")
        self.split.setSizes(sizes if sizes and len(sizes) == 2 else [330, 850])
        return self.split

    def _build_render_page(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        t = QtWidgets.QLabel("Render queue")
        t.setObjectName("SMTitle")
        lay.addWidget(t)
        note = QtWidgets.QLabel("Tick setups or folders in the Setups list to queue them. Renders run here, one after another.")
        note.setObjectName("SMMuted")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.queue = QtWidgets.QTreeWidget()
        self.queue.setObjectName("SMTree")
        self.queue.setHeaderLabels(["Setup", "Camera", "Size", "Frames", "Checks", "Output"])
        self.queue.setRootIsDecorated(False)
        self.queue.setColumnWidth(4, 180)
        lay.addWidget(self.queue, 1)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        b = _button("Render queue", primary=True)
        b.clicked.connect(lambda: self.on_render(sorted(self.checked, key=self._order_index)))
        row.addWidget(b)
        lay.addLayout(row)
        self.render_log = QtWidgets.QPlainTextEdit()
        self.render_log.setReadOnly(True)
        self.render_log.setMaximumHeight(140)
        lay.addWidget(self.render_log)
        return w

    def _build_claude_page(self):
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        t = QtWidgets.QLabel("Claude")
        t.setObjectName("SMTitle")
        lay.addWidget(t)
        row = QtWidgets.QHBoxLayout()
        self.bridge_label = QtWidgets.QLabel()
        row.addWidget(self.bridge_label, 1)
        self.bridge_btn = _button("Start bridge")
        self.bridge_btn.clicked.connect(self.on_bridge)
        row.addWidget(self.bridge_btn)
        lay.addLayout(row)
        how = QtWidgets.QLabel(
            "Open a terminal in the Scene Manager folder and run <b>claude</b>. Ask for changes in plain words, "
            "e.g. <i>“make a Dusk setup in the Street folder, sun low in the west, softer shadows”</i>. "
            "Every change Claude makes is one undo step (Ctrl+Z).")
        how.setWordWrap(True)
        how.setObjectName("SMMuted")
        lay.addWidget(how)
        l2 = QtWidgets.QLabel("Recent actions")
        l2.setObjectName("SMTitle")
        lay.addWidget(l2)
        self.claude_log = QtWidgets.QListWidget()
        self.claude_log.setObjectName("SMLog")
        lay.addWidget(self.claude_log, 1)
        return w

    def _build_settings_page(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        cfg = config.load()
        self.presets_edit = QtWidgets.QLineEdit(cfg.get("presets_folder", ""))
        self.presets_edit.setPlaceholderText(r"\\server\share\scene_manager_presets")
        b = QtWidgets.QToolButton()
        b.setText("…")
        b.clicked.connect(lambda: self.presets_edit.setText(
            QtWidgets.QFileDialog.getExistingDirectory(self, "Team presets folder", self.presets_edit.text())
            or self.presets_edit.text()))
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.presets_edit, 1)
        row.addWidget(b)
        form.addRow("Team presets folder", row)
        self.autostart = QtWidgets.QCheckBox("Start the Claude bridge with 3ds Max")
        self.autostart.setChecked(bool(cfg.get("bridge_autostart", True)))
        form.addRow("", self.autostart)
        self.glass_box = QtWidgets.QCheckBox("Patterned backdrop with glass cards (reopen the panel to apply)")
        self.glass_box.setChecked(bool(cfg.get("glass_backdrop", True)))
        form.addRow("Look", self.glass_box)
        self.scheme_box = QtWidgets.QComboBox()
        for key, label in backdrop.SCHEME_LABELS.items():
            self.scheme_box.addItem(label, key)
        self.scheme_box.setCurrentIndex(max(0, self.scheme_box.findData(cfg.get("backdrop_scheme", backdrop.DEFAULT_SCHEME))))
        self.scheme_box.currentIndexChanged.connect(lambda *_: self._preview_scheme())
        form.addRow("Colours", self.scheme_box)
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(int(cfg.get("bridge_port", 8765)))
        form.addRow("Bridge port", self.port)
        tok = QtWidgets.QLabel("Output tokens: " + "  ".join("{%s}" % k for k in tokens.TOKENS))
        tok.setObjectName("SMMuted")
        tok.setWordWrap(True)
        form.addRow("", tok)
        save = _button("Save settings", primary=True)
        save.clicked.connect(self._save_settings)
        form.addRow("", save)
        return w

    def _build_status(self):
        bar = QtWidgets.QFrame()
        bar.setObjectName("SMStatusBar")
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(10, 3, 10, 3)
        self.status = QtWidgets.QLabel()
        self.status.setObjectName("SMStatus")
        self.claude_dot = QtWidgets.QLabel()
        self.claude_dot.setObjectName("SMClaude")
        lay.addWidget(self.status, 1)
        lay.addWidget(self.claude_dot)
        return bar

    # ======================================================================
    # refresh
    # ======================================================================
    def schedule_refresh(self):
        self._refresh_timer.start()

    def refresh(self):
        self._refresh_timer.stop()  # one rebuild per change, not two
        if self.mgr.get(self.selected) is None:
            self.selected = self.mgr.active_id or (self.mgr.items[0]["id"] if self.mgr.items else None)
        self.checked = {c for c in self.checked if self.mgr.get(c)}
        self.refresh_chips()
        self.refresh_tree()
        self.refresh_detail()
        if self.pages.currentIndex() == 1:
            self.refresh_queue()
        self.refresh_status()

    def refresh_status(self):
        from ..bridge import max_server
        a = self.mgr.get(self.mgr.active_id)
        try:
            renderer = str(rt.classOf(rt.renderers.current))
        except Exception:
            renderer = "?"
        text = "%s   ·   %s" % (self.mgr.path(a) if a else "No active setup", renderer)
        from ..core import repair  # M2: baseline indicator and missing-node warning
        if self.mgr.baseline:
            text += "   ·   baseline"
        if repair.NOTICES:
            text = "⚠ " + repair.NOTICES[-1]
        if self._flash_timer.isActive() and self._flash_text:
            text = self._flash_text
        if self.status.text() != text:
            self.status.setText(text)
        on = max_server.is_running()
        self.claude_dot.setText("● Claude connected" if on else "○ Claude off")
        self.claude_dot.setStyleSheet("color: %s;" % ("#30d158" if on else theme.LABEL_3))
        self.bridge_label.setText("Bridge listening on 127.0.0.1:%d" % max_server._server.port if on else "Bridge is off")
        self.bridge_btn.setText("Stop bridge" if on else "Start bridge")
        self._refresh_claude_log()

    def _refresh_claude_log(self):
        from ..bridge import commands
        self.claude_log.clear()
        self.claude_log.addItems(list(reversed(commands.LOG)))

    def refresh_chips(self):
        sig = (tuple(sorted((t, n) for t, n in self._tag_counts().items())), len(self.mgr.setups()),
               tuple(sorted(self.tag_filter)))
        if sig == self._chips_sig:
            return
        self._chips_sig = sig
        while self.chips.count():
            it = self.chips.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        tags = self._tag_counts()
        self.tag_filter &= set(tags)
        self.chips_holder.setVisible(bool(tags))
        all_btn = QtWidgets.QPushButton("All %d" % len(self.mgr.setups()), self.chips_holder)
        all_btn.setObjectName("SMChip")
        all_btn.setCheckable(True)
        all_btn.setChecked(not self.tag_filter)
        all_btn.clicked.connect(lambda: (self.tag_filter.clear(), self.refresh_chips(), self.refresh_tree()))
        self.chips.addWidget(all_btn)
        for t in sorted(tags):
            b = QtWidgets.QPushButton("%s %d" % (t, tags[t]), self.chips_holder)
            b.setObjectName("SMChip")
            b.setCheckable(True)
            b.setChecked(t in self.tag_filter)
            b.clicked.connect(lambda on, t=t: (self.tag_filter.add(t) if on else self.tag_filter.discard(t),
                                               self.refresh_chips(), self.refresh_tree()))
            self.chips.addWidget(b)

    def _tag_counts(self):
        tags = {}
        for s in self.mgr.items:
            for t in s.get("tags", []):
                tags[t] = tags.get(t, 0) + 1
        return tags

    def _thumb_icon(self, item, w, h):
        """Rounded thumbnail icon, decoded once per thumbnail (not on every refresh)."""
        b64 = item.get("thumbnail")
        key = (item["id"], w, h)
        hit = self._thumbs.get(key)
        if hit is not None and hit[0] is b64:
            return hit[1]
        pm = thumbnails.to_pixmap(b64)
        icon = QtGui.QIcon(icons.rounded(pm, 8) if not pm.isNull() else icons.placeholder(w, h))
        self._thumbs[key] = (b64, icon)
        return icon

    def _visible(self, item):
        text = self.search.text().strip().lower()
        if item["type"] == "folder":
            if not self._filtering():
                return True
            return any(self._visible(c) for c in self.mgr.children(item["id"])) or (
                not self.tag_filter and text and text in item["name"].lower())
        if text and text not in self.mgr.path(item).lower():
            return False
        if self.tag_filter and not (self.tag_filter & set(item.get("tags", []))):
            return False
        return True

    def _filtering(self):
        return bool(self.search.text().strip() or self.tag_filter)

    def refresh_tree(self):
        self._building = True
        try:
            self.count_label.setText(str(len(self.mgr.setups())))
            if self.views.currentIndex() == 0:
                self.tree.sync()
            else:
                self._sync_grid()
        finally:
            self._building = False

    def _sync_grid(self):
        """Thumbnail view: items are reused; the list is only refilled when setups appear, go or move."""
        shown = [s for s in self.mgr.setups() if self._visible(s)]
        ids = [s["id"] for s in shown]
        if [self.grid.item(i).data(ID_ROLE) for i in range(self.grid.count())] != ids:
            self.grid.clear()
            for s in shown:
                it = QtWidgets.QListWidgetItem()
                it.setData(ID_ROLE, s["id"])
                self.grid.addItem(it)
        for i, s in enumerate(shown):
            it = self.grid.item(i)
            if it.text() != s["name"]:
                it.setText(s["name"])
            it.setIcon(self._thumb_icon(s, *thumbnails.SIZE))
            f = it.font()
            if f.bold() != (s["id"] == self.mgr.active_id):
                f.setBold(s["id"] == self.mgr.active_id)
                it.setFont(f)
            if s["id"] == self.selected and self.grid.currentItem() is not it:
                self.grid.setCurrentItem(it)

    def refresh_detail(self):
        item = self.mgr.get(self.selected)
        for w in (self.name_edit, self.desc_edit, self.tags_edit, self.apply_btn, self.render_btn,
                  self.add_rail_btn, self.thumb):
            w.setEnabled(item is not None)
        if item is None:
            self.name_edit.setText("")
            self.desc_edit.setText("")
            self.tags_edit.setText("")
            self.folder_note.setText("No setups yet. Set up the scene and press New Setup.")
            self.thumb.setIcon(QtGui.QIcon(icons.placeholder(112, 63)))
            self.refresh_cards()
            return
        is_folder = item["type"] == "folder"
        for e, text in ((self.name_edit, item["name"]), (self.desc_edit, item.get("description", "")),
                        (self.tags_edit, ", ".join(item.get("tags", [])))):
            if e.text() != text and not (e.hasFocus() and e.isModified()):  # never overwrite what is being typed
                e.setText(text)
                e.setCursorPosition(0)
        self.apply_btn.setEnabled(not is_folder)
        self.thumb.setIcon(self._thumb_icon(item, 112, 63))
        if is_folder:
            n = len([d for d in self.mgr.descendants(item["id"]) if d["type"] == "setup"])
            self.folder_note.setText("Folder. Values set here pass down to the %d setup(s) inside; "
                                     "a setup overrides any of them by ticking the property." % n)
        else:
            parent = self.mgr.get(item.get("parent"))
            self.folder_note.setText(("In folder '%s'. Grey dots are inherited, blue dots are set on this setup, "
                                      "orange = differs from the scene." % self.mgr.path(parent)) if parent else "")
        self.time_label.setText("%d ms" % self.mgr.last_apply_ms
                                if item["id"] == self.mgr.active_id and self.mgr.last_apply_ms is not None else "")
        self.refresh_cards()

    def refresh_cards(self, force=False):
        """Show the cards of the selected item. Cards that are already on screen are updated in place
        (values, dots, ticks); a card is only built when its module is new on the board."""
        item = self.mgr.get(self.selected)
        L = layout.current()
        cols = self._columns()
        tok = (repr(sorted(L.items())), cols)
        mods, empty = [], None
        if item is not None:
            cat = self.category or "all"
            mods = sort_modules([m for m in registry.modules()
                                 if (m.key in item["modules"] or self.mgr.module_state(item, m.key)["enabled"])
                                 and (cat == "all" or groups.group_of(m) == cat)])
            if not mods:
                empty = ("No %s modules on this %s. Use + in the left bar." % (
                    groups.LABEL.get(cat, "").lower(), item["type"])) if cat != "all" \
                    else "No modules on this %s. Use + in the left bar." % item["type"]
        note = None
        if empty:
            note = QtWidgets.QLabel(empty)
            note.setObjectName("SMMuted")
        board = self._board
        if force or board is None or tok != self._board_tok:
            cards = [ModuleCard(self.mgr, item, m, collapsed=m.key in self.collapsed,
                                on_collapse=self._on_card_collapse) for m in mods]
            board = CardBoard(cards, cols, L["card_gap"], None, col_width=L["card_min_width"])
            if note is not None:
                board.add_note(note)
            old = self.card_scroll.takeWidget()
            if old is not None:
                old.hide()  # hidden before it loses its parent, so it can never flash as a window
                old.deleteLater()
            bar = self.card_scroll.verticalScrollBar()
            keep = bar.value()
            self.card_scroll.setWidget(board)
            QtCore.QTimer.singleShot(0, lambda: bar.setValue(keep))
            self._board, self._board_tok = board, tok
            return
        have = {c.m.key: c for c in board.cards}
        cards = []
        for m in mods:
            c = have.get(m.key)
            if c is None:
                c = ModuleCard(self.mgr, item, m, parent=board, collapsed=m.key in self.collapsed,
                               on_collapse=self._on_card_collapse)
            else:
                c.sync(item)
            cards.append(c)
        if [id(c) for c in cards] != [id(c) for c in board.cards] or note is not None or board.extra:
            board.set_cards(cards, note)

    def _on_card_collapse(self, key, collapsed):
        (self.collapsed.add if collapsed else self.collapsed.discard)(key)
        config.update(collapsed_cards=sorted(self.collapsed))

    def refresh_queue(self):
        self.queue.clear()  # only called while the Render page is open
        for entry in batch.preflight(self.mgr, sorted(self.checked, key=self._order_index)):
            s = entry.setup
            checks = ", ".join(entry.issues)
            row = QtWidgets.QTreeWidgetItem(self.queue, [
                self.mgr.path(s), self.mgr.summary(s, "camera"), self.mgr.summary(s, "output"),
                self.mgr.summary(s, "time"), checks, entry.output])
            row.setToolTip(5, entry.output)
            if checks:
                row.setToolTip(4, "\n".join(entry.issues))
                row.setForeground(4, QtGui.QColor(theme.ORANGE))

    def _order_index(self, iid):
        ids = [i["id"] for i in self.mgr.items]
        return ids.index(iid) if iid in ids else 0

    def _columns(self):
        """Default grid columns for cards without a stored place (the Layout setting; "auto" = 2, as in SM3)."""
        L = layout.current()
        return 2 if L["columns"] == "auto" else int(L["columns"])

    def _show_layout_popover(self):
        pop = layout.LayoutPopover(self._on_layout_changed, self)
        pop.setPalette(theme.dark_palette())
        pop.setStyleSheet(theme.stylesheet(False).replace("#SMPanel", "#SMPopover") + layout.LayoutPopover.POPOVER_QSS)
        pop.adjustSize()
        pos = self.layout_btn.mapToGlobal(QtCore.QPoint(self.layout_btn.width(), self.layout_btn.height() + 4))
        pop.move(pos.x() - pop.width(), pos.y())
        pop.show()

    def _on_layout_changed(self):
        self.setStyleSheet(theme.stylesheet(self.glass))
        self.refresh_cards(force=True)

    def paintEvent(self, event):
        if self.glass:
            p = QtGui.QPainter(self)
            host = _backdrop_host(self)
            off = self.mapTo(host, QtCore.QPoint(0, 0)) if host is not self else QtCore.QPoint(0, 0)
            p.drawPixmap(-off.x(), -off.y(), backdrop.pixmap(host.width(), host.height(), self.devicePixelRatioF(),
                                                           self.scheme))
            p.end()
        else:
            super().paintEvent(event)

    # ---- responsive layout ----
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def _after_resize(self):
        # Like Scene Manager 3: cards never reflow on resize (a smaller window just scrolls).
        # The column count is fixed when the board is built; only the sidebar moves above the cards.
        orient = QtCore.Qt.Vertical if self.width() < NARROW else QtCore.Qt.Horizontal
        if self.split.orientation() != orient:
            self.split.setOrientation(orient)
            self.split.setSizes([260, 400] if orient == QtCore.Qt.Vertical else [330, 850])

    # ======================================================================
    # actions
    # ======================================================================
    def select(self, iid):
        if self._building or iid == self.selected:
            return
        self.selected = iid
        self._building = True
        w = self.tree._items.get(iid)
        if w is not None and self.tree.currentItem() is not w:
            self.tree.setCurrentItem(w)
        self._building = False
        self.refresh_detail()

    def _edit_field(self, field, value):
        if self.selected and self.mgr.get(self.selected) and self.mgr.get(self.selected).get(field) != value:
            self.mgr.update_item(self.selected, **{field: value})

    def _on_name_edited(self):
        name = self.name_edit.text().strip()
        if name:
            self._edit_field("name", name)

    def _target_parent(self):
        item = self.mgr.get(self.selected)
        if item is None:
            return None
        return item["id"] if item["type"] == "folder" else item.get("parent")

    @_guard
    def on_new_setup(self, parent=False):
        parent = self._target_parent() if parent is False else parent
        # No dialog: the setup appears at once with a default name, ready to be renamed in the list.
        try:
            thumb = thumbnails.capture_viewport()
        except Exception:
            thumb = None
        s = self.mgr.add_setup(None, parent=parent, thumbnail=thumb)
        self._reveal(s["id"], rename=True)

    def _reveal(self, iid, rename=False):
        self.selected = iid
        if self.search.text() or self.tag_filter:  # a new item must not be hidden by the filter
            self.tag_filter.clear()
            self.search.clear()
        self.refresh()
        if self.views.currentIndex() == 0:
            self.tree.reveal(iid, rename)

    @_guard
    def on_new_folder(self, parent=False):
        parent = self._target_parent() if parent is False else parent
        f = self.mgr.add_folder("Folder", parent=parent)
        self._reveal(f["id"], rename=True)

    @_guard
    def on_activate(self, iid):
        item = self.mgr.get(iid)
        if item is None or item["type"] != "setup":
            return
        errors = self.mgr.apply(iid, undo="Scene Manager: activate %s" % item["name"])
        self.selected = iid
        self.flash(("Activated %s in %d ms" % (self.mgr.path(item), self.mgr.last_apply_ms))
                   if not errors else "Activated with errors: " + "; ".join(errors))

    @_guard
    def on_thumbnail(self, iid=None):
        iid = iid or self.selected
        if iid:
            self.mgr.update_item(iid, thumbnail=thumbnails.capture_viewport())

    @_guard
    def on_capture(self, iid=None):
        iid = iid or self.selected
        if iid:
            self.mgr.capture(iid)

    @_guard
    def on_duplicate(self, iid=None):
        if self.mgr.get(iid or self.selected) is None:
            return
        c = self.mgr.duplicate(iid or self.selected)
        self._reveal(c["id"])

    @_guard
    def on_delete(self, iid=None):
        item = self.mgr.get(iid or self.selected)
        if item is None:
            return
        extra = ""
        if item["type"] == "folder":
            extra = " and the %d item(s) inside it" % len(self.mgr.descendants(item["id"]))
        if QtWidgets.QMessageBox.question(self, "Delete", "Delete '%s'%s?" % (item["name"], extra)) \
                == QtWidgets.QMessageBox.Yes:
            self.mgr.delete(item["id"])

    @_guard
    def on_render(self, ids):
        ids = [i for i in ids if i]
        setups = batch.preflight(self.mgr, ids)
        if not setups:
            return
        flagged = [entry for entry in setups if entry.issues]
        if flagged:
            warning = QtWidgets.QMessageBox(self)
            warning.setWindowTitle("Render queue checks")
            warning.setIcon(QtWidgets.QMessageBox.Warning)
            warning.setTextFormat(QtCore.Qt.PlainText)
            warning.setText(f"Checks found issues in {len(flagged)} of {len(setups)} queued setups.")
            summaries = [
                f"{self.mgr.path(entry.setup)} ({', '.join(entry.issues)})"
                for entry in flagged
            ]
            preview = summaries[:4]
            if len(summaries) > len(preview):
                preview.append(f"{len(summaries) - len(preview)} more in Show Details")
            warning.setInformativeText("\n".join(preview))
            warning.setDetailedText("\n".join(
                f"{summary}\n  {entry.output}" if entry.output else summary
                for summary, entry in zip(summaries, flagged)
            ))
            warning.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
            warning.button(QtWidgets.QMessageBox.Yes).setText("Render anyway")
            warning.setDefaultButton(QtWidgets.QMessageBox.Cancel)
            if warning.exec() != QtWidgets.QMessageBox.Yes:
                return
        dlg = QtWidgets.QProgressDialog("Rendering...", "Stop after current", 0, len(setups), self)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.show()

        def progress(i, n, name):
            dlg.setValue(i)
            dlg.setLabelText("Rendering %d/%d: %s" % (min(i + 1, n), n, name))
            QtWidgets.QApplication.processEvents()

        results = batch.render_setups(self.mgr, ids, progress, dlg.wasCanceled)
        dlg.close()
        self.render_log.appendPlainText("\n".join("%s: %s" % r for r in results))
        QtWidgets.QMessageBox.information(self, "Batch render", "\n".join("%s: %s" % r for r in results))

    @_guard
    def on_bridge(self):
        from ..bridge import max_server
        if max_server.is_running():
            max_server.stop()
        else:
            max_server.start()
        self.refresh_status()

    def _save_settings(self):
        cfg = config.load()
        cfg.update(presets_folder=self.presets_edit.text().strip(), bridge_autostart=self.autostart.isChecked(),
                   bridge_port=self.port.value(), glass_backdrop=self.glass_box.isChecked(),
                   backdrop_scheme=self.scheme_box.currentData())
        config.save(cfg)
        self.flash("Settings saved.")

    def _preview_scheme(self):
        self.scheme = self.scheme_box.currentData()
        self.update()

    def _preset_dir(self):
        return config.load().get("presets_folder") or os.path.expanduser("~")

    @_guard
    def on_export(self, ids=None):
        ids = ids or sorted(self.checked, key=self._order_index) or [self.selected]
        ids = [i for i in ids if i]
        if not ids:
            return
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export setups", self._preset_dir(),
                                                      "Scene Manager presets (*.smsetups.json)")
        if fn:
            if not fn.endswith(".json"):
                fn += ".smsetups.json"
            n = self.mgr.export_items(ids, fn)
            self.flash("Exported %d setup(s) to %s" % (n, fn))

    @_guard
    def on_import(self, parent=None):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import setups", self._preset_dir(),
                                                      "Scene Manager presets (*.json)")
        if fn:
            added = self.mgr.import_items(fn, parent=parent)
            self.flash("Imported %d setup(s). Cameras and lights are matched by name." % len(added))

    def _set_color(self, iid, color):
        self.mgr.update_item(iid, color=color)

    def _fill_item_menu(self, menu, iid):
        menu.clear()
        item = self.mgr.get(iid)
        if item is None:
            menu.addAction("New setup", lambda: self.on_new_setup(None))
            menu.addAction("New folder", lambda: self.on_new_folder(None))
            menu.addSeparator()
            menu.addAction("Import presets…", lambda: self.on_import(None))
            scene_tools.fill_menu(self, menu)
            return
        folder = item["id"] if item["type"] == "folder" else item.get("parent")
        if item["type"] == "setup":
            menu.addAction("Activate", lambda: self.on_activate(iid))
        menu.addAction("Render", lambda: self.on_render([iid]))
        menu.addSeparator()
        menu.addAction("New setup here", lambda: self.on_new_setup(folder))
        menu.addAction("New folder here", lambda: self.on_new_folder(folder))
        menu.addSeparator()
        menu.addAction("Capture scene into this %s" % item["type"], lambda: self.on_capture(iid))
        menu.addAction("Grab thumbnail", lambda: self.on_thumbnail(iid))
        menu.addAction("Rename", lambda: self.tree.edit_item(iid))
        menu.addAction("Duplicate", lambda: self.on_duplicate(iid))
        colors = menu.addMenu("Colour")
        colors.addAction("None", lambda: self._set_color(iid, None))
        for c in theme.TAG_COLORS:
            colors.addAction(_swatch(c), c, lambda c=c: self._set_color(iid, c))
        menu.addSeparator()
        menu.addAction("Export…", lambda: self.on_export([iid]))
        menu.addAction("Import presets here…", lambda: self.on_import(folder))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.on_delete(iid))
        scene_tools.fill_menu(self, menu)

    def _context_menu(self, iid, global_pos):
        menu = QtWidgets.QMenu(self)
        self._fill_item_menu(menu, iid)
        menu.exec(global_pos)

    def _show_module_palette(self, anchor):
        item = self.mgr.get(self.selected)
        if item is None:
            return
        pop = ModulePalette(self.mgr, item, self.category, self)
        pop.setPalette(theme.dark_palette())
        pop.setStyleSheet(theme.stylesheet(False).replace("#SMPanel", "#SMPopover") + layout.LayoutPopover.POPOVER_QSS
                          + theme.rgba(ModulePalette.QSS))
        pop.finalize()
        pos = anchor.mapToGlobal(QtCore.QPoint(anchor.width() + 6, 0))
        screen = QtGui.QGuiApplication.screenAt(pos) or QtGui.QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        pop.move(pos.x(), max(avail.top(), min(pos.y(), avail.bottom() - pop.height())))
        pop.show()



class ModulePalette(QtWidgets.QFrame):
    """Popover from the + in the left bar: every module as a tile with its group icon, grouped like the rail."""

    QSS = """
#SMPopover QToolButton#SMTile { background: #ffffff0d; border: 1px solid #ffffff12; border-radius: 8px;
    padding: 6px 8px; text-align: left; color: #f5f5f7; }
#SMPopover QToolButton#SMTile:hover { background: #ffffff1f; border-color: #ffffff2e; }
#SMPopover QToolButton#SMTile:disabled { color: #6e6e73; background: transparent; }
#SMPopover QLabel#SMGroup { color: #a1a1a6; font-size: 11px; font-weight: 600; }
"""

    def __init__(self, mgr, item, category, parent=None):
        super().__init__(parent, QtCore.Qt.Popup)
        self.setObjectName("SMPopover")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WA_StyledBackground)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)
        t = QtWidgets.QLabel("Add module")
        t.setObjectName("SMTitle")
        outer.addWidget(t)
        body = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)
        all_mods = registry.modules()
        for key, label, icon_name, tint in groups.GROUPS:
            if category and key != category:
                continue
            # modules for a renderer that is not installed are not offered (a card already on the item stays)
            mods = [m for m in groups.modules_in(key, all_mods)
                    if m.installed() or mgr.module_state(item, m.key)["enabled"]]
            if not mods:
                continue
            head = QtWidgets.QHBoxLayout()
            ic = QtWidgets.QLabel()
            ic.setPixmap(icons.tinted(icon_name, tint).pixmap(14, 14))
            head.addWidget(ic)
            g = QtWidgets.QLabel(label.upper())
            g.setObjectName("SMGroup")
            head.addWidget(g, 1)
            bl.addLayout(head)
            grid = QtWidgets.QGridLayout()
            grid.setSpacing(6)
            for i, m in enumerate(mods):
                on = mgr.module_state(item, m.key)["enabled"]
                b = QtWidgets.QToolButton()
                b.setObjectName("SMTile")
                b.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
                b.setIcon(icons.tinted(icon_name, tint if not on else theme.LABEL_3))
                b.setIconSize(QtCore.QSize(16, 16))
                b.setText(m.label.replace("&", "&&") + ("  ✓" if on else ""))
                try:
                    usable = bool(m.available())
                except Exception:
                    usable = True
                if on:
                    b.setToolTip("Already on this %s" % item["type"])
                elif not usable:  # still addable on purpose, but say why it is not there by default
                    b.setToolTip("Add %s. Not part of a new setup in this scene (other renderer, or nothing "
                                 "for it to control yet)." % m.label)
                else:
                    b.setToolTip("Add %s, filled from the scene" % m.label)
                b.setEnabled(not on)
                b.setMinimumWidth(190)
                b.setFixedHeight(32)
                b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                b.clicked.connect(lambda _=False, k=m.key: (self.close(), mgr.capture(item["id"], keys=[k])))
                grid.addWidget(b, i // 2, i % 2)
            bl.addLayout(grid)
            bl.addSpacing(4)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        scroll.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        outer.addWidget(scroll)
        self.body, self.scroll = body, scroll

    def finalize(self):
        """Size the list once the stylesheet is set (tile padding comes from it)."""
        for w in self.body.findChildren(QtWidgets.QWidget):
            w.ensurePolished()
        h = self.body.layout().sizeHint().height()
        self.body.setMinimumHeight(h)
        self.scroll.setFixedWidth(self.body.layout().sizeHint().width() + 14)
        self.scroll.setFixedHeight(min(520, h + 2))
        self.adjustSize()


_setup_icons = {}


def _setup_icon(color, active):
    """Setup marker in the list: its colour bar, plus an accent dot when it is the active setup."""
    key = (color, active)
    if key not in _setup_icons:
        pm = QtGui.QPixmap(36, 32)
        pm.setDevicePixelRatio(2)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        if color:
            p.setBrush(QtGui.QColor(color))
            p.drawRoundedRect(QtCore.QRectF(1, 1, 3, 14), 1.5, 1.5)
        if active:
            p.setBrush(QtGui.QColor(theme.ACCENT))
            p.drawEllipse(QtCore.QRectF(8, 4.5, 7, 7))
        else:
            pen = QtGui.QPen(QtGui.QColor(theme.LABEL_3))
            pen.setWidthF(1.2)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawEllipse(QtCore.QRectF(8.6, 5.1, 5.8, 5.8))
        p.end()
        _setup_icons[key] = QtGui.QIcon(pm)
    return _setup_icons[key]


class SetupTree(QtWidgets.QTreeWidget):
    """Folders and setups. Drag to reorder or move into folders; tick to queue for rendering.

    sync() updates the rows in place; the tree is only refilled when items appear, go or move, so the
    scroll position, the selection and an open rename editor survive every other change."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.mgr = panel.mgr
        self.cols = [m for m in registry.modules() if m.column]
        self.setHeaderLabels(["Setup"] + [m.column for m in self.cols])
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditKeyPressed)
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setUniformRowHeights(True)   # lets Qt skip measuring every row
        self.setAllColumnsShowFocus(True)
        self.setIndentation(16)
        self.setIconSize(QtCore.QSize(18, 16))
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setMouseTracking(True)
        self.customContextMenuRequested.connect(
            lambda pos: panel._context_menu(self.itemAt(pos) and self.itemAt(pos).data(0, ID_ROLE),
                                            self.viewport().mapToGlobal(pos)))
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.header().setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.header().customContextMenuRequested.connect(self._header_menu)
        self.header().setMinimumSectionSize(40)
        self.header().setToolTip("Right-click to choose the columns")
        shown = config.load().get("tree_columns")
        if shown is None:
            shown = ["camera", "output"]  # a slim list by default; the rest is one right-click away
        for i, m in enumerate(self.cols, start=1):
            self.setColumnHidden(i, m.key not in shown)
        self.currentItemChanged.connect(lambda cur, _: cur and panel.select(cur.data(0, ID_ROLE)))
        self.itemDoubleClicked.connect(lambda it, col: panel.on_activate(it.data(0, ID_ROLE)))
        self.itemChanged.connect(self._on_changed)
        self.itemExpanded.connect(lambda it: self._on_fold(it, False))
        self.itemCollapsed.connect(lambda it: self._on_fold(it, True))
        self._items = {}
        self._structure = None
        self._widths = None

    def _on_fold(self, it, folded):
        if self.panel._building or self.panel._filtering():
            return
        (self.panel.collapsed.add if folded else self.panel.collapsed.discard)(it.data(0, ID_ROLE))

    def _header_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        for i, m in enumerate(self.cols, start=1):
            a = menu.addAction(m.column)
            a.setCheckable(True)
            a.setChecked(not self.isColumnHidden(i))
            a.toggled.connect(lambda on, i=i: self._toggle_column(i, on))
        menu.exec(self.header().mapToGlobal(pos))

    def _toggle_column(self, i, on):
        self.setColumnHidden(i, not on)
        self._widths = None
        self.sync()
        self.panel.save_view_state()

    # ---- painting: one rounded highlight across the whole row ----
    def drawRow(self, painter, option, index):
        sel = self.selectionModel().isSelected(index)
        hover = index.row() == getattr(self, "_hover_row", -1) and index.parent() == getattr(self, "_hover_parent", None)
        if sel or hover:
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtCore.Qt.NoPen)
            c = QtGui.QColor(theme.ACCENT) if sel else QtGui.QColor(255, 255, 255)
            c.setAlpha(64 if sel else 12)
            painter.setBrush(c)
            r = QtCore.QRectF(2, option.rect.y() + 1, self.viewport().width() - 4, option.rect.height() - 2)
            painter.drawRoundedRect(r, 6, 6)
            painter.restore()
        super().drawRow(painter, option, index)

    def mouseMoveEvent(self, e):
        idx = self.indexAt(e.position().toPoint())
        row, parent = (idx.row(), idx.parent()) if idx.isValid() else (-1, None)
        if (row, parent) != (getattr(self, "_hover_row", -1), getattr(self, "_hover_parent", None)):
            self._hover_row, self._hover_parent = row, parent
            self.viewport().update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover_row, self._hover_parent = -1, None
        self.viewport().update()
        super().leaveEvent(e)

    def viewportEvent(self, e):
        # Tooltips are built when asked for, not for every row on every refresh.
        if e.type() == QtCore.QEvent.ToolTip:
            it = self.itemAt(e.pos())
            item = self.mgr.get(it.data(0, ID_ROLE)) if it is not None else None
            if item is not None and item["type"] == "setup":
                lines = [self.mgr.path(item)] + self.mgr.describe(item)
                if item.get("description"):
                    lines.append(item["description"])
                QtWidgets.QToolTip.showText(e.globalPos(), "\n".join(lines), self)
            else:
                QtWidgets.QToolTip.hideText()
            return True
        return super().viewportEvent(e)

    # ---- content ----
    def _visible_structure(self):
        p, out = self.panel, []

        def walk(parent_id):
            for item in self.mgr.children(parent_id):
                if p._visible(item):
                    out.append((item["id"], parent_id))
                    if item["type"] == "folder":
                        walk(item["id"])

        walk(None)
        return out

    def _fill(self, w, item):
        """Write one row. Only fields that changed are touched, so an unchanged tree repaints nothing."""
        p = self.panel
        active = item["id"] == self.mgr.active_id
        folder = item["type"] == "folder"

        def text(col, value):
            if w.text(col) != value:
                w.setText(col, value)

        if self.state() != QtWidgets.QAbstractItemView.EditingState or self.currentItem() is not w:
            text(0, item["name"])
        look = (item.get("color"), active, folder)
        if w.data(0, ID_ROLE + 1) != look:
            w.setData(0, ID_ROLE + 1, look)
            w.setIcon(0, icons.tinted("folder", item.get("color") or theme.LABEL_2) if folder
                      else _setup_icon(item.get("color"), active))
            f = w.font(0)
            f.setBold(folder or active)
            w.setFont(0, f)
            w.setForeground(0, QtGui.QBrush(QtGui.QColor(theme.ACCENT if active else theme.LABEL)))
        if folder:
            n = len([d for d in self.mgr.descendants(item["id"]) if d["type"] == "setup"])
            first = next((i for i in range(1, self.columnCount()) if not self.isColumnHidden(i)), None)
            for i in range(1, self.columnCount()):
                text(i, ("%d" % n) if i == first else "")
        else:
            for i, m in enumerate(self.cols, start=1):
                if not self.isColumnHidden(i):
                    text(i, self.mgr.summary(item, m.key))
            state = QtCore.Qt.Checked if item["id"] in p.checked else QtCore.Qt.Unchecked
            if w.checkState(0) != state:
                w.setCheckState(0, state)

    def sync(self):
        p = self.panel
        structure = self._visible_structure()
        vbar = self.verticalScrollBar()
        self.blockSignals(True)
        try:
            if structure != self._structure:
                keep = vbar.value()
                self.clear()
                self._items = {}
                muted = QtGui.QBrush(QtGui.QColor(theme.LABEL_2))
                for iid, parent_id in structure:
                    item = self.mgr.get(iid)
                    w = QtWidgets.QTreeWidgetItem(self._items[parent_id] if parent_id else self.invisibleRootItem())
                    w.setData(0, ID_ROLE, iid)
                    flags = QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsEditable | \
                        QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsUserCheckable
                    if item["type"] == "folder":
                        flags |= QtCore.Qt.ItemIsDropEnabled | QtCore.Qt.ItemIsAutoTristate
                    w.setFlags(flags)
                    w.setCheckState(0, QtCore.Qt.Unchecked)
                    for i in range(1, self.columnCount()):
                        w.setForeground(i, muted)
                    self._items[iid] = w
                self._structure = structure
                for iid, _parent in structure:
                    item = self.mgr.get(iid)
                    self._fill(self._items[iid], item)
                    if item["type"] == "folder":
                        self._items[iid].setExpanded(iid not in p.collapsed or p._filtering())
                vbar.setValue(keep)
            else:
                for iid, _parent in structure:
                    self._fill(self._items[iid], self.mgr.get(iid))
            cur = self._items.get(p.selected)
            if cur is not None and self.currentItem() is not cur:
                self.setCurrentItem(cur)
        finally:
            self.blockSignals(False)
        widths = tuple(self._items[iid].text(i) for iid, _ in structure for i in range(1, self.columnCount()))
        if widths != self._widths:  # column widths only when a column's text changed
            self._widths = widths
            for i in range(1, self.columnCount()):
                if not self.isColumnHidden(i):
                    self.resizeColumnToContents(i)
        self.viewport().update()

    rebuild = sync  # old name

    def reveal(self, iid, rename=False):
        w = self._items.get(iid)
        if w is None:
            return
        parent = w.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.scrollToItem(w)
        self.setFocus()
        if rename:
            self.editItem(w, 0)

    def edit_item(self, iid):
        self.reveal(iid, rename=True)

    def _on_changed(self, w, col):
        if col != 0 or self.panel._building:
            return
        iid = w.data(0, ID_ROLE)
        item = self.mgr.get(iid)
        if item is None:
            return
        # check state (for folders Qt propagates to children)
        state = w.checkState(0)
        if item["type"] == "setup":
            (self.panel.checked.add if state == QtCore.Qt.Checked else self.panel.checked.discard)(iid)
        text = w.text(0).strip()
        if text and text != item["name"]:
            self.mgr.update_item(iid, name=text)
        elif not text:
            self.blockSignals(True)
            w.setText(0, item["name"])
            self.blockSignals(False)
        if self.panel.pages.currentIndex() == 1:
            self.panel.refresh_queue()

    def dropEvent(self, event):
        super().dropEvent(event)
        self._structure = None  # Qt moved the rows itself: refill from the manager afterwards
        structure = []

        def walk(parent_widget, parent_id):
            for i in range(parent_widget.childCount()):
                w = parent_widget.child(i)
                iid = w.data(0, ID_ROLE)
                item = self.mgr.get(iid)
                if item is not None and item["type"] == "setup" and w.childCount():
                    pass  # setups do not accept drops (no ItemIsDropEnabled)
                structure.append((iid, parent_id))
                walk(w, iid)

        walk(self.invisibleRootItem(), None)
        if self.panel._filtering():
            # hidden items keep their place: only re-parent the visible ones
            for iid, parent in structure:
                it = self.mgr.get(iid)
                if it is not None:
                    it["parent"] = parent
            self.mgr.commit()
        else:
            self.mgr.set_order(structure)
