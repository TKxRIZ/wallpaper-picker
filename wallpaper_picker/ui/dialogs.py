import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__
from ..constants import ENGINE_DIR, IS_ATOMIC, DISTRO_NAME, DISTRO_ID, _vtuple
from ..config import Config
from ..workers import (
    AppUpdateWorker, UpdateChecker, TestBinaryWorker,
    ServiceControlWorker, UpdateLWEWorker, LWEVersionChecker, BuildWorker,
)
from ..models import LWEStatus


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
        self.setWindowTitle("Update verfügbar")
        self.resize(540, 400)
        self._worker: Optional[AppUpdateWorker] = None
        self._build_ui(current, remote, remote_changelog)

    def _build_ui(self, current: str, remote: str, changelog: dict):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b style='font-size:14px'>Update verfügbar</b><br><br>"
            f"Installiert: &nbsp;<code>{current}</code><br>"
            f"Verfügbar: &nbsp;&nbsp;<code style='color:#89b4fa'>{remote}</code>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        new_entries = {v: items for v, items in changelog.items() if _vtuple(v) > _vtuple(current)}
        if new_entries:
            layout.addWidget(QLabel("<b>Was ist neu:</b>"))
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
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setText("Jetzt aktualisieren")
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
            self._log.append("App wird neu gestartet…")
            QTimer.singleShot(1500, self._restart)
        else:
            self._btns.setEnabled(True)

    def _restart(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)


class SettingsDialog(QDialog):
    saved = Signal()

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Einstellungen")
        self.resize(640, 520)
        self._test_worker: Optional[TestBinaryWorker] = None
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._refresh_log)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._engine_tab(), "Engine")
        tabs.addTab(self._service_tab(), "Service")
        tabs.addTab(self._updates_tab(), "Updates")
        tabs.addTab(self._info_tab(), "Info / Setup")
        tabs.currentChanged.connect(self._on_tab)
        root.addWidget(tabs)
        self._tabs = tabs

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _engine_tab(self) -> QWidget:
        w    = QWidget()
        form = QFormLayout(w)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._mode = QComboBox()
        self._mode.addItems(["distrobox", "direct", "toolbox", "custom"])
        self._mode.setCurrentText(self.cfg.mode)
        self._mode.currentTextChanged.connect(self._update_mode_vis)
        form.addRow("Ausführungsmodus:", self._mode)

        self._container = QLineEdit(self.cfg.container)
        form.addRow("Container-Name:", self._container)

        bin_row = QHBoxLayout()
        self._binary = QLineEdit(self.cfg.binary)
        b1 = QPushButton("…")
        b1.setFixedWidth(30)
        b1.clicked.connect(lambda: self._browse_file(self._binary))
        bin_row.addWidget(self._binary)
        bin_row.addWidget(b1)
        form.addRow("Binary-Pfad:", bin_row)

        ast_row = QHBoxLayout()
        self._assets = QLineEdit(self.cfg.assets_dir)
        b2 = QPushButton("…")
        b2.setFixedWidth(30)
        b2.clicked.connect(lambda: self._browse_dir(self._assets))
        ast_row.addWidget(self._assets)
        ast_row.addWidget(b2)
        form.addRow("Assets-Verzeichnis:", ast_row)

        self._custom_prefix = QLineEdit(self.cfg.custom_prefix)
        form.addRow("Custom Prefix:", self._custom_prefix)

        key_row = QHBoxLayout()
        self._steam_key = QLineEdit(self.cfg.steam_api_key)
        self._steam_key.setPlaceholderText("Optional — verbessert Rate-Limiting beim Laden des Verfügbar-Tabs")
        self._steam_key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        key_link = QLabel('<a href="https://steamcommunity.com/dev/apikey">Key holen</a>')
        key_link.setOpenExternalLinks(True)
        key_row.addWidget(self._steam_key)
        key_row.addWidget(key_link)
        form.addRow("Steam API-Key:", key_row)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Binary testen")
        self._test_btn.clicked.connect(self._test_binary)
        self._test_out = QLabel("")
        self._test_out.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_out, stretch=1)
        form.addRow("", test_row)

        self._update_mode_vis(self.cfg.mode)
        return w

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
        c     = "#4caf50" if ok else "#f44336"
        label = "OK" if ok else "FEHLER"
        self._test_out.setText(f'<span style="color:{c}">{label}</span>')
        self._test_out.setToolTip(msg)

    def _service_tab(self) -> QWidget:
        w      = QWidget()
        layout = QVBoxLayout(w)

        status_row = QHBoxLayout()
        self._svc_status = QLabel("…")
        self._svc_status.setStyleSheet("font-weight:bold;")
        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self._svc_status)
        status_row.addStretch()
        layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        for label, action in [("Start", "start"), ("Stop", "stop"), ("Restart", "restart")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, a=action: self._svc_action(a))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._autostart = QCheckBox("Autostart aktivieren (systemd enable)")
        self._autostart.setChecked(self._is_enabled())
        self._autostart.toggled.connect(self._toggle_autostart)
        layout.addWidget(self._autostart)

        layout.addWidget(QLabel("Log (letzte 40 Zeilen):"))
        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Monospace", 9))
        layout.addWidget(self._log_view, stretch=1)

        return w

    def _on_tab(self, idx: int):
        if idx == 1:
            self._refresh_status()
            self._refresh_log()
            self._log_timer.start(3000)
        else:
            self._log_timer.stop()

    def _refresh_status(self):
        r = subprocess.run(["systemctl", "--user", "is-active", self.cfg.service_name],
                           capture_output=True, text=True, timeout=3)
        s = r.stdout.strip()
        c = "#4caf50" if s == "active" else "#f44336"
        self._svc_status.setText(f'<span style="color:{c}">{s}</span>')

    def _refresh_log(self):
        self._refresh_status()
        r = subprocess.run(
            ["journalctl", "--user", "-u", self.cfg.service_name, "-n", "40", "--no-pager"],
            capture_output=True, text=True, timeout=5,
        )
        self._log_view.setPlainText(r.stdout or "(kein Log)")
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

    def _updates_tab(self) -> QWidget:
        w      = QWidget()
        layout = QVBoxLayout(w)

        app_box  = QGroupBox("App-Update (wallpaper-picker)")
        app_form = QFormLayout(app_box)

        self._update_url = QLineEdit(self.cfg.update_url)
        self._update_url.setPlaceholderText(
            "https://raw.githubusercontent.com/USER/REPO/main/wallpaper_picker/__init__.py"
        )
        app_form.addRow("Update-URL:", self._update_url)

        ver_row = QHBoxLayout()
        self._ver_label   = QLabel(f"Installiert: <b>{__version__}</b>")
        self._check_btn   = QPushButton("Jetzt prüfen")
        self._check_btn.clicked.connect(self._check_update)
        self._check_result = QLabel("")
        ver_row.addWidget(self._ver_label)
        ver_row.addWidget(self._check_btn)
        ver_row.addWidget(self._check_result, stretch=1)
        app_form.addRow("", ver_row)

        layout.addWidget(app_box)

        lwe_box    = QGroupBox("linux-wallpaperengine")
        lwe_layout = QVBoxLayout(lwe_box)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        self._lwe_local_lbl  = QLabel("…")
        self._lwe_remote_lbl = QLabel("…")
        self._lwe_compat_lbl = QLabel("…")
        self._lwe_upd_lbl    = QLabel("…")
        grid.addWidget(QLabel("Installiert:"),  0, 0); grid.addWidget(self._lwe_local_lbl,  0, 1)
        grid.addWidget(QLabel("Verfügbar:"),    1, 0); grid.addWidget(self._lwe_remote_lbl, 1, 1)
        grid.addWidget(QLabel("Update:"),       2, 0); grid.addWidget(self._lwe_upd_lbl,    2, 1)
        grid.addWidget(QLabel("Kompatibel:"),   3, 0); grid.addWidget(self._lwe_compat_lbl, 3, 1)
        lwe_layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self._lwe_check_btn = QPushButton("Status prüfen")
        self._lwe_check_btn.clicked.connect(self._check_lwe_status)
        self._lwe_btn = QPushButton("Aktualisieren")
        self._lwe_btn.clicked.connect(self._update_lwe)
        self._lwe_btn.setEnabled(False)
        btn_row.addWidget(self._lwe_check_btn)
        btn_row.addWidget(self._lwe_btn)
        btn_row.addStretch()
        lwe_layout.addLayout(btn_row)

        self._lwe_log = QTextEdit()
        self._lwe_log.setReadOnly(True)
        self._lwe_log.setFont(QFont("Monospace", 9))
        self._lwe_log.setFixedHeight(120)
        self._lwe_log.hide()
        lwe_layout.addWidget(self._lwe_log)

        layout.addWidget(lwe_box)
        self._lwe_checker: Optional[LWEVersionChecker] = None

        layout.addWidget(QLabel(
            "<small>Update-URL: Raw-URL zur wallpaper_picker/__init__.py auf GitHub.</small>"
        ))
        layout.addStretch()
        return w

    def _check_update(self):
        url = self._update_url.text().strip()
        if not url:
            self._check_result.setText("Keine URL konfiguriert.")
            return
        self._check_btn.setEnabled(False)
        self._check_result.setText("Prüfe…")
        self._update_checker = UpdateChecker(url)
        self._update_checker.update_available.connect(self._on_update_found)
        self._update_checker.up_to_date.connect(lambda v: self._on_check_done(True, f"Bereits aktuell (v{v}) ✓"))
        self._update_checker.check_failed.connect(lambda e: self._on_check_done(False, e))
        self._update_checker.start()

    def _on_update_found(self, remote: str, changelog: dict):
        self._check_btn.setEnabled(True)
        self._check_result.setText(f'<span style="color:#89b4fa">v{remote} verfügbar</span>')
        dlg = UpdateDialog(__version__, remote, changelog, self)
        dlg.exec()

    def _on_check_done(self, ok: bool, msg: str):
        self._check_btn.setEnabled(True)
        c = "#4caf50" if ok else "#f44336"
        self._check_result.setText(f'<span style="color:{c}">{msg}</span>')

    def _update_lwe(self):
        if not ENGINE_DIR.exists():
            self._lwe_log.show()
            self._lwe_log.append("Repo nicht gefunden — bitte zuerst bauen (Setup-Assistent).")
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
        self._lwe_local_lbl.setText("Wird geprüft…")
        self._lwe_checker = LWEVersionChecker(self.cfg)
        self._lwe_checker.finished.connect(self._on_lwe_status)
        self._lwe_checker.start()

    def _on_lwe_status(self, status: LWEStatus):
        self._lwe_check_btn.setEnabled(True)

        if status.local_commit:
            self._lwe_local_lbl.setText(f"<code>{status.local_commit}</code>  ({status.local_date})")
        else:
            self._lwe_local_lbl.setText('<span style="color:#f38ba8">nicht gefunden</span>')

        if status.remote_commit != "?":
            self._lwe_remote_lbl.setText(f"<code>{status.remote_commit}</code>  ({status.remote_date})")
        else:
            self._lwe_remote_lbl.setText('<span style="color:#888">nicht erreichbar</span>')

        if status.remote_commit == "?":
            self._lwe_upd_lbl.setText('<span style="color:#888">unbekannt</span>')
            self._lwe_btn.setEnabled(False)
        elif status.up_to_date:
            self._lwe_upd_lbl.setText('<span style="color:#a6e3a1">✓ Aktuell</span>')
            self._lwe_btn.setEnabled(False)
        else:
            self._lwe_upd_lbl.setText(
                f'<span style="color:#89b4fa">Update verfügbar → {status.remote_commit} ({status.remote_date})</span>'
            )
            self._lwe_btn.setEnabled(True)

        if status.compatible:
            self._lwe_compat_lbl.setText('<span style="color:#a6e3a1">✓ Kompatibel</span>')
        else:
            missing = ", ".join(status.missing_flags)
            self._lwe_compat_lbl.setText(f'<span style="color:#f38ba8">✗ Inkompatibel: {missing}</span>')

    def _info_tab(self) -> QWidget:
        w      = QWidget()
        layout = QVBoxLayout(w)

        ptype = "Atomic (Immutable)" if IS_ATOMIC else "Traditionell"
        layout.addWidget(self._info_row("Distro:", f"{DISTRO_NAME} ({ptype})"))

        b_ok = bool(self.cfg.binary) and Path(self.cfg.binary).exists()
        layout.addWidget(self._info_row("Binary:", self.cfg.binary or "nicht konfiguriert", ok=b_ok))

        a_ok = bool(self.cfg.assets_dir) and Path(self.cfg.assets_dir).is_dir()
        layout.addWidget(self._info_row("Assets:", self.cfg.assets_dir or "nicht konfiguriert", ok=a_ok))

        from ..constants import WORKSHOP_DIR
        wp_count = len(list(WORKSHOP_DIR.iterdir())) if WORKSHOP_DIR.exists() else 0
        layout.addWidget(self._info_row("Workshop:", f"{wp_count} Wallpapers lokal"))

        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("<b>Setup-Guide für dieses System:</b>"))

        guide = QTextEdit()
        guide.setReadOnly(True)
        guide.setFont(QFont("Monospace", 9))
        guide.setPlainText(self._guide())
        layout.addWidget(guide, stretch=1)
        return w

    def _info_row(self, label: str, value: str, ok: Optional[bool] = None) -> QWidget:
        w   = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(80)
        val = QLabel(value)
        val.setWordWrap(True)
        row.addWidget(lbl)
        row.addWidget(val, stretch=1)
        if ok is not None:
            ind = QLabel("✓" if ok else "✗")
            ind.setStyleSheet(f"color:{'#4caf50' if ok else '#f44336'}; font-weight:bold;")
            row.addWidget(ind)
        return w

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
        self.cfg.mode          = self._mode.currentText()
        self.cfg.container     = self._container.text().strip()
        self.cfg.binary        = self._binary.text().strip()
        self.cfg.assets_dir    = self._assets.text().strip()
        self.cfg.custom_prefix = self._custom_prefix.text().strip()
        self.cfg.steam_api_key = self._steam_key.text().strip()
        self.cfg.update_url    = self._update_url.text().strip()
        self.cfg.save()
        self.saved.emit()
        self.accept()
