"""Card board: a canvas with a dot grid; every card sits on the dots.

The board paints the dots (one every GRID px) and they scroll with the cards. A card's left edge, width and
height are whole numbers of dots. Each card keeps its left edge (card_prefs "gx", in dots) and packs upward
under the cards above it; the order is config "card_order". A new card is as tall as its module's rows need
and as wide as the Layout "Card width", both rounded to the dots.

Dragging a header or the resize corner shows a glowing box on the exact dots where the card will land.
"""
from PySide6 import QtCore, QtGui, QtWidgets

from .. import config
from . import card_prefs
from .cards import ModuleCard

GRID = 18          # px between dots
GLOW = "#2ad4c4"   # teal of the target box
MIN_W = 10         # narrowest card, in dots
PAD = 8            # room around the target box for its glow


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


def snap(px, up=False):
    """Pixels to whole dots."""
    return int(-(-px // GRID)) if up else int(round(px / float(GRID)))


def _dot_tile(color, alpha, radius, dpr):
    pm = QtGui.QPixmap(int(GRID * dpr), int(GRID * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    c = QtGui.QColor(color)
    c.setAlpha(alpha)
    p.setBrush(c)
    # the dot is split over the four corners of the tile, so tiling puts dots exactly on multiples of GRID
    for x in (0, GRID):
        for y in (0, GRID):
            p.drawEllipse(QtCore.QPointF(x, y), radius, radius)
    p.end()
    return pm


class _Target(QtWidgets.QWidget):
    """Glowing box on the dots where the dragged or resized card will land."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.fill = True

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        box = QtCore.QRectF(self.rect()).adjusted(PAD, PAD, -PAD, -PAD)
        p.setBrush(QtCore.Qt.NoBrush)
        for i, alpha in enumerate((14, 22, 34, 52, 80)):  # soft halo, strongest next to the edge
            grow = PAD - 1 - i * 1.6
            pen = QtGui.QPen(QtGui.QColor(42, 212, 196, alpha))
            pen.setWidthF(2.2)
            p.setPen(pen)
            p.drawRoundedRect(box.adjusted(-grow, -grow, grow, grow), 12 + grow, 12 + grow)
        pen = QtGui.QPen(QtGui.QColor(GLOW))
        pen.setWidthF(1.8)
        p.setPen(pen)
        p.setBrush(QtGui.QColor(42, 212, 196, 30) if self.fill else QtCore.Qt.NoBrush)
        p.drawRoundedRect(box.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.end()


class CardBoard(QtWidgets.QWidget):
    """The cards of one setup, placed on the dot grid. `base_cols` columns are used for cards without a
    stored place. `on_reorder()` is called after a drop (optional)."""

    def __init__(self, cards, base_cols, gap, on_reorder, col_width=300, parent=None):
        super().__init__(parent)
        self.setObjectName("SMCards")
        self.setAcceptDrops(True)
        self.on_reorder = on_reorder
        self.cards = cards
        self.base_cols = max(1, base_cols)
        self.gap_u = max(1, snap(gap))                 # space between cards, in dots
        self.col_u = max(MIN_W, snap(col_width))       # default card width, in dots
        self.gap = self.gap_u * GRID
        self.colw = self.col_u * GRID
        self.extra = []    # non-card widgets (e.g. an empty-board note) shown at the top
        self._hot = None   # board rect whose dots light up (the target of a drag or resize)
        self._tiles = {}
        self._rects = {}
        for c in cards:
            c.setParent(self)
            c.installEventFilter(self)
        self.target = _Target(self)
        self.target.hide()
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

    # ---- dots ----
    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        dpr = self.devicePixelRatioF()
        for name, color, alpha, radius in (("dim", "#ffffff", 34, 1.0), ("hot", GLOW, 255, 1.7)):
            if (name, dpr) not in self._tiles:
                self._tiles[(name, dpr)] = _dot_tile(color, alpha, radius, dpr)
        p.drawTiledPixmap(e.rect(), self._tiles[("dim", dpr)], e.rect().topLeft())
        if self._hot is not None:
            hot = self._hot.adjusted(-2, -2, 3, 3).intersected(e.rect())
            if not hot.isEmpty():
                p.drawTiledPixmap(hot, self._tiles[("hot", dpr)], hot.topLeft())
        p.end()

    def _show_target(self, rect, fill, under=None):
        """Glow box + bright dots on `rect` (board coordinates)."""
        old = self._hot
        self._hot = QtCore.QRect(rect)
        self.target.fill = fill
        self.target.setGeometry(rect.adjusted(-PAD, -PAD, PAD, PAD))
        self.target.show()
        if under is not None:
            self.target.stackUnder(under)
        else:
            self.target.raise_()
        self.target.update()
        for r in (old, self._hot):
            if r is not None:
                self.update(r.adjusted(-PAD, -PAD, PAD, PAD))

    def _hide_target(self):
        old, self._hot = self._hot, None
        self.target.hide()
        if old is not None:
            self.update(old.adjusted(-PAD, -PAD, PAD, PAD))

    # ---- grid ----
    def step(self):
        return self.colw + self.gap

    def width_u(self, card):
        """Card width in dots: its own (resized) width, or the default for its kind."""
        return max(MIN_W, snap(card.width_px(self.colw, self.gap)))

    def height_u(self, card):
        """Card height in dots: as tall as its rows need (or as resized), rounded up to the next dot."""
        return max(2, snap(card.layout_height(), up=True))

    def _gx(self, card):
        if card.gx is not None:
            return max(0, int(card.gx))
        if card.col is not None:  # place stored by the older column layout
            return max(0, int(card.col)) * (self.col_u + self.gap_u)
        return None

    def plan(self, order=None, moved=None, moved_gx=None):
        """Where every card goes: {card: (gx, gy, wu, hu)} in dots. Cards pack upward in `order`.
        `moved`/`moved_gx` plan a drag without changing anything."""
        order = self.cards if order is None else order
        y0 = 0
        for w in self.extra:
            y0 += snap(w.sizeHint().height(), up=True) + self.gap_u
        sky = {}  # dot column -> first free dot row

        def top(gx, wu):
            return max([sky.get(i, y0) for i in range(gx, gx + wu + self.gap_u)])

        out = {}
        for c in order:
            wu, hu = self.width_u(c), self.height_u(c)
            gx = moved_gx if c is moved else self._gx(c)
            if gx is None:  # first free spot among the default columns
                gx = min((i * (self.col_u + self.gap_u) for i in range(self.base_cols)), key=lambda x: (top(x, wu), x))
            gy = top(gx, wu)
            for i in range(gx, gx + wu + self.gap_u):
                sky[i] = gy + hu + self.gap_u
            out[c] = (gx, gy, wu, hu)
        return out

    @staticmethod
    def _px(cell):
        gx, gy, wu, hu = cell
        return QtCore.QRect(gx * GRID, gy * GRID, wu * GRID, hu * GRID)

    def relayout(self):
        w0 = (self.base_cols * (self.col_u + self.gap_u) - self.gap_u) * GRID
        for w in self.extra:
            w.setGeometry(0, 0, w0, w.sizeHint().height())
        cells = self.plan()
        right = bottom = 0
        self._rects = {}
        for c, cell in cells.items():
            r = self._px(cell)
            c.slot_gx = cell[0]
            self._rects[c] = r
            if c.geometry() != r:
                c.setGeometry(r)
            if not c.isVisible():
                c.show()
            right, bottom = max(right, r.right() + 1), max(bottom, r.bottom() + 1)
        self.setMinimumSize(max(1, right), bottom + GRID)

    def eventFilter(self, obj, e):
        if e.type() == QtCore.QEvent.LayoutRequest and obj in self.cards:
            self._relayout_timer.start()  # a card folded or changed its rows
        return False

    def sizeHint(self):
        return self.minimumSize()

    # ---- resize from a card's corner: whole dots, with the glow on the new footprint ----
    def card_resizing(self, card, width, height):
        wu = max(MIN_W, snap(width))
        hu = max(snap(card.min_height(), up=True), snap(height))
        card.set_size(wu * GRID, hu * GRID)
        self.relayout()
        self._show_target(self._rects[card], fill=False, under=card)

    def card_resize_done(self):
        self._hide_target()

    # ---- drag a card: it lands on the dots under the pointer ----
    HOTSPOT = QtCore.QPoint(24, 16)  # where the pointer holds the dragged card (see ModuleCard._start_drag)

    def _drop_plan(self, pos, card):
        """(gx, new order, landing rect) for dropping `card` with the pointer at `pos`."""
        wu = self.width_u(card)
        gx = max(0, snap(pos.x() - self.HOTSPOT.x()))
        others = [c for c in self.cards if c is not card]
        # among the cards the footprint overlaps sideways, go in front of the first one below the pointer
        before = None
        for c in sorted(others, key=lambda c: self._rects[c].y() if c in self._rects else 0):
            r = self._rects.get(c)
            if r is None:
                continue
            cu, cw = r.x() // GRID, r.width() // GRID
            if cu < gx + wu + self.gap_u and gx < cu + cw + self.gap_u and pos.y() < r.center().y():
                before = c
                break
        order = list(others)
        order.insert(order.index(before) if before is not None else len(order), card)
        cell = self.plan(order, moved=card, moved_gx=gx)[card]
        return gx, order, self._px(cell)

    def _dragged(self, e):
        key = bytes(e.mimeData().data(ModuleCard.MIME)).decode()
        return next((c for c in self.cards if c.m.key == key), None)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(ModuleCard.MIME):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasFormat(ModuleCard.MIME):
            return
        card = self._dragged(e)
        if card is None:
            return
        _gx, _order, rect = self._drop_plan(e.position().toPoint(), card)
        if rect != self._hot:
            self._show_target(rect, fill=True)
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._hide_target()

    def dropEvent(self, e):
        self._hide_target()
        if not e.mimeData().hasFormat(ModuleCard.MIME):
            return
        card = self._dragged(e)
        if card is None:
            return
        gx, order, _rect = self._drop_plan(e.position().toPoint(), card)
        e.acceptProposedAction()
        self.move_card(card, gx, order)

    def move_card(self, card, gx, order):
        """Put `card` at dot column `gx`. Every other card is pinned where it shows now, so only this one moves."""
        for c in self.cards:
            new = gx if c is card else c.slot_gx
            if c.gx != new or c.col is not None:
                c.gx, c.col = new, None
                card_prefs.update(c.m.key, gx=new, col=None)
        save_order([c.m.key for c in order])
        self.cards = list(order)  # moved in place: no card is rebuilt
        self.relayout()
        if self.on_reorder:
            QtCore.QTimer.singleShot(0, self.on_reorder)
