"""Extra card property kinds for the lighting & environment modules (M3).

light      light picker; prop.options ["dome"] lists dome lights first
hdri       HDRI file field + button that opens the HDRI browser (thumbnails, favourite folders)
image      image file field + open-file button
checklist  {name: bool} list, e.g. atmospheric effects (names from the stored value and the scene)

Registered through ui/prop_kinds.py, so cards.py is not edited.
"""
from PySide6 import QtCore, QtWidgets
from pymxs import runtime as rt

from ..core import nodes
from ..env import renderers
from .prop_kinds import register_kind
from .widgets import Switch


def _light(prop, value, emit, ctx):
    w = QtWidgets.QComboBox()
    pool = renderers.list_domes() if "dome" in (prop.options or []) else []
    pool += [l for l in nodes.list_lights() if l not in pool]
    names = [str(n.name) for n in pool]
    cur = value.get("name") if isinstance(value, dict) else None
    if cur and cur not in names:
        names.insert(0, cur)
    w.addItems(["(none)"] + names)
    w.setCurrentText(cur or "(none)")
    w.activated.connect(lambda *_: emit())

    def get():
        name = w.currentText()
        if name == "(none)":
            return None
        n = rt.getNodeByName(name)
        return nodes.ref(n) if n is not None else {"name": name, "handle": None}
    w.value = get
    return w


class _FileField(QtWidgets.QWidget):
    def __init__(self, value, emit, browse, tip=""):
        super().__init__()
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.edit = QtWidgets.QLineEdit("" if value is None else str(value))
        self.edit.setToolTip(tip or str(value or ""))
        self.edit.editingFinished.connect(emit)
        b = QtWidgets.QToolButton()
        b.setObjectName("SMPlain")
        b.setText("…")
        b.setToolTip("Browse")
        b.clicked.connect(lambda: self._pick(browse, emit))
        lay.addWidget(self.edit, 1)
        lay.addWidget(b)

    def _pick(self, browse, emit):
        path = browse(self, self.edit.text())
        if path:
            self.edit.setText(path)
            self.edit.setToolTip(path)
            emit()

    def value(self):
        return self.edit.text().strip()


def _hdri(prop, value, emit, ctx):
    def browse(parent, current):
        from .hdri_browser import pick_hdri
        return pick_hdri(parent, current)
    return _FileField(value, emit, browse, prop.tip)


def _image(prop, value, emit, ctx):
    def browse(parent, current):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(parent, "Image", current,
                                                      "Images (*.jpg *.jpeg *.png *.tif *.tiff *.exr *.hdr *.bmp)")
        return fn
    return _FileField(value, emit, browse, prop.tip)


class _Checklist(QtWidgets.QWidget):
    def __init__(self, value, emit, scene):
        super().__init__()
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(4)
        value = value if isinstance(value, dict) else {}
        scene = scene if isinstance(scene, dict) else {}
        names = list(scene.keys()) + [n for n in value if n not in scene]
        self.boxes = {}
        if not names:
            empty = QtWidgets.QLabel("(none in the scene)")
            empty.setObjectName("SMCardOrigin")
            lay.addWidget(empty)
        for n in names:
            row = QtWidgets.QHBoxLayout()
            sw = Switch()
            sw.setChecked(bool(value.get(n, scene.get(n))))
            sw.toggled.connect(lambda *_: emit())
            lab = QtWidgets.QLabel(n + ("" if n in scene else "  (missing)"))
            row.addWidget(sw)
            row.addWidget(lab, 1)
            lay.addLayout(row)
            self.boxes[n] = sw

    def value(self):
        return {n: sw.isChecked() for n, sw in self.boxes.items()}


def _checklist(prop, value, emit, ctx):
    scene = (ctx or {}).get("scene")
    return _Checklist(value, emit, scene)


register_kind("light", _light)
register_kind("hdri", _hdri)
register_kind("image", _image)
register_kind("checklist", _checklist, wide=True)
