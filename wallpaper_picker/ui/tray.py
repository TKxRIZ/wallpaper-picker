from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import random as _random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..config import Config
from ..models import MonitorConfig
from ..workers import ApplyWorker, ServiceControlWorker

if TYPE_CHECKING:
    from .main_window import MainWindow


def _make_tray_icon() -> QIcon:
    icon = QIcon.fromTheme("preferences-desktop-wallpaper")
    if not icon.isNull():
        return icon
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setBrush(QColor("#89b4fa"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(0, 0, 32, 32, 6, 6)
    p.setPen(QColor("#1e1e2e"))
    p.setFont(QFont("Sans", 14, QFont.Weight.Bold))
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "W")
    p.end()
    return QIcon(pix)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, app: QApplication, win: MainWindow):
        super().__init__(_make_tray_icon(), app)
        self._app = app
        self._win = win
        self.setToolTip("Wallpaper Engine – Linux")
        self.activated.connect(self._on_activate)
        self._svc_timer = QTimer(self)
        self._svc_timer.timeout.connect(self._refresh_svc)
        self._svc_timer.start(10_000)
        self.rebuild_menu()

    def rebuild_menu(self):
        from PySide6.QtGui import QAction
        menu      = QMenu()
        installed = {wp.id: wp for wp in self._win._installed}
        recents   = self._win._cfg.recent_wallpapers

        valid_recents = [r for r in recents if r in installed]
        if valid_recents:
            menu.addSection("Zuletzt verwendet")
            for wp_id in valid_recents[:5]:
                wp  = installed[wp_id]
                act = QAction(wp.title, menu)
                if wp.preview_path:
                    pix = QPixmap(str(wp.preview_path)).scaled(
                        22, 22,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    act.setIcon(QIcon(pix))
                act.triggered.connect(lambda checked=False, id=wp_id: self._apply(id))
                menu.addAction(act)
            menu.addSeparator()

        rand_act = QAction("🎲  Zufälliges Wallpaper", menu)
        rand_act.triggered.connect(self._apply_random)
        rand_act.setEnabled(bool(self._win._installed))
        menu.addAction(rand_act)
        menu.addSeparator()

        self._svc_label_act = QAction("…", menu)
        self._svc_label_act.setEnabled(False)
        menu.addAction(self._svc_label_act)

        toggle_act = QAction("Service starten / stoppen", menu)
        toggle_act.triggered.connect(self._toggle_svc)
        menu.addAction(toggle_act)
        menu.addSeparator()

        open_act = QAction("Öffnen", menu)
        open_act.triggered.connect(self._show)
        menu.addAction(open_act)

        quit_act = QAction("Beenden", menu)
        quit_act.triggered.connect(self._quit)
        menu.addAction(quit_act)

        self.setContextMenu(menu)
        self._refresh_svc()

    def _on_activate(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show()

    def _show(self):
        self._win.show()
        self._win.raise_()
        self._win.activateWindow()

    def _apply(self, wp_id: str):
        configs = self._win._monitor_panel.get_configs()
        if configs:
            configs[0].wallpaper_id = wp_id
        else:
            configs = [MonitorConfig(name=self._win._monitors[0], wallpaper_id=wp_id)]
        worker = ApplyWorker(self._win._cfg, configs, self._win._cfg.fps)
        worker.done.connect(lambda ok, msg: self.showMessage(
            "Wallpaper Engine",
            msg,
            QSystemTrayIcon.MessageIcon.Information if ok else QSystemTrayIcon.MessageIcon.Warning,
            3000,
        ))
        worker.start()
        self._win._workers.append(worker)

    def _apply_random(self):
        if self._win._installed:
            self._apply(_random.choice(self._win._installed).id)

    def _toggle_svc(self):
        r = subprocess.run(
            ["systemctl", "--user", "is-active", self._win._cfg.service_name],
            capture_output=True, text=True, timeout=3,
        )
        action = "stop" if r.stdout.strip() == "active" else "start"
        w = ServiceControlWorker(action, self._win._cfg.service_name)
        w.done.connect(lambda *_: self._refresh_svc())
        w.start()

    def _refresh_svc(self):
        if not hasattr(self, "_svc_label_act"):
            return
        r = subprocess.run(
            ["systemctl", "--user", "is-active", self._win._cfg.service_name],
            capture_output=True, text=True, timeout=3,
        )
        active = r.stdout.strip() == "active"
        self._svc_label_act.setText("● Service aktiv" if active else "○ Service inaktiv")

    def _quit(self):
        for w in self._win._workers:
            if w.isRunning():
                w.quit()
                w.wait(2000)
        self._app.quit()
