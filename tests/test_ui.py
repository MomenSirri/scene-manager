"""UI test without 3ds Max: python -m tests.test_ui (needs PySide6; runs offscreen).

Checks the things that make the panel feel solid: an edit must not rebuild cards or the setups tree,
switching setups reuses the cards, and no stray top-level window may ever appear."""
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from tests import ui_harness

FAILS = []


def check(ok, text):
    print(("PASS " if ok else "FAIL ") + text)
    if not ok:
        FAILS.append(text)


def main():
    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("skip UI test (no PySide6)")
        return 0
    from PySide6 import QtCore, QtWidgets
    app, win, mgr = ui_harness.build()
    panel = win.panel

    class Spy(QtCore.QObject):
        windows = []

        def eventFilter(self, obj, ev):
            if ev.type() == QtCore.QEvent.Show and isinstance(obj, QtWidgets.QWidget) and obj.isWindow() \
                    and obj is not win and not isinstance(obj, QtWidgets.QMenu):
                self.windows.append(type(obj).__name__ + ":" + obj.objectName())
            return False

    spy = Spy()
    app.installEventFilter(spy)

    def pump():
        for _ in range(4):
            app.processEvents()

    day, dusk = mgr.get("Exterior / Day"), mgr.get("Exterior / Dusk")
    check(mgr.get("Kitchen")["parent"] == mgr.get("Interior")["id"], "manager: parent given by name is stored as id")
    panel.select(day["id"])
    pump()
    board = panel._board
    cards = {c.m.key: c for c in board.cards}
    rows = dict(panel.tree._items)
    check(len(cards) >= 5, "cards built (%d)" % len(cards))

    # 1. edit a value on a card: same board, same cards, same field widgets, same tree rows
    card = cards["output"]
    field, _tick = card.rows["width"]
    field.w.setValue(2560)
    field.changed.emit()
    pump()
    check(panel._board is board and {c.m.key: c for c in board.cards} == cards, "edit: no card was rebuilt")
    check(card.rows["width"][0] is field, "edit: the edited field is the same widget (focus is kept)")
    check(panel.tree._items == rows, "edit: tree rows are reused")
    check(mgr.effective(day)["output"]["width"] == 2560, "edit: value stored")
    col = 1 + [m.key for m in panel.tree.cols].index("output")
    check("2560" in rows[day["id"]].text(col), "edit: tree column shows the new size (%r)" % rows[day["id"]].text(col))

    # 2. switch to another setup: the same cards show other values
    panel.select(dusk["id"])
    pump()
    check(panel._board is board and all(cards.get(c.m.key) is c for c in board.cards), "switch setup: cards are reused")
    check(cards["output"].rows["width"][0].get() == mgr.effective(dusk)["output"]["width"],
          "switch setup: field shows the other setup's value")
    check(cards["output"].item is dusk, "switch setup: card points at the new setup")

    # 3. untick an override: row greys out in place, value is cleared
    panel.select(day["id"])
    pump()
    card.rows["width"][1].setChecked(False)
    pump()
    check("width" not in day["modules"]["output"]["values"], "override off: value removed from the setup")
    check(not card.rows["width"][0].isEnabled() and card.rows["width"][0] is field, "override off: same widget, disabled")

    # 4. remove and add a module: only that card goes / comes
    mgr.remove_module(day["id"], "camera")
    pump()
    check("camera" not in [c.m.key for c in panel._board.cards] and panel._board is board, "remove module: its card is dropped")
    check(all(cards[c.m.key] is c for c in board.cards), "remove module: the other cards stay")
    mgr.capture(day["id"], keys=["camera"])
    pump()
    check("camera" in [c.m.key for c in board.cards], "add module: one card is added")

    # 5. new setup without a dialog; rename happens in the list
    n = len(mgr.setups())
    panel.on_new_setup()
    pump()
    check(len(mgr.setups()) == n + 1, "new setup: created without a dialog")
    new = mgr.get(panel.selected)
    check(new is not None and panel.tree.currentItem() is panel.tree._items[new["id"]], "new setup: selected in the list")
    check(panel.tree.state() == QtWidgets.QAbstractItemView.EditingState, "new setup: name is being edited in place")
    panel.tree.setCurrentItem(None)

    # 6. drag-reorder path: order changes in place
    keys = [c.m.key for c in board.cards]
    from scene_manager.ui import board as board_mod
    board_mod.save_order(list(reversed(keys)))
    board.cards.sort(key=lambda c: list(reversed(keys)).index(c.m.key))
    board.relayout()
    pump()
    check(panel._board is board, "reorder: board kept")

    # 7. speed: a refresh with nothing changed
    t0 = time.perf_counter()
    for _ in range(20):
        panel.refresh()
    ms = (time.perf_counter() - t0) * 1000 / 20
    print("refresh: %.1f ms" % ms)

    # 8. window: grips, no stray windows
    check(len(win._grips) == 8 and all(g.parentWidget() is win for g in win._grips), "window: 8 resize grips")
    win.resize(900, 600)
    pump()
    check(win._grips[1].geometry().right() == win.width() - 1, "window: grips follow the window size")
    check(not spy.windows, "no stray windows opened %s" % spy.windows)

    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / "preview.exr"
        output.touch()
        mgr.set_values(day["id"], "output", {"save_file": True, "path": str(output)})
        mgr.set_values(dusk["id"], "output", {"save_file": True, "path": str(output)})
        mgr.set_values(dusk["id"], "camera", {"camera": {"name": "Missing camera", "handle": None}})
        night = mgr.get("Exterior / Night")
        mgr.set_values(night["id"], "output", {"save_file": True, "path": "{unfinished"})
        panel.checked = {mgr.get("Exterior")["id"], day["id"]}
        active = mgr.data["active"]
        panel.pages.setCurrentIndex(1)
        panel.refresh_queue()
        rows = {panel.queue.topLevelItem(i).text(0): panel.queue.topLevelItem(i)
                for i in range(panel.queue.topLevelItemCount())}
        checks = rows["Exterior / Day"].toolTip(4)
        check("Shared output path" in checks and "Output file already exists" in checks
              and rows["Exterior / Day"].text(5) == str(output), "queue: reports a shared existing file")
        check("Stored camera unavailable" in rows["Exterior / Dusk"].toolTip(4),
              "queue: reports a missing stored camera")
        check("Invalid output template" in rows["Exterior / Night"].toolTip(4),
              "queue: a malformed output template leaves the queue usable")
        check(panel.queue.topLevelItemCount() == len(rows),
              "queue: expanding a folder and a checked child does not duplicate the child")
        check(mgr.data["active"] == active, "queue: checking leaves the active setup in place")
        from scene_manager.render import batch
        with patch.object(QtWidgets.QMessageBox, "exec", return_value=QtWidgets.QMessageBox.Cancel) as dialog, \
                patch.object(batch, "render_setups") as render:
            panel.on_render([day["id"], dusk["id"]])
            check(dialog.called and not render.called, "queue: cancelling preflight does not start a render")

    print("\n%d failed" % len(FAILS) if FAILS else "\nall passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
