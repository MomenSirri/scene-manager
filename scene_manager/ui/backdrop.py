"""Patterned dark backdrop painted behind the panel, so the translucent cards read as glass.

Soft colour glows (Apple accent tints) on near-black, plus a faint dot grid. Cached per size.
"""
from PySide6 import QtCore, QtGui

# Colour schemes: (x, y as fraction of size, radius as fraction of the larger side, colour, alpha)
SCHEMES = {
    "lagoon": [  # teal and blue
        (0.25, 0.05, 0.60, "#0a84ff", 115),
        (0.95, 0.40, 0.50, "#2ad4c4", 95),
        (0.55, 1.05, 0.55, "#1f9e7a", 80),
        (0.02, 0.85, 0.40, "#3a7bd5", 55),
    ],
    "aurora": [  # green and cyan, brighter
        (0.20, 0.00, 0.55, "#30d158", 90),
        (0.85, 0.20, 0.55, "#64d2ff", 105),
        (0.60, 1.05, 0.60, "#0a84ff", 85),
        (0.00, 0.70, 0.40, "#2ad49a", 60),
    ],
    "deep_sea": [  # muted navy, teal and emerald
        (0.30, 0.00, 0.65, "#123f8c", 150),
        (0.95, 0.55, 0.55, "#0f7c7c", 120),
        (0.15, 1.05, 0.55, "#0f6b4f", 110),
    ],
}
SCHEME_LABELS = {"lagoon": "Lagoon", "aurora": "Aurora", "deep_sea": "Deep Sea"}
DEFAULT_SCHEME = "lagoon"
DOT_STEP = 18
_cache = {}


def pixmap(w, h, dpr=1.0, scheme=DEFAULT_SCHEME):
    key = (w, h, round(dpr, 2), scheme)
    if key in _cache:
        return _cache[key]
    _cache.clear()
    pm = QtGui.QPixmap(int(w * dpr), int(h * dpr))
    pm.setDevicePixelRatio(dpr)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    base = QtGui.QLinearGradient(0, 0, 0, h)
    base.setColorAt(0, QtGui.QColor("#0d0d12"))
    base.setColorAt(1, QtGui.QColor("#08080b"))
    p.fillRect(QtCore.QRectF(0, 0, w, h), base)
    big = max(w, h)
    for fx, fy, fr, color, alpha in SCHEMES.get(scheme, SCHEMES[DEFAULT_SCHEME]):
        g = QtGui.QRadialGradient(QtCore.QPointF(fx * w, fy * h), fr * big)
        c = QtGui.QColor(color)
        c.setAlpha(alpha)
        g.setColorAt(0, c)
        c2 = QtGui.QColor(color)
        c2.setAlpha(int(alpha * 0.35))
        g.setColorAt(0.45, c2)
        c3 = QtGui.QColor(color)
        c3.setAlpha(0)
        g.setColorAt(1, c3)
        p.fillRect(QtCore.QRectF(0, 0, w, h), g)
    # no dots here: the card board draws the dot grid its cards snap to (ui/board.py)
    # gentle vignette
    v = QtGui.QRadialGradient(QtCore.QPointF(w / 2, h / 2), big * 0.75)
    v.setColorAt(0.6, QtGui.QColor(0, 0, 0, 0))
    v.setColorAt(1, QtGui.QColor(0, 0, 0, 120))
    p.fillRect(QtCore.QRectF(0, 0, w, h), v)
    p.end()
    _cache[key] = pm
    return pm
