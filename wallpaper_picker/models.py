import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_WP_CONFIGS_DIR = Path.home() / ".config/wallpaper-picker/wallpaper-configs"


@dataclass
class WallpaperConfig:
    """Per-wallpaper overrides. None = fall back to global config."""
    fps:                  Optional[int]  = None
    fullscreen_pause:     Optional[bool] = None
    disable_particles:    Optional[bool] = None
    disable_mouse:        Optional[bool] = None
    no_audio_processing:  Optional[bool] = None

    def is_customized(self) -> bool:
        return any(v is not None for v in dataclasses.asdict(self).values())

    @classmethod
    def merge(cls, configs: list["WallpaperConfig"]) -> "WallpaperConfig":
        """Merge configs from multiple active wallpapers.

        fps: minimum of all overrides (most conservative).
        booleans: True wins — if any wallpaper enables a restriction, it applies.
        """
        if not configs:
            return cls()
        fps_values = [c.fps for c in configs if c.fps is not None]
        def _any_true(attr: str) -> Optional[bool]:
            vals = [getattr(c, attr) for c in configs if getattr(c, attr) is not None]
            return True if True in vals else (False if vals else None)
        return cls(
            fps               = min(fps_values) if fps_values else None,
            fullscreen_pause  = _any_true("fullscreen_pause"),
            disable_particles = _any_true("disable_particles"),
            disable_mouse     = _any_true("disable_mouse"),
            no_audio_processing = _any_true("no_audio_processing"),
        )

    def save(self, wp_id: str) -> None:
        _WP_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in dataclasses.asdict(self).items() if v is not None}
        (_WP_CONFIGS_DIR / f"{wp_id}.json").write_text(json.dumps(data, indent=2))

    def delete(self, wp_id: str) -> None:
        p = _WP_CONFIGS_DIR / f"{wp_id}.json"
        p.unlink(missing_ok=True)

    @classmethod
    def load(cls, wp_id: str) -> "WallpaperConfig":
        p = _WP_CONFIGS_DIR / f"{wp_id}.json"
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text())
            valid = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in valid})
        except Exception:
            return cls()


@dataclass
class LWEStatus:
    local_commit:    str  = ""
    local_date:      str  = ""
    remote_commit:   str  = ""
    remote_date:     str  = ""
    up_to_date:      bool = True
    supported_flags: list = None  # type: ignore
    compatible:      bool = True
    missing_flags:   list = None  # type: ignore
    error:           str  = ""

    def __post_init__(self):
        if self.supported_flags is None:
            self.supported_flags = []
        if self.missing_flags is None:
            self.missing_flags = []


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
        for name in ("preview.jpg", "preview.gif", "preview.png", "preview.webp"):
            p = self.path / name
            if p.exists() and p.stat().st_size > 0:
                return p
        return None


@dataclass
class MonitorConfig:
    name: str
    wallpaper_id: str = ""
