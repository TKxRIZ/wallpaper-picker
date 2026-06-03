import ast
import json
import re
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap

from . import __version__
from .constants import (
    PROJECT_DIR, ENGINE_DIR, STEAM_API, THUMB_W, THUMB_H,
    LWE_REQUIRED_FLAGS, LWE_MIN_COMMIT_DATE, LWE_GITHUB_API, _vtuple,
)
from .models import Wallpaper, MonitorConfig, LWEStatus
from .config import Config
from .engine import write_service


class ApplyWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, cfg: Config, configs: list[MonitorConfig], fps: int, wp_cfg=None):
        super().__init__()
        self.cfg, self.configs, self.fps, self.wp_cfg = cfg, configs, fps, wp_cfg

    def run(self):
        try:
            write_service(self.cfg, self.configs, self.fps, self.wp_cfg)
            subprocess.run(["pkill", "-f", "linux-wallpaperengine"], capture_output=True, timeout=5)
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True, timeout=10)
            subprocess.run(
                ["systemctl", "--user", "restart", self.cfg.service_name],
                check=True, timeout=30,
            )
            from .i18n import t
            self.done.emit(True, t("worker_apply_ok"))
        except ValueError as e:
            self.done.emit(False, str(e))
        except subprocess.TimeoutExpired:
            from .i18n import t
            self.done.emit(False, t("worker_timeout"))
        except subprocess.CalledProcessError as e:
            from .i18n import t
            self.done.emit(False, t("worker_systemctl_err", e=e))
        except Exception as e:
            from .i18n import t
            self.done.emit(False, t("worker_err", e=e))


class ServiceControlWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, action: str, service: str):
        super().__init__()
        self.action, self.service = action, service

    def run(self):
        try:
            subprocess.run(["systemctl", "--user", self.action, self.service], check=True, timeout=120)
            self.done.emit(True, f"{self.action} erfolgreich")
        except Exception as e:
            self.done.emit(False, str(e))


class SteamMetaWorker(QThread):
    batch_ready = Signal(list)

    def __init__(self, ids: list[str], api_key: str = ""):
        super().__init__()
        self.ids      = ids
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
                req  = urllib.request.Request(STEAM_API, data=body.encode(), method="POST")
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
            r   = subprocess.run(self.cmd, capture_output=True, text=True, timeout=20)
            out = (r.stdout + r.stderr).strip()[:800]
            ok  = r.returncode == 0 or "linux-wallpaperengine" in out.lower() or "usage" in out.lower()
            self.result.emit(ok, out or "(kein Output)")
        except subprocess.TimeoutExpired:
            self.result.emit(False, "Timeout nach 20s — Binary antwortet nicht.")
        except FileNotFoundError as e:
            self.result.emit(False, f"Nicht gefunden: {e}")
        except Exception as e:
            self.result.emit(False, str(e))


class LocalThumbnailWorker(QThread):
    loaded = Signal(str, QPixmap)

    def __init__(self, wallpapers: list[Wallpaper]):
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
            if pix.width() > THUMB_W * 2 or pix.height() > THUMB_H * 2:
                pix = pix.scaled(
                    THUMB_W * 2, THUMB_H * 2,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self.loaded.emit(wp.id, pix)


class BuildWorker(QThread):
    output_line = Signal(str)
    done        = Signal(bool, str, str)

    def __init__(self, container: str, repo_dir: str):
        super().__init__()
        self._container_name = container
        self.repo_dir        = repo_dir

    def _run(self, label: str, cmd: list[str]) -> bool:
        self.output_line.emit(f"\n▶ {label}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
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

        if not Path(repo).exists():
            if not self._run("Repository klonen",
                             ["git", "clone", "https://github.com/Almamu/linux-wallpaperengine", repo]):
                self.done.emit(False, "git clone fehlgeschlagen", "")
                return
        else:
            self._run("git pull", ["git", "-C", repo, "pull", "--ff-only"])

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


class AppUpdateWorker(QThread):
    output_line = Signal(str)
    done        = Signal(bool, str)

    def _run_step(self, label: str, cmd: list[str]) -> bool:
        self.output_line.emit(f"▶ {label}")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            for line in proc.stdout:  # type: ignore
                self.output_line.emit(f"  {line.rstrip()}")
            proc.wait()
            return proc.returncode == 0
        except Exception as e:
            self.output_line.emit(f"  Fehler: {e}")
            return False

    def run(self):
        from .i18n import t
        self.output_line.emit(f"Repo: {PROJECT_DIR}")

        if not self._run_step("git fetch origin", ["git", "-C", str(PROJECT_DIR), "fetch", "origin"]):
            self.done.emit(False, t("worker_fetch_fail"))
            return

        if not self._run_step(
            "git reset --hard origin/main",
            ["git", "-C", str(PROJECT_DIR), "reset", "--hard", "origin/main"],
        ):
            self.done.emit(False, t("worker_reset_fail"))
            return

        install_sh = PROJECT_DIR / "install.sh"
        if install_sh.exists():
            self._run_step("install.sh", ["bash", str(install_sh)])

        self.done.emit(True, t("worker_update_ok"))


class UpdateChecker(QThread):
    update_available = Signal(str, dict)
    up_to_date       = Signal(str)
    check_failed     = Signal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers={"User-Agent": f"wallpaper-picker/{__version__}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                head = r.read(8192).decode("utf-8", errors="ignore")

            vm = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', head)
            if not vm:
                self.check_failed.emit("Keine Versionsinformation gefunden.")
                return
            remote = vm.group(1)

            changelog: dict = {}
            cm = re.search(r'__changelog__[^=]+=\s*(\{.+?\n\})', head, re.DOTALL)
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


class UpdateLWEWorker(QThread):
    output_line = Signal(str)
    done        = Signal(bool, str)

    def __init__(self, container: str, repo_dir: str):
        super().__init__()
        self._container_name = container
        self._repo_dir       = repo_dir

    def _host(self, label: str, cmd: list[str]) -> bool:
        self.output_line.emit(f"\n▶ {label}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:  # type: ignore
            self.output_line.emit(line.rstrip())
        proc.wait()
        ok = proc.returncode == 0
        self.output_line.emit("✓ OK" if ok else f"✗ exit {proc.returncode}")
        return ok

    def _container(self, label: str, cmd: str) -> bool:
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
        self._host("Aktueller Commit", ["git", "-C", r, "log", "-1", "--format=Vorher: %h — %s"])
        if not self._host("git pull", ["git", "-C", r, "pull", "--ff-only"]):
            self.done.emit(False, "git pull fehlgeschlagen — evtl. lokale Änderungen vorhanden.")
            return
        self._host("Neuer Commit", ["git", "-C", r, "log", "-1", "--format=Nachher: %h — %s"])
        if not self._container("cmake build", f'cd "{r}" && cmake --build build -j$(nproc)'):
            self.done.emit(False, "Build fehlgeschlagen.")
            return
        self.done.emit(True, "linux-wallpaperengine aktualisiert.")


class LWEVersionChecker(QThread):
    finished = Signal(object)

    def __init__(self, cfg: Config):
        super().__init__()
        self._cfg = cfg

    def run(self):
        status = LWEStatus()
        repo   = str(ENGINE_DIR)

        try:
            r = subprocess.run(
                ["git", "-C", repo, "log", "-1", "--format=%h\t%H\t%cd", "--date=short"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                short, _, date    = r.stdout.strip().split("\t")
                status.local_commit = short
                status.local_date   = date
        except Exception as e:
            status.error = f"git log: {e}"

        try:
            req = urllib.request.Request(LWE_GITHUB_API, headers={"User-Agent": f"wallpaper-picker/{__version__}"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            status.remote_commit = data["sha"][:7]
            status.remote_date   = data["commit"]["committer"]["date"][:10]
            status.up_to_date    = data["sha"].startswith(status.local_commit) if status.local_commit else False
        except Exception as e:
            status.remote_commit = "?"
            status.remote_date   = "?"
            if not status.error:
                status.error = f"GitHub API: {e}"

        if self._cfg.binary and Path(self._cfg.binary).exists():
            try:
                bin_dir = str(Path(self._cfg.binary).parent)
                lib_dir = str(Path(self._cfg.binary).parent.parent / "lib")
                ld_path = f"{bin_dir}:{lib_dir}"
                if self._cfg.mode == "distrobox":
                    cmd = ["distrobox", "enter", self._cfg.container, "--",
                           "bash", "-c", f"LD_LIBRARY_PATH={ld_path} {self._cfg.binary} --help"]
                elif self._cfg.mode == "toolbox":
                    cmd = ["toolbox", "run", "--container", self._cfg.container,
                           "bash", "-c", f"LD_LIBRARY_PATH={ld_path} {self._cfg.binary} --help"]
                else:
                    cmd = [self._cfg.binary, "--help"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                                   env={**__import__("os").environ, "LD_LIBRARY_PATH": ld_path})
                help_text           = r.stdout + r.stderr
                status.supported_flags = re.findall(r'(--[\w-]+)', help_text)
                status.missing_flags   = [f for f in LWE_REQUIRED_FLAGS if f not in status.supported_flags]
                if status.local_date and status.local_date < LWE_MIN_COMMIT_DATE:
                    status.missing_flags.append(f"Zu alter Commit ({status.local_date} < {LWE_MIN_COMMIT_DATE})")
                status.compatible = len(status.missing_flags) == 0
            except Exception as e:
                status.compatible    = False
                status.missing_flags = [f"--help fehlgeschlagen: {e}"]
        else:
            status.compatible    = False
            status.missing_flags = ["Binary nicht gefunden"]

        self.finished.emit(status)
