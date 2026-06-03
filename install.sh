#!/usr/bin/env bash
# Wallpaper Engine – Linux  |  Installer
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${GREEN}▶${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
fail()  { echo -e "${RED}✗${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${BOLD}── $* ──${NC}"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
APP_DEST="$BIN_DIR/wallpaper-picker"
TRAY_DEST="$BIN_DIR/wallpaper-tray"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"
TRAY_RELEASE_URL="https://github.com/TKxRIZ/wallpaper-tray/releases/latest/download/wallpaper-tray-linux-x86_64"

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Wallpaper Engine – Linux  ·  Installer${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

# ── 1. Voraussetzungen ──────────────────────────────────────────────────────

step "Voraussetzungen"

command -v python3 &>/dev/null || fail "Python 3 nicht gefunden."
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJ=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MIN=$(python3 -c "import sys; print(sys.version_info.minor)")
[[ "$PY_MAJ" -ge 3 && "$PY_MIN" -ge 11 ]] || fail "Python 3.11+ benötigt (gefunden: $PY_VER)"
ok "Python $PY_VER"

if ! python3 -c "import PySide6" 2>/dev/null; then
    warn "PySide6 nicht gefunden – installiere via pip..."
    pip install --user --quiet PySide6 || fail "pip install PySide6 fehlgeschlagen."
    ok "PySide6 installiert"
else
    ok "PySide6 vorhanden"
fi

[[ -f "$REPO_DIR/wallpaper_picker/__init__.py" ]] \
    || fail "Paket wallpaper_picker/ nicht gefunden. Bitte im Repo-Verzeichnis ausführen."
VERSION=$(python3 -c "
import re, pathlib
m = re.search(r'__version__\s*=\s*[\"\']([\w.]+)[\"\']]',
              pathlib.Path('$REPO_DIR/wallpaper_picker/__init__.py').read_text())
print(m.group(1) if m else '?')
" 2>/dev/null || echo "?")
ok "wallpaper-picker v$VERSION erkannt"

# ── 2. wallpaper-picker installieren ───────────────────────────────────────

step "wallpaper-picker installieren"

mkdir -p "$BIN_DIR"

# Erzeuge Launcher mit festem Repo-Pfad (damit git pull ausreicht)
cat > "$APP_DEST" << LAUNCHER
#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT = Path("$REPO_DIR")
sys.path.insert(0, str(PROJECT))

from wallpaper_picker.__main__ import main
main()
LAUNCHER
chmod +x "$APP_DEST"
ok "Launcher → $APP_DEST  (verweist auf $REPO_DIR)"

# ── 3. wallpaper-tray installieren ─────────────────────────────────────────

step "wallpaper-tray installieren"

# Prüfe ob bereits lokal gebaut (Cargo)
LOCAL_TRAY="$REPO_DIR/tray/target/release/wallpaper-tray"
if [[ -f "$LOCAL_TRAY" ]]; then
    cp "$LOCAL_TRAY" "$TRAY_DEST"
    chmod +x "$TRAY_DEST"
    ok "Tray-Binary aus lokalem Build → $TRAY_DEST"
elif command -v curl &>/dev/null || command -v wget &>/dev/null; then
    info "Lade wallpaper-tray von GitHub Releases..."
    TMP_TRAY="$(mktemp)"
    if command -v curl &>/dev/null; then
        curl -fsSL "$TRAY_RELEASE_URL" -o "$TMP_TRAY" \
            && mv "$TMP_TRAY" "$TRAY_DEST" \
            && chmod +x "$TRAY_DEST" \
            && ok "wallpaper-tray heruntergeladen → $TRAY_DEST" \
            || { warn "Download fehlgeschlagen — Tray übersprungen"; rm -f "$TMP_TRAY"; }
    else
        wget -qO "$TMP_TRAY" "$TRAY_RELEASE_URL" \
            && mv "$TMP_TRAY" "$TRAY_DEST" \
            && chmod +x "$TRAY_DEST" \
            && ok "wallpaper-tray heruntergeladen → $TRAY_DEST" \
            || { warn "Download fehlgeschlagen — Tray übersprungen"; rm -f "$TMP_TRAY"; }
    fi
else
    warn "Kein curl/wget — wallpaper-tray nicht installiert (optional)"
fi

# ── 4. Desktop-Einträge ────────────────────────────────────────────────────

step "Desktop-Einträge"

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/wallpaper-picker.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Wallpaper Engine – Linux
GenericName=Wallpaper Manager
Comment=GUI für linux-wallpaperengine (Wallpaper Engine auf Linux)
Exec=$APP_DEST
Icon=preferences-desktop-wallpaper
Categories=Settings;DesktopSettings;
Keywords=wallpaper;hintergrund;wallpaper-engine;linux;
Terminal=false
StartupNotify=true
EOF
ok "Anwendungseintrag → $DESKTOP_DIR/wallpaper-picker.desktop"

# Autostart: tray (wenn vorhanden), sonst picker
mkdir -p "$AUTOSTART_DIR"
if [[ -x "$TRAY_DEST" ]]; then
    AUTOSTART_EXEC="$TRAY_DEST"
    AUTOSTART_NAME="Wallpaper Tray"
else
    AUTOSTART_EXEC="$APP_DEST"
    AUTOSTART_NAME="Wallpaper Engine – Linux"
fi
cat > "$AUTOSTART_DIR/wallpaper-picker.desktop" << EOF
[Desktop Entry]
Type=Application
Name=$AUTOSTART_NAME (Autostart)
Exec=$AUTOSTART_EXEC
Icon=preferences-desktop-wallpaper
X-KDE-autostart-condition=ksmserver
Hidden=false
NoDisplay=true
EOF
ok "Autostart → $AUTOSTART_DIR/wallpaper-picker.desktop  ($AUTOSTART_EXEC)"

# KDE: Tray-Icon sichtbar machen
KDE_CFG="$HOME/.config/plasma-org.kde.plasma.desktop-appletsrc"
if [[ -f "$KDE_CFG" ]]; then
    python3 - "$KDE_CFG" <<'PYEOF' 2>/dev/null && ok "KDE Tray-Icon sichtbar gesetzt" || true
import re, sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
if "wallpaper-tray" not in text:
    text = re.sub(r'(knownItems=[^\n]+)', r'shownItems=wallpaper-tray\n\1', text, count=1)
    path.write_text(text)
PYEOF
fi

# ── 5. Systemd-Service ─────────────────────────────────────────────────────

SERVICE_FILE="$HOME/.config/systemd/user/linux-wallpaperengine.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
    step "Systemd-Service anlegen"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=Linux WallpaperEngine
After=graphical-session.target plasma-workspace.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/bin/true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF
    warn "Engine noch nicht konfiguriert → Einstellungen in der App öffnen"
fi
systemctl --user daemon-reload 2>/dev/null || true

# ── 6. PATH-Hinweis ─────────────────────────────────────────────────────────

if ! echo "$PATH" | grep -q "$BIN_DIR"; then
    warn "\$HOME/.local/bin nicht in PATH."
    echo -e "  Füge zur ~/.bashrc oder ~/.zshrc hinzu:"
    echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
fi

# ── Fertig ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
ok "Installation abgeschlossen!"
echo ""
echo -e "  GUI starten:   ${BOLD}wallpaper-picker${NC}"
if [[ -x "$TRAY_DEST" ]]; then
echo -e "  Tray starten:  ${BOLD}wallpaper-tray${NC}  (startet beim nächsten Login automatisch)"
fi
echo ""
echo -e "  ${YELLOW}Beim ersten Start: Einstellungen öffnen${NC}"
echo -e "  ${YELLOW}und Binary + Assets-Verzeichnis konfigurieren.${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
