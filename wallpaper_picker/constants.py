from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
ENGINE_DIR  = PROJECT_DIR / "linux-wallpaperengine"

WORKSHOP_DIR = Path.home() / ".local/share/Steam/steamapps/workshop/content/431960"
ACF_FILE     = Path.home() / ".local/share/Steam/steamapps/workshop/appworkshop_431960.acf"
SERVICE_FILE = Path.home() / ".config/systemd/user/linux-wallpaperengine.service"
CONFIG_PATH  = Path.home() / ".config/wallpaper-picker/config.json"
STEAM_API    = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"

CARD_W, CARD_H   = 204, 168
THUMB_W, THUMB_H = 200, 130

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

LWE_REQUIRED_FLAGS  = ["--screen-root", "--bg", "--fps", "--assets-dir"]
LWE_MIN_COMMIT_DATE = "2024-01-01"
LWE_GITHUB_API      = "https://api.github.com/repos/Almamu/linux-wallpaperengine/commits/main"

IS_ATOMIC = Path("/run/ostree-booted").exists()
try:
    _osr = dict(l.split("=", 1) for l in Path("/etc/os-release").read_text().splitlines() if "=" in l)
    DISTRO_NAME = _osr.get("NAME", "Unknown").strip('"')
    DISTRO_ID   = _osr.get("ID", "").strip('"')
except Exception:
    DISTRO_NAME, DISTRO_ID = "Unknown", ""


def _vtuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)
