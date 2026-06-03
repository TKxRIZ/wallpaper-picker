import json
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGroupBox, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QStatusBar, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from ..config import Config, validate_setup
from ..constants import CONFIG_PATH, UPDATE_STATE_PATH
from ..engine import get_monitors, parse_service, load_installed, load_available_ids
from ..i18n import t
from ..models import WallpaperConfig
from ..workers import ApplyWorker, SteamMetaWorker, UpdateChecker, QThread
from .panels import SetupBanner, UpdateBanner, ServiceStatusWidget, MonitorPanel
from .tabs import InstalledTab, AvailableTab
from .dialogs import UpdateDialog, SettingsDialog, WallpaperConfigDialog
from .wizard import SetupWizard


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.resize(1150, 720)

        self._cfg          = Config.load()
        self._installed    = load_installed()
        self._svc_configs, _ = parse_service()
        self._monitors     = get_monitors()
        self._workers: list[QThread] = []
        self._meta_worker: Optional[SteamMetaWorker] = None

        self._build_ui()
        self._init_selections()

        if not CONFIG_PATH.exists() or validate_setup(self._cfg):
            QTimer.singleShot(200, self._run_wizard)

        QTimer.singleShot(500, self._check_tray_update_state)

        if self._cfg.update_url and (time.time() - self._cfg.last_update_check > 86400):
            self._cfg.last_update_check = time.time()
            self._cfg.save()
            QTimer.singleShot(3000, self._silent_update_check)

    def _build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        title_lbl = QLabel(f"  {t('app_title')}  ")
        title_lbl.setStyleSheet("font-weight:bold;")
        toolbar.addWidget(title_lbl)
        toolbar.addSeparator()

        wizard_btn = QPushButton(t("btn_wizard"))
        wizard_btn.clicked.connect(self._run_wizard)
        self._update_check_btn = QPushButton(t("btn_updates"))
        self._update_check_btn.clicked.connect(self._manual_update_check)
        settings_btn = QPushButton(t("btn_settings"))
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(wizard_btn)
        toolbar.addWidget(self._update_check_btn)
        toolbar.addWidget(settings_btn)

        central = QWidget()
        outer   = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setCentralWidget(central)

        self._setup_banner = SetupBanner(self._cfg)
        self._setup_banner.run_wizard.connect(self._run_wizard)
        outer.addWidget(self._setup_banner)

        self._update_banner = UpdateBanner("")
        self._update_banner.hide()
        self._update_banner.show_dialog.connect(self._show_update_dialog)
        outer.addWidget(self._update_banner)

        content = QWidget()
        root    = QHBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(content, stretch=1)

        self._tabs = QTabWidget()
        self._installed_tab = InstalledTab(self._installed)
        if hasattr(self._installed_tab, "grid"):
            self._installed_tab.wallpaper_selected.connect(self._on_wp_selected)
            self._installed_tab.grid.configure.connect(self._open_wp_config)
        self._tabs.addTab(self._installed_tab, t("tab_installed", n=len(self._installed)))

        self._available_tab = AvailableTab()
        self._tabs.addTab(self._available_tab, t("tab_available"))
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, stretch=1)

        right = QWidget()
        right.setFixedWidth(300)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        self._preview_img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._preview_img.setFixedHeight(176)
        self._preview_img.setStyleSheet(
            "background:#11111b; border-radius:8px; color:#45475a; font-size:12px;"
        )
        self._preview_img.setText(t("preview_hint"))
        self._preview_img.setWordWrap(True)
        rl.addWidget(self._preview_img)

        self._preview_title = QLabel("")
        self._preview_title.setWordWrap(True)
        self._preview_title.setStyleSheet("font-weight:bold; padding:2px 4px; font-size:12px;")
        rl.addWidget(self._preview_title)

        self._preview_id = QLabel("")
        self._preview_id.setStyleSheet("color:#585b70; font-size:10px; padding:0 4px 4px 4px;")
        rl.addWidget(self._preview_id)

        self._monitor_panel = MonitorPanel(self._monitors, self._svc_configs)
        self._monitor_panel.register_wallpapers(self._installed)
        rl.addWidget(self._monitor_panel)

        fps_box  = QGroupBox(t("group_playback"))
        fps_form = QFormLayout(fps_box)
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(self._cfg.fps)
        fps_form.addRow(t("label_fps"), self._fps_spin)
        rl.addWidget(fps_box)

        rl.addStretch()

        self._apply_btn = QPushButton(t("btn_apply"))
        self._apply_btn.setFixedHeight(42)
        self._apply_btn.clicked.connect(self._apply)
        rl.addWidget(self._apply_btn)

        root.addWidget(right)

        self._status             = QStatusBar()
        self._svc_status_widget  = ServiceStatusWidget(self._cfg.service_name)
        self._status.addPermanentWidget(self._svc_status_widget)
        self.setStatusBar(self._status)

    def _init_selections(self):
        if not hasattr(self._installed_tab, "grid"):
            return
        for mc in self._svc_configs:
            if mc.wallpaper_id:
                self._installed_tab.grid.set_selected(mc.wallpaper_id)
                break

    def _on_tab_changed(self, idx: int):
        if idx == 1 and self._meta_worker is None:
            ids = load_available_ids()
            self._tabs.setTabText(1, t("tab_available_n", n=len(ids)))
            self._available_tab.start_loading(ids)
            self._meta_worker = SteamMetaWorker(ids, self._cfg.steam_api_key)
            self._meta_worker.batch_ready.connect(self._available_tab.on_batch)
            self._meta_worker.start()
            self._workers.append(self._meta_worker)

    def _on_wp_selected(self, wp_id: str):
        self._monitor_panel.assign_wallpaper(wp_id)
        wp = next((w for w in self._installed if w.id == wp_id), None)
        if not wp:
            return
        self._preview_title.setText(wp.title)
        self._preview_id.setText(t("label_id", id=wp.id))
        p = wp.preview_path
        if p:
            pix = QPixmap(str(p))
            if not pix.isNull():
                pix = pix.scaled(290, 176,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
                self._preview_img.setPixmap(pix)
                return
        self._preview_img.clear()
        self._preview_img.setText(t("preview_no_image"))

    def _apply(self):
        issues = validate_setup(self._cfg)
        if issues:
            QMessageBox.warning(self, t("dlg_setup_incomplete"),
                                t("dlg_setup_incomplete_body", issues="\n• ".join(issues)))
            return

        configs = self._monitor_panel.get_configs()
        if not any(mc.wallpaper_id for mc in configs):
            self._status.showMessage(t("status_no_wallpaper"))
            return

        self._cfg.fps = self._fps_spin.value()
        self._cfg.save()
        self._apply_btn.setEnabled(False)
        self._status.showMessage(t("status_applying"))

        active_ids = [mc.wallpaper_id for mc in configs if mc.wallpaper_id]
        wp_cfg = WallpaperConfig.merge([WallpaperConfig.load(i) for i in active_ids]) if active_ids else None

        worker = ApplyWorker(self._cfg, configs, self._fps_spin.value(), wp_cfg)
        worker.done.connect(self._on_apply_done)
        worker.start()
        self._workers.append(worker)

    def _on_apply_done(self, ok: bool, msg: str):
        self._apply_btn.setEnabled(True)
        self._status.showMessage(msg)
        self._svc_status_widget.refresh()
        if ok:
            configs = self._monitor_panel.get_configs()
            for mc in configs:
                if mc.wallpaper_id:
                    recents: list = self._cfg.recent_wallpapers
                    if mc.wallpaper_id in recents:
                        recents.remove(mc.wallpaper_id)
                    recents.insert(0, mc.wallpaper_id)
                    self._cfg.recent_wallpapers = recents[:10]
                    self._cfg.save()
                    break

    def _run_wizard(self):
        wizard = SetupWizard(self._cfg, self)
        wizard.setup_complete.connect(self._on_setup_complete)
        wizard.exec()

    def _check_tray_update_state(self):
        try:
            state = json.loads(UPDATE_STATE_PATH.read_text())
            if time.time() - state.get("checked_at", 0) > 90000:
                return
            picker = state.get("picker", {})
            latest = picker.get("latest", "")
            if picker.get("has_update") and latest != self._cfg.dismissed_update:
                self._on_update_available(latest, {})
        except Exception:
            pass

    def _silent_update_check(self):
        if not self._cfg.update_url:
            return
        self._update_checker = UpdateChecker(self._cfg.update_url)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.check_failed.connect(lambda _: None)
        self._update_checker.start()

    def _manual_update_check(self):
        if not self._cfg.update_url:
            self._status.showMessage(t("status_no_url"), 4000)
            return
        self._update_check_btn.setEnabled(False)
        self._update_check_btn.setText(t("btn_checking"))
        checker = UpdateChecker(self._cfg.update_url)
        checker.update_available.connect(self._on_update_available)
        checker.up_to_date.connect(lambda v: self._on_check_done(t("status_up_to_date", v=v)))
        checker.check_failed.connect(lambda e: self._on_check_done(t("status_error", e=e)))
        checker.start()
        self._workers.append(checker)

    def _on_check_done(self, msg: str):
        self._update_check_btn.setEnabled(True)
        self._update_check_btn.setText(t("btn_updates"))
        self._status.showMessage(msg, 5000)

    def _on_update_available(self, remote: str, changelog: dict):
        self._pending_update = (remote, changelog)
        self._update_check_btn.setEnabled(True)
        self._update_check_btn.setText(t("btn_updates"))
        self._update_check_btn.setStyleSheet(
            "background:#1e3a5f;border:1px solid #89b4fa;border-radius:5px;padding:4px 10px;"
        )
        self._update_banner.deleteLater()
        self._update_banner = UpdateBanner(remote, self)
        self._update_banner.show_dialog.connect(self._show_update_dialog)
        self._update_banner.dismissed.connect(self._on_banner_dismissed)
        outer = self.centralWidget().layout()
        outer.insertWidget(1, self._update_banner)

    def _on_banner_dismissed(self, version: str):
        self._cfg.dismissed_update = version
        self._cfg.save()
        self._update_check_btn.setStyleSheet("")

    def _show_update_dialog(self):
        if not hasattr(self, "_pending_update"):
            return
        from .. import __version__
        remote, changelog = self._pending_update
        dlg = UpdateDialog(__version__, remote, changelog, self)
        dlg.exec()

    def _open_wp_config(self, wp_id: str):
        wp = next((w for w in self._installed if w.id == wp_id), None)
        title = wp.title if wp else wp_id
        dlg = WallpaperConfigDialog(wp_id, title, self._cfg, self)
        if dlg.exec():
            if hasattr(self._installed_tab, "grid"):
                self._installed_tab.grid.refresh_card(wp_id)

    def _open_settings(self):
        dlg = SettingsDialog(self._cfg, self)
        dlg.saved.connect(self._on_setup_complete)
        dlg.exec()

    def _on_setup_complete(self):
        self._fps_spin.setValue(self._cfg.fps)
        self._setup_banner.update_cfg(self._cfg)
        self._status.showMessage(t("status_config_saved"))

    def closeEvent(self, event):
        for w in self._workers:
            if w.isRunning():
                w.quit()
                w.wait(2000)
        event.accept()
