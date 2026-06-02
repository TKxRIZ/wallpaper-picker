import subprocess

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from ..config import Config, validate_setup, lwe_quick_compat_check
from ..models import Wallpaper, MonitorConfig


class UpdateBanner(QFrame):
    show_dialog = Signal()

    def __init__(self, remote_version: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet("UpdateBanner{background:#1e3a5f;border-radius:6px;margin:4px 4px 0 4px;}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        icon = QLabel("↑")
        icon.setStyleSheet("color:#89b4fa; font-size:16px; font-weight:bold;")
        msg = QLabel(f"Update verfügbar — Version <b>{remote_version}</b>")
        msg.setStyleSheet("color:#cdd6f4;")

        update_btn = QPushButton("Aktualisieren")
        update_btn.setStyleSheet(
            "background:#89b4fa;color:#1e1e2e;font-weight:bold;border-radius:4px;padding:4px 12px;"
        )
        update_btn.setFixedHeight(28)
        update_btn.clicked.connect(self.show_dialog)

        dismiss_btn = QPushButton("✕")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.setStyleSheet("background:transparent;color:#585b70;font-size:12px;")
        dismiss_btn.clicked.connect(self.hide)

        layout.addWidget(icon)
        layout.addWidget(msg, stretch=1)
        layout.addWidget(update_btn)
        layout.addWidget(dismiss_btn)


class SetupBanner(QFrame):
    open_settings = Signal()
    run_wizard    = Signal()

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self._refresh(cfg)

    def _refresh(self, cfg: Config):
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        issues = validate_setup(cfg) + lwe_quick_compat_check(cfg)
        if not issues:
            self.setVisible(False)
            return

        self.setVisible(True)
        self.setStyleSheet(
            "SetupBanner{background:#7c2d12;border-radius:6px;margin:4px 4px 0 4px;}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        icon = QLabel("⚠")
        icon.setStyleSheet("color:#fbbf24; font-size:16px;")

        first  = issues[0]
        suffix = f" (+{len(issues)-1} weitere)" if len(issues) > 1 else ""
        msg    = QLabel(f"{first}{suffix}")
        msg.setStyleSheet("color:#fef3c7; font-weight:bold;")
        msg.setToolTip("\n".join(issues))

        wizard_btn = QPushButton("Setup-Assistent öffnen")
        wizard_btn.setStyleSheet(
            "background:#fbbf24;color:#1c1917;font-weight:bold;border-radius:4px;padding:4px 12px;"
        )
        wizard_btn.setFixedHeight(28)
        wizard_btn.clicked.connect(self.run_wizard)

        layout.addWidget(icon)
        layout.addWidget(msg, stretch=1)
        layout.addWidget(wizard_btn)

    def update_cfg(self, cfg: Config):
        self._refresh(cfg)


class ServiceStatusWidget(QWidget):
    def __init__(self, service_name: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)
        self._dot     = QLabel("●")
        self._lbl     = QLabel("…")
        self._lbl.setStyleSheet("color:#aaa; font-size:11px;")
        self._service = service_name
        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        QTimer(self, timeout=self.refresh, interval=5000).start()
        self.refresh()

    def refresh(self):
        r = subprocess.run(
            ["systemctl", "--user", "is-active", self._service],
            capture_output=True, text=True, timeout=3,
        )
        s = r.stdout.strip()
        if s == "active":
            self._dot.setStyleSheet("color:#4caf50; font-size:10px;")
            self._lbl.setText("Service aktiv")
        elif s == "inactive":
            self._dot.setStyleSheet("color:#888; font-size:10px;")
            self._lbl.setText("Service inaktiv")
        else:
            self._dot.setStyleSheet("color:#f44336; font-size:10px;")
            self._lbl.setText(f"Service: {s or 'unbekannt'}")


class MonitorPanel(QGroupBox):
    def __init__(self, monitors: list[str], configs: list[MonitorConfig], parent=None):
        super().__init__("Monitor-Zuordnung", parent)
        self._monitors = monitors
        self._configs: dict[str, str] = {mc.name: mc.wallpaper_id for mc in configs}
        self._active   = monitors[0] if monitors else ""
        self._wallpapers: dict[str, Wallpaper] = {}
        self._rows: dict[str, tuple[QPushButton, QLabel]] = {}

        layout = QVBoxLayout(self)
        hint = QLabel("Monitor wählen → Wallpaper klicken → Anwenden")
        hint.setStyleSheet("color:#888; font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for mon in monitors:
            row = QHBoxLayout()
            btn = QPushButton(mon)
            btn.setCheckable(True)
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _, m=mon: self._select(m))
            lbl = QLabel(self._display(mon))
            lbl.setStyleSheet("color:#aaa;")
            row.addWidget(btn)
            row.addWidget(lbl, stretch=1)
            layout.addLayout(row)
            self._rows[mon] = (btn, lbl)

        if self._active:
            self._rows[self._active][0].setChecked(True)

    def _display(self, mon: str) -> str:
        wp_id = self._configs.get(mon, "")
        if not wp_id:
            return "— kein Wallpaper"
        wp = self._wallpapers.get(wp_id)
        return wp.title if wp else wp_id

    def _select(self, mon: str):
        for m, (btn, _) in self._rows.items():
            btn.setChecked(m == mon)
        self._active = mon

    def register_wallpapers(self, wallpapers: list[Wallpaper]):
        self._wallpapers = {wp.id: wp for wp in wallpapers}
        for mon, (_, lbl) in self._rows.items():
            lbl.setText(self._display(mon))

    def assign_wallpaper(self, wp_id: str):
        if not self._active:
            return
        self._configs[self._active] = wp_id
        self._rows[self._active][1].setText(self._display(self._active))

    def get_configs(self) -> list[MonitorConfig]:
        return [MonitorConfig(name=m, wallpaper_id=self._configs.get(m, "")) for m in self._monitors]
