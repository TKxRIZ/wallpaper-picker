import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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
