"""Card widgets for the M2 prop kinds: table (Lights, Layers, Objects, XRef Scenes), note, todo.

Table: one row per light / layer / rule. The tick at the left stores the row on this setup or
folder; unticked rows show what is inherited (grey) or what the scene has now. Editing a cell
ticks its row. Column kinds: bool, tristate (square = leave alone), float, int, enum, color.
"""
from PySide6 import QtCore, QtGui, QtWidgets

from . import theme
from .prop_kinds import register_kind

MAX_TABLE_HEIGHT = 260
ROW_HEIGHT = 26
TABLE_CSS = """
QTableWidget#SMTable { background: %(FIELD)s; border: 1px solid #ffffff0d; border-radius: 8px;
    gridline-color: transparent; outline: 0; }
QTableWidget#SMTable QHeaderView { background: transparent; }
QTableWidget#SMTable QHeaderView::section { background: transparent; color: %(L3)s; border: none;
    border-bottom: 1px solid %(SEP)s; padding: 3px 6px; font-size: 11px; }
QTableWidget#SMTable::item { padding: 0 4px; border: none; }
QTableWidget#SMTable QTableCornerButton::section { background: transparent; border: none; }
QTableWidget#SMTable QLineEdit, QTableWidget#SMTable QComboBox {
    background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 0 4px; min-height: 0; }
QTableWidget#SMTable QLineEdit:focus { border: 1px solid %(ACC)s; }
QPlainTextEdit#SMNote { background: %(FIELD)s; border: 1px solid #ffffff0d; border-radius: 8px; padding: 4px; }
QPlainTextEdit#SMNote:focus { border: 1px solid %(ACC)s; }
""" % dict(FIELD=theme.FIELD, L3=theme.LABEL_3, SEP=theme.SEPARATOR, ACC=theme.ACCENT)
TABLE_CSS = theme._rgba(TABLE_CSS)  # Qt reads #rrggbbaa as #aarrggbb


def _rows(v):
    return dict(v) if isinstance(v, dict) else {}


class TableWidget(QtWidgets.QWidget):
    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self.prop, self.emit = prop, emit
        own = _rows(ctx.get("own"))
        eff = _rows(ctx.get("effective"))
        scene = _rows(ctx.get("scene"))
        self.cols = list(prop.columns)
        self.data = {}      # row -> cols shown
        self.ticked = set(own)
        for src in (scene, eff, own):
            for r, c in src.items():
                if isinstance(c, dict):
                    self.data[r] = dict(self.data.get(r) or {}, **c)
        self.inherited = set(eff) - set(own)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if len(self.data) > 8:
            self.filter = QtWidgets.QLineEdit()
            self.filter.setPlaceholderText("Filter")
            self.filter.setClearButtonEnabled(True)
            self.filter.textChanged.connect(self._apply_filter)
            lay.addWidget(self.filter)
        self.table = QtWidgets.QTableWidget(0, len(self.cols) + 2)
        self.table.setObjectName("SMTable")
        self.table.setStyleSheet(TABLE_CSS)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalHeaderLabels([""] + [""] + [c.label for c in self.cols])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hh.setMinimumSectionSize(24)
        hh.setHighlightSections(False)
        for i, c in enumerate(self.cols):
            if c.kind in ("float", "int", "enum"):
                hh.setSectionResizeMode(i + 2, QtWidgets.QHeaderView.Fixed)
                self.table.setColumnWidth(i + 2, 76)
            if c.tip:
                self.table.horizontalHeaderItem(i + 2).setToolTip(c.tip)
        self.table.horizontalHeaderItem(0).setToolTip("Stored on this setup/folder")
        self.table.horizontalHeaderItem(1).setText("Name")
        self._editors = {}
        for r in self.data:
            self._add_row(r)
        self._fit()
        lay.addWidget(self.table)

        if callable(prop.options) or getattr(prop, "add_selection", None):
            add = QtWidgets.QHBoxLayout()
            self.new = QtWidgets.QComboBox()
            self.new.setEditable(True)
            self.new.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
            self.new.lineEdit().setPlaceholderText("set:Name, layer:Name, pattern:Tree_*, node:Name")
            if callable(prop.options):
                try:
                    self.new.addItems([""] + list(prop.options()))
                except Exception:
                    pass
            self.new.setCurrentText("")
            self.new.lineEdit().returnPressed.connect(self._on_add)
            b = QtWidgets.QToolButton()
            b.setObjectName("SMPlain")
            b.setText("+ Add")
            b.clicked.connect(self._on_add)
            add.addWidget(self.new, 1)
            add.addWidget(b)
            if getattr(prop, "add_selection", None):
                s = QtWidgets.QToolButton()
                s.setObjectName("SMPlain")
                s.setText("+ Selection")
                s.setToolTip("One rule per selected object. For many objects use a selection set.")
                s.clicked.connect(self._on_add_selection)
                add.addWidget(s)
            lay.addLayout(add)

    # ---- rows ----
    def _add_row(self, r):
        row = self.table.rowCount()
        self.table.insertRow(row)
        tick = QtWidgets.QCheckBox()
        tick.setChecked(r in self.ticked)
        tick.setToolTip("Store this row here" if r not in self.inherited else "Inherited from the folder; tick to override")
        tick.toggled.connect(lambda on, r=r: self._on_tick(r, on))
        self.table.setCellWidget(row, 0, _centered(tick))
        name = QtWidgets.QTableWidgetItem(r)
        name.setFlags(QtCore.Qt.ItemIsEnabled)
        if r not in self.ticked:
            name.setForeground(QtGui.QColor(theme.INHERITED))
        name.setToolTip(r)
        self.table.setItem(row, 1, name)
        eds = {}
        for i, c in enumerate(self.cols):
            w = self._editor(r, c, self.data[r].get(c.key))
            eds[c.key] = w
            self.table.setCellWidget(row, i + 2, w)
        self._editors[r] = (row, tick, eds)

    def _editor(self, r, c, v):
        k = c.kind
        if v is None and k not in ("tristate",):
            lbl = QtWidgets.QLabel("–")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            lbl.setToolTip("Not available on this %s" % ("light" if "light" in self.prop.key else "item"))
            lbl.value = lambda: None
            return lbl
        if k == "bool":
            w = QtWidgets.QCheckBox()
            w.setChecked(bool(v))
            w.toggled.connect(lambda *_: self._on_cell(r))
            box = _centered(w)
            box.value = w.isChecked
            return box
        if k == "tristate":
            w = TriButton(v)
            w.changed.connect(lambda: self._on_cell(r))
            return _centered_value(w)
        if k in ("float", "int"):
            # a line edit with a validator: spin boxes clip their text inside table cells
            w = QtWidgets.QLineEdit()
            if k == "float":
                w.setValidator(QtGui.QDoubleValidator(c.minimum, c.maximum, c.decimals, w))
                w.setText(("%%.%df" % c.decimals) % float(v))
            else:
                w.setValidator(QtGui.QIntValidator(int(max(c.minimum, -2**31)), int(min(c.maximum, 2**31 - 1)), w))
                w.setText(str(int(v)))
            w.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            w.editingFinished.connect(lambda: self._on_cell(r))

            def value(w=w, k=k, v=v):
                try:
                    x = float(w.text().replace(",", "."))
                except ValueError:
                    return v
                return round(x, c.decimals) if k == "float" else int(x)
            w.value = value
            return w
        if k == "enum":
            w = QtWidgets.QComboBox()
            w.addItems(list(c.options))
            w.setCurrentText(str(v))
            w.activated.connect(lambda *_: self._on_cell(r))
            w.value = w.currentText
            return w
        if k == "color":
            w = QtWidgets.QToolButton()
            w.setObjectName("SMPlain")
            w.setFixedSize(26, 18)
            w._c = list(v)
            _paint_swatch(w)

            def pick(w=w):
                c0 = QtGui.QColor(*[max(0, min(255, int(x))) for x in w._c])
                c1 = QtWidgets.QColorDialog.getColor(c0, self, "Light colour")
                if c1.isValid():
                    w._c = [c1.red(), c1.green(), c1.blue()]
                    _paint_swatch(w)
                    self._on_cell(r)
            w.clicked.connect(pick)
            w.value = lambda w=w: list(w._c)
            return w
        lbl = QtWidgets.QLabel(str(v))
        lbl.value = lambda: v
        return lbl

    def _fit(self):
        h = self.table.horizontalHeader().height() + 4
        for i in range(self.table.rowCount()):
            h += self.table.rowHeight(i)
        self.table.setFixedHeight(min(MAX_TABLE_HEIGHT, max(h, 40)))

    def _apply_filter(self, text):
        t = text.lower()
        for r, (row, _, _) in self._editors.items():
            self.table.setRowHidden(row, bool(t) and t not in r.lower())

    # ---- events ----
    def _on_tick(self, r, on):
        (self.ticked.add if on else self.ticked.discard)(r)
        self.emit()

    def _on_cell(self, r):
        row, tick, eds = self._editors[r]
        for k, w in eds.items():
            self.data[r][k] = w.value()
        self.ticked.add(r)
        if not tick.isChecked():
            tick.blockSignals(True)
            tick.setChecked(True)
            tick.blockSignals(False)
        self.emit()

    def _on_add(self):
        t = self.new.currentText().strip()
        if not t or t in self.data:
            return
        self._add(t)
        self.emit()

    def _on_add_selection(self):
        from pymxs import runtime as rt
        from ..core import nodes
        prefix = self.prop.add_selection
        added = False
        for n in rt.selection:
            t = prefix + str(n.name)
            if t not in self.data:
                self._add(t, ref=nodes.ref(n))
                added = True
        if added:
            self.emit()

    def _add(self, t, ref=None):
        row = dict(getattr(self.prop, "new_row", None) or {})
        if ref:
            row["ref"] = ref
        self.data[t] = row
        self.ticked.add(t)
        self._add_row(t)
        self._fit()

    def value(self):
        return {r: dict(self.data[r]) for r in self.data if r in self.ticked}


class TriButton(QtWidgets.QToolButton):
    """Three states: None = leave alone (·), True (✓), False (✕). Click cycles."""
    changed = QtCore.Signal()
    LOOK = {None: ("·", theme.INHERITED, "Leave alone (click: on)"),
            True: ("✓", theme.ACCENT, "On (click: off)"),
            False: ("✕", theme.ORANGE, "Off (click: leave alone)")}

    def __init__(self, v):
        super().__init__()
        self.setObjectName("SMPlain")
        self.setFixedSize(26, 20)
        self.v = v
        self.clicked.connect(self._cycle)
        self._show()

    def _cycle(self):
        self.v = {None: True, True: False, False: None}[self.v]
        self._show()
        self.changed.emit()

    def _show(self):
        text, color, tip = self.LOOK[self.v]
        self.setText(text)
        self.setToolTip(tip)
        self.setStyleSheet("QToolButton { color: %s; font-weight: 600; }" % color)

    def value(self):
        return self.v


def _centered_value(w):
    box = _centered(w)
    box.value = w.value
    return box


def _centered(w):
    box = QtWidgets.QWidget()
    l = QtWidgets.QHBoxLayout(box)
    l.setContentsMargins(0, 0, 0, 0)
    l.addWidget(w, 0, QtCore.Qt.AlignCenter)
    return box


def _paint_swatch(btn):
    pm = QtGui.QPixmap(20, 12)
    pm.fill(QtGui.QColor(*[max(0, min(255, int(x))) for x in btn._c]))
    btn.setIcon(QtGui.QIcon(pm))
    btn.setIconSize(QtCore.QSize(20, 12))
    btn.setToolTip("RGB %d, %d, %d" % tuple(btn._c))


class NoteEdit(QtWidgets.QPlainTextEdit):
    """Saves when focus leaves (not on every key, so the card is not rebuilt while typing)."""

    def __init__(self, value, emit):
        super().__init__(value or "")
        self._emit, self._start = emit, value or ""
        self.setObjectName("SMNote")
        self.setStyleSheet(TABLE_CSS)
        self.setPlaceholderText("Notes for this setup: feedback, what to check…")
        self.setFixedHeight(96)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if self.toPlainText() != self._start:
            self._start = self.toPlainText()
            self._emit()

    def value(self):
        return self.toPlainText()


class TodoList(QtWidgets.QWidget):
    def __init__(self, value, emit):
        super().__init__()
        self._emit = emit
        self.items = [dict(text=str(i.get("text", "")), done=bool(i.get("done")))
                      for i in (value or []) if isinstance(i, dict)]
        self.lay = QtWidgets.QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(2)
        for i, it in enumerate(self.items):
            row = QtWidgets.QHBoxLayout()
            cb = QtWidgets.QCheckBox(it["text"])
            cb.setChecked(it["done"])
            if it["done"]:
                f = cb.font()
                f.setStrikeOut(True)
                cb.setFont(f)
            cb.toggled.connect(lambda on, i=i: self._set(i, on))
            rm = QtWidgets.QToolButton()
            rm.setObjectName("SMPlain")
            rm.setText("×")
            rm.setToolTip("Remove")
            rm.clicked.connect(lambda _=False, i=i: self._remove(i))
            row.addWidget(cb, 1)
            row.addWidget(rm)
            self.lay.addLayout(row)
        self.new = QtWidgets.QLineEdit()
        self.new.setPlaceholderText("Add a to-do and press Enter")
        self.new.returnPressed.connect(self._add)
        self.lay.addWidget(self.new)

    def _set(self, i, on):
        self.items[i]["done"] = on
        self._emit()

    def _remove(self, i):
        del self.items[i]
        self._emit()

    def _add(self):
        t = self.new.text().strip()
        if t:
            self.items.append({"text": t, "done": False})
            self.new.clear()
            self._emit()

    def value(self):
        return [dict(i) for i in self.items]


register_kind("table", lambda prop, value, emit, ctx: TableWidget(prop, value, emit, ctx),
              always_editable=True, wide=True)
register_kind("note", lambda prop, value, emit, ctx: NoteEdit(value, emit), always_editable=True, wide=True)
register_kind("todo", lambda prop, value, emit, ctx: TodoList(value, emit), always_editable=True, wide=True)
