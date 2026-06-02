from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from ..constants import CARD_W, CARD_H, THUMB_W, THUMB_H
from ..models import Wallpaper

_CARD_NORMAL = (
    "WallpaperCard{background:#1e1e2e;border:1px solid #313244;border-radius:8px;}"
    "WallpaperCard:hover{background:#252545;border-color:#585b70;}"
)
_CARD_SELECTED = (
    "WallpaperCard{background:#1e2a3a;border:2px solid #89b4fa;border-radius:8px;}"
    "WallpaperCard:hover{background:#1e3050;border:2px solid #89dceb;}"
)


class WallpaperCard(QFrame):
    clicked = Signal(str)

    def __init__(self, wallpaper: Wallpaper, parent=None):
        super().__init__(parent)
        self.wallpaper = wallpaper
        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QFrame.Shape.Box)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 4)
        layout.setSpacing(3)

        self.thumb = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.thumb.setFixedHeight(THUMB_H)
        self.thumb.setStyleSheet("background:#11111b; border-radius:5px; color:#585b70; font-size:11px;")
        self.thumb.setText("lädt…" if self.wallpaper.preview_path else "kein Bild")
        layout.addWidget(self.thumb)

        title = QLabel()
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(30)
        title.setStyleSheet("color:#cdd6f4; font-size:11px;")
        title.setText(title.fontMetrics().elidedText(
            self.wallpaper.title, Qt.TextElideMode.ElideRight, CARD_W - 8
        ))
        title.setToolTip(self.wallpaper.title)
        layout.addWidget(title)
        self.setStyleSheet(_CARD_NORMAL)

    def set_pixmap(self, pix: QPixmap):
        self.thumb.setPixmap(pix.scaled(
            THUMB_W, THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self.thumb.setText("")

    def set_selected(self, on: bool):
        self.setStyleSheet(_CARD_SELECTED if on else _CARD_NORMAL)

    def mousePressEvent(self, _):
        self.clicked.emit(self.wallpaper.id)


class WallpaperGrid(QWidget):
    selection_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, WallpaperCard] = {}
        self._hidden: set[str] = set()
        self._selected_id = ""
        self._cols = 4

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._search = QLineEdit(placeholderText="Suchen…")
        self._search.textChanged.connect(self._filter)
        outer.addWidget(self._search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(self._container)

    def add_cards(self, wallpapers: list[Wallpaper]):
        for wp in wallpapers:
            card = WallpaperCard(wp)
            card.clicked.connect(self._on_click)
            self._cards[wp.id] = card
        self._relayout()

    def update_card_pixmap(self, wp_id: str, pix: QPixmap):
        if wp_id in self._cards:
            self._cards[wp_id].set_pixmap(pix)

    def set_selected(self, wp_id: str):
        if self._selected_id in self._cards:
            self._cards[self._selected_id].set_selected(False)
        self._selected_id = wp_id
        if wp_id in self._cards:
            self._cards[wp_id].set_selected(True)

    def _on_click(self, wp_id: str):
        self.set_selected(wp_id)
        self.selection_changed.emit(wp_id)

    def _filter(self, text: str):
        q = text.lower()
        self._hidden = {id_ for id_, c in self._cards.items() if q not in c.wallpaper.title.lower()}
        self._relayout()

    def _relayout(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)  # type: ignore
        visible = [c for id_, c in self._cards.items() if id_ not in self._hidden]
        for i, card in enumerate(visible):
            card.setParent(self._container)
            self._grid.addWidget(card, i // self._cols, i % self._cols)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        cols = max(1, (self.width() - 16) // (CARD_W + 8))
        if cols != self._cols:
            self._cols = cols
            self._relayout()
