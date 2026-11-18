"""Module cards: one per module, rows per property with an override checkbox.

Row dot: blue = set on this setup/folder, grey = inherited from a folder (or from the scene),
orange = differs from the scene right now.
"""
from PySide6 import QtCore, QtGui, QtWidgets
from pymxs import runtime as rt

from ..core import nodes, registry
from ..modules import sun as sun_mod
import json

from . import card_prefs, groups, icons, layout, prop_kinds, theme
from .widgets import Switch


# ---- property widgets -----------------------------------------------------
class PropWidget(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, prop, value, parent=None, ctx=None):
        super().__init__(parent)
        self.prop = prop
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        k = prop.kind
        self._refs = {}
        if k in prop_kinds.kinds():  # extra kinds registered in ui/kinds_*.py (M2+)
            w = prop_kinds.create(prop, value, self.changed.emit, ctx or {})
        elif k in ("camera", "sunlight"):
            w = QtWidgets.QComboBox()
            pool = nodes.list_cameras() if k == "camera" else (sun_mod.list_suns() or nodes.list_lights())
            names = [str(n.name) for n in pool]
            cur = (value or {}).get("name") if isinstance(value, dict) else None
            if cur and cur not in names:
                names.insert(0, cur)
            w.addItems(["(none)"] + names)
            w.setCurrentText(cur or "(none)")
            w.activated.connect(lambda *_: self.changed.emit())
        elif k == "int":
            w = QtWidgets.QSpinBox()
            w.setRange(int(prop.minimum), int(prop.maximum))
            w.setSuffix(prop.suffix)
            w.setValue(int(value) if value is not None else 0)
            w.editingFinished.connect(self.changed.emit)
        elif k == "float":
            w = QtWidgets.QDoubleSpinBox()
            w.setRange(prop.minimum, prop.maximum)
            w.setDecimals(prop.decimals)
            w.setSingleStep(prop.step)
            w.setSuffix(prop.suffix)
            w.setValue(float(value) if value is not None else 0.0)
            w.editingFinished.connect(self.changed.emit)
        elif k == "bool":
            w = Switch()
            w.setChecked(bool(value))
            w.toggled.connect(lambda *_: self.changed.emit())
        elif k == "enum":
            w = QtWidgets.QComboBox()
            w.addItems(list(prop.options))
            if value is not None:
                w.setCurrentText(str(value))
            w.activated.connect(lambda *_: self.changed.emit())
        else:  # text, path
            w = QtWidgets.QLineEdit("" if value is None else str(value))
            w.editingFinished.connect(self.changed.emit)
            if k == "path":
                b = QtWidgets.QToolButton()
                b.setObjectName("SMPlain")
                b.setText("…")
                b.setToolTip("Browse")
                b.clicked.connect(self._browse)
                lay.addWidget(w, 1)
                lay.addWidget(b)
        if prop.tip:
            w.setToolTip(prop.tip)
        self.w = w
        if lay.count() == 0:
            lay.addWidget(w, 1)

    def _browse(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Output file", self.w.text(),
                                                      "Images (*.exr *.png *.jpg *.tif *.tga)")
        if fn:
            self.w.setText(fn)
            self.changed.emit()

    def get(self):
        k, w = self.prop.kind, self.w
        if k in prop_kinds.kinds():
            return w.value()
        if k in ("camera", "sunlight"):
            name = w.currentText()
            if name == "(none)":
                return None
            n = rt.getNodeByName(name)
            return nodes.ref(n) if n is not None else {"name": name, "handle": None}
        if k == "int":
            return w.value()
        if k == "float":
            return round(w.value(), self.prop.decimals)
        if k == "bool":
            return w.isChecked()
        if k == "enum":
            return w.currentText()
        return w.text().strip()


def _dot(color, filled=True):
    pm = QtGui.QPixmap(10, 10)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    pen = QtGui.QPen(QtGui.QColor(color))
    pen.setWidthF(1.5)
    p.setPen(pen)
    p.setBrush(QtGui.QColor(color) if filled else QtCore.Qt.NoBrush)
    p.drawEllipse(2, 2, 6, 6)
    p.end()
    return pm


class _BodyScroll(QtWidgets.QScrollArea):
    """Card body; scrolls only when the card was resized shorter than its rows."""

    def __init__(self, body):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidget(body)
        self.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        self.setObjectName("SMCardBody")
        self.setStyleSheet("QScrollArea#SMCardBody, QScrollArea#SMCardBody > QWidget > QWidget { background: transparent; }")

    def sizeHint(self):
        return self.widget().sizeHint()

    def minimumSizeHint(self):
        return QtCore.QSize(self.widget().minimumSizeHint().width(), 0)


class _Grip(QtWidgets.QWidget):
    """Teal corner mark at the bottom-right: drag for width (snaps to columns) and height; double-click resets."""

    def __init__(self, card):
        super().__init__(card)
        self.card = card
        self.setFixedSize(14, 14)
        self.setCursor(QtCore.Qt.SizeFDiagCursor)
        self.setToolTip("Drag to resize · double-click to reset")
        self.dragging = False
        self._start = None

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("#2ad4c4"))
        pen.setWidthF(2.0)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QtCore.QPointF(12, 3), QtCore.QPointF(12, 12))
        p.drawLine(QtCore.QPointF(3, 12), QtCore.QPointF(12, 12))
        p.end()

    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.dragging = True
            self._start = (e.globalPosition().toPoint(), self.card.width(), self.card.height())

    def mouseMoveEvent(self, e):
        if self.dragging:
            d = e.globalPosition().toPoint() - self._start[0]
            board = self.card.parentWidget()
            if hasattr(board, "card_resizing"):
                board.card_resizing(self.card, self._start[1] + d.x(), self._start[2] + d.y())

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            self.card.set_size(self.card.fixed_w, self.card.fixed_h, save=True)
            if not self.card.underMouse():
                self.hide()

    def mouseDoubleClickEvent(self, e):
        self.card._reset_size()


class _ColorDots(QtWidgets.QWidget):
    """Row of colour dots for the card menu (first dot = no colour)."""

    def __init__(self, current, on_pick):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(14, 4, 14, 4)
        lay.setSpacing(6)
        for c in [None] + card_prefs.COLORS:
            b = QtWidgets.QToolButton()
            b.setFixedSize(18, 18)
            b.setToolTip("No colour" if c is None else c)
            ring = "2px solid #ffffff" if c == current else "1px solid rgba(255, 255, 255, 64)"
            b.setStyleSheet("QToolButton { background: %s; border: %s; border-radius: 9px; }" %
                            (c or "transparent", ring))
            b.clicked.connect(lambda _=False, c=c: on_pick(c))
            lay.addWidget(b)


# ---- card -------------------------------------------------------------------
class ModuleCard(QtWidgets.QFrame):
    """Card for one module on one setup or folder."""

    MIME = "application/x-scene-manager-module"

    def __init__(self, mgr, item, module, parent=None, collapsed=False, on_collapse=None):
        super().__init__(parent)
        self._on_collapse = on_collapse
        self._press = None
        self.setObjectName("SMCard")
        self.mgr, self.item, self.m = mgr, item, module
        self.state = mgr.module_state(item, module.key)
        own = item["modules"].get(module.key) or {}
        self.own_values = own.get("values") or {}
        try:
            self.scene = module.capture()
        except Exception:
            self.scene = {}
        # differs from the scene: reuse the capture above instead of reading the scene a second time
        self.differs = set()
        if item["type"] == "setup" and self.state["enabled"] and getattr(module, "touches_scene", True) and self.scene:
            try:
                self.differs = module.differs(self.state["values"], self.scene)
            except Exception:
                self.differs = set()
        self.prefs = card_prefs.get(module.key)
        self.fixed_w = self.prefs.get("w")
        self.fixed_h = self.prefs.get("h")
        self.col = self.prefs.get("col")  # grid column on the board (None = first free spot)
        self.slot_col = 0
        # table cards (Layers, Objects, Lights...) start two columns wide, as in SM3
        self.default_span = 2 if any(prop_kinds.is_wide(p.kind) for p in module.props) else 1
        self.collapsed = False

        L = layout.current()  # every gap below comes from the layout tokens
        pad = L["card_pad"]
        lay = QtWidgets.QVBoxLayout(self)
        self._bottom = max(4, pad - 4)
        lay.setContentsMargins(0, 0, 0, self._bottom)
        lay.setSpacing(0)

        group = groups.group_of(module)
        color = self.prefs.get("color")
        tint = color or groups.TINT.get(group, theme.ACCENT)
        head = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(head)
        hl.setContentsMargins(pad, L["header_pad"], pad, max(2, L["header_pad"] - 2))
        hl.setSpacing(L["header_gap"])
        self.head = head
        head.setCursor(QtCore.Qt.OpenHandCursor)
        head.setToolTip("Drag to move · double-click to fold")
        head.installEventFilter(self)
        badge = QtWidgets.QLabel()
        isz = L["icon_size"]
        badge.setPixmap(icons.tinted(groups.ICON.get(group, "scene"), tint).pixmap(isz, isz))
        badge.setToolTip(groups.LABEL.get(group, ""))
        if color:  # coloured card: tinted header band
            c = QtGui.QColor(color)
            head.setObjectName("SMCardHead")
            head.setAttribute(QtCore.Qt.WA_StyledBackground)
            r = L["card_radius"]
            head.setStyleSheet("#SMCardHead { background: rgba(%d, %d, %d, 46); border-top-left-radius: %dpx;"
                               " border-top-right-radius: %dpx; }" % (c.red(), c.green(), c.blue(), r, r))
        hl.addWidget(badge)
        title = QtWidgets.QLabel(self.prefs.get("title") or module.label)
        self.title_lbl = title
        title.setObjectName("SMCardTitle")
        title.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)  # head handles click (collapse) and drag
        hl.addWidget(title)
        origin = self._origin_text()
        if origin:
            o = QtWidgets.QLabel(origin)
            o.setObjectName("SMCardOrigin")
            hl.addWidget(o)
        hl.addStretch(1)
        bsz = max(28, isz + 10)  # header buttons scale with the icon size token
        self.collapse = QtWidgets.QToolButton()
        self.collapse.setObjectName("SMCardBtn")
        self.collapse.setCheckable(True)
        self.collapse.setIcon(icons.get("chev_up", theme.LABEL_2, theme.LABEL_2))
        self.collapse.setIconSize(QtCore.QSize(isz + 4, isz + 4))
        self.collapse.setFixedSize(bsz, bsz)
        self.collapse.setToolTip("Collapse")
        self.collapse.toggled.connect(self._toggle_body)
        self.collapse.hide()  # SM3 has no fold arrow: double-click the header or use the gear menu
        menu_btn = QtWidgets.QToolButton()
        menu_btn.setObjectName("SMCardBtn")
        menu_btn.setIcon(icons.get("gear", theme.LABEL_2, theme.LABEL_2))
        menu_btn.setIconSize(QtCore.QSize(isz, isz))
        menu_btn.setFixedSize(bsz, bsz)
        menu_btn.setToolTip("Card menu")
        menu_btn.setPopupMode(QtWidgets.QToolButton.InstantPopup)
        menu_btn.setMenu(self._menu())
        hl.addWidget(menu_btn)
        hl.addWidget(self.collapse)
        self.enabled_box = Switch(on_color=tint)
        self.enabled_box.setToolTip("Module on for this %s. Off = leave this part of the scene alone." % item["type"])
        self.enabled_box.setChecked(self.state["enabled"])
        self.enabled_box.toggled.connect(self._on_enabled)
        hl.addWidget(self.enabled_box)
        lay.addWidget(head)
        self.hair = QtWidgets.QFrame()
        self.hair.setObjectName("SMHairline")
        self.hair.setFixedHeight(1)
        hl2 = QtWidgets.QHBoxLayout()
        hl2.setContentsMargins(pad, 0, pad, 0)
        hl2.addWidget(self.hair)
        lay.addLayout(hl2)

        self.body = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self.body)
        grid.setContentsMargins(pad, max(2, L["row_gap"]), pad, 2)
        grid.setHorizontalSpacing(L["col_gap"])
        grid.setVerticalSpacing(L["row_gap"])
        grid.setColumnStretch(2, 1)
        above = L["label_pos"] == "above"
        dots = L["show_dots"] == "yes"
        if not above:
            grid.setColumnMinimumWidth(1, L["label_width"])  # one label column: fields line up across cards
        label_align = (QtCore.Qt.AlignRight if L["label_align"] == "right" else QtCore.Qt.AlignLeft) | \
            QtCore.Qt.AlignVCenter
        self.rows = {}
        r = -1
        for prop in module.props:
            r += 1
            own_set = prop.key in self.own_values
            inherited = prop.key in self.state["values"] and not own_set
            if own_set:
                value = self.own_values[prop.key]
            elif inherited:
                value = self.state["values"][prop.key]
            else:
                value = self.scene.get(prop.key)
            dot = QtWidgets.QLabel()
            if prop.key in self.differs:
                dot.setPixmap(_dot(theme.DIFFERS))
                dot.setToolTip("Differs from the scene right now")
            elif own_set:
                dot.setPixmap(_dot(theme.OVERRIDE))
                dot.setToolTip("Set on this %s" % item["type"])
            else:
                dot.setPixmap(_dot(theme.INHERITED, filled=inherited))
                dot.setToolTip(self._source_tip(prop.key) if inherited else "Not stored: the scene value is kept")
            label = QtWidgets.QLabel(prop.label)
            label.setObjectName("SMPropLabel")
            label.setAlignment(label_align)
            label.setWordWrap(not above)
            if not above:
                label.setFixedWidth(L["label_width"])
            ctx = {"own": self.own_values.get(prop.key), "effective": self.state["values"].get(prop.key),
                   "scene": self.scene.get(prop.key), "item": item, "mgr": mgr}
            w = PropWidget(prop, value, ctx=ctx)
            w.setEnabled(own_set or prop_kinds.always_editable(prop.kind))
            w.changed.connect(lambda p=prop.key: self._on_value(p))
            over = QtWidgets.QCheckBox()
            over.setChecked(own_set)
            over.setToolTip("Store this value here (unticked = inherit from the folder, or leave the scene alone)")
            over.toggled.connect(lambda on, p=prop.key: self._on_override(p, on))
            w.setMinimumHeight(L["field_height"]) if not prop_kinds.is_wide(prop.kind) else None
            grid.addWidget(dot, r, 0)
            if not dots:
                dot.hide()  # only after it has a parent: hiding/showing a parentless widget opens a window
            if prop_kinds.is_wide(prop.kind):  # tables, notes: full width on the next line
                grid.addWidget(label, r, 1, 1, 2)
                grid.addWidget(over, r, 3)
                r += 1
                grid.addWidget(w, r, 0, 1, 4)
            elif above:  # label on its own line, field under it at full width
                grid.addWidget(label, r, 1, 1, 2)
                grid.addWidget(over, r, 3)
                r += 1
                grid.addWidget(w, r, 1, 1, 2)
            else:
                grid.addWidget(label, r, 1)
                grid.addWidget(w, r, 2)
                grid.addWidget(over, r, 3)
            self.rows[prop.key] = (w, over)
        self.body_scroll = _BodyScroll(self.body)
        lay.addWidget(self.body_scroll, 1)
        self.body.setEnabled(self.state["enabled"])
        self.grip = _Grip(self)
        self.grip.hide()
        for text, seq, fn in (("Copy values", QtGui.QKeySequence.Copy, self._copy),
                              ("Paste values", QtGui.QKeySequence.Paste, self._paste)):
            a = QtGui.QAction(text, self)
            a.setShortcut(seq)
            a.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)
            a.triggered.connect(fn)
            self.addAction(a)
        self._apply_fixed_height()
        if collapsed:
            self.collapse.blockSignals(True)
            self.collapse.setChecked(True)
            self.collapse.blockSignals(False)
            self._toggle_body(True, notify=False)

    # ---- drag the header to move the card; double-click folds it ----
    def eventFilter(self, obj, e):
        if obj is self.head:
            t = e.type()
            if t == QtCore.QEvent.MouseButtonPress and e.button() == QtCore.Qt.LeftButton:
                self._press = e.position().toPoint()
                return True
            if t == QtCore.QEvent.MouseMove and self._press is not None:
                if (e.position().toPoint() - self._press).manhattanLength() >= QtWidgets.QApplication.startDragDistance():
                    self._press = None
                    self._start_drag()
                return True
            if t == QtCore.QEvent.MouseButtonRelease and self._press is not None:
                self._press = None
                return True
            if t == QtCore.QEvent.MouseButtonDblClick:
                self._press = None
                self.collapse.toggle()
                return True
        return super().eventFilter(obj, e)

    def _start_drag(self):
        drag = QtGui.QDrag(self)
        mime = QtCore.QMimeData()
        mime.setData(self.MIME, self.m.key.encode())
        drag.setMimeData(mime)
        pm = self.grab()
        if pm.height() > 220:
            pm = pm.copy(0, 0, pm.width(), 220)
        ghost = QtGui.QPixmap(pm.size())
        ghost.setDevicePixelRatio(pm.devicePixelRatio())
        ghost.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(ghost)
        p.setOpacity(0.75)
        p.drawPixmap(0, 0, pm)
        p.end()
        drag.setPixmap(ghost)
        drag.setHotSpot(QtCore.QPoint(24, 16))
        self.setProperty("dragging", True)
        self.style().unpolish(self)
        self.style().polish(self)
        drag.exec(QtCore.Qt.MoveAction)
        try:
            self.setProperty("dragging", False)
            self.style().unpolish(self)
            self.style().polish(self)
        except RuntimeError:  # the board was rebuilt during the drop
            pass

    # ---- helpers ----
    def _origin_text(self):
        if not self.state["enabled"]:
            return "off"
        srcs = set(self.state["source"].values())
        if not srcs or srcs == {self.item["id"]}:
            return ""
        names = [self.mgr.get(s)["name"] for s in srcs if s != self.item["id"] and self.mgr.get(s)]
        return "from " + ", ".join(sorted(names)) if names else ""

    def _source_tip(self, prop_key):
        src = self.mgr.get(self.state["source"].get(prop_key))
        return "Inherited from folder '%s'" % src["name"] if src else "Inherited"

    def _toggle_body(self, collapsed, notify=True):
        self.collapsed = collapsed
        self.body_scroll.setVisible(not collapsed)
        self.hair.setVisible(not collapsed)
        self._apply_fixed_height()
        self.layout().setContentsMargins(0, 0, 0, 0 if collapsed else self._bottom)
        self.collapse.setIcon(icons.get("chev_down" if collapsed else "chev_up", theme.LABEL_2, theme.LABEL_2))
        self.collapse.setToolTip("Expand" if collapsed else "Collapse")
        if notify and self._on_collapse:
            self._on_collapse(self.m.key, collapsed)

    def _menu(self):
        menu = QtWidgets.QMenu(self)
        menu.aboutToShow.connect(lambda: self._fill_menu(menu))
        return menu

    def _fill_menu(self, menu):
        menu.clear()
        name = QtWidgets.QLineEdit(self.title_lbl.text())
        name.setPlaceholderText(self.m.label)
        name.setStyleSheet("QLineEdit { margin: 4px 10px; padding: 4px 6px; border-radius: 6px;"
                           " background: rgba(0, 0, 0, 77); border: 1px solid rgba(255, 255, 255, 30); }")
        name.returnPressed.connect(lambda: (self._rename_to(name.text()), menu.close()))
        name.editingFinished.connect(lambda: self._rename_to(name.text()))
        wa = QtWidgets.QWidgetAction(menu)
        wa.setDefaultWidget(name)
        menu.addAction(wa)
        dots = QtWidgets.QWidgetAction(menu)
        dots.setDefaultWidget(_ColorDots(self.prefs.get("color"), lambda c: (menu.close(), self._set_color(c))))
        menu.addAction(dots)
        menu.addSeparator()
        add = menu.addMenu("Add a property")
        free = [p for p in self.m.props if p.key not in self.own_values]
        for p in free:
            add.addAction(p.label, lambda k=p.key: self.rows[k][1].setChecked(True))
        add.setEnabled(bool(free))
        menu.addAction("Unfold" if self.collapsed else "Fold", self.collapse.toggle)
        a = menu.addAction("Reset size", self._reset_size)
        a.setEnabled(bool(self.fixed_h or self.fixed_w))
        menu.addSeparator()
        menu.addAction("Copy values\tCtrl+C", self._copy)
        a = menu.addAction("Paste values\tCtrl+V", self._paste)
        a.setEnabled(self._clipboard_values() is not None)
        menu.addSeparator()
        menu.addAction("Fetch from scene", self._fetch)
        if self.item["type"] == "setup":
            menu.addAction("Apply this module only", self._apply_only)
        if self.m.actions():
            menu.addSeparator()
        for label, fn in self.m.actions():
            menu.addAction(label, lambda fn=fn: self._run_action(fn))
        menu.addSeparator()
        menu.addAction("Clear values set here", self._clear)
        menu.addAction("Remove", self._remove)

    # ---- card look: size, colour, title (per user, see card_prefs) ----
    def min_height(self):
        return self.head.sizeHint().height() + 40

    def layout_height(self):
        if self.collapsed or not self.fixed_h:
            return self.sizeHint().height()
        return max(self.min_height(), int(self.fixed_h))

    def _apply_fixed_height(self):
        short = bool(self.fixed_h) and not self.collapsed and int(self.fixed_h) < self.sizeHint().height()
        self.body_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded if short else QtCore.Qt.ScrollBarAlwaysOff)
        if self.fixed_h and not self.collapsed:
            self.setFixedHeight(self.layout_height())
        else:
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)

    def width_px(self, colw, gap):
        if self.fixed_w:
            return int(self.fixed_w)
        return int(self.default_span * colw + (self.default_span - 1) * gap)

    def set_size(self, width, height, save=False):
        self.fixed_w, self.fixed_h = width, height
        self._apply_fixed_height()
        if save:
            card_prefs.update(self.m.key, w=width, h=height)

    def _reset_size(self):
        self.set_size(None, None, save=True)
        self._relayout()

    def _relayout(self):
        board = self.parentWidget()
        if hasattr(board, "relayout"):
            board.relayout()

    def _set_color(self, color):
        card_prefs.update(self.m.key, color=color)
        self.mgr._notify()  # rebuild the board with the new colour

    def _rename_to(self, text):
        text = text.strip()
        card_prefs.update(self.m.key, title=text if text and text != self.m.label else None)
        self.title_lbl.setText(text or self.m.label)

    # ---- copy / paste values between cards (also across setups) ----
    _CLIP = "scene-manager-values:"

    def _copy(self):
        values = dict(self.scene)
        values.update(self.state["values"])
        values.update(self.own_values)
        QtWidgets.QApplication.clipboard().setText(self._CLIP + json.dumps({"module": self.m.key, "values": values}))

    def _clipboard_values(self):
        text = QtWidgets.QApplication.clipboard().text()
        if not text.startswith(self._CLIP):
            return None
        try:
            data = json.loads(text[len(self._CLIP):])
        except ValueError:
            return None
        return data.get("values") if data.get("module") == self.m.key else None

    def _paste(self):
        values = self._clipboard_values()
        if values:
            keys = {p.key for p in self.m.props}
            self.mgr.set_values(self.item["id"], self.m.key, {k: v for k, v in values.items() if k in keys})
            self._live_apply()

    # ---- hover shows the resize corner ----
    def enterEvent(self, e):
        self.grip.show()
        self.grip.raise_()
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self.grip.dragging:
            self.grip.hide()
        super().leaveEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.grip.move(self.width() - self.grip.width() - 3, self.height() - self.grip.height() - 3)

    def _is_active(self):
        return self.item["type"] == "setup" and self.item["id"] == self.mgr.active_id

    def _live_apply(self):
        if self._is_active():
            self.mgr.apply(self.item["id"], only=[self.m.key])

    # ---- actions ----
    def _on_enabled(self, on):
        self.mgr.set_enabled(self.item["id"], self.m.key, on)
        self._live_apply()

    def _on_override(self, prop_key, on):
        if on:
            self.mgr.set_values(self.item["id"], self.m.key, {prop_key: self.rows[prop_key][0].get()})
        else:
            self.mgr.clear_value(self.item["id"], self.m.key, prop_key)
        self._live_apply()

    def _on_value(self, prop_key):
        self.mgr.set_values(self.item["id"], self.m.key, {prop_key: self.rows[prop_key][0].get()})
        self._live_apply()

    def _fetch(self):
        self.mgr.capture(self.item["id"], keys=[self.m.key])

    def _apply_only(self):
        self.mgr.apply(self.item["id"], only=[self.m.key])

    def _run_action(self, fn):
        values = dict(self.scene)
        values.update(self.state["values"])
        new = fn(values)
        self.mgr.set_values(self.item["id"], self.m.key, {k: v for k, v in new.items() if values.get(k) != v})
        self._live_apply()

    def _clear(self):
        entry = self.item["modules"].get(self.m.key)
        if entry:
            entry["values"] = {}
            self.mgr.commit()

    def _remove(self):
        self.mgr.remove_module(self.item["id"], self.m.key)
