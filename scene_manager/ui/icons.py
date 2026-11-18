"""Rail icons drawn with QPainter (our own simple line icons, no external assets)."""
import math

from PySide6 import QtCore, QtGui

SIZE = 20


def _icon(draw, color="#a8adb5", active="#7fd3ff"):
    icon = QtGui.QIcon()
    for mode, c in ((QtGui.QIcon.Normal, color), (QtGui.QIcon.Active, color), (QtGui.QIcon.Selected, active)):
        for state, cc in ((QtGui.QIcon.Off, c), (QtGui.QIcon.On, active)):
            pm = QtGui.QPixmap(SIZE * 2, SIZE * 2)
            pm.setDevicePixelRatio(2)
            pm.fill(QtCore.Qt.transparent)
            p = QtGui.QPainter(pm)
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            pen = QtGui.QPen(QtGui.QColor(cc))
            pen.setWidthF(1.6)
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.NoBrush)
            draw(p, QtGui.QColor(cc))
            p.end()
            icon.addPixmap(pm, mode, state)
    return icon


def _setups(p, c):
    for y in (5, 10, 15):
        p.drawLine(QtCore.QPointF(7, y), QtCore.QPointF(17, y))
        p.drawEllipse(QtCore.QPointF(3.5, y), 1, 1)


def _render(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(6, 4)
    path.lineTo(16, 10)
    path.lineTo(6, 16)
    path.closeSubpath()
    p.drawPath(path)


def _camera(p, c):
    p.drawRoundedRect(QtCore.QRectF(2, 6, 12, 9), 2, 2)
    path = QtGui.QPainterPath()
    path.moveTo(14, 9)
    path.lineTo(18, 6.5)
    path.lineTo(18, 14.5)
    path.lineTo(14, 12)
    p.drawPath(path)
    p.drawEllipse(QtCore.QPointF(8, 10.5), 2, 2)


def _sun(p, c):
    p.drawEllipse(QtCore.QPointF(10, 10), 3.5, 3.5)
    for i in range(8):
        a = i * math.pi / 4
        p.drawLine(QtCore.QPointF(10 + 6 * math.cos(a), 10 + 6 * math.sin(a)),
                   QtCore.QPointF(10 + 8.5 * math.cos(a), 10 + 8.5 * math.sin(a)))


def _env(p, c):
    p.drawEllipse(QtCore.QPointF(10, 10), 7.5, 7.5)
    p.drawEllipse(QtCore.QRectF(6.5, 2.5, 7, 15))
    p.drawLine(QtCore.QPointF(2.5, 10), QtCore.QPointF(17.5, 10))


def _scene(p, c):
    for dy in (0, 4, 8):
        path = QtGui.QPainterPath()
        path.moveTo(10, 3 + dy)
        path.lineTo(17, 6.5 + dy)
        path.lineTo(10, 10 + dy)
        path.lineTo(3, 6.5 + dy)
        path.closeSubpath()
        p.drawPath(path)


def _rendersettings(p, c):
    for x, knob in ((5, 7), (10, 13), (15, 5)):
        p.drawLine(QtCore.QPointF(x, 3), QtCore.QPointF(x, 17))
        p.setBrush(c)
        p.drawEllipse(QtCore.QPointF(x, knob), 1.8, 1.8)
        p.setBrush(QtCore.Qt.NoBrush)


def _scripts(p, c):
    for pts in (((7, 5), (3, 10), (7, 15)), ((13, 5), (17, 10), (13, 15))):
        path = QtGui.QPainterPath()
        path.moveTo(*pts[0])
        path.lineTo(*pts[1])
        path.lineTo(*pts[2])
        p.drawPath(path)
    p.drawLine(QtCore.QPointF(11.5, 4), QtCore.QPointF(8.5, 16))


def _claude(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(10, 2)
    path.quadTo(11, 9, 18, 10)
    path.quadTo(11, 11, 10, 18)
    path.quadTo(9, 11, 2, 10)
    path.quadTo(9, 9, 10, 2)
    p.drawPath(path)


def _settings(p, c):
    p.drawEllipse(QtCore.QPointF(10, 10), 2.5, 2.5)
    p.drawEllipse(QtCore.QPointF(10, 10), 6, 6)
    for i in range(6):
        a = i * math.pi / 3
        p.drawLine(QtCore.QPointF(10 + 6 * math.cos(a), 10 + 6 * math.sin(a)),
                   QtCore.QPointF(10 + 8.5 * math.cos(a), 10 + 8.5 * math.sin(a)))


def _search(p, c):
    p.drawEllipse(QtCore.QPointF(8.5, 8.5), 5, 5)
    p.drawLine(QtCore.QPointF(12.3, 12.3), QtCore.QPointF(17, 17))


def _photo(p, c):
    p.drawRoundedRect(QtCore.QRectF(2.5, 4.5, 15, 11), 2, 2)
    path = QtGui.QPainterPath()
    path.moveTo(3, 14)
    path.lineTo(8, 9.5)
    path.lineTo(11.5, 12.5)
    path.lineTo(13.5, 11)
    path.lineTo(17, 14)
    p.drawPath(path)
    p.drawEllipse(QtCore.QPointF(13.5, 7.8), 1.2, 1.2)


def _folder(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(2.5, 5.5)
    path.lineTo(7.5, 5.5)
    path.lineTo(9, 7)
    path.lineTo(17.5, 7)
    path.lineTo(17.5, 15.5)
    path.lineTo(2.5, 15.5)
    path.closeSubpath()
    p.drawPath(path)


def _grid(p, c):
    for x in (3, 11):
        for y in (3, 11):
            p.drawRoundedRect(QtCore.QRectF(x, y, 6, 6), 1.5, 1.5)


def _chev_up(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(5, 12.5)
    path.lineTo(10, 7.5)
    path.lineTo(15, 12.5)
    p.drawPath(path)


def _chev_down(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(5, 7.5)
    path.lineTo(10, 12.5)
    path.lineTo(15, 7.5)
    p.drawPath(path)


def _more(p, c):
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(c)
    for x in (4.5, 10, 15.5):  # three dots on the exact centre line
        p.drawEllipse(QtCore.QPointF(x, 10), 1.6, 1.6)


def _plus(p, c):
    p.drawLine(QtCore.QPointF(10, 4), QtCore.QPointF(10, 16))
    p.drawLine(QtCore.QPointF(4, 10), QtCore.QPointF(16, 10))


def _close(p, c):
    p.drawLine(QtCore.QPointF(5.5, 5.5), QtCore.QPointF(14.5, 14.5))
    p.drawLine(QtCore.QPointF(14.5, 5.5), QtCore.QPointF(5.5, 14.5))


def _dock(p, c):
    p.drawRoundedRect(QtCore.QRectF(3, 4, 14, 12), 2, 2)
    p.drawLine(QtCore.QPointF(12, 4), QtCore.QPointF(12, 16))


def _grip(p, c):
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(c)
    for x in (7.5, 12.5):
        for y in (5, 10, 15):
            p.drawEllipse(QtCore.QPointF(x, y), 1.2, 1.2)


def _note(p, c):
    path = QtGui.QPainterPath()
    path.moveTo(4, 3)
    path.lineTo(12.5, 3)
    path.lineTo(16, 6.5)
    path.lineTo(16, 17)
    path.lineTo(4, 17)
    path.closeSubpath()
    p.drawPath(path)
    for y in (8.5, 11.5, 14.5):
        p.drawLine(QtCore.QPointF(7, y), QtCore.QPointF(13, y))


def _gear(p, c):
    p.drawEllipse(QtCore.QPointF(10, 10), 2.6, 2.6)
    path = QtGui.QPainterPath()
    for i in range(16):
        a = i * math.pi / 8 - math.pi / 16
        r = 7.2 if i % 2 == 0 else 5.4
        pt = QtCore.QPointF(10 + r * math.cos(a), 10 + r * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
        a2 = a + math.pi / 8
        path.lineTo(QtCore.QPointF(10 + r * math.cos(a2), 10 + r * math.sin(a2)))
    path.closeSubpath()
    p.drawPath(path)


def _minimize(p, c):
    p.drawLine(QtCore.QPointF(5, 10.5), QtCore.QPointF(15, 10.5))


def _maximize(p, c):
    p.drawRoundedRect(QtCore.QRectF(5, 5, 10, 10), 1.5, 1.5)


_DRAW = {"search": _search, "photo": _photo, "folder": _folder, "grid": _grid,
         "setups": _setups, "render": _render, "camera": _camera, "light": _sun, "env": _env,
         "scene": _scene, "rendersettings": _rendersettings, "script": _scripts,
         "claude": _claude, "settings": _settings,
         "chev_up": _chev_up, "chev_down": _chev_down, "more": _more, "plus": _plus,
         "close": _close, "dock": _dock, "grip": _grip,
         "note": _note, "gear": _gear, "minimize": _minimize, "maximize": _maximize}
_cache = {}
CATEGORY_ICON = {"camera": "camera", "light": "light", "env": "env", "scene": "scene",
                 "render": "rendersettings", "script": "script"}


def get(name, active="#f5f5f7", color="#8e8e93"):
    """Line icon: grey normally, `active` colour when the button is checked."""
    key = (name, active, color)
    if key not in _cache:
        _cache[key] = _icon(_DRAW[name], color, active)
    return _cache[key]


def tinted(name, color):
    return get(name, color, color)


def placeholder(w, h, radius=8):
    """Rounded empty-thumbnail tile with a photo glyph."""
    pm = QtGui.QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtCore.Qt.NoPen)
    p.setBrush(QtGui.QColor("#2c2c2e"))
    p.drawRoundedRect(QtCore.QRectF(0, 0, w, h), radius, radius)
    tinted("photo", "#6e6e73").paint(p, QtCore.QRect(int(w / 2 - 10), int(h / 2 - 10), 20, 20))
    p.end()
    return pm


def rounded(pixmap, radius=8):
    """Clip a thumbnail to rounded corners."""
    if pixmap.isNull():
        return pixmap
    out = QtGui.QPixmap(pixmap.size())
    out.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(out)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    path.addRoundedRect(QtCore.QRectF(out.rect()), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pixmap)
    p.end()
    return out
