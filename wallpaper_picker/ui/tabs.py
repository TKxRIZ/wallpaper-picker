from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from ..i18n import t
from ..models import Wallpaper
from ..workers import LocalThumbnailWorker, ThumbnailLoader
from .cards import WallpaperGrid


class InstalledTab(QWidget):
    wallpaper_selected = Signal(str)

    def __init__(self, wallpapers: list[Wallpaper], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not wallpapers:
            empty = QLabel(t("installed_empty"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color:#888; padding:40px;")
            layout.addWidget(empty)
            return

        self.grid = WallpaperGrid()
        self.grid.add_cards(wallpapers)
        self.grid.selection_changed.connect(self.wallpaper_selected)
        layout.addWidget(self.grid)

        self._loader = LocalThumbnailWorker(wallpapers)
        self._loader.loaded.connect(self.grid.update_card_pixmap)
        self._loader.start()


class AvailableTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        info = QLabel(t("available_info"))
        info.setWordWrap(True)
        info.setStyleSheet("color:#aaa; padding:8px;")
        layout.addWidget(info)

        self._progress = QProgressBar()
        self._progress.setFormat(t("available_loading"))
        layout.addWidget(self._progress)

        self.grid = WallpaperGrid()
        self.grid._search.setPlaceholderText(t("available_search"))
        layout.addWidget(self.grid)

        self._thumb_workers: list[ThumbnailLoader] = []

    def start_loading(self, ids: list[str]):
        self._progress.setMaximum(len(ids))
        self._progress.setValue(0)

    def on_batch(self, wallpapers: list[Wallpaper]):
        self.grid.add_cards(wallpapers)
        self._progress.setValue(self._progress.value() + len(wallpapers))
        for wp in wallpapers:
            if wp.preview_url:
                w = ThumbnailLoader(wp.id, wp.preview_url)
                w.loaded.connect(self.grid.update_card_pixmap)
                w.start()
                self._thumb_workers.append(w)
        if self._progress.value() >= self._progress.maximum():
            self._progress.hide()
