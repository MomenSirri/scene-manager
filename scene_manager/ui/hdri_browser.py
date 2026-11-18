"""HDRI browser: favourite folders on the left, thumbnail grid on the right, search on top.

pick_hdri(parent, current) -> chosen path or "" (double-click or Use). Thumbnails load lazily,
a few per timer tick, so big libraries do not freeze 3ds Max.
"""
import os

from PySide6 import QtCore, QtGui, QtWidgets

from ..env import hdri
from . import theme

PATH_ROLE = QtCore.Qt.UserRole + 1
ALL = "All favourites"
RECENT = "Recent"


class HdriBrowser(QtWidgets.QDialog):
    def __init__(self, parent=None, current=""):
        super().__init__(parent)
        self.setWindowTitle("HDRI library")
        self.setObjectName("SMPanel")
        self.resize(900, 560)
        self.chosen = ""
        self._pending = []

        root = QtWidgets.QVBoxLayout(self)
        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search HDRIs")
        self.search.textChanged.connect(lambda *_: self._timer_search.start(250))
        top.addWidget(self.search, 1)
        self.size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.size_slider.setRange(96, 320)
        self.size_slider.setValue(192)
        self.size_slider.setFixedWidth(120)
        self.size_slider.setToolTip("Thumbnail size")
        self.size_slider.valueChanged.connect(self._resize_icons)
        top.addWidget(self.size_slider)
        root.addLayout(top)

        split = QtWidgets.QSplitter()
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.folders = QtWidgets.QListWidget()
        self.folders.setObjectName("SMTree")
        self.folders.currentItemChanged.connect(lambda *_: self.refresh_grid())
        ll.addWidget(self.folders, 1)
        fb = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("Add folder")
        add.setObjectName("SMButton")
        add.clicked.connect(self._add_folder)
        rem = QtWidgets.QPushButton("Remove")
        rem.setObjectName("SMButton")
        rem.clicked.connect(self._remove_folder)
        fb.addWidget(add)
        fb.addWidget(rem)
        ll.addLayout(fb)
        split.addWidget(left)

        self.grid = QtWidgets.QListWidget()
        self.grid.setObjectName("SMGrid")
        self.grid.setViewMode(QtWidgets.QListView.IconMode)
        self.grid.setResizeMode(QtWidgets.QListView.Adjust)
        self.grid.setMovement(QtWidgets.QListView.Static)
        self.grid.setUniformItemSizes(True)
        self.grid.setSpacing(8)
        self.grid.setWordWrap(True)
        self.grid.itemDoubleClicked.connect(lambda it: self._use(it))
        split.addWidget(self.grid)
        split.setSizes([220, 680])
        root.addWidget(split, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("SMCardOrigin")
        bottom.addWidget(self.status, 1)
        other = QtWidgets.QPushButton("Open file…")
        other.setObjectName("SMButton")
        other.clicked.connect(self._open_file)
        bottom.addWidget(other)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("SMButton")
        cancel.clicked.connect(self.reject)
        use = QtWidgets.QPushButton("Use")
        use.setObjectName("SMPrimary")
        use.clicked.connect(lambda: self._use(self.grid.currentItem()))
        bottom.addWidget(cancel)
        bottom.addWidget(use)
        root.addLayout(bottom)

        self._timer_search = QtCore.QTimer(self, singleShot=True, timeout=self.refresh_grid)
        self._timer_thumbs = QtCore.QTimer(self, interval=30, timeout=self._load_some_thumbs)
        try:
            self.setStyleSheet(theme.stylesheet(glass=False))
        except Exception:
            pass
        self._placeholder = self._make_placeholder()
        self._current = current
        self.refresh_folders(select=os.path.dirname(current) if current else None)

    # ---- folders ----
    def refresh_folders(self, select=None):
        self.folders.blockSignals(True)
        self.folders.clear()
        for label in (ALL, RECENT):
            it = QtWidgets.QListWidgetItem(label)
            it.setData(PATH_ROLE, label)
            self.folders.addItem(it)
        row = 0
        for i, f in enumerate(hdri.load()["favourites"]):
            it = QtWidgets.QListWidgetItem(os.path.basename(f) or f)
            it.setToolTip(f)
            it.setData(PATH_ROLE, f)
            self.folders.addItem(it)
            if select and os.path.normcase(select).startswith(os.path.normcase(f)):
                row = i + 2
        self.folders.setCurrentRow(row)
        self.folders.blockSignals(False)
        self.refresh_grid()

    def _add_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "HDRI folder")
        if d:
            hdri.add_favourite(d)
            self.refresh_folders(select=d)

    def _remove_folder(self):
        it = self.folders.currentItem()
        if it and it.data(PATH_ROLE) not in (ALL, RECENT):
            hdri.remove_favourite(it.data(PATH_ROLE))
            self.refresh_folders()

    # ---- grid ----
    def _files(self):
        it = self.folders.currentItem()
        key = it.data(PATH_ROLE) if it else ALL
        s = self.search.text().strip()
        if key == ALL:
            return [e["path"] for e in hdri.library(search=s)]
        if key == RECENT:
            return [p for p in hdri.load()["recent"] if os.path.isfile(p) and s.lower() in os.path.basename(p).lower()]
        return hdri.scan(key, search=s)

    def refresh_grid(self):
        self.grid.clear()
        self._pending = []
        files = self._files()
        self._resize_icons(self.size_slider.value())
        for p in files:
            it = QtWidgets.QListWidgetItem(self._placeholder, os.path.splitext(os.path.basename(p))[0])
            it.setData(PATH_ROLE, p)
            it.setToolTip(p)
            self.grid.addItem(it)
            if os.path.normcase(p) == os.path.normcase(self._current or ""):
                self.grid.setCurrentItem(it)
            self._pending.append(it)
        self.status.setText("%d HDRIs" % len(files) if files else
                            "No HDRIs here. Add a favourite folder on the left.")
        self._timer_thumbs.start()

    def _load_some_thumbs(self):
        for _ in range(2):
            if not self._pending:
                self._timer_thumbs.stop()
                return
            it = self._pending.pop(0)
            try:
                tp = hdri.thumbnail(it.data(PATH_ROLE))
            except RuntimeError:   # item deleted by a refresh
                continue
            if tp:
                pm = QtGui.QPixmap(tp)
                if not pm.isNull():
                    it.setIcon(QtGui.QIcon(pm))

    def _resize_icons(self, w):
        h = int(w / 2)
        self.grid.setIconSize(QtCore.QSize(w, h))
        self.grid.setGridSize(QtCore.QSize(w + 16, h + 40))

    def _make_placeholder(self):
        pm = QtGui.QPixmap(256, 128)
        pm.fill(QtGui.QColor(theme.SURFACE))
        p = QtGui.QPainter(pm)
        p.setPen(QtGui.QColor(theme.LABEL_3))
        p.drawText(pm.rect(), QtCore.Qt.AlignCenter, "HDRI")
        p.end()
        return QtGui.QIcon(pm)

    # ---- choose ----
    def _use(self, it):
        if it is None:
            return
        self.chosen = it.data(PATH_ROLE)
        hdri.add_recent(self.chosen)
        self.accept()

    def _open_file(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "HDRI", self._current or "",
                                                      "HDRI (*.hdr *.exr *.hdri);;All files (*.*)")
        if fn:
            self.chosen = fn
            hdri.add_recent(fn)
            self.accept()


def pick_hdri(parent=None, current=""):
    dlg = HdriBrowser(parent, current)
    return dlg.chosen if dlg.exec() else ""
