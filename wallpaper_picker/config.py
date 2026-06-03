import dataclasses
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .constants import CONFIG_PATH, ENGINE_DIR, LWE_MIN_COMMIT_DATE, PROJECT_DIR


@dataclass
class Config:
    mode: str             = "distrobox"
    container: str        = "wallpaperengine"
    binary: str           = ""
    assets_dir: str       = ""
    custom_prefix: str    = ""
    fps: int              = 30
    service_name: str     = "linux-wallpaperengine"
    steam_api_key: str    = ""
    update_url: str       = ""
    last_update_check: float = 0.0
    dismissed_update: str    = ""
    project_dir: str         = str(PROJECT_DIR)
    fullscreen_pause: bool   = True
    disable_particles: bool  = False
    disable_mouse: bool      = False
    no_audio_processing: bool = False
    recent_wallpapers: list  = dataclasses.field(default_factory=list)

    _BINARY_HINTS = [
        ENGINE_DIR / "build/output/linux-wallpaperengine",
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
                pass
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
        tmp.replace(CONFIG_PATH)

    def build_exec_start(self, screen_args: str, fps: int, wp_cfg=None) -> str:
        # wp_cfg is an optional WallpaperConfig; its non-None values override global settings
        def _get(attr):
            if wp_cfg is not None:
                v = getattr(wp_cfg, attr, None)
                if v is not None:
                    return v
            return getattr(self, attr)

        effective_fps              = wp_cfg.fps if (wp_cfg and wp_cfg.fps is not None) else fps
        effective_fullscreen_pause = _get("fullscreen_pause")
        effective_particles        = _get("disable_particles")
        effective_mouse            = _get("disable_mouse")
        effective_audio            = _get("no_audio_processing")

        bin_dir = str(Path(self.binary).parent) if self.binary else "."
        lib_dir = str(Path(self.binary).parent.parent / "lib") if self.binary else ""
        ld_path = f"{bin_dir}:{lib_dir}" if bin_dir else ""
        env = (
            "WAYLAND_DISPLAY=${WAYLAND_DISPLAY} "
            "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR} "
            "XDG_SESSION_TYPE=wayland"
            + (f" LD_LIBRARY_PATH={ld_path}" if ld_path else "")
        )
        extra_flags = " --fullscreen-pause-only-active" if effective_fullscreen_pause else ""
        if effective_particles: extra_flags += " --disable-particles"
        if effective_mouse:     extra_flags += " --disable-mouse"
        if effective_audio:     extra_flags += " --no-audio-processing"
        inner = (
            f"cd {bin_dir} && {env} "
            f"./linux-wallpaperengine "
            f"--assets-dir {self.assets_dir} "
            f"--fps {effective_fps}{extra_flags} {screen_args}"
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
    return True


def lwe_quick_compat_check(cfg: Config) -> list[str]:
    if not ENGINE_DIR.exists():
        return []
    try:
        r = subprocess.run(
            ["git", "-C", str(ENGINE_DIR), "log", "-1", "--format=%cd", "--date=short"],
            capture_output=True, text=True, timeout=3,
        )
        date = r.stdout.strip()
        if date and date < LWE_MIN_COMMIT_DATE:
            return [f"linux-wallpaperengine zu alt ({date}). Bitte aktualisieren."]
    except Exception:
        pass
    return []
