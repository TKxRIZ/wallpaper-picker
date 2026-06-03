import json
import re
import subprocess
from pathlib import Path

from .constants import WORKSHOP_DIR, ACF_FILE, SERVICE_FILE, SERVICE_TEMPLATE
from .config import Config, validate_setup
from .models import Wallpaper, MonitorConfig


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
        fps     = int(fps_m.group(1)) if fps_m else 30
        configs = [
            MonitorConfig(name=s, wallpaper_id=bgs[i] if i < len(bgs) else "")
            for i, s in enumerate(screens)
        ]
        return configs, fps
    except Exception:
        return [], 30


def write_service(cfg: Config, monitor_configs: list[MonitorConfig], fps: int, wp_cfg=None):
    issues = validate_setup(cfg)
    if issues:
        raise ValueError("Konfiguration unvollständig:\n• " + "\n• ".join(issues))
    if not any(mc.wallpaper_id for mc in monitor_configs):
        raise ValueError("Kein Wallpaper ausgewählt.")

    screen_args = " ".join(
        f"--screen-root {mc.name} --bg {mc.wallpaper_id}"
        for mc in monitor_configs if mc.wallpaper_id
    )
    exec_start = cfg.build_exec_start(screen_args, fps, wp_cfg)

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
