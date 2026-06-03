import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpacerItem,
    QSpinBox, QStackedWidget, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__
from ..constants import ENGINE_DIR, IS_ATOMIC, DISTRO_NAME, DISTRO_ID, _vtuple
from ..config import Config
from ..i18n import t, set_language, get_language
from ..workers import (
    AppUpdateWorker, UpdateChecker, TestBinaryWorker,
    ServiceControlWorker, UpdateLWEWorker, LWEVersionChecker, BuildWorker,
)
from ..models import LWEStatus, WallpaperConfig


class WallpaperConfigDialog(QDialog):
    """Per-wallpaper settings override dialog."""

    def __init__(self, wallpaper_id: str, title: str, global_cfg: Config, parent=None):
        super().__init__(parent)
        self.wallpaper_id = wallpaper_id
        self.global_cfg   = global_cfg
        self.wp_cfg       = WallpaperConfig.load(wallpaper_id)
        self.setWindowTitle(t("wpcfg_title", title=title))
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        info = QLabel(t("wpcfg_info"))
        info.setWordWrap(True)
        info.setStyleSheet("color:#a6adc8; font-size:11px; padding:4px 0 8px 0;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.addLayout(form)

        fps_row = QHBoxLayout()
        self._fps_enabled = QCheckBox()
        self._fps_spin    = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(self.wp_cfg.fps if self.wp_cfg.fps is not None else self.global_cfg.fps)
        self._fps_spin.setEnabled(self.wp_cfg.fps is not None)
        self._fps_enabled.setChecked(self.wp_cfg.fps is not None)
        self._fps_enabled.toggled.connect(self._fps_spin.setEnabled)
        fps_row.addWidget(self._fps_enabled)
        fps_row.addWidget(self._fps_spin, stretch=1)
        fps_row.addWidget(QLabel(t("wpcfg_global", v=self.global_cfg.fps)))
        form.addRow(t("wpcfg_fps"), fps_row)

        self._bool_rows: dict[str, tuple[QCheckBox, QCheckBox]] = {}
        bool_fields = [
            ("fullscreen_pause",    "cb_fullscreen_pause_short"),
            ("disable_particles",   "cb_disable_particles_short"),
            ("disable_mouse",       "cb_disable_mouse_short"),
            ("no_audio_processing", "cb_no_audio_short"),
        ]
        for attr, label_key in bool_fields:
            row        = QHBoxLayout()
            enabled_cb = QCheckBox()
            value_cb   = QCheckBox(t(label_key))
            cur_val    = getattr(self.wp_cfg, attr)
            global_val = getattr(self.global_cfg, attr)
            enabled_cb.setChecked(cur_val is not None)
            value_cb.setChecked(cur_val if cur_val is not None else global_val)
            value_cb.setEnabled(cur_val is not None)
            enabled_cb.toggled.connect(value_cb.setEnabled)
            global_hint = QLabel(t("wpcfg_global", v=t("wpcfg_on") if global_val else t("wpcfg_off")))
            global_hint.setStyleSheet("color:#585b70; font-size:10px;")
            row.addWidget(enabled_cb)
            row.addWidget(value_cb, stretch=1)
            row.addWidget(global_hint)
            form.addRow("", row)
            self._bool_rows[attr] = (enabled_cb, value_cb)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Reset |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Save).setText(t("btn_save"))
        btns.button(QDialogButtonBox.StandardButton.Reset).setText(t("wpcfg_reset"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(t("btn_cancel"))
        btns.accepted.connect(self._save)
        btns.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save(self):
        fps = self._fps_spin.value() if self._fps_enabled.isChecked() else None
        self.wp_cfg = WallpaperConfig(fps=fps)
        for attr, (enabled_cb, value_cb) in self._bool_rows.items():
            setattr(self.wp_cfg, attr, value_cb.isChecked() if enabled_cb.isChecked() else None)
        if self.wp_cfg.is_customized():
            self.wp_cfg.save(self.wallpaper_id)
        else:
            self.wp_cfg.delete(self.wallpaper_id)
        self.accept()

    def _reset(self):
        self.wp_cfg.delete(self.wallpaper_id)
        self.wp_cfg = WallpaperConfig()
        self.accept()


class BuildDialog(QDialog):
    binary_built = Signal(str)

    def __init__(self, container: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("linux-wallpaperengine bauen")
        self.resize(700, 450)
        self._worker: Optional[BuildWorker] = None
        self._container = container
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            f"Baut linux-wallpaperengine im Container <b>{self._container}</b>.\n"
            "Das kann 5–15 Minuten dauern — bitte warten."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 9))
        self._log.setStyleSheet("background:#0d1117; color:#e6edf3;")
        layout.addWidget(self._log, stretch=1)

        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Build starten")
        self._start_btn.clicked.connect(self._start)
        self._close_btn = QPushButton("Schließen")
        self._close_btn.setEnabled(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._start_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _start(self):
        self._start_btn.setEnabled(False)
        repo = str(ENGINE_DIR)
        self._log.append(f"Container: {self._container}\nRepo: {repo}\n")
        self._worker = BuildWorker(self._container, repo)
        self._worker.output_line.connect(self._log.append)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, msg: str, binary_path: str):
        self._log.append(f"\n{'✓' if ok else '✗'} {msg}")
        self._close_btn.setEnabled(True)
        if ok and binary_path:
            self.binary_built.emit(binary_path)

    def closeEvent(self, e):
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        e.accept()


class UpdateDialog(QDialog):
    def __init__(self, current: str, remote: str, remote_changelog: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("upddlg_title"))
        self.resize(540, 400)
        self._worker: Optional[AppUpdateWorker] = None
        self._build_ui(current, remote, remote_changelog)

    def _build_ui(self, current: str, remote: str, changelog: dict):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"{t('upddlg_header')}<br><br>"
            f"{t('upddlg_current')} &nbsp;<code>{current}</code><br>"
            f"{t('upddlg_remote')} &nbsp;&nbsp;<code style='color:#89b4fa'>{remote}</code>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        new_entries = {v: items for v, items in changelog.items() if _vtuple(v) > _vtuple(current)}
        if new_entries:
            layout.addWidget(QLabel(t("upddlg_whats_new")))
            cl = QTextEdit()
            cl.setReadOnly(True)
            cl.setFixedHeight(120)
            lines = []
            for v in sorted(new_entries, key=_vtuple, reverse=True):
                lines.append(f"v{v}:")
                lines.extend(f"  • {item}" for item in new_entries[v])
            cl.setPlainText("\n".join(lines))
            layout.addWidget(cl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 9))
        self._log.setFixedHeight(80)
        self._log.hide()
        layout.addWidget(self._log)

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setText(t("btn_install_now"))
        self._btns.button(QDialogButtonBox.StandardButton.Cancel).setText(t("btn_cancel"))
        self._btns.accepted.connect(self._start_update)
        self._btns.rejected.connect(self.reject)
        layout.addWidget(self._btns)

    def _start_update(self):
        self._btns.setEnabled(False)
        self._log.show()
        self._worker = AppUpdateWorker()
        self._worker.output_line.connect(self._log.append)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, msg: str):
        self._log.append(("✓ " if ok else "✗ ") + msg)
        if ok:
            self._log.append(t("update_restarting"))
            QTimer.singleShot(1500, self._restart)
        else:
            self._btns.setEnabled(True)

    def _restart(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)


class SettingsDialog(QDialog):
    saved = Signal()

    # ── colours (Catppuccin Mocha) ──────────────────────────────────────────
    _C_BG      = "#1e1e2e"
    _C_SIDEBAR = "#181825"
    _C_SURFACE = "#313244"
    _C_OVERLAY = "#45475a"
    _C_TEXT    = "#cdd6f4"
    _C_SUBTEXT = "#a6adc8"
    _C_MUTED   = "#585b70"
    _C_BLUE    = "#89b4fa"
    _C_GREEN   = "#a6e3a1"
    _C_RED     = "#f38ba8"
    _C_YELLOW  = "#f9e2af"

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Einstellungen — Wallpaper Engine – Linux")
        self.setMinimumSize(820, 580)
        self.resize(860, 620)
        self._test_worker:  Optional[TestBinaryWorker]  = None
        self._lwe_checker:  Optional[LWEVersionChecker] = None
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._build()

    # ── shell ───────────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(f"QDialog{{background:{self._C_BG};}}")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(168)
        sidebar.setStyleSheet(f"background:{self._C_SIDEBAR};")
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(8, 16, 8, 16)
        sb_layout.setSpacing(2)

        logo = QLabel(t("settings_header"))
        logo.setStyleSheet(f"color:{self._C_SUBTEXT};font-size:11px;font-weight:bold;"
                           f"padding:0 4px 12px 4px;letter-spacing:1px;")
        sb_layout.addWidget(logo)

        self._nav_btns: list[QPushButton] = []
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{self._C_BG};")

        pages = [
            ("🔧", t("nav_engine"),  self._page_engine()),
            ("⚡", t("nav_service"), self._page_service()),
            ("↑",  t("nav_updates"), self._page_updates()),
            ("ℹ",  t("nav_info"),    self._page_info()),
        ]
        for i, (icon, label, page) in enumerate(pages):
            btn = QPushButton(f"  {icon}  {label}")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setStyleSheet(self._nav_style())
            btn.clicked.connect(lambda _, idx=i: self._nav_select(idx))
            sb_layout.addWidget(btn)
            self._nav_btns.append(btn)
            self._stack.addWidget(page)

        sb_layout.addStretch()
        root.addWidget(sidebar)

        # Thin separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{self._C_SURFACE};")
        root.addWidget(sep)

        # Right: stack + bottom bar
        right = QWidget()
        right.setStyleSheet(f"background:{self._C_BG};")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._stack, stretch=1)

        # Bottom bar
        bar = QWidget()
        bar.setStyleSheet(f"background:{self._C_SIDEBAR};border-top:1px solid {self._C_SURFACE};")
        bar.setFixedHeight(52)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.addStretch()

        cancel_btn = QPushButton(t("btn_cancel"))
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{self._C_SUBTEXT};border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;padding:5px 16px;}}"
            f"QPushButton:hover{{background:{self._C_OVERLAY};color:{self._C_TEXT};}}"
        )
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton(t("btn_save"))
        save_btn.setStyleSheet(
            f"QPushButton{{background:{self._C_BLUE};color:#1e1e2e;font-weight:bold;"
            f"border:none;border-radius:5px;padding:5px 20px;}}"
            f"QPushButton:hover{{background:#b4c9fc;}}"
        )
        save_btn.clicked.connect(self._save)

        bl.addWidget(cancel_btn)
        bl.addSpacing(8)
        bl.addWidget(save_btn)
        rl.addWidget(bar)
        root.addWidget(right, stretch=1)

    def _nav_style(self) -> str:
        return (
            f"QPushButton{{background:transparent;color:{self._C_SUBTEXT};text-align:left;"
            f"border:none;border-radius:6px;padding:8px 10px;font-size:13px;}}"
            f"QPushButton:hover{{background:{self._C_SURFACE};color:{self._C_TEXT};}}"
            f"QPushButton:checked{{background:{self._C_SURFACE};color:{self._C_BLUE};font-weight:bold;}}"
        )

    def _nav_select(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        if idx == 1:
            self._refresh_status()
            self._refresh_log()
            self._log_timer.start(3000)
        else:
            self._log_timer.stop()

    # ── page helpers ────────────────────────────────────────────────────────

    def _scrollable(self, inner: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner.setStyleSheet("background:transparent;")
        scroll.setWidget(inner)
        return scroll

    def _section_header(self, text: str) -> QWidget:
        w   = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 12, 0, 4)
        row.setSpacing(8)
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color:{self._C_BLUE};font-size:10px;font-weight:bold;letter-spacing:1.5px;"
        )
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{self._C_SURFACE};")
        row.addWidget(lbl)
        row.addWidget(line, stretch=1)
        return w

    def _field(self, layout: QVBoxLayout, label: str, widget: QWidget, hint: str = "") -> None:
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{self._C_SUBTEXT};font-size:11px;margin-bottom:2px;")
        layout.addWidget(lbl)
        layout.addWidget(widget)
        if hint:
            h = QLabel(hint)
            h.setStyleSheet(f"color:{self._C_MUTED};font-size:10px;margin-top:1px;")
            h.setWordWrap(True)
            layout.addWidget(h)
        layout.addSpacing(8)

    def _input(self, text: str = "", placeholder: str = "") -> QLineEdit:
        w = QLineEdit(text)
        w.setPlaceholderText(placeholder)
        w.setStyleSheet(
            f"QLineEdit{{background:#11111b;border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;padding:5px 8px;color:{self._C_TEXT};}}"
            f"QLineEdit:focus{{border-color:{self._C_BLUE};}}"
            f"QLineEdit:disabled{{color:{self._C_MUTED};border-color:{self._C_SURFACE};}}"
        )
        return w

    def _checkbox(self, label: str, checked: bool, hint: str = "") -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setStyleSheet(f"QCheckBox{{color:{self._C_TEXT};spacing:6px;}}"
                         f"QCheckBox::indicator{{width:15px;height:15px;border-radius:3px;"
                         f"border:1px solid {self._C_SURFACE};background:#11111b;}}"
                         f"QCheckBox::indicator:checked{{background:{self._C_BLUE};border-color:{self._C_BLUE};}}")
        if hint:
            cb.setToolTip(hint)
        return cb

    def _action_btn(self, label: str, primary: bool = False) -> QPushButton:
        btn = QPushButton(label)
        if primary:
            btn.setStyleSheet(
                f"QPushButton{{background:{self._C_BLUE};color:#1e1e2e;font-weight:bold;"
                f"border:none;border-radius:5px;padding:5px 14px;}}"
                f"QPushButton:hover{{background:#b4c9fc;}}"
                f"QPushButton:disabled{{background:{self._C_OVERLAY};color:{self._C_MUTED};}}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:{self._C_SURFACE};color:{self._C_TEXT};"
                f"border:none;border-radius:5px;padding:5px 14px;}}"
                f"QPushButton:hover{{background:{self._C_OVERLAY};}}"
                f"QPushButton:disabled{{color:{self._C_MUTED};}}"
            )
        return btn

    def _status_badge(self, text: str, color: str) -> QLabel:
        lbl = QLabel(f"● {text}")
        lbl.setStyleSheet(f"color:{color};font-weight:bold;font-size:12px;")
        return lbl

    # ── pages ───────────────────────────────────────────────────────────────

    def _page_engine(self) -> QWidget:
        inner  = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)

        layout.addWidget(self._section_header(t("sec_execution")))

        combo_style = (
            f"QComboBox{{background:#11111b;border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;padding:5px 8px;color:{self._C_TEXT};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:#181825;border:1px solid {self._C_SURFACE};"
            f"selection-background-color:{self._C_SURFACE};}}"
        )

        self._mode = QComboBox()
        self._mode.addItems(["distrobox", "direct", "toolbox", "custom"])
        self._mode.setCurrentText(self.cfg.mode)
        self._mode.setStyleSheet(combo_style)
        self._mode.currentTextChanged.connect(self._update_mode_vis)
        self._field(layout, t("field_exec_mode"), self._mode)

        self._container = self._input(self.cfg.container)
        self._field(layout, t("field_container"), self._container, t("hint_container"))

        bin_row = QWidget()
        br      = QHBoxLayout(bin_row)
        br.setContentsMargins(0, 0, 0, 0)
        br.setSpacing(6)
        self._binary = self._input(self.cfg.binary)
        b1 = self._action_btn("…")
        b1.setFixedWidth(32)
        b1.clicked.connect(lambda: self._browse_file(self._binary))
        br.addWidget(self._binary)
        br.addWidget(b1)
        self._field(layout, t("field_binary"), bin_row)

        ast_row = QWidget()
        ar      = QHBoxLayout(ast_row)
        ar.setContentsMargins(0, 0, 0, 0)
        ar.setSpacing(6)
        self._assets = self._input(self.cfg.assets_dir)
        b2 = self._action_btn("…")
        b2.setFixedWidth(32)
        b2.clicked.connect(lambda: self._browse_dir(self._assets))
        ar.addWidget(self._assets)
        ar.addWidget(b2)
        self._field(layout, t("field_assets"), ast_row)

        self._custom_prefix = self._input(self.cfg.custom_prefix)
        self._field(layout, t("field_prefix"), self._custom_prefix, t("hint_prefix"))

        test_row = QWidget()
        tr       = QHBoxLayout(test_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(8)
        self._test_btn = self._action_btn(t("btn_test_binary"))
        self._test_btn.clicked.connect(self._test_binary)
        self._test_out = QLabel("")
        self._test_out.setWordWrap(True)
        tr.addWidget(self._test_btn)
        tr.addWidget(self._test_out, stretch=1)
        layout.addWidget(test_row)
        layout.addSpacing(16)

        layout.addWidget(self._section_header(t("sec_steam")))
        key_row = QWidget()
        kr      = QHBoxLayout(key_row)
        kr.setContentsMargins(0, 0, 0, 0)
        kr.setSpacing(6)
        self._steam_key = self._input(self.cfg.steam_api_key, t("hint_steam_key"))
        self._steam_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        key_link = QLabel(f'<a href="https://steamcommunity.com/dev/apikey" '
                          f'style="color:{self._C_BLUE}">{t("steam_key_link")}</a>')
        key_link.setOpenExternalLinks(True)
        kr.addWidget(self._steam_key)
        kr.addWidget(key_link)
        self._field(layout, t("field_steam_key"), key_row)

        layout.addWidget(self._section_header(t("sec_performance")))
        self._disable_particles   = self._checkbox(t("cb_disable_particles"), self.cfg.disable_particles, t("hint_particles"))
        self._disable_mouse       = self._checkbox(t("cb_disable_mouse"),      self.cfg.disable_mouse,    t("hint_mouse"))
        self._no_audio_processing = self._checkbox(t("cb_no_audio"),           self.cfg.no_audio_processing, t("hint_audio"))
        for cb in (self._disable_particles, self._disable_mouse, self._no_audio_processing):
            layout.addWidget(cb)
            layout.addSpacing(4)

        layout.addWidget(self._section_header(t("sec_language")))
        self._language = QComboBox()
        self._language.addItem("Deutsch", "de")
        self._language.addItem("English", "en")
        self._language.setStyleSheet(combo_style)
        self._language.setCurrentIndex(0 if get_language() == "de" else 1)
        self._field(layout, t("field_language"), self._language, t("hint_language"))

        layout.addStretch()
        self._update_mode_vis(self.cfg.mode)
        return self._scrollable(inner)

    def _page_service(self) -> QWidget:
        inner  = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)

        layout.addWidget(self._section_header(t("sec_status")))

        status_row = QWidget()
        sr         = QHBoxLayout(status_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(12)
        self._svc_status = QLabel("…")
        self._svc_status.setStyleSheet(f"color:{self._C_TEXT};font-weight:bold;font-size:13px;")
        sr.addWidget(self._svc_status)
        sr.addStretch()
        self._autostart = self._checkbox(t("cb_autostart"), self._is_enabled())
        self._autostart.toggled.connect(self._toggle_autostart)
        sr.addWidget(self._autostart)
        layout.addWidget(status_row)
        layout.addSpacing(12)

        layout.addWidget(self._section_header(t("sec_control")))

        ctrl_row = QWidget()
        cr       = QHBoxLayout(ctrl_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(8)
        for label_key, action in [("btn_start", "start"), ("btn_stop", "stop"), ("btn_restart", "restart")]:
            btn = self._action_btn(t(label_key))
            btn.clicked.connect(lambda _, a=action: self._svc_action(a))
            cr.addWidget(btn)
        cr.addStretch()
        layout.addWidget(ctrl_row)
        layout.addSpacing(16)

        layout.addWidget(self._section_header(t("sec_log")))
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Monospace", 9))
        self._log_view.setStyleSheet(
            f"QTextEdit{{background:#11111b;border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;color:{self._C_TEXT};padding:4px;}}"
        )
        layout.addWidget(self._log_view, stretch=1)
        return inner

    def _page_updates(self) -> QWidget:
        inner  = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)

        layout.addWidget(self._section_header(t("sec_picker_updates")))

        self._update_url = self._input(
            self.cfg.update_url,
            "https://raw.githubusercontent.com/USER/REPO/main/wallpaper_picker/__init__.py"
        )
        self._field(layout, t("field_update_url"), self._update_url, t("hint_update_url"))

        ver_row = QWidget()
        vr      = QHBoxLayout(ver_row)
        vr.setContentsMargins(0, 0, 0, 0)
        vr.setSpacing(8)
        ver_lbl = QLabel(t("installed_version", c=self._C_BLUE, v=__version__))
        ver_lbl.setStyleSheet(f"color:{self._C_TEXT};")
        self._check_btn = self._action_btn(t("btn_check_now"))
        self._check_btn.clicked.connect(self._check_update)
        self._check_result = QLabel("")
        self._check_result.setStyleSheet(f"color:{self._C_SUBTEXT};")
        vr.addWidget(ver_lbl)
        vr.addWidget(self._check_btn)
        vr.addWidget(self._check_result, stretch=1)
        layout.addWidget(ver_row)
        layout.addSpacing(8)

        self._fullscreen_pause = self._checkbox(
            t("cb_fullscreen_pause"),
            getattr(self.cfg, "fullscreen_pause", True),
            t("hint_fullscreen")
        )
        layout.addWidget(self._fullscreen_pause)
        layout.addSpacing(16)

        layout.addWidget(self._section_header(t("sec_lwe_updates")))

        lwe_grid = QWidget()
        gl       = QGridLayout(lwe_grid)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setColumnStretch(1, 1)
        gl.setVerticalSpacing(6)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{self._C_SUBTEXT};font-size:11px;")
            return l

        self._lwe_local_lbl  = QLabel("…")
        self._lwe_remote_lbl = QLabel("…")
        self._lwe_upd_lbl    = QLabel("…")
        self._lwe_compat_lbl = QLabel("…")
        for w in (self._lwe_local_lbl, self._lwe_remote_lbl,
                  self._lwe_upd_lbl, self._lwe_compat_lbl):
            w.setStyleSheet(f"color:{self._C_TEXT};")

        gl.addWidget(_lbl(t("lbl_installed")), 0, 0); gl.addWidget(self._lwe_local_lbl,  0, 1)
        gl.addWidget(_lbl(t("lbl_available")), 1, 0); gl.addWidget(self._lwe_remote_lbl, 1, 1)
        gl.addWidget(_lbl(t("lbl_update")),    2, 0); gl.addWidget(self._lwe_upd_lbl,    2, 1)
        gl.addWidget(_lbl(t("lbl_compatible")),3, 0); gl.addWidget(self._lwe_compat_lbl, 3, 1)
        layout.addWidget(lwe_grid)
        layout.addSpacing(10)

        lwe_btns = QWidget()
        lb       = QHBoxLayout(lwe_btns)
        lb.setContentsMargins(0, 0, 0, 0)
        lb.setSpacing(8)
        self._lwe_check_btn = self._action_btn(t("btn_check_status"))
        self._lwe_check_btn.clicked.connect(self._check_lwe_status)
        self._lwe_btn = self._action_btn(t("btn_update_lwe"), primary=True)
        self._lwe_btn.clicked.connect(self._update_lwe)
        self._lwe_btn.setEnabled(False)
        lb.addWidget(self._lwe_check_btn)
        lb.addWidget(self._lwe_btn)
        lb.addStretch()
        layout.addWidget(lwe_btns)

        self._lwe_log = QTextEdit()
        self._lwe_log.setReadOnly(True)
        self._lwe_log.setFont(QFont("Monospace", 9))
        self._lwe_log.setFixedHeight(110)
        self._lwe_log.setStyleSheet(
            f"QTextEdit{{background:#11111b;border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;color:{self._C_TEXT};padding:4px;margin-top:8px;}}"
        )
        self._lwe_log.hide()
        layout.addWidget(self._lwe_log)
        layout.addStretch()
        return self._scrollable(inner)

    def _page_info(self) -> QWidget:
        inner  = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(0)

        layout.addWidget(self._section_header(t("sec_system")))

        ptype    = t("info_atomic") if IS_ATOMIC else t("info_traditional")
        b_ok     = bool(self.cfg.binary) and Path(self.cfg.binary).exists()
        a_ok     = bool(self.cfg.assets_dir) and Path(self.cfg.assets_dir).is_dir()
        from ..constants import WORKSHOP_DIR
        wp_count = len(list(WORKSHOP_DIR.iterdir())) if WORKSHOP_DIR.exists() else 0

        info_rows = [
            (t("info_distro"),   f"{DISTRO_NAME} ({ptype})",                           None),
            (t("info_binary"),   self.cfg.binary    or t("info_not_configured"),        b_ok),
            (t("info_assets"),   self.cfg.assets_dir or t("info_not_configured"),       a_ok),
            (t("info_workshop"), t("info_workshop_count", n=wp_count),                  None),
        ]
        grid_w = QWidget()
        gl     = QGridLayout(grid_w)
        gl.setContentsMargins(0, 4, 0, 4)
        gl.setColumnStretch(1, 1)
        gl.setVerticalSpacing(8)
        for i, (lbl, val, ok) in enumerate(info_rows):
            l = QLabel(lbl)
            l.setStyleSheet(f"color:{self._C_SUBTEXT};font-size:11px;")
            v = QLabel(val)
            v.setStyleSheet(f"color:{self._C_TEXT};font-size:11px;")
            v.setWordWrap(True)
            gl.addWidget(l, i, 0)
            gl.addWidget(v, i, 1)
            if ok is not None:
                ind = QLabel("✓" if ok else "✗")
                ind.setStyleSheet(f"color:{self._C_GREEN if ok else self._C_RED};font-weight:bold;")
                gl.addWidget(ind, i, 2)
        layout.addWidget(grid_w)
        layout.addSpacing(8)

        layout.addWidget(self._section_header(t("sec_setup_guide")))

        guide = QTextEdit()
        guide.setReadOnly(True)
        guide.setFont(QFont("Monospace", 9))
        guide.setPlainText(self._guide())
        guide.setStyleSheet(
            f"QTextEdit{{background:#11111b;border:1px solid {self._C_SURFACE};"
            f"border-radius:5px;color:{self._C_TEXT};padding:8px;}}"
        )
        layout.addWidget(guide, stretch=1)
        return inner

    # ── logic (unchanged) ───────────────────────────────────────────────────

    def _update_mode_vis(self, mode: str):
        self._container.setEnabled(mode in ("distrobox", "toolbox"))
        self._custom_prefix.setEnabled(mode == "custom")

    def _browse_file(self, target: QLineEdit):
        p, _ = QFileDialog.getOpenFileName(self, "Binary wählen")
        if p:
            target.setText(p)

    def _browse_dir(self, target: QLineEdit):
        p = QFileDialog.getExistingDirectory(self, "Ordner wählen")
        if p:
            target.setText(p)

    def _test_binary(self):
        self._test_btn.setEnabled(False)
        self._test_out.setText("Wird getestet…")
        tmp = Config(mode=self._mode.currentText(), container=self._container.text().strip(),
                     binary=self._binary.text().strip())
        self._test_worker = TestBinaryWorker(tmp.test_cmd())
        self._test_worker.result.connect(self._on_test)
        self._test_worker.start()

    def _on_test(self, ok: bool, msg: str):
        self._test_btn.setEnabled(True)
        c, label = (self._C_GREEN, t("test_ok")) if ok else (self._C_RED, t("test_fail"))
        self._test_out.setText(f'<span style="color:{c}">{label}</span>')
        self._test_out.setToolTip(msg)

    def _refresh_status(self):
        r = subprocess.run(["systemctl", "--user", "is-active", self.cfg.service_name],
                           capture_output=True, text=True, timeout=3)
        s = r.stdout.strip()
        c = self._C_GREEN if s == "active" else self._C_RED
        self._svc_status.setText(f'<span style="color:{c}">● {s}</span>')

    def _refresh_log(self):
        self._refresh_status()
        r = subprocess.run(
            ["journalctl", "--user", "-u", self.cfg.service_name, "-n", "40", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
        self._log_view.setPlainText(r.stdout or "(no log)")
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _is_enabled(self) -> bool:
        r = subprocess.run(["systemctl", "--user", "is-enabled", self.cfg.service_name],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() == "enabled"

    def _svc_action(self, action: str):
        w = ServiceControlWorker(action, self.cfg.service_name)
        w.done.connect(lambda ok, msg: self._refresh_status())
        w.start()

    def _toggle_autostart(self, enabled: bool):
        subprocess.run(
            ["systemctl", "--user", "enable" if enabled else "disable", self.cfg.service_name],
            capture_output=True, timeout=5,
        )

    def _check_update(self):
        url = self._update_url.text().strip()
        if not url:
            self._check_result.setText(t("status_no_url"))
            return
        self._check_btn.setEnabled(False)
        self._check_result.setText(t("checking"))
        self._update_checker = UpdateChecker(url)
        self._update_checker.update_available.connect(self._on_update_found)
        self._update_checker.up_to_date.connect(lambda v: self._on_check_done(True, t("update_checker_ok", v=v)))
        self._update_checker.check_failed.connect(lambda e: self._on_check_done(False, e))
        self._update_checker.start()

    def _on_update_found(self, remote: str, changelog: dict):
        self._check_btn.setEnabled(True)
        self._check_result.setText(f'<span style="color:{self._C_BLUE}">{t("update_avail_label", v=remote)}</span>')
        dlg = UpdateDialog(__version__, remote, changelog, self)
        dlg.exec()

    def _on_check_done(self, ok: bool, msg: str):
        self._check_btn.setEnabled(True)
        c = self._C_GREEN if ok else self._C_RED
        self._check_result.setText(f'<span style="color:{c}">{msg}</span>')

    def _update_lwe(self):
        if not ENGINE_DIR.exists():
            self._lwe_log.show()
            self._lwe_log.append(t("lwe_no_repo"))
            return
        self._lwe_btn.setEnabled(False)
        self._lwe_log.show()
        self._lwe_log.clear()
        self._lwe_worker = UpdateLWEWorker(self.cfg.container, str(ENGINE_DIR))
        self._lwe_worker.output_line.connect(self._lwe_log.append)
        self._lwe_worker.done.connect(self._on_lwe_done)
        self._lwe_worker.start()

    def _on_lwe_done(self, ok: bool, msg: str):
        self._lwe_btn.setEnabled(True)
        self._lwe_log.append(("✓ " if ok else "✗ ") + msg)
        if ok:
            self._check_lwe_status()

    def _check_lwe_status(self):
        self._lwe_check_btn.setEnabled(False)
        self._lwe_local_lbl.setText(t("checking"))
        self._lwe_checker = LWEVersionChecker(self.cfg)
        self._lwe_checker.finished.connect(self._on_lwe_status)
        self._lwe_checker.start()

    def _on_lwe_status(self, status: LWEStatus):
        self._lwe_check_btn.setEnabled(True)
        if status.local_commit:
            self._lwe_local_lbl.setText(
                f"<code>{status.local_commit}</code>"
                f"<span style='color:{self._C_MUTED}'> ({status.local_date})</span>"
            )
        else:
            self._lwe_local_lbl.setText(f'<span style="color:{self._C_RED}">{t("lwe_not_found")}</span>')
        if status.remote_commit != "?":
            self._lwe_remote_lbl.setText(
                f"<code>{status.remote_commit}</code>"
                f"<span style='color:{self._C_MUTED}'> ({status.remote_date})</span>"
            )
        else:
            self._lwe_remote_lbl.setText(f'<span style="color:{self._C_MUTED}">{t("lwe_unreachable")}</span>')
        if status.remote_commit == "?":
            self._lwe_upd_lbl.setText(f'<span style="color:{self._C_MUTED}">{t("lwe_unknown")}</span>')
            self._lwe_btn.setEnabled(False)
        elif status.up_to_date:
            self._lwe_upd_lbl.setText(f'<span style="color:{self._C_GREEN}">{t("lwe_up_to_date")}</span>')
            self._lwe_btn.setEnabled(False)
        else:
            self._lwe_upd_lbl.setText(
                f'<span style="color:{self._C_BLUE}">'
                f'{t("lwe_update_avail", commit=status.remote_commit, date=status.remote_date)}</span>'
            )
            self._lwe_btn.setEnabled(True)
        if status.compatible:
            self._lwe_compat_lbl.setText(f'<span style="color:{self._C_GREEN}">{t("lwe_compatible")}</span>')
        else:
            missing = ", ".join(status.missing_flags)
            self._lwe_compat_lbl.setText(
                f'<span style="color:{self._C_RED}">{t("lwe_incompatible", flags=missing)}</span>'
            )

    def _guide(self) -> str:
        lines = []
        if IS_ATOMIC:
            lines += [
                "=== Atomic Desktop (Bazzite/Silverblue) ===\n",
                "Empfohlener Modus: distrobox\n",
                "1. Container einrichten (einmalig):",
                "   distrobox create --name wallpaperengine \\",
                "     --image registry.fedoraproject.org/fedora:42 --nvidia\n",
                "2. Dependencies im Container installieren:",
                "   distrobox enter wallpaperengine -- sudo dnf install -y \\",
                "     cmake gcc-c++ glm-devel glfw-devel zlib-devel \\",
                "     pulseaudio-libs-devel lz4-devel ffmpeg-devel SDL2-devel\n",
                "3. Binary bauen:",
                "   → Setup-Assistent → Binary-Seite → 'Jetzt bauen'",
                f"   (Zielort: {ENGINE_DIR}/build/output/linux-wallpaperengine)",
            ]
        else:
            if "fedora" in DISTRO_ID:
                pkg = "sudo dnf install -y cmake gcc-c++ glm-devel glfw-devel zlib-devel pulseaudio-libs-devel lz4-devel ffmpeg-devel SDL2-devel"
            elif "ubuntu" in DISTRO_ID or "debian" in DISTRO_ID:
                pkg = "sudo apt install -y cmake g++ libglm-dev libglfw3-dev zlib1g-dev libpulse-dev libfreeimage-dev liblz4-dev libavcodec-dev libsdl2-dev"
            elif "arch" in DISTRO_ID:
                pkg = "sudo pacman -S cmake glm glfw-x11 zlib libpulse freeimage lz4 ffmpeg sdl2"
            else:
                pkg = "# Pakete für deine Distro installieren"
            lines += [
                f"=== {DISTRO_NAME} ===\n",
                f"1. {pkg}\n",
                f"2. cd {ENGINE_DIR.parent} && git clone https://github.com/Almamu/linux-wallpaperengine",
                f"   cd {ENGINE_DIR} && cmake -B build && cmake --build build -j$(nproc)\n",
            ]
        return "\n".join(lines)

    def _save(self):
        new_lang = self._language.currentData()
        lang_changed = new_lang != self.cfg.language

        self.cfg.mode             = self._mode.currentText()
        self.cfg.container        = self._container.text().strip()
        self.cfg.binary           = self._binary.text().strip()
        self.cfg.assets_dir       = self._assets.text().strip()
        self.cfg.custom_prefix    = self._custom_prefix.text().strip()
        self.cfg.steam_api_key    = self._steam_key.text().strip()
        self.cfg.update_url          = self._update_url.text().strip()
        self.cfg.fullscreen_pause    = self._fullscreen_pause.isChecked()
        self.cfg.disable_particles   = self._disable_particles.isChecked()
        self.cfg.disable_mouse       = self._disable_mouse.isChecked()
        self.cfg.no_audio_processing = self._no_audio_processing.isChecked()
        self.cfg.language            = new_lang
        self.cfg.save()
        self.saved.emit()
        self.accept()

        if lang_changed:
            btn = QMessageBox.question(
                None,
                t("restart_required"),
                t("restart_required_body"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if btn == QMessageBox.StandardButton.Yes:
                os.execv(sys.executable, [sys.executable] + sys.argv)
