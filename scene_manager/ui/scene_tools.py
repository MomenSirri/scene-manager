"""M2 panel tools: scene baseline and Repair missing nodes (added to the setup context / ••• menus)."""
from PySide6 import QtCore, QtWidgets
from pymxs import runtime as rt

from ..core import repair


def fill_menu(panel, menu):
    mgr = panel.mgr
    menu.addSeparator()
    sub = menu.addMenu("Scene baseline" + ("  (on)" if mgr.baseline else ""))
    sub.setToolTipsVisible(True)
    a = sub.addAction("Capture baseline from the scene", lambda: _capture(panel))
    a.setToolTip("Every setup starts from this scene state, so activating a setup gives the same result "
                 "whichever setup was active before. Capture it with the scene in its neutral state.")
    b = sub.addAction("Restore scene to baseline", lambda: _guard(panel, mgr.restore_baseline))
    c = sub.addAction("Clear baseline", lambda: _guard(panel, mgr.clear_baseline))
    b.setEnabled(bool(mgr.baseline))
    c.setEnabled(bool(mgr.baseline))
    menu.addAction("Repair missing nodes…", lambda: RepairDialog(panel).exec())


def _guard(panel, fn):
    try:
        r = fn()
        if isinstance(r, list) and r and all(isinstance(x, str) for x in r) and r is not None:
            panel.flash("; ".join(r))
    except Exception as e:
        QtWidgets.QMessageBox.warning(panel, "Scene Manager", str(e))


def _capture(panel):
    mgr = panel.mgr
    if mgr.baseline and QtWidgets.QMessageBox.question(
            panel, "Scene baseline", "Replace the stored baseline with the current scene?") != QtWidgets.QMessageBox.Yes:
        return
    try:
        keys = mgr.capture_baseline()
        panel.flash("Baseline captured: %s" % ", ".join(keys))
    except Exception as e:
        QtWidgets.QMessageBox.warning(panel, "Scene Manager", str(e))


class RepairDialog(QtWidgets.QDialog):
    """Lists node references that do not resolve and lets the user pick a replacement for each."""

    def __init__(self, panel):
        super().__init__(panel)
        self.panel, self.mgr = panel, panel.mgr
        self.setWindowTitle("Repair missing nodes")
        self.resize(560, 320)
        lay = QtWidgets.QVBoxLayout(self)
        self.missing = repair.find_missing(self.mgr)
        repair.NOTICES.clear()
        if not self.missing:
            lay.addWidget(QtWidgets.QLabel("Every camera, light and object the setups use exists. Nothing to repair."))
        else:
            lay.addWidget(QtWidgets.QLabel("These nodes are used by setups but no longer exist. "
                                           "Pick a replacement for each, then Repair."))
            self.table = QtWidgets.QTableWidget(len(self.missing), 3)
            self.table.setHorizontalHeaderLabels(["Missing", "Used by", "Replace with"])
            self.table.verticalHeader().hide()
            self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            names = sorted(str(n.name) for n in rt.objects)
            self.combos = []
            for r, m in enumerate(self.missing):
                self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(m["name"])))
                used = QtWidgets.QTableWidgetItem(", ".join(m["used_by"]))
                used.setToolTip("\n".join(m["used_by"]))
                self.table.setItem(r, 1, used)
                cb = QtWidgets.QComboBox()
                cb.setEditable(True)
                cb.addItems(["(leave)"] + names)
                comp = QtWidgets.QCompleter(names, cb)
                comp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
                comp.setFilterMode(QtCore.Qt.MatchContains)
                cb.setCompleter(comp)
                self.table.setCellWidget(r, 2, cb)
                self.combos.append(cb)
            lay.addWidget(self.table, 1)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        if self.missing:
            go = btns.addButton("Repair", QtWidgets.QDialogButtonBox.AcceptRole)
            go.clicked.connect(self._repair)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _repair(self):
        done = 0
        try:
            for m, cb in zip(self.missing, self.combos):
                t = cb.currentText().strip()
                if t and t != "(leave)":
                    done += repair.repair(self.mgr, m["name"], t)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Scene Manager", str(e))
            return
        self.panel.flash("Repaired %d reference(s)." % done)
        self.accept()
