# Wallpaper Engine – Linux GUI

A GUI for [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) — run Wallpaper Engine wallpapers on Linux. Built with Atomic desktops (Bazzite, Silverblue) in mind, but works on traditional distros too.

![Screenshot](screenshot.png)

## Features

- **Browse wallpapers** — installed (local) + subscribed but not downloaded (Steam API)
- **Multi-monitor** — assign a different wallpaper per monitor
- **Setup wizard** — guided first-run, builds linux-wallpaperengine in-app via Distrobox
- **Self-updater** — checks GitHub on startup, downloads with syntax verification + rollback
- **LWE updater** — `git pull` + incremental rebuild with version/compatibility check
- **Service management** — start/stop/restart, autostart, live log (systemd user service)
- **Atomic-first** — runs on immutable distros without system packages (Distrobox, Toolbox, or direct)

## Requirements

- [Wallpaper Engine](https://store.steampowered.com/app/431960/) on Steam (for assets + workshop wallpapers)
- [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) binary (the setup wizard can build it for you)
- Python 3.11+
- **Atomic desktops:** [Distrobox](https://distrobox.it/) (pre-installed on Bazzite)
- **Traditional distros:** build dependencies listed in `Einstellungen → Info / Setup`

## Installation

```bash
git clone https://github.com/TKxRIZ/wallpaper-picker
cd wallpaper-picker
./install.sh
```

Then launch from the app menu or run `wallpaper-picker`.

On first start, the **Setup wizard** opens and guides you through:
1. Choosing execution mode (Distrobox recommended on Atomic)
2. Locating or building the linux-wallpaperengine binary
3. Locating the Wallpaper Engine assets directory

## Usage

| Action | How |
|---|---|
| Apply wallpaper | Click a wallpaper → click **Anwenden** |
| Multi-monitor | Click a monitor button in the right panel → click a wallpaper |
| Change FPS | Right panel → Wiedergabe → FPS |
| Check for updates | Toolbar → **↑ Updates** |
| Build / update LWE | Settings → Updates → linux-wallpaperengine |

## Update URL

After cloning, set your update URL in `Einstellungen → Updates`:

```
https://raw.githubusercontent.com/TKxRIZ/wallpaper-picker/main/wallpaper-picker.py
```

The app checks for updates once per day on startup.

## Execution modes

| Mode | When to use |
|---|---|
| `distrobox` | Bazzite, Silverblue, other immutable distros |
| `direct` | Traditional distros with LWE installed to `~/.local/bin` |
| `toolbox` | Toolbx/Toolbox containers |
| `custom` | Any other prefix command |

## License

[LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html) — uses [PySide6](https://doc.qt.io/qtforpython/) (LGPL-3.0).

linux-wallpaperengine is [GPL-3.0](https://github.com/Almamu/linux-wallpaperengine/blob/master/LICENSE). Wallpaper Engine is proprietary software by Zlexy GmbH — you must own it on Steam.
