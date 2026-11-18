"""Visual style: "Apple Native Experience" (from the UI/UX Pro Max skill), dark appearance.

Semantic tokens modelled on Apple's dark system colours; 8 pt spacing; system font
(Segoe UI Variable on Windows, as SF Pro is not available there); 10-12 px radii; restrained borders.
"""
import os
import tempfile

# ---- semantic tokens -------------------------------------------------------
BG = "#1c1c1e"            # window / content background
RAIL = "#151517"          # icon bar
SIDEBAR = "#202022"       # source list
SURFACE = "#2c2c2e"       # grouped surface (cards)
SURFACE_2 = "#3a3a3c"     # controls on a surface
FIELD = "#232325"         # text fields
SEPARATOR = "#38383a"
LABEL = "#f5f5f7"
LABEL_2 = "#a1a1a6"       # secondary label (contrast > 4.5:1 on BG)
LABEL_3 = "#6e6e73"       # tertiary
ACCENT = "#0a84ff"
ACCENT_SOFT = "#0a84ff40"
ORANGE = "#ff9f0a"
OVERRIDE = ACCENT
INHERITED = "#8e8e93"
DIFFERS = ORANGE
FONT = '"Segoe UI Variable Text", "Segoe UI", "SF Pro Text", system-ui, sans-serif'
FONT_DISPLAY = '"Segoe UI Variable Display", "Segoe UI", "SF Pro Display", system-ui, sans-serif'

# Apple dark system tints, one per module group
TINTS = {"camera": "#0a84ff", "light": "#ff9f0a", "env": "#64d2ff",
         "scene": "#bf5af2", "render": "#ff453a", "script": "#30d158"}
TAG_COLORS = ["#ff9f0a", "#ff453a", "#bf5af2", "#30d158", "#0a84ff", "#64d2ff", "#ffd60a", "#8e8e93"]


def _check_png():
    """Write the checkbox tick image once (QSS needs a file)."""
    from PySide6 import QtCore, QtGui
    path = os.path.join(tempfile.gettempdir(), "scene_manager_check.png")
    if not os.path.exists(path):
        pm = QtGui.QPixmap(32, 32)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("white"))
        pen.setWidthF(4.0)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen)
        path_ = QtGui.QPainterPath()
        path_.moveTo(8, 17)
        path_.lineTo(13.5, 22.5)
        path_.lineTo(24, 10)
        p.drawPath(path_)
        p.end()
        pm.save(path)
    return path.replace("\\", "/")


def stylesheet(glass=True):
    from . import layout
    L = layout.current()
    t = dict(CR=L["card_radius"], FR=L["field_radius"], FH=max(12, L["field_height"] - 8),BG=BG, RAIL=RAIL, SIDEBAR=SIDEBAR, SURFACE=SURFACE, SURFACE_2=SURFACE_2, FIELD=FIELD,
             SEP=SEPARATOR, L1=LABEL, L2=LABEL_2, L3=LABEL_3, ACC=ACCENT, ACCS=ACCENT_SOFT,
             FONT=FONT, FONTD=FONT_DISPLAY, CHECK=_check_png())
    css = """
#SMPanel, #SMPanel QWidget { font-family: %(FONT)s; font-size: 12px; }
QWidget { color: %(L1)s; }
QWidget:disabled { color: %(L2)s; }
#SMPanel, #SMDetail, #SMCards, #SMPanel QScrollArea, #SMPanel QStackedWidget { background: %(BG)s; }
#SMPanel QToolTip { background: %(SURFACE)s; color: %(L1)s; border: 1px solid %(SEP)s; border-radius: 6px; padding: 4px 6px; }

/* icon bar */
#SMRail { background: %(RAIL)s; border-right: 1px solid %(SEP)s; }
#SMRail QToolButton { border: none; border-radius: 8px; min-width: 34px; min-height: 34px; }
#SMRail QToolButton:hover { background: #ffffff10; }
#SMRail QToolButton:checked { background: #ffffff1a; }
#SMRail QFrame#SMRailSep { background: %(SEP)s; max-height: 1px; margin: 4px 8px; }

/* source list */
#SMSidebar { background: %(SIDEBAR)s; border-right: 1px solid %(SEP)s; }
#SMTitle { font-family: %(FONTD)s; font-size: 15px; font-weight: 600; }
#SMPanel #SMCount, #SMPanel #SMMuted, #SMPanel #SMPropLabel, #SMPanel #SMCardOrigin { color: %(L2)s; }
#SMSection { color: %(L3)s; font-size: 11px; font-weight: 600; letter-spacing: 0.4px; }

QLineEdit#SMSearch { background: %(FIELD)s; border: 1px solid %(SEP)s; border-radius: 8px; padding: 5px 8px; }
QLineEdit#SMSearch:focus { border: 2px solid %(ACC)s; padding: 4px 7px; }
QLineEdit#SMName { font-family: %(FONTD)s; font-size: 18px; font-weight: 600; background: transparent;
    border: 1px solid transparent; border-radius: 6px; padding: 1px 4px; }
QLineEdit#SMDesc, QLineEdit#SMTags { color: %(L2)s; background: transparent; border: 1px solid transparent;
    border-radius: 6px; padding: 1px 4px; }
QLineEdit#SMName:hover, QLineEdit#SMDesc:hover, QLineEdit#SMTags:hover { background: #ffffff08; }
QLineEdit#SMName:focus, QLineEdit#SMDesc:focus, QLineEdit#SMTags:focus { background: %(FIELD)s; border: 1px solid %(ACC)s; }

QPushButton#SMChip { border: none; border-radius: 10px; padding: 3px 10px; color: %(L2)s; background: #ffffff0f; }
QPushButton#SMChip:hover { background: #ffffff1a; }
QPushButton#SMChip:checked { background: %(ACCS)s; color: #9fcdff; }

QPushButton#SMPrimary { background: %(ACC)s; border: none; border-radius: 7px; color: white;
    padding: 6px 14px; font-weight: 600; }
QPushButton#SMPrimary:hover { background: #2e95ff; }
QPushButton#SMPrimary:pressed { background: #0070e0; }
QPushButton#SMPrimary:disabled { background: %(SURFACE_2)s; color: %(L3)s; }
QPushButton#SMButton, QToolButton#SMButton { background: %(SURFACE_2)s; border: none; border-radius: 7px;
    color: %(L1)s; padding: 6px 12px; }
QPushButton#SMButton:hover, QToolButton#SMButton:hover { background: #48484a; }
QPushButton#SMButton:pressed, QToolButton#SMButton:pressed { background: #2c2c2e; }
QToolButton#SMButton::menu-indicator { image: none; width: 0; }
QToolButton#SMPlain { border: none; border-radius: 6px; padding: 2px 6px; color: %(L2)s; }
QToolButton#SMPlain:hover { background: #ffffff14; color: %(L1)s; }
QToolButton#SMPlain::menu-indicator { image: none; width: 0; }
QToolButton#SMCardBtn { border: none; border-radius: 6px; padding: 0; }
QToolButton#SMCardBtn:hover { background: #ffffff1a; }
QToolButton#SMCardBtn:checked { background: transparent; }
QToolButton#SMCardBtn::menu-indicator { image: none; width: 0; height: 0; }
QFrame#SMCard[dragging="true"] { border: 1px dashed %(ACC)s; }

/* tree and grid */
QTreeWidget#SMTree, QListWidget#SMGrid { background: %(SIDEBAR)s; border: none; outline: 0; }
QTreeWidget#SMTree::branch { background: transparent; }
QTreeWidget#SMTree::branch:selected { background: %(ACCS)s; }
QTreeWidget#SMTree::item { height: 28px; border: none; }
QTreeWidget#SMTree::item:hover, QListWidget#SMGrid::item:hover { background: #ffffff0a; }
QTreeWidget#SMTree::item:selected, QListWidget#SMGrid::item:selected { background: %(ACCS)s; color: %(L1)s; }
QListWidget#SMGrid::item { border-radius: 8px; padding: 6px; }
#SMPanel QHeaderView { background: %(SIDEBAR)s; }
#SMPanel QHeaderView::section { background: %(SIDEBAR)s; color: %(L3)s; border: none;
    border-bottom: 1px solid %(SEP)s; padding: 4px 6px; font-size: 11px; font-weight: 600; }

/* cards */
QFrame#SMCard { background: %(SURFACE)s; border: 1px solid #ffffff0d; border-radius: %(CR)spx; }
QFrame#SMPopover { background: %(SURFACE)s; border: 1px solid %(SEP)s; border-radius: 12px; }
#SMPopover QSlider::groove:horizontal { height: 4px; background: %(SURFACE_2)s; border-radius: 2px; }
#SMPopover QSlider::sub-page:horizontal { background: %(ACC)s; border-radius: 2px; }
#SMPopover QSlider::handle:horizontal { background: white; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QLabel#SMCardTitle { font-size: 13px; font-weight: 600; color: %(L1)s; }
QLabel#SMCardOrigin { color: %(L2)s; font-size: 11px; }
QFrame#SMHairline { background: %(SEP)s; max-height: 1px; }

/* controls inside cards */
#SMCard QSpinBox, #SMCard QDoubleSpinBox, #SMCard QLineEdit, #SMCard QComboBox {
    background: %(FIELD)s; border: 1px solid %(SEP)s; border-radius: %(FR)spx; padding: 3px 6px; min-height: %(FH)spx; }
#SMCard QSpinBox:focus, #SMCard QDoubleSpinBox:focus, #SMCard QLineEdit:focus, #SMCard QComboBox:focus {
    border: 1px solid %(ACC)s; }
#SMCard QSpinBox:disabled, #SMCard QDoubleSpinBox:disabled, #SMCard QLineEdit:disabled, #SMCard QComboBox:disabled {
    background: transparent; border: 1px solid transparent; color: %(L2)s; }
#SMCard QSpinBox::up-button, #SMCard QSpinBox::down-button,
#SMCard QDoubleSpinBox::up-button, #SMCard QDoubleSpinBox::down-button { width: 0; border: none; }
#SMCard QComboBox::drop-down { border: none; width: 16px; }
#SMCard QComboBox QAbstractItemView { background: %(SURFACE)s; border: 1px solid %(SEP)s; border-radius: 6px;
    selection-background-color: %(ACC)s; }

/* round checkboxes (override ticks and plain checks) */
#SMPanel QCheckBox::indicator { width: 14px; height: 14px; border-radius: 8px;
    border: 1.5px solid %(L3)s; background: transparent; }
#SMPanel QCheckBox::indicator:hover { border-color: %(L2)s; }
#SMPanel QCheckBox::indicator:checked { background: %(ACC)s; border-color: %(ACC)s; image: url(%(CHECK)s); }
#SMPanel QCheckBox::indicator:disabled { border-color: #48484a; }
#SMPanel QTreeWidget::indicator { width: 13px; height: 13px; border-radius: 4px; border: 1.5px solid %(L3)s; }
#SMPanel QTreeWidget::indicator:checked { background: %(ACC)s; border-color: %(ACC)s; image: url(%(CHECK)s); }
#SMPanel QTreeWidget::indicator:indeterminate { background: %(ACCS)s; border-color: %(ACC)s; }

/* scroll bars: thin overlay style */
#SMPanel QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
#SMPanel QScrollBar::handle:vertical { background: #ffffff2e; border-radius: 3px; min-height: 30px; }
#SMPanel QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
#SMPanel QScrollBar::handle:horizontal { background: #ffffff2e; border-radius: 3px; min-width: 30px; }
#SMPanel QScrollBar::add-line, #SMPanel QScrollBar::sub-line, #SMPanel QScrollBar::add-page,
#SMPanel QScrollBar::sub-page { background: none; border: none; width: 0; height: 0; }
#SMPanel QSplitter::handle { background: transparent; }

#SMStatusBar { background: %(RAIL)s; border-top: 1px solid %(SEP)s; }
#SMStatus { color: %(L2)s; font-size: 11px; }
#SMPanel QPlainTextEdit, #SMPanel QListWidget#SMLog { background: %(SURFACE)s; border: none; border-radius: 10px; padding: 6px; }
#SMPanel QMenu { background: %(SURFACE)s; border: 1px solid %(SEP)s; border-radius: 8px; padding: 4px; }
#SMPanel QMenu::item { padding: 5px 18px; border-radius: 5px; }
#SMPanel QMenu::item:selected { background: %(ACC)s; }
#SMPanel QMenu::separator { height: 1px; background: %(SEP)s; margin: 4px 6px; }
""" % t
    if glass:
        css += GLASS % t
    return _rgba(css)


# Glass mode: the panel paints a patterned backdrop (backdrop.py); surfaces become translucent.
GLASS = """
#SMPanel QScrollArea, #SMPanel QStackedWidget, #SMDetail, #SMCards, #SMPanel QSplitter { background: transparent; }
#SMRail { background: #0a0a0c80; border-right: 1px solid #ffffff14; }
#SMSidebar { background: #1c1c1e66; border-right: 1px solid #ffffff14; }
QTreeWidget#SMTree, QListWidget#SMGrid, #SMPanel QHeaderView, #SMPanel QHeaderView::section { background: transparent; }
QFrame#SMCard { border: 1px solid #ffffff14; border-radius: %(CR)spx; background: #1c1c1e8c; }  /* flat glass: no sheen */
QFrame#SMCard[dragging="true"] { border: 1px dashed %(ACC)s; background: #0a84ff1a; }
#SMCard QSpinBox, #SMCard QDoubleSpinBox, #SMCard QLineEdit, #SMCard QComboBox { background: #0000004d; border: 1px solid #ffffff14; }
QLineEdit#SMSearch { background: #0000004d; border: 1px solid #ffffff1a; }
QPushButton#SMButton, QToolButton#SMButton { background: #ffffff1f; }
QPushButton#SMButton:hover, QToolButton#SMButton:hover { background: #ffffff2e; }
#SMStatusBar { background: #0a0a0cb3; border-top: 1px solid #ffffff14; }
#SMPanel QPlainTextEdit, #SMPanel QListWidget#SMLog { background: #2c2c2eb3; }
"""


def _rgba(css):
    """Qt reads 8-digit hex as #AARRGGBB; we write #RRGGBBAA, so convert to rgba()."""
    import re

    def conv(m):
        h = m.group(1)
        r, g, b, a = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
        return "rgba(%d, %d, %d, %d)" % (r, g, b, a)
    return re.sub(r"#([0-9a-fA-F]{8})\b", conv, css)


rgba = _rgba  # public alias for other modules' QSS


def dark_palette():
    from PySide6 import QtGui
    pal = QtGui.QPalette()
    roles = {
        QtGui.QPalette.Window: BG, QtGui.QPalette.WindowText: LABEL,
        QtGui.QPalette.Base: FIELD, QtGui.QPalette.AlternateBase: SIDEBAR,
        QtGui.QPalette.Text: LABEL, QtGui.QPalette.Button: SURFACE_2,
        QtGui.QPalette.ButtonText: LABEL, QtGui.QPalette.Highlight: ACCENT,
        QtGui.QPalette.HighlightedText: "#ffffff", QtGui.QPalette.ToolTipBase: SURFACE,
        QtGui.QPalette.ToolTipText: LABEL, QtGui.QPalette.PlaceholderText: LABEL_3,
    }
    for role, color in roles.items():
        pal.setColor(role, QtGui.QColor(color))
    for role in (QtGui.QPalette.Text, QtGui.QPalette.ButtonText, QtGui.QPalette.WindowText):
        pal.setColor(QtGui.QPalette.Disabled, role, QtGui.QColor(LABEL_3))
    return pal
