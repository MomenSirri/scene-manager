"""Card widgets for the M4 render modules (loaded by ui/prop_kinds.py).

Kinds: toggles (name -> on), rdiff (name -> value, edited in a table dialog), blob (large text, e.g.
V-Ray VFB layers), rps (.rps file), lmgroups (LightMix groups), cprops (custom property rows).
Each factory(prop, value, emit, ctx) returns a QWidget with .value().
"""
import json

from PySide6 import QtCore, QtWidgets

from . import theme
from .prop_kinds import register_kind
from .widgets import Switch


def _small_button(text, tip=""):
    b = QtWidgets.QToolButton()
    b.setObjectName("SMPlain")
    b.setText(text)
    b.setToolTip(tip)
    return b


def _muted(text):
    lab = QtWidgets.QLabel(text)
    lab.setObjectName("SMMuted")
    return lab


def _to_text(v):
    return json.dumps(v) if not isinstance(v, str) else v


def _from_text(t):
    t = t.strip()
    try:
        return json.loads(t)
    except ValueError:
        return t


# ---- toggles ----------------------------------------------------------------
class TogglesWidget(QtWidgets.QWidget):
    """One switch per name. Names = stored values plus what the scene has now."""

    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self._emit = emit
        value = dict(value or {})
        scene = (ctx or {}).get("scene", {}).get(prop.key) or {}
        names = list(value.keys()) + [n for n in scene if n not in value]
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._switches = {}
        if not names:
            lay.addWidget(_muted("No render elements in the scene"))
        for n in names:
            row = QtWidgets.QHBoxLayout()
            sw = Switch(on_color=theme.TINTS.get("render", theme.ACCENT))
            sw.setChecked(bool(value.get(n, scene.get(n))))
            sw.toggled.connect(lambda *_: self._emit())
            lab = QtWidgets.QLabel(n)
            if n not in scene:
                lab.setToolTip("Not in the scene right now")
                lab.setObjectName("SMMuted")
            row.addWidget(sw)
            row.addWidget(lab, 1)
            lay.addLayout(row)
            self._switches[n] = sw

    def value(self):
        return {n: sw.isChecked() for n, sw in self._switches.items()}


# ---- dict edited in a table --------------------------------------------------
class TableDialog(QtWidgets.QDialog):
    def __init__(self, title, rows, headers, parent=None, editable_keys=True):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 420)
        lay = QtWidgets.QVBoxLayout(self)
        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText("Filter")
        self.filter.textChanged.connect(self._filter)
        lay.addWidget(self.filter)
        self.table = QtWidgets.QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        for r in rows:
            self._add(r, editable_keys)
        lay.addWidget(self.table, 1)
        btns = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("Add row")
        add.clicked.connect(lambda: self._add([""] * len(headers), True))
        rem = QtWidgets.QPushButton("Remove selected")
        rem.clicked.connect(self._remove)
        btns.addWidget(add)
        btns.addWidget(rem)
        btns.addStretch(1)
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        btns.addWidget(box)
        lay.addLayout(btns)

    def _add(self, cells, editable_key):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, text in enumerate(cells):
            it = QtWidgets.QTableWidgetItem(str(text))
            if c == 0 and not editable_key:
                it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
            self.table.setItem(r, c, it)

    def _remove(self):
        for r in sorted({i.row() for i in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(r)

    def _filter(self, text):
        t = text.lower()
        for r in range(self.table.rowCount()):
            k = self.table.item(r, 0)
            self.table.setRowHidden(r, bool(t) and t not in (k.text().lower() if k else ""))

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            out.append([self.table.item(r, c).text() if self.table.item(r, c) else ""
                        for c in range(self.table.columnCount())])
        return out


class DictWidget(QtWidgets.QWidget):
    """'12 values  Edit…'; the dialog edits name -> JSON value."""

    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self.prop, self._emit = prop, emit
        self._value = dict(value or {})
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = _muted("")
        lay.addWidget(self.label, 1)
        b = _small_button("Edit…", "Show and edit the stored values")
        b.clicked.connect(self._edit)
        lay.addWidget(b)
        self._update()

    def _update(self):
        n = len(self._value)
        self.label.setText("%d value%s" % (n, "" if n == 1 else "s") if n else "none")
        self.label.setToolTip("\n".join("%s = %s" % (k, _to_text(v)) for k, v in list(self._value.items())[:40]))

    def _edit(self):
        d = TableDialog(self.prop.label, [[k, _to_text(v)] for k, v in sorted(self._value.items())],
                        ["Name", "Value (JSON)"], self)
        if d.exec():
            self._value = {k.strip(): _from_text(v) for k, v in d.rows() if k.strip()}
            self._update()
            self._emit()

    def value(self):
        return dict(self._value)


# ---- blob ---------------------------------------------------------------------
class BlobWidget(QtWidgets.QWidget):
    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self._emit = emit
        self._value = value or ""
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.label = _muted("")
        lay.addWidget(self.label, 1)
        b = _small_button("Clear", "Forget the stored data")
        b.clicked.connect(self._clear)
        lay.addWidget(b)
        self._update()

    def _update(self):
        self.label.setText("stored, %.1f KB" % (len(self._value) / 1024.0) if self._value else "empty (Fetch from scene)")

    def _clear(self):
        self._value = ""
        self._update()
        self._emit()

    def value(self):
        return self._value


# ---- .rps file -------------------------------------------------------------------
class RpsWidget(QtWidgets.QWidget):
    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self._emit = emit
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QtWidgets.QLineEdit(value or "")
        self.edit.editingFinished.connect(emit)
        lay.addWidget(self.edit, 1)
        b = _small_button("…", "Pick a render preset")
        b.clicked.connect(self._browse)
        lay.addWidget(b)

    def _browse(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Render preset", self.edit.text(), "Render presets (*.rps)")
        if fn:
            self.edit.setText(fn)
            self._emit()

    def value(self):
        return self.edit.text().strip()


# ---- LightMix groups ---------------------------------------------------------------
class LightMixWidget(QtWidgets.QWidget):
    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self._emit = emit
        value = dict(value or {})
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(4)
        self._rows = {}
        if not value:
            grid.addWidget(_muted("Fetch from scene to list the light groups"), 0, 0)
        for r, (name, row) in enumerate(sorted(value.items())):
            row = row or {}
            sw = Switch(on_color=theme.TINTS.get("light", theme.ACCENT))
            sw.setChecked(row.get("on", True) is not False)
            sw.toggled.connect(lambda *_: self._emit())
            mult = QtWidgets.QDoubleSpinBox()
            mult.setRange(0.0, 1000.0)
            mult.setDecimals(3)
            mult.setSingleStep(0.1)
            mult.setPrefix("× ")
            mult.setValue(float(row.get("mult", 1.0)))
            mult.editingFinished.connect(self._emit)
            grid.addWidget(sw, r, 0)
            grid.addWidget(QtWidgets.QLabel(name), r, 1)
            grid.addWidget(mult, r, 2)
            self._rows[name] = (sw, mult)
        grid.setColumnStretch(1, 1)

    def value(self):
        return {n: {"on": sw.isChecked(), "mult": round(m.value(), 3)} for n, (sw, m) in self._rows.items()}


# ---- custom property rows --------------------------------------------------------------
class CustomPropsWidget(QtWidgets.QWidget):
    def __init__(self, prop, value, emit, ctx):
        super().__init__()
        self._emit = emit
        self._value = {k: dict(v) for k, v in (value or {}).items() if isinstance(v, dict)}
        self.lay = QtWidgets.QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(4)
        self._build()

    def _build(self):
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                QtWidgets.QWidget().setLayout(it.layout())
        self._edits = {}
        for key in sorted(self._value):
            row = QtWidgets.QHBoxLayout()
            lab = QtWidgets.QLabel(key)
            lab.setToolTip(key)
            e = QtWidgets.QLineEdit(_to_text(self._value[key].get("value")))
            e.setToolTip("Value as JSON: 0.5, true, \"text\", {\"color\": [255, 0, 0, 255]}")
            e.editingFinished.connect(lambda k=key: self._changed(k))
            rm = _small_button("✕", "Remove this property")
            rm.clicked.connect(lambda _=False, k=key: self._remove(k))
            row.addWidget(lab, 1)
            row.addWidget(e, 1)
            row.addWidget(rm)
            self.lay.addLayout(row)
            self._edits[key] = e
        add = _small_button("+ Property", "Add a property of a node (selected node by default), the renderer or the environment")
        add.clicked.connect(self._add)
        self.lay.addWidget(add, 0, QtCore.Qt.AlignLeft)

    def _changed(self, key):
        self._value[key]["value"] = _from_text(self._edits[key].text())
        self._emit()

    def _remove(self, key):
        self._value.pop(key, None)
        self._build()
        self._emit()

    def _add(self):
        from pymxs import runtime as rt
        from ..modules import custom_props
        sel = rt.selection
        default = str(sel[0].name) if len(sel) else ""
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add custom property")
        form = QtWidgets.QFormLayout(d)
        target = QtWidgets.QComboBox()
        target.addItems(["node", "renderer", "environment", "maxscript"])
        node = QtWidgets.QLineEdit(default)
        path = QtWidgets.QLineEdit()
        path.setPlaceholderText("optional, e.g. material   or   modifiers.1")
        prop = QtWidgets.QLineEdit()
        prop.setPlaceholderText("e.g. multiplier")
        form.addRow("Target", target)
        form.addRow("Node", node)
        form.addRow("Path / expression", path)
        form.addRow("Property", prop)
        box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        box.accepted.connect(d.accept)
        box.rejected.connect(d.reject)
        form.addRow(box)
        if not d.exec():
            return
        try:
            key, row = custom_props.make_row(target.currentText(), prop.text().strip(), path.text().strip(),
                                             node.text().strip())
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Custom property", str(e))
            return
        self._value[key] = row
        self._build()
        self._emit()

    def value(self):
        return {k: dict(v) for k, v in self._value.items()}


register_kind("toggles", TogglesWidget, wide=True)
register_kind("rdiff", DictWidget)
register_kind("blob", BlobWidget)
register_kind("rps", RpsWidget)
register_kind("lmgroups", LightMixWidget, wide=True)
register_kind("cprops", CustomPropsWidget, wide=True)
