"""Card board, as in Scene Manager 3: a canvas with a fixed grid of columns of fixed width.

Cards keep their place when the window is resized (a smaller window scrolls). Each card sits in a column
(card_prefs "col") and packs upward; the order inside the columns is config "card_order". Drag a card's header
to another spot: a teal dashed box shows where it lands. A card can be wider than one column.
"""
import math

from PySide6 import QtCore, QtGui, QtWidgets

from .. import config
from . import card_prefs
from .cards import ModuleCard


def saved_order():
    return list(config.load().get("card_order") or [])


def sort_modules(mods):
    order = saved_order()
    pos = {k: i for i, k in enumerate(order)}
    base = {m.key: i for i, m in enumerate(mods)}
    return sorted(mods, key=lambda m: (pos.get(m.key, len(order) + base[m.key])))


def save_order(keys):
    cfg = config.load()
    old = [k for k in (cfg.get("card_order") or []) if k not in keys]
    cfg["card_order"] = list(keys) + old  # keep keys of modules hidden by a group filter
    config.save(cfg)


class _DropBox(QtWidgets.QWidget):
    """Teal dashed box showing where the dragged card will land."""

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        pen = QtGui.QPen(QtGui.QColor("#2ad4c4"))
        pen.setWidthF(1.6)
        pen.setStyle(QtCore.Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(42, 212, 196, 28))
        p.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1), 12, 12)
        p.end()


class CardBoard(QtWidgets.QWidget):
    """The cards of one setup. `base_cols` columns are used for cards without a stored column; one empty
    column is always kept on the right to drop into. `on_reorder()` is called after a drop."""

    def __init__(self, cards, base_cols, gap, on_reorder, col_width=300, parent=None):
        super().__init__(parent)
        self.setObjectName("SMCards")
        self.setAcceptDrops(True)
        self.on_reorder = on_reorder
        self.cards = cards
        self.base_cols = max(1, base_cols)
        self.gap = gap
        self.colw = max(200, int(col_width))
        self.extra = []  # non-card widgets (e.g. an empty-board note) shown at the top
        for c in cards:
            c.setParent(self)
            c.installEventFilter(self)
        self.dropbox = _DropBox(self)
        self.dropbox.hide()
        self._relayout_timer = QtCore.QTimer(self, singleShot=True, interval=0, timeout=self.relayout)
        self.relayout()

    def add_note(self, widget):
        widget.setParent(self)
        self.extra.append(widget)
        widget.show()
        self.relayout()

    def set_cards(self, cards, note=None):
        """Replace the card list in place: cards that stay keep their widgets, the others are dropped."""
        keep = set(map(id, cards))
        for c in self.cards:
            if id(c) not in keep:
                c.removeEventFilter(self)
                c.hide()
                c.deleteLater()
        for c in cards:
            if c.parentWidget() is not self:
                c.setParent(self)
                c.installEventFilter(self)
        self.cards = list(cards)
        for w in self.extra:
            w.hide()
            w.deleteLater()
        self.extra = []
        if note is not None:
            self.add_note(note)
        else:
            self.relayout()

    # ---- grid ----
    def step(self):
        return self.colw + self.gap

    def span_of(self, card):
        return max(1, int(math.ceil((card.width_px(self.colw, self.gap) + self.gap) / float(self.step()) - 0.01)))

    def ncols(self):
        used = max([(c.col or 0) + self.span_of(c) for c in self.cards if c.col is not None] + [0])
        return max(self.base_cols, used) + 1

    def relayout(self):
        n = self.ncols()
        y0 = 0
        for w in self.extra:
            h = w.sizeHint().height()
            w.setGeometry(0, 0, self.step() * self.base_cols - self.gap, h)
            y0 += h + self.gap
        heights = [y0] * (n + 8)
        for c in self.cards:
            span = self.span_of(c)
            if c.col is None:  # first free spot among the default columns
                c.slot_col = min(range(self.base_cols), key=lambda i: (max(heights[i:i + span]), i))
            else:
                c.slot_col = c.col
            col = c.slot_col
            y = max(heights[col:col + span])
            h = c.layout_height()
            c.setGeometry(col * self.step(), y, c.width_px(self.colw, self.gap), h)
            c.show()
            for i in range(col, col + span):
                heights[i] = y + h + self.gap
        # The spare drop column on the right is not part of the minimum width: it must not cause a scroll bar.
        self.setMinimumSize(max(1, (self.ncols() - 1) * self.step() - self.gap), max(heights))

    def eventFilter(self, obj, e):
        if e.type() == QtCore.QEvent.LayoutRequest and obj in self.cards:
            self._relayout_timer.start()  # a card folded or changed its rows
        return False

    def card_resizing(self, card, width, height):
        """Live resize from a card's corner: free width and height."""
        card.set_size(max(int(self.colw * 0.6), int(width)), max(card.min_height(), int(height)))
        self.relayout()

    def sizeHint(self):
        return self.minimumSize()

    # ---- drop target ----
    def _drop_target(self, pos, dragged=None):
        """(column, key to insert before or None for the end of the column, placeholder rect)."""
        col = max(0, min(self.ncols() - 1, int(pos.x() // self.step())))
        in_col = sorted([c for c in self.cards if c is not dragged and c.slot_col <= col < c.slot_col + self.span_of(c)],
                        key=lambda c: c.y())
        w = dragged.width_px(self.colw, self.gap) if dragged else self.colw
        h = dragged.layout_height() if dragged else 120
        before = None
        y = (self.extra[-1].geometry().bottom() + self.gap) if self.extra else 0
        for c in in_col:
            if pos.y() < c.geometry().center().y():
                before = c
                break
            y = c.geometry().bottom() + self.gap + 1
        return col, before, QtCore.QRect(col * self.step(), y, w, min(h, 400))

    def _dragged(self, e):
        key = bytes(e.mimeData().data(ModuleCard.MIME)).decode()
        return next((c for c in self.cards if c.m.key == key), None)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(ModuleCard.MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasFormat(ModuleCard.MIME):
            return
        _col, _before, rect = self._drop_target(e.position().toPoint(), self._dragged(e))
        self.dropbox.setGeometry(rect)
        self.dropbox.show()
        self.dropbox.raise_()
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.dropbox.hide()

    def dropEvent(self, e):
        self.dropbox.hide()
        if not e.mimeData().hasFormat(ModuleCard.MIME):
            return
        card = self._dragged(e)
        if card is None:
            return
        col, before, _ = self._drop_target(e.position().toPoint(), card)
        keys = [c.m.key for c in self.cards if c is not card]
        if before is not None:
            keys.insert(keys.index(before.m.key), card.m.key)
        else:  # end of that column: right after the last card that sits in it
            in_col = [keys.index(c.m.key) for c in self.cards
                      if c is not card and c.slot_col <= col < c.slot_col + self.span_of(c)]
            keys.insert(max(in_col) + 1 if in_col else len(keys), card.m.key)
        e.acceptProposedAction()
        # Pin every card to the column it shows in now, so the drop moves only the dragged card.
        for c in self.cards:
            c.col = col if c is card else c.slot_col
            card_prefs.update(c.m.key, col=c.col)
        save_order(keys)
        self.cards.sort(key=lambda c: keys.index(c.m.key))  # move in place: no card is rebuilt
        self.relayout()
        if self.on_reorder:
            QtCore.QTimer.singleShot(0, self.on_reorder)
