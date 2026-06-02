__version__ = "1.0.3"

__changelog__: dict[str, list[str]] = {
    "1.0.3": [
        "System-Tray: Rechtsklick-Menü mit Zuletzt verwendet, Zufällig, Service-Toggle",
        "Fenster schließen versteckt die App (Beenden nur über Tray → Beenden)",
        "Start-Flag --minimized / --tray für Autostart ohne Fenster",
        "Tray-Icon: preferences-desktop-wallpaper + gemalter Fallback",
        "App-Name 'wallpaper-picker' statt Skriptdateiname in KDE-Tray",
    ],
    "1.0.2": [
        "LWE-Versionserkennung: Commit-Hash, Datum, Update-Check via GitHub API",
        "Kompatibilitätsprüfung: --help-Parsing, Required-Flags-Check",
        "LWE-Status-Widget im Updates-Tab mit Ampel-Anzeige",
    ],
    "1.0.1": [
        "Fix: git-Befehle laufen auf dem Host statt im Container (git nicht in distrobox)",
        "Fix: Changelog-Regex unterstützt jetzt Type-Annotationen",
        "Verbesserter Updater: Fortschrittsbalken, Syntax-Check, Backup/Rollback",
    ],
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
