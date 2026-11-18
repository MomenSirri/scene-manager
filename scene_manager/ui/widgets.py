"""Small custom controls: an animated switch (module on/off and yes/no values)."""
from PySide6 import QtCore, QtGui, QtWidgets

from . import theme


class Switch(QtWidgets.QAbstractButton):
    """Pill toggle, 150 ms knob animation. Behaves like a checkable button (toggled signal)."""

    def __init__(self, parent=None, on_color=theme.ACCENT):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFixedSize(30, 18)
        self._on_color = QtGui.QColor(on_color)
        self._pos = 0.0
        self._anim = QtCore.QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_knob(self):
        return self._pos

    def _set_knob(self, v):
        self._pos = v
        self.update()

    knob = QtCore.Property(float, _get_knob, _set_knob)

    def setChecked(self, on):
        super().setChecked(on)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def sizeHint(self):
        return QtCore.QSize(30, 18)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        off = QtGui.QColor(theme.SURFACE_2 if self.isEnabled() else "#2a2a2c")
        on = QtGui.QColor(self._on_color)
        if not self.isEnabled():
            on.setAlpha(110)
        t = self._pos
        track = QtGui.QColor(int(off.red() + (on.red() - off.red()) * t),
                             int(off.green() + (on.green() - off.green()) * t),
                             int(off.blue() + (on.blue() - off.blue()) * t),
                             int(off.alpha() + (on.alpha() - off.alpha()) * t))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QtCore.QRectF(0, 0, 30, 18), 9, 9)
        p.setBrush(QtGui.QColor("#ffffff" if self.isEnabled() else "#9a9a9e"))
        x = 2 + t * 12
        p.drawEllipse(QtCore.QRectF(x, 2, 14, 14))
        if self.hasFocus():
            pen = QtGui.QPen(QtGui.QColor(theme.ACCENT))
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRoundedRect(QtCore.QRectF(0.75, 0.75, 28.5, 16.5), 8.25, 8.25)
        p.end()
