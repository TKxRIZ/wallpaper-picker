#!/usr/bin/env python3
"""linux-wallpaperengine GUI — AIO für Linux (Atomic-First)"""

__version__ = "1.0.0"

__changelog__: dict[str, list[str]] = {
    "1.0.0": [
        "Setup-Assistent mit In-App-Build (linux-wallpaperengine im Distrobox-Container)",
        "Multi-Monitor-Unterstützung mit per-Monitor Wallpaper-Zuordnung",
        "Ausführungsmodi: Distrobox, Toolbox, Direct, Custom",
        "Installiert-Tab (lokale Wallpapers) + Verfügbar-Tab (Steam-API)",
        "Service-Management: Start/Stop/Restart, Autostart, Live-Log",
        "Dark Theme (Catppuccin Mocha), async Thumbnail-Loading (gif/jpg/png/webp)",
        "Self-Updater + linux-wallpaperengine Updater",
        "Atomic-First: funktioniert auf Bazzite/Silverblue ohne System-Pakete",
    ],
}

import ast
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QCursor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QSpinBox, QLineEdit, QFormLayout,
    QGroupBox, QStatusBar, QTabWidget, QScrollArea, QGridLayout,
    QFrame, QComboBox, QProgressBar, QDialog, QDialogButtonBox,
    QTextEdit, QCheckBox, QFileDialog, QToolBar,
    QWizard, QWizardPage, QMessageBox,
)

# ---------------------------------------------------------------------------
# Paths / Constants
# ---------------------------------------------------------------------------

WORKSHOP_DIR = Path.home() / ".local/share/Steam/steamapps/workshop/content/431960"
ACF_FILE     = Path.home() / ".local/share/Steam/steamapps/workshop/appworkshop_431960.acf"
SERVICE_FILE = Path.home() / ".config/systemd/user/linux-wallpaperengine.service"
CONFIG_PATH  = Path.home() / ".config/wallpaper-picker/config.json"
STEAM_API    = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

CARD_W, CARD_H   = 204, 168
THUMB_W, THUMB_H = 200, 130

# Card stylesheets (hover works via Qt CSS)
_CARD_NORMAL = (
    "WallpaperCard{background:#1e1e2e;border:1px solid #313244;border-radius:8px;}"
    "WallpaperCard:hover{background:#252545;border-color:#585b70;}"
)
_CARD_SELECTED = (
    "WallpaperCard{background:#1e2a3a;border:2px solid #89b4fa;border-radius:8px;}"
    "WallpaperCard:hover{background:#1e3050;border:2px solid #89dceb;}"
)

SERVICE_TEMPLATE = (
    "[Unit]\n"
    "Description=Linux WallpaperEngine\n"
    "After=graphical-session.target plasma-workspace.target\n"
    "PartOf=graphical-session.target\n\n"
    "[Service]\n"
    "Type=simple\n"
    "ExecStart={exec_start}\n"
    "Restart=on-failure\n"
    "RestartSec=5\n\n"
    "[Install]\n"
    "WantedBy=graphical-session.target\n"
)

IS_ATOMIC = Path("/run/ostree-booted").exists()
try:
    _osr = dict(l.split("=", 1) for l in Path("/etc/os-release").read_text().splitlines() if "=" in l)
    DISTRO_NAME = _osr.get("NAME", "Unknown").strip('"')
    DISTRO_ID   = _osr.get("ID", "").strip('"')
except Exception:
    DISTRO_NAME, DISTRO_ID = "Unknown", ""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    mode: str          = "distrobox"
    container: str     = "wallpaperengine"
    binary: str        = ""
    assets_dir: str    = ""
    custom_prefix: str = ""
    fps: int           = 30
    service_name: str  = "linux-wallpaperengine"
    steam_api_key: str    = ""
    update_url: str       = ""   # raw GitHub URL to wallpaper-picker.py
    last_update_check: float = 0.0  # unix timestamp

    _BINARY_HINTS = [
        Path.home() / "linux-wallpaperengine/build/output/linux-wallpaperengine",
        Path.home() / ".local/bin/linux-wallpaperengine",
        Path("/usr/local/bin/linux-wallpaperengine"),
        Path("/usr/bin/linux-wallpaperengine"),
    ]
    _ASSETS_HINTS = [
        Path.home() / ".local/share/Steam/steamapps/common/wallpaper_engine/assets",
    ]

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                raw = json.loads(CONFIG_PATH.read_text())
                valid = {f.name for f in dataclasses.fields(cls)}
                return cls(**{k: v for k, v in raw.items() if k in valid})
            except Exception:
                pass  # corrupted config → start fresh
        c = cls()
        c.autodetect()
        return c

    def autodetect(self):
        if not self.binary:
            for p in self._BINARY_HINTS:
                if p.exists() and os.access(str(p), os.X_OK):
                    self.binary = str(p)
                    break
        if not self.assets_dir:
            for p in self._ASSETS_HINTS:
                if p.is_dir():
                    self.assets_dir = str(p)
                    break

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(dataclasses.asdict(self), indent=2))
        tmp.replace(CONFIG_PATH)  # atomic rename

    def build_exec_start(self, screen_args: str, fps: int) -> str:
        binary_dir = str(Path(self.binary).parent) if self.binary else "."
        env = (
            "WAYLAND_DISPLAY=${WAYLAND_DISPLAY} "
            "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR} "
            "XDG_SESSION_TYPE=wayland"
        )
        inner = (
            f"cd {binary_dir} && {env} "
            f"./linux-wallpaperengine "
            f"--assets-dir {self.assets_dir} "
            f"--fps {fps} {screen_args}"
        )
        if self.mode == "distrobox":
            return f'/usr/bin/distrobox enter {self.container} -- bash -c "{inner}"'
        if self.mode == "toolbox":
            return f'toolbox run --container {self.container} bash -c "{inner}"'
        if self.mode == "direct":
            return f'/bin/bash -c "{inner}"'
        return f'{self.custom_prefix} bash -c "{inner}"'

    def test_cmd(self) -> list[str]:
        binary = self.binary or "linux-wallpaperengine"
        if self.mode == "distrobox":
            return ["distrobox", "enter", self.container, "--", binary, "--help"]
        if self.mode == "toolbox":
            return ["toolbox", "run", "--container", self.container, binary, "--help"]
        return [binary, "--help"]


def validate_setup(cfg: Config) -> list[str]:
    issues = []
    if not cfg.binary:
        issues.append("Binary-Pfad nicht konfiguriert")
    elif not Path(cfg.binary).exists():
        issues.append(f"Binary nicht gefunden: {cfg.binary}")
    elif not os.access(cfg.binary, os.X_OK):
        issues.append(f"Binary nicht ausführbar: {cfg.binary}")

    if not cfg.assets_dir:
        issues.append("Assets-Verzeichnis nicht konfiguriert")
    elif not Path(cfg.assets_dir).is_dir():
        issues.append(f"Assets-Verzeichnis fehlt: {cfg.assets_dir}")

    if cfg.mode in ("distrobox", "toolbox"):
        runtime = "distrobox" if cfg.mode == "distrobox" else "toolbox"
        if not cfg.container:
            issues.append("Container-Name nicht gesetzt")
        elif not _container_exists(cfg.mode, cfg.container):
            issues.append(f"Container '{cfg.container}' nicht gefunden")

    return issues


def _container_exists(mode: str, name: str) -> bool:
    try:
        if mode == "distrobox":
            r = subprocess.run(["distrobox", "list"], capture_output=True, text=True, timeout=5)
            return name in r.stdout
        if mode == "toolbox":
            r = subprocess.run(["toolbox", "list"], capture_output=True, text=True, timeout=5)
            return name in r.stdout
    except Exception:
        pass
    return True  # can't check → assume OK


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@dataclass
class Wallpaper:
    id: str
    title: str
    path: Optional[Path] = None
    preview_url: Optional[str] = None

    @property
    def preview_path(self) -> Optional[Path]:
        if not self.path:
            return None
        # project.json names the exact preview file
        pf = self.path / "project.json"
        if pf.exists():
            try:
                name = json.loads(pf.read_text()).get("preview", "")
                if name:
                    p = self.path / name
                    if p.exists() and p.stat().st_size > 0:
                        return p
            except Exception:
                pass
        # Fallback: scan known formats
        for name in ("preview.jpg", "preview.gif", "preview.png", "preview.webp"):
            p = self.path / name
            if p.exists() and p.stat().st_size > 0:
                return p
        return None


@dataclass
class MonitorConfig:
    name: str
    wallpaper_id: str = ""


def get_monitors() -> list[str]:
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"], capture_output=True, text=True, timeout=5,
        ).stdout
        mons = [line.strip().split()[1].lstrip("+*") for line in out.splitlines()[1:] if line.strip()]
        if mons:
            return mons
    except Exception:
        pass
    return ["DP-2"]


def parse_service() -> tuple[list[MonitorConfig], int]:
    if not SERVICE_FILE.exists():
        return [], 30
    try:
        text = SERVICE_FILE.read_text()
        screens = re.findall(r"--screen-root\s+(\S+)", text)
        bgs     = re.findall(r"--bg\s+(\d+)", text)
        fps_m   = re.search(r"--fps\s+(\d+)", text)
        fps = int(fps_m.group(1)) if fps_m else 30
        configs = [MonitorConfig(name=s, wallpaper_id=bgs[i] if i < len(bgs) else "") for i, s in enumerate(screens)]
        return configs, fps
    except Exception:
        return [], 30


def write_service(cfg: Config, monitor_configs: list[MonitorConfig], fps: int):
    issues = validate_setup(cfg)
    if issues:
        raise ValueError("Konfiguration unvollständig:\n• " + "\n• ".join(issues))
    if not any(mc.wallpaper_id for mc in monitor_configs):
        raise ValueError("Kein Wallpaper ausgewählt.")

    screen_args = " ".join(
        f"--screen-root {mc.name} --bg {mc.wallpaper_id}"
        for mc in monitor_configs if mc.wallpaper_id
    )
    exec_start = cfg.build_exec_start(screen_args, fps)

    # Backup existing service
    if SERVICE_FILE.exists():
        SERVICE_FILE.with_suffix(".bak").write_text(SERVICE_FILE.read_text())

    SERVICE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SERVICE_FILE.write_text(SERVICE_TEMPLATE.format(exec_start=exec_start))


def load_installed() -> list[Wallpaper]:
    if not WORKSHOP_DIR.exists():
        return []
    result = []
    for d in sorted(WORKSHOP_DIR.iterdir()):
        if not d.is_dir():
            continue
        title = d.name
        pf = d / "project.json"
        if pf.exists():
            try:
                title = json.loads(pf.read_text()).get("title", d.name)
            except Exception:
                pass
        result.append(Wallpaper(id=d.name, title=title, path=d))
    return result


def load_available_ids() -> list[str]:
    if not ACF_FILE.exists():
        return []
    try:
        text = ACF_FILE.read_text()
        m = re.search(r'"WorkshopItemsInstalled"\s*\{(.*?)\}\s*"WorkshopItemDetails"', text, re.DOTALL)
        if not m:
            return []
        acf_ids  = set(re.findall(r'"(\d{7,})"', m.group(1)))
        disk_ids = {d.name for d in WORKSHOP_DIR.iterdir() if d.is_dir()} if WORKSHOP_DIR.exists() else set()
        return sorted(acf_ids - disk_ids)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------

class ApplyWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, cfg: Config, configs: list[MonitorConfig], fps: int):
        super().__init__()
        self.cfg, self.configs, self.fps = cfg, configs, fps

    def run(self):
        try:
            write_service(self.cfg, self.configs, self.fps)
            subprocess.run(["pkill", "-f", "linux-wallpaperengine"], capture_output=True, timeout=5)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
            subprocess.run(["systemctl", "--user", "restart", self.cfg.service_name], check=True, timeout=30)
            self.done.emit(True, "Wallpaper angewendet.")
        except ValueError as e:
            self.done.emit(False, str(e))
        except subprocess.TimeoutExpired:
            self.done.emit(False, "Timeout — Service antwortet nicht.")
        except subprocess.CalledProcessError as e:
            self.done.emit(False, f"systemctl Fehler: {e}")
        except Exception as e:
            self.done.emit(False, f"Fehler: {e}")


class ServiceControlWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, action: str, service: str):
        super().__init__()
        self.action, self.service = action, service

    def run(self):
        try:
            if self.action == "stop":
                subprocess.run(["pkill", "-f", "linux-wallpaperengine"], capture_output=True, timeout=5)
            subprocess.run(["systemctl", "--user", self.action, self.service], check=True, timeout=15)
            self.done.emit(True, f"{self.action} erfolgreich")
        except Exception as e:
            self.done.emit(False, str(e))


class SteamMetaWorker(QThread):
    batch_ready = Signal(list)

    def __init__(self, ids: list[str], api_key: str = ""):
        super().__init__()
        self.ids = ids
        self._api_key = api_key

    def run(self):
        for i in range(0, len(self.ids), 100):
            batch = self.ids[i:i + 100]
            try:
                params: dict = {"itemcount": len(batch)}
                if self._api_key:
                    params["key"] = self._api_key
                params |= {f"publishedfileids[{j}]": id_ for j, id_ in enumerate(batch)}
                body = urllib.parse.urlencode(params)
                req = urllib.request.Request(STEAM_API, data=body.encode(), method="POST")
                with urllib.request.urlopen(req, timeout=10) as r:
                    files = json.loads(r.read()).get("response", {}).get("publishedfiledetails", [])
                self.batch_ready.emit([
                    Wallpaper(
                        id=f.get("publishedfileid", ""),
                        title=f.get("title") or f.get("publishedfileid", ""),
                        preview_url=f.get("preview_url"),
                    )
                    for f in files
                ])
            except Exception:
                self.batch_ready.emit([Wallpaper(id=id_, title=id_) for id_ in batch])


class ThumbnailLoader(QThread):
    loaded = Signal(str, QPixmap)

    def __init__(self, wp_id: str, url: str):
        super().__init__()
        self.wp_id, self.url = wp_id, url

    def run(self):
        try:
            with urllib.request.urlopen(self.url, timeout=8) as r:
                data = r.read()
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                self.loaded.emit(self.wp_id, pix)
        except Exception:
            pass


class TestBinaryWorker(QThread):
    result = Signal(bool, str)

    def __init__(self, cmd: list[str]):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            r = subprocess.run(self.cmd, capture_output=True, text=True, timeout=20)
            out = (r.stdout + r.stderr).strip()[:800]
            ok = r.returncode == 0 or "linux-wallpaperengine" in out.lower() or "usage" in out.lower()
            self.result.emit(ok, out or "(kein Output)")
        except subprocess.TimeoutExpired:
            self.result.emit(False, "Timeout nach 20s — Binary antwortet nicht.")
        except FileNotFoundError as e:
            self.result.emit(False, f"Nicht gefunden: {e}")
        except Exception as e:
            self.result.emit(False, str(e))


class LocalThumbnailWorker(QThread):
    """Loads local preview images in background, one by one."""
    loaded = Signal(str, QPixmap)

    def __init__(self, wallpapers: list["Wallpaper"]):
        super().__init__()
        self._wallpapers = wallpapers

    def run(self):
        for wp in self._wallpapers:
            p = wp.preview_path
            if not p:
                continue
            pix = QPixmap(str(p))
            if pix.isNull():
                continue
            # Pre-scale to 2× thumbnail size to save memory
            if pix.width() > THUMB_W * 2 or pix.height() > THUMB_H * 2:
                pix = pix.scaled(
                    THUMB_W * 2, THUMB_H * 2,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.loaded.emit(wp.id, pix)


class BuildWorker(QThread):
    """Builds linux-wallpaperengine: git on host, cmake inside distrobox."""
    output_line = Signal(str)
    done        = Signal(bool, str, str)  # ok, message, binary_path

    def __init__(self, container: str, repo_dir: str):
        super().__init__()
        self._container_name = container
        self.repo_dir        = repo_dir

    def _run(self, label: str, cmd: list[str]) -> bool:
        self.output_line.emit(f"\n▶ {label}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in proc.stdout:  # type: ignore
            self.output_line.emit(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        self.output_line.emit("✓ OK" if ok else f"✗ exit {proc.returncode}")
        return ok

    def _in_container(self, label: str, bash_cmd: str) -> bool:
        return self._run(label, ["distrobox", "enter", self._container_name, "--", "bash", "-c", bash_cmd])

    def run(self):
        repo   = self.repo_dir
        binary = f"{repo}/build/output/linux-wallpaperengine"

        # git runs on the HOST
        if not Path(repo).exists():
            if not self._run("Repository klonen",
                             ["git", "clone",
                              "https://github.com/Almamu/linux-wallpaperengine", repo]):
                self.done.emit(False, "git clone fehlgeschlagen", "")
                return
        else:
            self._run("git pull", ["git", "-C", repo, "pull", "--ff-only"])

        # Build steps run INSIDE the container
        container_steps = [
            ("Dependencies installieren",
             "sudo dnf install -y cmake gcc-c++ glm-devel glfw-devel zlib-devel "
             "pulseaudio-libs-devel lz4-devel ffmpeg-devel SDL2-devel 2>/dev/null || true"),
            ("CMake konfigurieren",
             f'cd "{repo}" && cmake -B build -DCMAKE_BUILD_TYPE=Release'),
            ("Build (kann einige Minuten dauern…)",
             f'cd "{repo}" && cmake --build build -j$(nproc)'),
        ]
        for label, cmd in container_steps:
            if not self._in_container(label, cmd):
                self.done.emit(False, f"Fehlgeschlagen bei: {label}", "")
                return

        self.done.emit(True, "Build erfolgreich!", binary)


def _vtuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


class UpdateChecker(QThread):
    """Fetches remote file header, parses version + changelog."""
    update_available = Signal(str, dict)  # remote_version, remote_changelog
    up_to_date       = Signal(str)        # remote_version
    check_failed     = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            req = urllib.request.Request(
                self._url, headers={"User-Agent": f"wallpaper-picker/{__version__}"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                head = r.read(8192).decode("utf-8", errors="ignore")

            vm = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', head)
            if not vm:
                self.check_failed.emit("Keine Versionsinformation in der Remote-Datei gefunden.")
                return
            remote = vm.group(1)

            changelog: dict = {}
            cm = re.search(r'__changelog__\s*=\s*(\{.+?\})\s*\n', head, re.DOTALL)
            if cm:
                try:
                    changelog = ast.literal_eval(cm.group(1))
                except Exception:
                    pass

            if _vtuple(remote) > _vtuple(__version__):
                self.update_available.emit(remote, changelog)
            else:
                self.up_to_date.emit(remote)
        except urllib.error.URLError as e:
            self.check_failed.emit(f"Netzwerk-Fehler: {e.reason}")
        except Exception as e:
            self.check_failed.emit(str(e))


class SelfUpdateWorker(QThread):
    """Downloads, verifies (syntax check), backs up, and atomically replaces the script."""
    progress = Signal(str)
    done     = Signal(bool, str)

    def __init__(self, url: str, target: Path):
        super().__init__()
        self._url, self._target = url, target

    def run(self):
        backup = self._target.with_suffix(".bak")
        tmp    = self._target.with_suffix(".update.tmp")
        try:
            # 1. Download with progress
            req = urllib.request.Request(
                self._url, headers={"User-Agent": f"wallpaper-picker/{__version__}"}
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                total = int(r.headers.get("Content-Length", 0))
                data  = b""
                while chunk := r.read(8192):
                    data += chunk
                    if total:
                        kb = len(data) // 1024
                        pct = len(data) * 100 // total
                        self.progress.emit(f"Herunterladen… {kb} KB / {total//1024} KB ({pct}%)")
                    else:
                        self.progress.emit(f"Herunterladen… {len(data)//1024} KB")

            # 2. Sanity checks
            if len(data) < 5000:
                raise ValueError(f"Datei zu klein ({len(data)} Bytes) — kein Update durchgeführt.")

            # 3. Syntax check — verify it's valid Python before replacing anything
            self.progress.emit("Syntax wird geprüft…")
            try:
                ast.parse(data.decode("utf-8"))
            except SyntaxError as e:
                raise ValueError(f"Syntax-Fehler in der heruntergeladenen Datei: {e}")

            # 4. Backup current file
            self.progress.emit("Backup erstellt…")
            if self._target.exists():
                shutil.copy2(self._target, backup)

            # 5. Atomic replace
            self.progress.emit("Schreibe neue Version…")
            tmp.write_bytes(data)
            tmp.chmod(0o755)
            tmp.replace(self._target)

            self.done.emit(True, "Update erfolgreich.")
        except Exception as e:
            # Try to restore backup if replacement went wrong
            if not self._target.exists() and backup.exists():
                shutil.copy2(backup, self._target)
                self.done.emit(False, f"{e}\n(Backup wurde wiederhergestellt.)")
            else:
                self.done.emit(False, str(e))


class UpdateLWEWorker(QThread):
    """git pull (host) + incremental cmake build (distrobox)."""
    output_line = Signal(str)
    done        = Signal(bool, str)

    def __init__(self, container: str, repo_dir: str):
        super().__init__()
        self._container_name = container
        self._repo_dir       = repo_dir

    def _host(self, label: str, cmd: list[str]) -> bool:
        """Run a command on the host and stream output."""
        self.output_line.emit(f"\n▶ {label}")
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in proc.stdout:  # type: ignore
            self.output_line.emit(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        self.output_line.emit("✓ OK" if ok else f"✗ exit {proc.returncode}")
        return ok

    def _container(self, label: str, cmd: str) -> bool:
        """Run a command inside the distrobox container."""
        self.output_line.emit(f"\n▶ {label}")
        proc = subprocess.Popen(
            ["distrobox", "enter", self._container_name, "--", "bash", "-c", cmd],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in proc.stdout:  # type: ignore
            self.output_line.emit(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        self.output_line.emit("✓ OK" if ok else f"✗ exit {proc.returncode}")
        return ok

    def run(self):
        r = self._repo_dir
        # git runs on the HOST — no container needed
        self._host("Aktueller Commit",
                   ["git", "-C", r, "log", "-1", "--format=Vorher: %h — %s"])
        if not self._host("git pull",
                          ["git", "-C", r, "pull", "--ff-only"]):
            self.done.emit(False, "git pull fehlgeschlagen — evtl. lokale Änderungen vorhanden.")
            return
        self._host("Neuer Commit",
                   ["git", "-C", r, "log", "-1", "--format=Nachher: %h — %s"])
        # cmake build runs INSIDE the container
        if not self._container("cmake build",
                               f'cd "{r}" && cmake --build build -j$(nproc)'):
            self.done.emit(False, "Build fehlgeschlagen.")
            return
        self.done.emit(True, "linux-wallpaperengine aktualisiert.")


# ---------------------------------------------------------------------------
# Update banner (shown at top of main window)
# ---------------------------------------------------------------------------

class UpdateBanner(QFrame):
    """Dismissable banner shown when a new app version is available."""
    show_dialog = Signal()

    def __init__(self, remote_version: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "UpdateBanner{background:#1e3a5f;border-radius:6px;margin:4px 4px 0 4px;}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        icon = QLabel("↑")
        icon.setStyleSheet("color:#89b4fa; font-size:16px; font-weight:bold;")
        msg = QLabel(f"Update verfügbar — Version <b>{remote_version}</b>")
        msg.setStyleSheet("color:#cdd6f4;")

        update_btn = QPushButton("Aktualisieren")
        update_btn.setStyleSheet(
            "background:#89b4fa;color:#1e1e2e;font-weight:bold;"
            "border-radius:4px;padding:4px 12px;"
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


# ---------------------------------------------------------------------------
# Update dialog
# ---------------------------------------------------------------------------

class UpdateDialog(QDialog):
    def __init__(self, current: str, remote: str, remote_changelog: dict,
                 url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update verfügbar")
        self.resize(540, 400)
        self._url      = url
        self._target   = Path(sys.argv[0])
        self._worker: Optional[SelfUpdateWorker] = None
        self._build_ui(current, remote, remote_changelog)

    def _build_ui(self, current: str, remote: str, changelog: dict):
        layout = QVBoxLayout(self)

        # Version comparison
        header = QLabel(
            f"<b style='font-size:14px'>Update verfügbar</b><br><br>"
            f"Installiert: &nbsp;<code>{current}</code><br>"
            f"Verfügbar: &nbsp;&nbsp;<code style='color:#89b4fa'>{remote}</code>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        # Changelog — show all versions newer than current
        new_entries = {
            v: items for v, items in changelog.items()
            if _vtuple(v) > _vtuple(current)
        }
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

        # Progress log
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Monospace", 9))
        self._log.setFixedHeight(80)
        self._log.hide()
        layout.addWidget(self._log)

        # Rollback (shown only if .bak exists)
        self._rollback_btn = QPushButton("⟲  Rollback auf vorherige Version")
        self._rollback_btn.setStyleSheet("color:#f38ba8;")
        self._rollback_btn.clicked.connect(self._rollback)
        backup = self._target.with_suffix(".bak")
        self._rollback_btn.setVisible(backup.exists())
        layout.addWidget(self._rollback_btn)

        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Jetzt aktualisieren")
        self._btns.accepted.connect(self._start_update)
        self._btns.rejected.connect(self.reject)
        layout.addWidget(self._btns)

    def _start_update(self):
        self._btns.setEnabled(False)
        self._rollback_btn.hide()
        self._progress_bar.show()
        self._log.show()
        self._log.append(f"Ziel: {self._target}")
        self._worker = SelfUpdateWorker(self._url, self._target)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, msg: str):
        self._log.append(msg)
        # Parse percentage for progress bar
        m = re.search(r'\((\d+)%\)', msg)
        if m:
            self._progress_bar.setValue(int(m.group(1)))

    def _on_done(self, ok: bool, msg: str):
        self._progress_bar.setValue(100 if ok else 0)
        self._log.append(("✓ " if ok else "✗ ") + msg)
        if ok:
            self._log.append("App wird neu gestartet…")
            QTimer.singleShot(1500, self._restart)
        else:
            self._btns.setEnabled(True)
            self._rollback_btn.setVisible(self._target.with_suffix(".bak").exists())

    def _rollback(self):
        backup = self._target.with_suffix(".bak")
        if not backup.exists():
            self._log.show()
            self._log.append("Kein Backup vorhanden.")
            return
        self._log.show()
        self._log.append(f"Stelle {backup} wieder her…")
        try:
            shutil.copy2(backup, self._target)
            self._log.append("✓ Backup wiederhergestellt — App wird neu gestartet…")
            QTimer.singleShot(1500, self._restart)
        except Exception as e:
            self._log.append(f"✗ {e}")

    def _restart(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)


# ---------------------------------------------------------------------------
# Wallpaper card
# ---------------------------------------------------------------------------

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
        self.thumb.setStyleSheet(
            "background:#11111b; border-radius:5px; color:#585b70; font-size:11px;"
        )
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


# ---------------------------------------------------------------------------
# Wallpaper grid
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Monitor panel
# ---------------------------------------------------------------------------

class MonitorPanel(QGroupBox):
    def __init__(self, monitors: list[str], configs: list[MonitorConfig], parent=None):
        super().__init__("Monitor-Zuordnung", parent)
        self._monitors = monitors
        self._configs: dict[str, str] = {mc.name: mc.wallpaper_id for mc in configs}
        self._active = monitors[0] if monitors else ""
        self._wallpapers: dict[str, Wallpaper] = {}
        self._rows: dict[str, tuple[QPushButton, QLabel]] = {}

        layout = QVBoxLayout(self)
        hint = QLabel("Monitor wählen → Wallpaper klicken → Anwenden")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for mon in monitors:
            row = QHBoxLayout()
            btn = QPushButton(mon)
            btn.setCheckable(True)
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _, m=mon: self._select(m))
            lbl = QLabel(self._display(mon))
            lbl.setStyleSheet("color: #aaa;")
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


# ---------------------------------------------------------------------------
# Setup banner + service status widget
# ---------------------------------------------------------------------------

class SetupBanner(QFrame):
    open_settings = Signal()
    run_wizard    = Signal()

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self._refresh(cfg)

    def _refresh(self, cfg: Config):
        # Clear old layout
        old = self.layout()
        if old:
            while old.count():
                item = old.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        issues = validate_setup(cfg)
        if not issues:
            self.setVisible(False)
            return

        self.setVisible(True)
        self.setStyleSheet(
            "SetupBanner { background: #7c2d12; border-radius: 6px; margin: 4px 4px 0 4px; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)

        icon = QLabel("⚠")
        icon.setStyleSheet("color: #fbbf24; font-size: 16px;")

        first = issues[0]
        suffix = f" (+{len(issues)-1} weitere)" if len(issues) > 1 else ""
        msg = QLabel(f"{first}{suffix}")
        msg.setStyleSheet("color: #fef3c7; font-weight: bold;")
        msg.setToolTip("\n".join(issues))

        wizard_btn = QPushButton("Setup-Assistent öffnen")
        wizard_btn.setStyleSheet(
            "background: #fbbf24; color: #1c1917; font-weight: bold; "
            "border-radius: 4px; padding: 4px 12px;"
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
        self._dot = QLabel("●")
        self._lbl = QLabel("…")
        self._lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        self._service = service_name
        QTimer(self, timeout=self.refresh, interval=5000).start()
        self.refresh()

    def refresh(self):
        r = subprocess.run(
            ["systemctl", "--user", "is-active", self._service],
            capture_output=True, text=True, timeout=3,
        )
        s = r.stdout.strip()
        if s == "active":
            self._dot.setStyleSheet("color: #4caf50; font-size: 10px;")
            self._lbl.setText("Service aktiv")
        elif s == "inactive":
            self._dot.setStyleSheet("color: #888; font-size: 10px;")
            self._lbl.setText("Service inaktiv")
        else:
            self._dot.setStyleSheet("color: #f44336; font-size: 10px;")
            self._lbl.setText(f"Service: {s or 'unbekannt'}")


# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------

class InstalledTab(QWidget):
    wallpaper_selected = Signal(str)

    def __init__(self, wallpapers: list[Wallpaper], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not wallpapers:
            empty = QLabel(
                "Keine Wallpapers gefunden.\n\n"
                "Steam → Wallpaper Engine → Workshop → Wallpapers abonnieren,\n"
                "dann Steam neu starten damit sie heruntergeladen werden."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888; padding: 40px;")
            layout.addWidget(empty)
            return

        self.grid = WallpaperGrid()
        self.grid.add_cards(wallpapers)
        self.grid.selection_changed.connect(self.wallpaper_selected)
        layout.addWidget(self.grid)

        # Load thumbnails in background
        if wallpapers:
            self._loader = LocalThumbnailWorker(wallpapers)
            self._loader.loaded.connect(self.grid.update_card_pixmap)
            self._loader.start()


class AvailableTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        info = QLabel(
            "In Steam abonniert, aber noch nicht heruntergeladen.\n"
            "Steam → Wallpaper Engine → Workshop → Abonnements"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; padding: 8px;")
        layout.addWidget(info)

        self._progress = QProgressBar()
        self._progress.setFormat("Metadaten laden… %v / %m")
        layout.addWidget(self._progress)

        self.grid = WallpaperGrid()
        self.grid._search.setPlaceholderText("Suchen… (nach dem Laden)")
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


# ---------------------------------------------------------------------------
# Build Dialog
# ---------------------------------------------------------------------------

class BuildDialog(QDialog):
    binary_built = Signal(str)  # emits binary path

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
        self._log.setStyleSheet("background: #0d1117; color: #e6edf3;")
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
        repo = str(Path.home() / "linux-wallpaperengine")
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


# ---------------------------------------------------------------------------
# Setup Wizard
# ---------------------------------------------------------------------------

PAGE_WELCOME = 0
PAGE_MODE    = 1
PAGE_BINARY  = 2
PAGE_ASSETS  = 3
PAGE_FINISH  = 4


class WelcomePage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle("Willkommen")
        self.setSubTitle("Einrichtungs-Assistent für linux-wallpaperengine")

        layout = QVBoxLayout(self)

        ptype = "Atomic (Immutable)" if IS_ATOMIC else "Traditionell"
        info = QLabel(
            f"<b>System:</b> {DISTRO_NAME} — {ptype}<br><br>"
            "Dieser Assistent führt dich durch die Einrichtung von<br>"
            "<b>linux-wallpaperengine</b> — einer Open-Source-Implementierung<br>"
            "der Wallpaper Engine für Linux.<br><br>"
            "Du benötigst:<br>"
            "• linux-wallpaperengine Binary (bereits gebaut oder jetzt bauen)<br>"
            "• Wallpaper Engine Assets (aus Steam)<br>"
            "• Mindestens ein abonniertes Wallpaper"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        issues = validate_setup(cfg)
        if not issues:
            ok = QLabel("✓ Setup bereits vollständig konfiguriert!")
            ok.setStyleSheet("color: #4caf50; font-weight: bold; padding-top: 12px;")
            layout.addWidget(ok)

        layout.addStretch()


class ModePage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle("Ausführungsmodus")
        self.setSubTitle("Wie soll linux-wallpaperengine gestartet werden?")

        layout = QFormLayout(self)

        self._mode = QComboBox()
        self._mode.currentTextChanged.connect(self._on_mode)
        layout.addRow("Modus:", self._mode)

        self._container = QLineEdit(cfg.container)
        layout.addRow("Container:", self._container)

        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color: #aaa; font-size: 11px; padding-top: 8px;")
        layout.addRow("", self._desc)

        self._populate_modes()

    def _populate_modes(self):
        self._mode.clear()
        available = []
        for runtime, mode in [("distrobox", "distrobox"), ("toolbox", "toolbox")]:
            if Path(f"/usr/bin/{runtime}").exists():
                available.append((f"{mode}  (empfohlen für Atomic)", mode))
        available += [("direct  (Binary direkt ausführen)", "direct"),
                      ("custom  (eigener Prefix)", "custom")]
        for label, val in available:
            self._mode.addItem(label, val)
        # Pre-select current
        for i in range(self._mode.count()):
            if self._mode.itemData(i) == self._cfg.mode:
                self._mode.setCurrentIndex(i)
                break

    def _on_mode(self, _):
        mode = self._mode.currentData()
        descs = {
            "distrobox": "Führt die Binary in einem Distrobox-Container aus. Empfohlen für Bazzite/Silverblue.",
            "toolbox": "Wie Distrobox, aber mit Toolbox/Toolbx.",
            "direct": "Führt die Binary direkt auf dem Host aus. Benötigt alle Libraries auf dem Host.",
            "custom": "Benutzerdefinierter Prefix-Befehl vor der Binary.",
        }
        self._desc.setText(descs.get(mode or "", ""))
        self._container.setEnabled(mode in ("distrobox", "toolbox"))

    def initializePage(self):
        self._on_mode(None)

    def validatePage(self) -> bool:
        mode = self._mode.currentData()
        container = self._container.text().strip()
        if mode in ("distrobox", "toolbox") and not container:
            QMessageBox.warning(self, "Fehler", "Container-Name darf nicht leer sein.")
            return False
        self._cfg.mode = mode
        self._cfg.container = container
        return True


class BinaryPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self._complete = False
        self._test_worker: Optional[TestBinaryWorker] = None
        self.setTitle("Binary konfigurieren")
        self.setSubTitle("Pfad zur linux-wallpaperengine Binary angeben und testen")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self._path = QLineEdit(self._cfg.binary)
        self._path.setPlaceholderText("/home/user/linux-wallpaperengine/build/output/linux-wallpaperengine")
        self._path.textChanged.connect(self._on_path_changed)
        detect_btn = QPushButton("Auto-Detect")
        detect_btn.clicked.connect(self._autodetect)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(detect_btn)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Binary testen")
        self._test_btn.clicked.connect(self._test)
        self._test_result = QLabel("")
        self._test_result.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_result, stretch=1)
        layout.addLayout(test_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        build_lbl = QLabel("<b>Binary nicht gefunden?</b> Direkt hier in einem Distrobox-Container bauen:")
        build_lbl.setWordWrap(True)
        layout.addWidget(build_lbl)

        self._build_btn = QPushButton("⚙  linux-wallpaperengine jetzt bauen…")
        self._build_btn.clicked.connect(self._open_build)
        layout.addWidget(self._build_btn)

        layout.addStretch()

    def initializePage(self):
        path = self._path.text().strip()
        if path and Path(path).exists() and os.access(path, os.X_OK):
            self._set_ok(True, "Binary bereits vorhanden ✓")

    def _autodetect(self):
        tmp = Config(binary="", assets_dir=self._cfg.assets_dir)
        tmp.autodetect()
        if tmp.binary:
            self._path.setText(tmp.binary)
            self._test()
        else:
            self._test_result.setText("Nicht gefunden — bitte manuell angeben oder bauen.")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Binary wählen")
        if path:
            self._path.setText(path)

    def _on_path_changed(self, text: str):
        if not text.strip():
            self._set_ok(False, "")

    def _test(self):
        path = self._path.text().strip()
        if not path:
            self._test_result.setText("Kein Pfad angegeben.")
            return
        self._test_btn.setEnabled(False)
        self._test_result.setText("Wird getestet…")
        tmp_cfg = Config(mode=self._cfg.mode, container=self._cfg.container, binary=path)
        self._test_worker = TestBinaryWorker(tmp_cfg.test_cmd())
        self._test_worker.result.connect(self._on_test)
        self._test_worker.start()

    def _on_test(self, ok: bool, msg: str):
        self._test_btn.setEnabled(True)
        self._set_ok(ok, ("✓ Binary funktioniert" if ok else f"✗ {msg[:120]}"))
        if ok:
            self._test_result.setToolTip(msg)

    def _set_ok(self, ok: bool, msg: str):
        color = "#4caf50" if ok else "#f44336"
        self._test_result.setText(f'<span style="color:{color}">{msg}</span>')
        self._complete = ok
        self.completeChanged.emit()

    def _open_build(self):
        dlg = BuildDialog(self._cfg.container, self)
        dlg.binary_built.connect(self._on_built)
        dlg.exec()

    def _on_built(self, path: str):
        self._path.setText(path)
        self._test()

    def isComplete(self) -> bool:
        return self._complete

    def validatePage(self) -> bool:
        self._cfg.binary = self._path.text().strip()
        return True


class AssetsPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self._complete = False
        self.setTitle("Assets-Verzeichnis")
        self.setSubTitle("Pfad zum Wallpaper Engine Assets-Ordner (aus Steam)")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Das Assets-Verzeichnis befindet sich normalerweise unter:\n"
            "~/.local/share/Steam/steamapps/common/wallpaper_engine/assets"
        ))

        path_row = QHBoxLayout()
        self._path = QLineEdit(self._cfg.assets_dir)
        self._path.setPlaceholderText("Pfad zum assets/-Ordner")
        self._path.textChanged.connect(self._validate_path)
        detect_btn = QPushButton("Auto-Detect")
        detect_btn.clicked.connect(self._autodetect)
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(30)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(detect_btn)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        layout.addStretch()

    def initializePage(self):
        self._validate_path(self._path.text())

    def _autodetect(self):
        tmp = Config(binary=self._cfg.binary, assets_dir="")
        tmp.autodetect()
        if tmp.assets_dir:
            self._path.setText(tmp.assets_dir)
        else:
            self._status.setText("Nicht gefunden. Bitte Wallpaper Engine in Steam installieren.")

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Assets-Ordner wählen")
        if path:
            self._path.setText(path)

    def _validate_path(self, text: str):
        p = Path(text.strip())
        if not text.strip():
            self._set_ok(False, "")
            return
        if not p.is_dir():
            self._set_ok(False, f"✗ Verzeichnis nicht gefunden: {text}")
            return
        # Check for a key file that should exist in the assets dir
        key_files = ["shaders", "materials", "effects"]
        missing = [f for f in key_files if not (p / f).exists()]
        if missing:
            self._set_ok(False, f"✗ Kein gültiges Assets-Verzeichnis (fehlt: {', '.join(missing)})")
            return
        self._set_ok(True, "✓ Assets-Verzeichnis gefunden")

    def _set_ok(self, ok: bool, msg: str):
        color = "#4caf50" if ok else "#f44336"
        self._status.setText(f'<span style="color:{color}">{msg}</span>')
        self._complete = ok
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._complete

    def validatePage(self) -> bool:
        self._cfg.assets_dir = self._path.text().strip()
        return True


class FinishPage(QWizardPage):
    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg
        self.setTitle("Einrichtung abgeschlossen")
        self.setSubTitle("Konfiguration wird gespeichert")
        self._layout = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._layout.addWidget(self._summary)
        self._layout.addStretch()

    def initializePage(self):
        lines = [
            "<b>Konfiguration:</b><br>",
            f"Modus: {self._cfg.mode}",
        ]
        if self._cfg.mode in ("distrobox", "toolbox"):
            lines.append(f"Container: {self._cfg.container}")
        lines += [
            f"Binary: {self._cfg.binary}",
            f"Assets: {self._cfg.assets_dir}",
            "<br>Klicke <b>Fertigstellen</b> um die Konfiguration zu speichern.",
        ]
        self._summary.setText("<br>".join(lines))


class SetupWizard(QWizard):
    setup_complete = Signal()

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Einrichtungs-Assistent")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.resize(720, 520)

        self.setPage(PAGE_WELCOME, WelcomePage(cfg))
        self.setPage(PAGE_MODE,    ModePage(cfg))
        self.setPage(PAGE_BINARY,  BinaryPage(cfg))
        self.setPage(PAGE_ASSETS,  AssetsPage(cfg))
        self.setPage(PAGE_FINISH,  FinishPage(cfg))
        self.setStartId(PAGE_WELCOME)

        btn = self.button(QWizard.WizardButton.FinishButton)
        btn.clicked.connect(self._on_finish)

    def _on_finish(self):
        self.cfg.save()
        self.setup_complete.emit()


# ---------------------------------------------------------------------------
# Settings Dialog
# ---------------------------------------------------------------------------

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

    # --- Engine tab ---
    def _engine_tab(self) -> QWidget:
        w = QWidget()
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
        c = "#4caf50" if ok else "#f44336"
        label = "OK" if ok else "FEHLER"
        self._test_out.setText(f'<span style="color:{c}">{label}</span>')
        self._test_out.setToolTip(msg)

    # --- Service tab ---
    def _service_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        status_row = QHBoxLayout()
        self._svc_status = QLabel("…")
        self._svc_status.setStyleSheet("font-weight: bold;")
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
        subprocess.run(["systemctl", "--user", "enable" if enabled else "disable",
                        self.cfg.service_name], capture_output=True, timeout=5)

    # --- Info tab ---
    def _info_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        ptype = "Atomic (Immutable)" if IS_ATOMIC else "Traditionell"
        layout.addWidget(self._info_row("Distro:", f"{DISTRO_NAME} ({ptype})"))

        b_ok = bool(self.cfg.binary) and Path(self.cfg.binary).exists()
        layout.addWidget(self._info_row("Binary:", self.cfg.binary or "nicht konfiguriert", ok=b_ok))

        a_ok = bool(self.cfg.assets_dir) and Path(self.cfg.assets_dir).is_dir()
        layout.addWidget(self._info_row("Assets:", self.cfg.assets_dir or "nicht konfiguriert", ok=a_ok))

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

    # --- Updates tab ---
    def _updates_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # --- App-Update ---
        app_box = QGroupBox("App-Update (wallpaper-picker)")
        app_form = QFormLayout(app_box)

        self._update_url = QLineEdit(self.cfg.update_url)
        self._update_url.setPlaceholderText(
            "https://raw.githubusercontent.com/USER/REPO/main/wallpaper-picker.py"
        )
        app_form.addRow("Update-URL:", self._update_url)

        ver_row = QHBoxLayout()
        self._ver_label = QLabel(f"Installiert: <b>{__version__}</b>")
        self._check_btn = QPushButton("Jetzt prüfen")
        self._check_btn.clicked.connect(self._check_update)
        self._check_result = QLabel("")
        ver_row.addWidget(self._ver_label)
        ver_row.addWidget(self._check_btn)
        ver_row.addWidget(self._check_result, stretch=1)
        app_form.addRow("", ver_row)

        layout.addWidget(app_box)

        # Rollback app
        backup = Path(sys.argv[0]).with_suffix(".bak")
        if backup.exists():
            rollback_box = QGroupBox("Rollback")
            rb_layout = QVBoxLayout(rollback_box)
            rb_layout.addWidget(QLabel(f"Backup vorhanden: <code>{backup}</code>"))
            rb_btn = QPushButton("⟲  Auf vorherige Version zurücksetzen")
            rb_btn.setStyleSheet("color:#f38ba8;")
            rb_btn.clicked.connect(lambda: self._do_rollback(backup))
            rb_layout.addWidget(rb_btn)
            layout.addWidget(rollback_box)

        # --- LWE-Update ---
        lwe_box = QGroupBox("linux-wallpaperengine aktualisieren")
        lwe_layout = QVBoxLayout(lwe_box)

        repo = str(Path.home() / "linux-wallpaperengine")
        lwe_commit = self._get_lwe_commit(repo)
        lwe_info = QLabel(
            f"Repo: <code>{repo}</code><br>"
            f"Aktueller Commit: <code>{lwe_commit}</code>"
        )
        lwe_info.setWordWrap(True)
        lwe_layout.addWidget(lwe_info)

        lwe_btn_row = QHBoxLayout()
        self._lwe_btn = QPushButton("linux-wallpaperengine aktualisieren")
        self._lwe_btn.clicked.connect(self._update_lwe)
        lwe_btn_row.addWidget(self._lwe_btn)
        lwe_btn_row.addStretch()
        lwe_layout.addLayout(lwe_btn_row)

        self._lwe_log = QTextEdit()
        self._lwe_log.setReadOnly(True)
        self._lwe_log.setFont(QFont("Monospace", 9))
        self._lwe_log.setFixedHeight(120)
        self._lwe_log.hide()
        lwe_layout.addWidget(self._lwe_log)

        layout.addWidget(lwe_box)

        layout.addWidget(QLabel(
            "<small>Update-URL: Raw-URL zur wallpaper-picker.py auf GitHub.<br>"
            "Repo anlegen → Datei pushen → Raw-URL eintragen → fertig.</small>"
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
        dlg = UpdateDialog(__version__, remote, changelog, self._update_url.text().strip(), self)
        dlg.exec()

    def _on_check_done(self, ok: bool, msg: str):
        self._check_btn.setEnabled(True)
        c = "#4caf50" if ok else "#f44336"
        self._check_result.setText(f'<span style="color:{c}">{msg}</span>')

    def _update_lwe(self):
        repo = str(Path.home() / "linux-wallpaperengine")
        if not Path(repo).exists():
            self._lwe_log.show()
            self._lwe_log.append("Repo nicht gefunden — bitte zuerst bauen (Setup-Assistent).")
            return
        self._lwe_btn.setEnabled(False)
        self._lwe_log.show()
        self._lwe_log.clear()
        self._lwe_worker = UpdateLWEWorker(self.cfg.container, repo)
        self._lwe_worker.output_line.connect(self._lwe_log.append)
        self._lwe_worker.done.connect(self._on_lwe_done)
        self._lwe_worker.start()

    def _on_lwe_done(self, ok: bool, msg: str):
        self._lwe_btn.setEnabled(True)
        self._lwe_log.append(("✓ " if ok else "✗ ") + msg)

    @staticmethod
    def _get_lwe_commit(repo: str) -> str:
        if not Path(repo).exists():
            return "nicht installiert"
        try:
            r = subprocess.run(
                ["git", "-C", repo, "log", "-1", "--format=%h — %s (%cd)", "--date=short"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip() or "unbekannt"
        except Exception:
            return "unbekannt"

    def _do_rollback(self, backup: Path):
        try:
            shutil.copy2(backup, Path(sys.argv[0]))
            QMessageBox.information(self, "Rollback", "Backup wiederhergestellt — App wird neu gestartet.")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            QMessageBox.critical(self, "Rollback fehlgeschlagen", str(e))

    def _info_row(self, label: str, value: str, ok: Optional[bool] = None) -> QWidget:
        w = QWidget()
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
            ind.setStyleSheet(f"color: {'#4caf50' if ok else '#f44336'}; font-weight: bold;")
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
                "   git clone https://github.com/Almamu/linux-wallpaperengine ~/linux-wallpaperengine",
                "   distrobox enter wallpaperengine -- bash -c \\",
                '     "cd ~/linux-wallpaperengine && cmake -B build && cmake --build build -j$(nproc)"\n',
                "→ Oder: Setup-Assistent → Binary-Seite → 'Jetzt bauen'",
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
                "2. git clone https://github.com/Almamu/linux-wallpaperengine ~/linux-wallpaperengine",
                "   cd ~/linux-wallpaperengine && cmake -B build && cmake --build build -j$(nproc)\n",
                "3. Optional: cp ~/linux-wallpaperengine/build/output/linux-wallpaperengine ~/.local/bin/",
                "   → Modus auf 'direct' setzen",
            ]
        return "\n".join(lines)

    # --- Save ---
    def _save(self):
        self.cfg.mode           = self._mode.currentText()
        self.cfg.container      = self._container.text().strip()
        self.cfg.binary         = self._binary.text().strip()
        self.cfg.assets_dir     = self._assets.text().strip()
        self.cfg.custom_prefix  = self._custom_prefix.text().strip()
        self.cfg.steam_api_key  = self._steam_key.text().strip()
        self.cfg.update_url     = self._update_url.text().strip()
        self.cfg.save()
        self.saved.emit()
        self.accept()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wallpaper Engine – Linux")
        self.resize(1150, 720)

        self._cfg = Config.load()
        self._installed = load_installed()
        self._svc_configs, _ = parse_service()
        self._monitors = get_monitors()

        self._workers: list[QThread] = []  # tracked for cleanup
        self._meta_worker: Optional[SteamMetaWorker] = None

        self._build_ui()
        self._init_selections()

        # Show wizard on first run or broken setup
        if not CONFIG_PATH.exists() or validate_setup(self._cfg):
            QTimer.singleShot(200, self._run_wizard)

        # Silent update check (max once per 24h)
        if self._cfg.update_url and (time.time() - self._cfg.last_update_check > 86400):
            self._cfg.last_update_check = time.time()
            self._cfg.save()
            QTimer.singleShot(3000, self._silent_update_check)

    def _build_ui(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        title_lbl = QLabel("  Wallpaper Engine – Linux  ")
        title_lbl.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(title_lbl)
        toolbar.addSeparator()
        wizard_btn = QPushButton("⭐  Einrichtungs-Assistent")
        wizard_btn.clicked.connect(self._run_wizard)
        self._update_check_btn = QPushButton("↑  Updates")
        self._update_check_btn.clicked.connect(self._manual_update_check)
        self._update_check_btn.setToolTip("Auf Updates prüfen")
        settings_btn = QPushButton("⚙  Einstellungen")
        settings_btn.clicked.connect(self._open_settings)
        toolbar.addWidget(wizard_btn)
        toolbar.addWidget(self._update_check_btn)
        toolbar.addWidget(settings_btn)

        central = QWidget()
        outer = QVBoxLayout(central)
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
        root = QHBoxLayout(content)
        root.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(content, stretch=1)

        self._tabs = QTabWidget()
        self._installed_tab = InstalledTab(self._installed)
        if hasattr(self._installed_tab, "grid"):
            self._installed_tab.wallpaper_selected.connect(self._on_wp_selected)
        self._tabs.addTab(self._installed_tab, f"Installiert ({len(self._installed)})")

        self._available_tab = AvailableTab()
        self._tabs.addTab(self._available_tab, "Verfügbar (wird geladen…)")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, stretch=1)

        right = QWidget()
        right.setFixedWidth(300)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)

        # Large preview
        self._preview_img = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._preview_img.setFixedHeight(176)
        self._preview_img.setStyleSheet(
            "background:#11111b; border-radius:8px; color:#45475a; font-size:12px;"
        )
        self._preview_img.setText("← Wallpaper auswählen")
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

        fps_box = QGroupBox("Wiedergabe")
        fps_form = QFormLayout(fps_box)
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(self._cfg.fps)
        fps_form.addRow("FPS:", self._fps_spin)
        rl.addWidget(fps_box)

        rl.addStretch()

        self._apply_btn = QPushButton("Anwenden")
        self._apply_btn.setFixedHeight(42)
        self._apply_btn.clicked.connect(self._apply)
        rl.addWidget(self._apply_btn)

        root.addWidget(right)

        self._status = QStatusBar()
        self._svc_status_widget = ServiceStatusWidget(self._cfg.service_name)
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
            self._tabs.setTabText(1, f"Verfügbar ({len(ids)})")
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
        self._preview_id.setText(f"ID: {wp.id}")
        p = wp.preview_path
        if p:
            pix = QPixmap(str(p))
            if not pix.isNull():
                pix = pix.scaled(
                    290, 176,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._preview_img.setPixmap(pix)
                return
        self._preview_img.clear()
        self._preview_img.setText("Kein Vorschaubild")

    def _apply(self):
        issues = validate_setup(self._cfg)
        if issues:
            QMessageBox.warning(
                self, "Setup unvollständig",
                "Bitte zuerst die Einrichtung abschließen:\n\n• " + "\n• ".join(issues)
            )
            return

        configs = self._monitor_panel.get_configs()
        if not any(mc.wallpaper_id for mc in configs):
            self._status.showMessage("Kein Wallpaper ausgewählt — bitte Wallpaper anklicken.")
            return

        self._cfg.fps = self._fps_spin.value()
        self._cfg.save()
        self._apply_btn.setEnabled(False)
        self._status.showMessage("Wird angewendet…")

        worker = ApplyWorker(self._cfg, configs, self._fps_spin.value())
        worker.done.connect(self._on_apply_done)
        worker.start()
        self._workers.append(worker)

    def _on_apply_done(self, ok: bool, msg: str):
        self._apply_btn.setEnabled(True)
        self._status.showMessage(msg)
        self._svc_status_widget.refresh()

    def _run_wizard(self):
        wizard = SetupWizard(self._cfg, self)
        wizard.setup_complete.connect(self._on_setup_complete)
        wizard.exec()

    def _silent_update_check(self):
        if not self._cfg.update_url:
            return
        self._update_checker = UpdateChecker(self._cfg.update_url)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.check_failed.connect(lambda _: None)  # silent on fail
        self._update_checker.start()

    def _manual_update_check(self):
        if not self._cfg.update_url:
            self._status.showMessage("Keine Update-URL konfiguriert — Einstellungen → Updates", 4000)
            return
        self._update_check_btn.setEnabled(False)
        self._update_check_btn.setText("↑  Prüfe…")
        checker = UpdateChecker(self._cfg.update_url)
        checker.update_available.connect(self._on_update_available)
        checker.up_to_date.connect(lambda v: self._on_check_done(f"Bereits aktuell (v{v})"))
        checker.check_failed.connect(lambda e: self._on_check_done(f"Fehler: {e}"))
        checker.start()
        self._workers.append(checker)

    def _on_check_done(self, msg: str):
        self._update_check_btn.setEnabled(True)
        self._update_check_btn.setText("↑  Updates")
        self._status.showMessage(msg, 5000)

    def _on_update_available(self, remote: str, changelog: dict):
        self._pending_update = (remote, changelog)
        self._update_check_btn.setEnabled(True)
        self._update_check_btn.setText("↑  Updates")
        self._update_check_btn.setStyleSheet(
            "background:#1e3a5f;border:1px solid #89b4fa;border-radius:5px;padding:4px 10px;"
        )
        # Show UpdateBanner
        self._update_banner.deleteLater()
        self._update_banner = UpdateBanner(remote, self)
        self._update_banner.show_dialog.connect(self._show_update_dialog)
        # Insert after setup_banner
        outer = self.centralWidget().layout()
        outer.insertWidget(1, self._update_banner)

    def _show_update_dialog(self):
        if not hasattr(self, "_pending_update"):
            return
        remote, changelog = self._pending_update
        dlg = UpdateDialog(__version__, remote, changelog, self._cfg.update_url, self)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self._cfg, self)
        dlg.saved.connect(self._on_setup_complete)
        dlg.exec()

    def _on_setup_complete(self):
        self._fps_spin.setValue(self._cfg.fps)
        self._setup_banner.update_cfg(self._cfg)
        self._status.showMessage("Konfiguration gespeichert.")

    def closeEvent(self, event):
        for w in self._workers:
            if w.isRunning():
                w.quit()
                w.wait(2000)
        event.accept()


# ---------------------------------------------------------------------------

def _setup_palette(app: QApplication):
    from PySide6.QtGui import QPalette, QColor
    app.setStyle("Fusion")
    p = QPalette()
    bg   = QColor(30,  30,  46)   # #1e1e2e
    bg2  = QColor(24,  24,  37)   # #18182
    fg   = QColor(205, 214, 244)  # #cdd6f4
    sub  = QColor(166, 173, 200)  # #a6adc8
    btn  = QColor(49,  50,  68)   # #313244
    acc  = QColor(137, 180, 250)  # #89b4fa

    p.setColor(QPalette.ColorRole.Window,          bg)
    p.setColor(QPalette.ColorRole.WindowText,      fg)
    p.setColor(QPalette.ColorRole.Base,            bg2)
    p.setColor(QPalette.ColorRole.AlternateBase,   bg)
    p.setColor(QPalette.ColorRole.Text,            fg)
    p.setColor(QPalette.ColorRole.PlaceholderText, sub)
    p.setColor(QPalette.ColorRole.Button,          btn)
    p.setColor(QPalette.ColorRole.ButtonText,      fg)
    p.setColor(QPalette.ColorRole.Highlight,       acc)
    p.setColor(QPalette.ColorRole.HighlightedText, bg)
    p.setColor(QPalette.ColorRole.Link,            acc)
    p.setColor(QPalette.ColorRole.ToolTipBase,     btn)
    p.setColor(QPalette.ColorRole.ToolTipText,     fg)

    # Disabled state
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, sub)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, sub)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       sub)

    app.setPalette(p)
    app.setStyleSheet(
        "QToolTip{background:#313244;color:#cdd6f4;border:1px solid #585b70;padding:4px;}"
        "QScrollBar:vertical{width:8px;background:#1e1e2e;border-radius:4px;}"
        "QScrollBar::handle:vertical{background:#45475a;border-radius:4px;min-height:24px;}"
        "QScrollBar::handle:vertical:hover{background:#585b70;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        "QScrollBar:horizontal{height:8px;background:#1e1e2e;border-radius:4px;}"
        "QScrollBar::handle:horizontal{background:#45475a;border-radius:4px;min-width:24px;}"
        "QTabBar::tab{padding:6px 14px;border-radius:4px 4px 0 0;}"
        "QTabBar::tab:selected{background:#313244;}"
        "QPushButton{border-radius:5px;padding:4px 10px;}"
        "QPushButton:hover{background:#45475a;}"
        "QLineEdit{border:1px solid #313244;border-radius:5px;padding:3px 6px;}"
        "QLineEdit:focus{border-color:#89b4fa;}"
        "QGroupBox{border:1px solid #313244;border-radius:6px;margin-top:8px;padding-top:6px;}"
        "QGroupBox::title{subcontrol-origin:margin;left:8px;}"
    )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    _setup_palette(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
