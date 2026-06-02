#!/usr/bin/env bash
# Wallpaper Engine – Linux  |  Installer
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${GREEN}▶${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
ok()      { echo -e "${GREEN}✓${NC} $*"; }
fail()    { echo -e "${RED}✗${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SRC="$SCRIPT_DIR/wallpaper-picker.py"
APP_DEST="$HOME/.local/bin/wallpaper-picker"
DESKTOP_DIR="$HOME/.local/share/applications"
SERVICE_FILE="$HOME/.config/systemd/user/linux-wallpaperengine.service"

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${BOLD}  Wallpaper Engine – Linux  ·  Installer${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""

# ── 1. Voraussetzungen ──────────────────────────────────────────────────────

info "Prüfe Python 3..."
command -v python3 &>/dev/null || fail "Python 3 nicht gefunden."
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
[[ "$PY_MAJOR" -ge 3 && "$PY_MINOR" -ge 11 ]] || fail "Python 3.11+ benötigt (gefunden: $PY_VER)"
ok "Python $PY_VER"

info "Prüfe PySide6..."
if ! python3 -c "import PySide6" 2>/dev/null; then
    warn "PySide6 nicht gefunden – installiere via pip..."
    pip install --user --quiet PySide6 || fail "pip install PySide6 fehlgeschlagen."
    ok "PySide6 installiert"
else
    ok "PySide6 vorhanden"
fi

# ── 2. App installieren ──────────────────────────────────────────────────────

info "Installiere wallpaper-picker..."
[[ -f "$APP_SRC" ]] || fail "wallpaper-picker.py nicht gefunden in $SCRIPT_DIR"
mkdir -p "$HOME/.local/bin"
cp "$APP_SRC" "$APP_DEST"
chmod +x "$APP_DEST"
ok "Installiert → $APP_DEST"

# ── 3. Desktop-Eintrag ──────────────────────────────────────────────────────

info "Erstelle Desktop-Eintrag..."
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
ok "Desktop-Eintrag → $DESKTOP_DIR/wallpaper-picker.desktop"

# ── 4. systemd-Service (nur wenn nicht vorhanden) ───────────────────────────

if [[ ! -f "$SERVICE_FILE" ]]; then
    warn "Kein Service gefunden – lege Platzhalter an"
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
    warn "Engine noch nicht konfiguriert → bitte Einstellungen in der App öffnen"
else
    ok "Service bereits vorhanden"
fi

systemctl --user daemon-reload 2>/dev/null || true

# ── 5. PATH-Hinweis ─────────────────────────────────────────────────────────

if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    warn "\$HOME/.local/bin ist nicht in PATH – füge folgendes zu ~/.bashrc oder ~/.zshrc hinzu:"
    echo "       export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Fertig ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
ok "Installation abgeschlossen!"
echo ""
echo -e "  Starten:    ${BOLD}wallpaper-picker${NC}"
echo -e "  Oder:       KDE App-Launcher → Wallpaper Engine"
echo ""
echo -e "  ${YELLOW}Beim ersten Start: Einstellungen öffnen${NC}"
echo -e "  ${YELLOW}und Binary + Assets konfigurieren.${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
