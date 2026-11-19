"""Viewport thumbnails stored as base64 PNG inside the setup (so they travel with the .max)."""
import base64
import os
import tempfile

from pymxs import runtime as rt

SIZE = (192, 108)


def capture_viewport():
    from PySide6 import QtCore, QtGui

    rt.redrawViews()
    dib = rt.gw.getViewportDib()
    path = os.path.join(tempfile.gettempdir(), "scene_manager_thumb.png")
    dib.filename = path
    rt.save(dib)
    rt.close(dib)
    img = QtGui.QImage(path)
    if img.isNull():
        return None
    img = img.scaled(SIZE[0], SIZE[1], QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return base64.b64encode(bytes(buf.data())).decode("ascii")


def to_pixmap(b64):
    from PySide6 import QtGui

    pm = QtGui.QPixmap()
    if b64:
        pm.loadFromData(base64.b64decode(b64), "PNG")
    return pm
