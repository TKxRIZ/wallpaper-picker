from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..constants import CARD_W, CARD_H, THUMB_W, THUMB_H
from ..i18n import t
from ..models import Wallpaper, WallpaperConfig

_CARD_NORMAL = (
    "WallpaperCard{background:#1e1e2e;border:1px solid #313244;border-radius:8px;}"
    "WallpaperCard:hover{background:#252545;border-color:#585b70;}"
)
_CARD_SELECTED = (
    "WallpaperCard{background:#1e2a3a;border:2px solid #89b4fa;border-radius:8px;}"
    "WallpaperCard:hover{background:#1e3050;border:2px solid #89dceb;}"
)
_CFG_BTN = (
    "QPushButton{background:rgba(30,30,46,180);color:#585b70;border:1px solid #313244;"
    "border-radius:4px;font-size:13px;padding:0;}"
    "QPushButton:hover{background:#1e3a5f;color:#89b4fa;border-color:#89b4fa;}"
)
_CFG_BTN_ACTIVE = (
    "QPushButton{background:#1e3a5f;color:#89b4fa;border:1px solid #89b4fa;"
    "border-radius:4px;font-size:13px;padding:0;}"
    "QPushButton:hover{background:#263f5a;color:#89dceb;}"
)


class WallpaperCard(QFrame):
    clicked   = Signal(str)
    configure = Signal(str)

    def __init__(self, wallpaper: Wallpaper, parent=None):
        super().__init__(parent)
        self.wallpaper = wallpaper
        self.setFixedSize(CARD_W, CARD_H)
        self.setFrameShape(QFrame.Shape.Box)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._build()
        self._refresh_cfg_btn()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 4)
        layout.setSpacing(3)

        self.thumb = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.thumb.setFixedHeight(THUMB_H)
        self.thumb.setStyleSheet("background:#11111b; border-radius:5px; color:#585b70; font-size:11px;")
        self.thumb.setText(t("card_loading") if self.wallpaper.preview_path else t("card_no_image"))
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

        self._cfg_btn = QPushButton("⚙", self)
        self._cfg_btn.setFixedSize(22, 22)
        self._cfg_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._cfg_btn.move(CARD_W - 28, THUMB_H - 18)
        self._cfg_btn.clicked.connect(lambda: self.configure.emit(self.wallpaper.id))

    def _refresh_cfg_btn(self):
        has_cfg = WallpaperConfig.load(self.wallpaper.id).is_customized()
        self._cfg_btn.setStyleSheet(_CFG_BTN_ACTIVE if has_cfg else _CFG_BTN)
        self._cfg_btn.setToolTip(t("card_cfg_active") if has_cfg else t("card_cfg_tooltip"))

    def set_pixmap(self, pix: QPixmap):
        self.thumb.setPixmap(pix.scaled(
            THUMB_W, THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self.thumb.setText("")

    def set_selected(self, on: bool):
        self.setStyleSheet(_CARD_SELECTED if on else _CARD_NORMAL)

    def mousePressEvent(self, event):
        if not self._cfg_btn.geometry().contains(event.pos()):
            self.clicked.emit(self.wallpaper.id)


class WallpaperGrid(QWidget):
    selection_changed = Signal(str)
    configure         = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, WallpaperCard] = {}
        self._hidden: set[str] = set()
        self._selected_id = ""
        self._cols = 4

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._search = QLineEdit(placeholderText=t("search_placeholder"))
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
            card.configure.connect(self.configure)
            self._cards[wp.id] = card
        self._relayout()

    def refresh_card(self, wp_id: str):
        if wp_id in self._cards:
            self._cards[wp_id]._refresh_cfg_btn()

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
