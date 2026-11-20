"""QML image providers: remote images (cached on disk) and icons from the system icon theme."""
import hashlib
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QRunnable, QSize, Qt, QThreadPool, Signal, QObject
from PySide6.QtGui import QIcon, QImage
from PySide6.QtQuick import QQuickAsyncImageProvider, QQuickImageProvider, QQuickImageResponse, QQuickTextureFactory

from .. import util


def _cached(url):
    path = util.cache_dir() / "img" / (hashlib.sha1(url.encode()).hexdigest() + Path(urllib.parse.urlsplit(url).path).suffix[:5])
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        util.http.download(url, path)
    return path


class _Done(QObject):
    done = Signal()


class _Response(QQuickImageResponse):
    def __init__(self, url, size):
        super().__init__()
        self._image = QImage()
        self._url, self._size = url, size
        self._sig = _Done()
        self._sig.done.connect(self.finished)

    def run(self):
        try:
            img = QImage(str(_cached(self._url)))
            if self._size.isValid() and self._size.width() > 0 and not img.isNull():
                img = img.scaled(self._size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._image = img
        except Exception:
            self._image = QImage()
        self._sig.done.emit()

    def textureFactory(self):
        return QQuickTextureFactory.textureFactoryForImage(self._image)


class _Job(QRunnable):
    def __init__(self, resp):
        super().__init__()
        self.resp = resp

    def run(self):
        self.resp.run()


class WebImages(QQuickAsyncImageProvider):
    """image://web/<url-encoded URL>"""

    def __init__(self):
        super().__init__()
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(6)

    def requestImageResponse(self, id_, requested_size):
        resp = _Response(urllib.parse.unquote(id_), requested_size)
        self.pool.start(_Job(resp))
        return resp


class ThemeIcons(QQuickImageProvider):
    """image://icon/<theme icon name>, drawn from the user's icon theme."""

    def __init__(self):
        super().__init__(QQuickImageProvider.Pixmap)

    def requestPixmap(self, id_, size, requested):
        s = requested if requested.isValid() and requested.width() > 0 else QSize(24, 24)
        icon = QIcon.fromTheme(id_)
        if icon.isNull():
            icon = QIcon.fromTheme(id_.removesuffix("-symbolic"))
        pm = icon.pixmap(s)
        if size is not None:
            size.setWidth(pm.width())
            size.setHeight(pm.height())
        return pm
