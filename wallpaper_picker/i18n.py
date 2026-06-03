"""
Simple two-language translation module.
Import: from ..i18n import t
Usage:  t("apply")  or  t("n_installed", n=52)
"""

_lang = "de"

_strings: dict[str, dict[str, str]] = {
    # ── Window / toolbar ────────────────────────────────────────────────────
    "app_title":           {"de": "Wallpaper Engine – Linux",     "en": "Wallpaper Engine – Linux"},
    "btn_wizard":          {"de": "⭐  Einrichtungs-Assistent",   "en": "⭐  Setup Wizard"},
    "btn_updates":         {"de": "↑  Updates",                   "en": "↑  Updates"},
    "btn_checking":        {"de": "↑  Prüfe…",                    "en": "↑  Checking…"},
    "btn_settings":        {"de": "⚙  Einstellungen",             "en": "⚙  Settings"},
    "btn_apply":           {"de": "Anwenden",                     "en": "Apply"},

    # ── Tabs ─────────────────────────────────────────────────────────────────
    "tab_installed":       {"de": "Installiert ({n})",            "en": "Installed ({n})"},
    "tab_available":       {"de": "Verfügbar (wird geladen…)",    "en": "Available (loading…)"},
    "tab_available_n":     {"de": "Verfügbar ({n})",              "en": "Available ({n})"},

    # ── Preview panel ────────────────────────────────────────────────────────
    "preview_hint":        {"de": "← Wallpaper auswählen",        "en": "← Select a wallpaper"},
    "preview_no_image":    {"de": "Kein Vorschaubild",            "en": "No preview image"},
    "label_id":            {"de": "ID: {id}",                     "en": "ID: {id}"},
    "label_fps":           {"de": "FPS:",                         "en": "FPS:"},
    "group_playback":      {"de": "Wiedergabe",                   "en": "Playback"},

    # ── Status bar messages ───────────────────────────────────────────────────
    "status_no_wallpaper": {"de": "Kein Wallpaper ausgewählt — bitte Wallpaper anklicken.", "en": "No wallpaper selected — click a wallpaper first."},
    "status_applying":     {"de": "Wird angewendet…",             "en": "Applying…"},
    "status_applied":      {"de": "Wallpaper angewendet.",        "en": "Wallpaper applied."},
    "status_config_saved": {"de": "Konfiguration gespeichert.",   "en": "Configuration saved."},
    "status_no_url":       {"de": "Keine Update-URL konfiguriert — Einstellungen → Updates", "en": "No update URL configured — Settings → Updates"},
    "status_up_to_date":   {"de": "Bereits aktuell (v{v})",       "en": "Already up to date (v{v})"},
    "status_error":        {"de": "Fehler: {e}",                  "en": "Error: {e}"},

    # ── Dialogs ───────────────────────────────────────────────────────────────
    "dlg_setup_incomplete":      {"de": "Setup unvollständig",    "en": "Setup incomplete"},
    "dlg_setup_incomplete_body": {"de": "Bitte zuerst die Einrichtung abschließen:\n\n• {issues}", "en": "Please complete setup first:\n\n• {issues}"},

    # ── InstalledTab ─────────────────────────────────────────────────────────
    "installed_empty": {
        "de": "Keine Wallpapers gefunden.\n\nSteam → Wallpaper Engine → Workshop → Wallpapers abonnieren,\ndann Steam neu starten damit sie heruntergeladen werden.",
        "en": "No wallpapers found.\n\nSubscribe to wallpapers in Steam → Wallpaper Engine → Workshop,\nthen restart Steam so they get downloaded.",
    },
    "search_placeholder":  {"de": "Suchen…",                      "en": "Search…"},

    # ── AvailableTab ─────────────────────────────────────────────────────────
    "available_info": {
        "de": "In Steam abonniert, aber noch nicht heruntergeladen.\nSteam → Wallpaper Engine → Workshop → Abonnements",
        "en": "Subscribed on Steam but not yet downloaded.\nSteam → Wallpaper Engine → Workshop → Subscriptions",
    },
    "available_loading":   {"de": "Metadaten laden… %v / %m",    "en": "Loading metadata… %v / %m"},
    "available_search":    {"de": "Suchen… (nach dem Laden)",     "en": "Search… (after loading)"},

    # ── UpdateBanner ─────────────────────────────────────────────────────────
    "update_available":    {"de": "Update verfügbar — Version <b>{v}</b>", "en": "Update available — Version <b>{v}</b>"},
    "btn_update":          {"de": "Aktualisieren",                "en": "Update"},

    # ── SetupBanner ──────────────────────────────────────────────────────────
    "issues_more":         {"de": " (+{n} weitere)",              "en": " (+{n} more)"},
    "btn_open_wizard":     {"de": "Setup-Assistent öffnen",       "en": "Open Setup Wizard"},

    # ── ServiceStatusWidget ──────────────────────────────────────────────────
    "service_active":      {"de": "Service aktiv",                "en": "Service active"},
    "service_inactive":    {"de": "Service inaktiv",              "en": "Service inactive"},
    "service_status":      {"de": "Service: {s}",                 "en": "Service: {s}"},

    # ── MonitorPanel ─────────────────────────────────────────────────────────
    "monitor_group":       {"de": "Monitor-Zuordnung",            "en": "Monitor Assignment"},
    "monitor_hint":        {"de": "Monitor wählen → Wallpaper klicken → Anwenden", "en": "Select monitor → click wallpaper → Apply"},
    "monitor_none":        {"de": "— kein Wallpaper",             "en": "— no wallpaper"},

    # ── WallpaperConfigDialog ─────────────────────────────────────────────────
    "wpcfg_title":         {"de": "Konfiguration — {title}",      "en": "Configuration — {title}"},
    "wpcfg_info":          {"de": "Eigene Einstellungen überschreiben die globale Konfiguration nur für dieses Wallpaper.\nLeere Felder verwenden den globalen Wert.", "en": "Custom settings override the global configuration for this wallpaper only.\nEmpty fields use the global value."},
    "wpcfg_fps":           {"de": "FPS:",                         "en": "FPS:"},
    "wpcfg_global":        {"de": "(Global: {v})",                "en": "(Global: {v})"},
    "wpcfg_on":            {"de": "an",                           "en": "on"},
    "wpcfg_off":           {"de": "aus",                          "en": "off"},
    "wpcfg_reset":         {"de": "Zurücksetzen",                 "en": "Reset"},

    # ── SettingsDialog — nav ──────────────────────────────────────────────────
    "settings_title":      {"de": "Einstellungen — Wallpaper Engine – Linux", "en": "Settings — Wallpaper Engine – Linux"},
    "settings_header":     {"de": "⚙  Einstellungen",             "en": "⚙  Settings"},
    "nav_engine":          {"de": "Engine",                       "en": "Engine"},
    "nav_service":         {"de": "Service",                      "en": "Service"},
    "nav_updates":         {"de": "Updates",                      "en": "Updates"},
    "nav_info":            {"de": "Info",                         "en": "Info"},
    "btn_save":            {"de": "Speichern",                    "en": "Save"},
    "btn_cancel":          {"de": "Abbrechen",                    "en": "Cancel"},

    # ── SettingsDialog — Engine ───────────────────────────────────────────────
    "sec_execution":       {"de": "Ausführung",                   "en": "Execution"},
    "field_exec_mode":     {"de": "Ausführungsmodus",             "en": "Execution mode"},
    "field_container":     {"de": "Container-Name",               "en": "Container name"},
    "hint_container":      {"de": "Nur für distrobox / toolbox relevant", "en": "Only relevant for distrobox / toolbox"},
    "field_binary":        {"de": "Binary-Pfad",                  "en": "Binary path"},
    "field_assets":        {"de": "Assets-Verzeichnis",           "en": "Assets directory"},
    "field_prefix":        {"de": "Custom Prefix",                "en": "Custom prefix"},
    "hint_prefix":         {"de": "Nur für Modus 'custom' — Präfix vor dem Binary-Aufruf", "en": "Only for mode 'custom' — prefix before the binary call"},
    "btn_test_binary":     {"de": "Binary testen",                "en": "Test binary"},
    "test_ok":             {"de": "✓ OK",                         "en": "✓ OK"},
    "test_fail":           {"de": "✗ Fehler",                     "en": "✗ Error"},
    "test_running":        {"de": "Wird getestet…",               "en": "Testing…"},
    "sec_steam":           {"de": "Steam",                        "en": "Steam"},
    "field_steam_key":     {"de": "Steam API-Key",                "en": "Steam API key"},
    "hint_steam_key":      {"de": "Optional — verbessert Rate-Limiting beim Laden des Verfügbar-Tabs", "en": "Optional — improves rate limiting when loading the available tab"},
    "steam_key_link":      {"de": "Key holen ↗",                  "en": "Get key ↗"},
    "sec_performance":     {"de": "Performance",                  "en": "Performance"},
    "cb_disable_particles":{"de": "Partikel deaktivieren",        "en": "Disable particles"},
    "hint_particles":      {"de": "Reduziert CPU bei partikelreichen Wallpapers", "en": "Reduces CPU usage for particle-heavy wallpapers"},
    "cb_disable_mouse":    {"de": "Maus-Interaktion deaktivieren","en": "Disable mouse interaction"},
    "hint_mouse":          {"de": "Kleiner CPU-Vorteil, deaktiviert Maus-Reaktion", "en": "Small CPU saving, disables mouse reactivity"},
    "cb_no_audio":         {"de": "Audio-Verarbeitung deaktivieren","en": "Disable audio processing"},
    "hint_audio":          {"de": "Deaktiviert audio-reaktive Effekte", "en": "Disables audio-reactive effects"},
    "sec_language":        {"de": "Sprache",                      "en": "Language"},
    "field_language":      {"de": "Sprache / Language",           "en": "Language"},
    "hint_language":       {"de": "Änderung wird nach Neustart aktiv", "en": "Change takes effect after restart"},
    "restart_required":    {"de": "Neustart erforderlich",        "en": "Restart required"},
    "restart_required_body":{"de": "Die Sprache wurde geändert. Jetzt neu starten?", "en": "The language has been changed. Restart now?"},
    "btn_restart_now":     {"de": "Jetzt neu starten",            "en": "Restart now"},
    "btn_later":           {"de": "Später",                       "en": "Later"},

    # ── SettingsDialog — Service ──────────────────────────────────────────────
    "sec_status":          {"de": "Status",                       "en": "Status"},
    "sec_control":         {"de": "Steuerung",                    "en": "Control"},
    "sec_log":             {"de": "Log",                          "en": "Log"},
    "cb_autostart":        {"de": "Mit Sitzung starten (systemd enable)", "en": "Start with session (systemd enable)"},
    "btn_start":           {"de": "▶  Start",                     "en": "▶  Start"},
    "btn_stop":            {"de": "■  Stop",                      "en": "■  Stop"},
    "btn_restart":         {"de": "↺  Restart",                   "en": "↺  Restart"},

    # ── SettingsDialog — Updates ──────────────────────────────────────────────
    "sec_picker_updates":  {"de": "wallpaper-picker",             "en": "wallpaper-picker"},
    "field_update_url":    {"de": "Update-URL",                   "en": "Update URL"},
    "hint_update_url":     {"de": "Raw-URL zur wallpaper_picker/__init__.py auf GitHub", "en": "Raw URL to wallpaper_picker/__init__.py on GitHub"},
    "installed_version":   {"de": "Installiert: <b style='color:{c}'>{v}</b>", "en": "Installed: <b style='color:{c}'>{v}</b>"},
    "btn_check_now":       {"de": "Jetzt prüfen",                 "en": "Check now"},
    "cb_fullscreen_pause": {"de": "Wallpaper bei Vollbild-Apps automatisch pausieren", "en": "Automatically pause wallpaper when a fullscreen app is active"},
    "hint_fullscreen":     {"de": "Nutzt --fullscreen-pause-only-active der Engine (kein Neustart nötig)", "en": "Uses the engine's --fullscreen-pause-only-active flag (no restart needed)"},
    "sec_lwe_updates":     {"de": "linux-wallpaperengine",        "en": "linux-wallpaperengine"},
    "lbl_installed":       {"de": "Installiert:",                 "en": "Installed:"},
    "lbl_available":       {"de": "Verfügbar:",                   "en": "Available:"},
    "lbl_update":          {"de": "Update:",                      "en": "Update:"},
    "lbl_compatible":      {"de": "Kompatibel:",                  "en": "Compatible:"},
    "btn_check_status":    {"de": "Status prüfen",                "en": "Check status"},
    "btn_update_lwe":      {"de": "Aktualisieren",                "en": "Update"},
    "lwe_up_to_date":      {"de": "✓ Aktuell",                    "en": "✓ Up to date"},
    "lwe_update_avail":    {"de": "↑ Update verfügbar → {commit} ({date})", "en": "↑ Update available → {commit} ({date})"},
    "lwe_unknown":         {"de": "unbekannt",                    "en": "unknown"},
    "lwe_not_found":       {"de": "nicht gefunden",               "en": "not found"},
    "lwe_unreachable":     {"de": "nicht erreichbar",             "en": "unreachable"},
    "lwe_compatible":      {"de": "✓ Kompatibel",                 "en": "✓ Compatible"},
    "lwe_incompatible":    {"de": "✗ Inkompatibel: {flags}",      "en": "✗ Incompatible: {flags}"},
    "lwe_no_repo":         {"de": "Repo nicht gefunden — bitte zuerst bauen (Setup-Assistent).", "en": "Repo not found — please build first (Setup Wizard)."},
    "checking":            {"de": "Wird geprüft…",                "en": "Checking…"},
    "update_checker_ok":   {"de": "Aktuell (v{v}) ✓",            "en": "Up to date (v{v}) ✓"},
    "update_avail_label":  {"de": "v{v} verfügbar",               "en": "v{v} available"},

    # ── SettingsDialog — Info ─────────────────────────────────────────────────
    "sec_system":          {"de": "System",                       "en": "System"},
    "sec_setup_guide":     {"de": "Setup-Guide",                  "en": "Setup Guide"},
    "info_distro":         {"de": "Distro",                       "en": "Distro"},
    "info_binary":         {"de": "Binary",                       "en": "Binary"},
    "info_assets":         {"de": "Assets",                       "en": "Assets"},
    "info_workshop":       {"de": "Workshop",                     "en": "Workshop"},
    "info_workshop_count": {"de": "{n} Wallpapers lokal",         "en": "{n} wallpapers local"},
    "info_not_configured": {"de": "nicht konfiguriert",           "en": "not configured"},
    "info_atomic":         {"de": "Atomic (Immutable)",           "en": "Atomic (Immutable)"},
    "info_traditional":    {"de": "Traditionell",                 "en": "Traditional"},

    # ── UpdateDialog ─────────────────────────────────────────────────────────
    "upddlg_title":        {"de": "Update verfügbar",             "en": "Update available"},
    "upddlg_header":       {"de": "<b style='font-size:14px'>Update verfügbar</b>", "en": "<b style='font-size:14px'>Update available</b>"},
    "upddlg_current":      {"de": "Installiert:",                 "en": "Installed:"},
    "upddlg_remote":       {"de": "Verfügbar:",                   "en": "Available:"},
    "upddlg_whats_new":    {"de": "<b>Was ist neu:</b>",          "en": "<b>What's new:</b>"},
    "btn_install_now":     {"de": "Jetzt aktualisieren",          "en": "Install now"},
    "update_restarting":   {"de": "App wird neu gestartet…",      "en": "Restarting app…"},

    # ── Wizard ────────────────────────────────────────────────────────────────
    "wiz_title":           {"de": "Einrichtungs-Assistent",       "en": "Setup Wizard"},
    "wiz_welcome_title":   {"de": "Willkommen",                   "en": "Welcome"},
    "wiz_welcome_sub":     {"de": "Einrichtungs-Assistent für linux-wallpaperengine", "en": "Setup wizard for linux-wallpaperengine"},
    "wiz_welcome_body": {
        "de": "<b>System:</b> {distro} — {ptype}<br><br>Dieser Assistent führt dich durch die Einrichtung von<br><b>linux-wallpaperengine</b> — einer Open-Source-Implementierung<br>der Wallpaper Engine für Linux.<br><br>Du benötigst:<br>• linux-wallpaperengine Binary (bereits gebaut oder jetzt bauen)<br>• Wallpaper Engine Assets (aus Steam)<br>• Mindestens ein abonniertes Wallpaper",
        "en": "<b>System:</b> {distro} — {ptype}<br><br>This wizard guides you through setting up<br><b>linux-wallpaperengine</b> — an open-source implementation<br>of Wallpaper Engine for Linux.<br><br>You need:<br>• linux-wallpaperengine binary (already built or build now)<br>• Wallpaper Engine assets (from Steam)<br>• At least one subscribed wallpaper",
    },
    "wiz_already_ok":      {"de": "✓ Setup bereits vollständig konfiguriert!", "en": "✓ Setup already fully configured!"},
    "wiz_mode_title":      {"de": "Ausführungsmodus",             "en": "Execution mode"},
    "wiz_mode_sub":        {"de": "Wie soll linux-wallpaperengine gestartet werden?", "en": "How should linux-wallpaperengine be launched?"},
    "wiz_mode_label":      {"de": "Modus:",                       "en": "Mode:"},
    "wiz_container_label": {"de": "Container:",                   "en": "Container:"},
    "wiz_mode_recommended":{"de": "  (empfohlen für Atomic)",     "en": "  (recommended for Atomic)"},
    "wiz_mode_direct":     {"de": "direct  (Binary direkt ausführen)", "en": "direct  (run binary directly)"},
    "wiz_mode_custom":     {"de": "custom  (eigener Prefix)",     "en": "custom  (custom prefix)"},
    "wiz_desc_distrobox":  {"de": "Führt die Binary in einem Distrobox-Container aus. Empfohlen für Bazzite/Silverblue.", "en": "Runs the binary inside a Distrobox container. Recommended for Bazzite/Silverblue."},
    "wiz_desc_toolbox":    {"de": "Wie Distrobox, aber mit Toolbox/Toolbx.", "en": "Like Distrobox but with Toolbox/Toolbx."},
    "wiz_desc_direct":     {"de": "Führt die Binary direkt auf dem Host aus. Benötigt alle Libraries auf dem Host.", "en": "Runs the binary directly on the host. Requires all libraries on the host."},
    "wiz_desc_custom":     {"de": "Benutzerdefinierter Prefix-Befehl vor der Binary.", "en": "Custom prefix command before the binary."},
    "wiz_err_container":   {"de": "Container-Name darf nicht leer sein.", "en": "Container name must not be empty."},
    "wiz_binary_title":    {"de": "Binary konfigurieren",         "en": "Configure binary"},
    "wiz_binary_sub":      {"de": "Pfad zur linux-wallpaperengine Binary angeben und testen", "en": "Specify and test the path to the linux-wallpaperengine binary"},
    "btn_autodetect":      {"de": "Auto-Detect",                  "en": "Auto-Detect"},
    "wiz_autodetect_fail": {"de": "Nicht gefunden — bitte manuell angeben oder bauen.", "en": "Not found — please specify manually or build."},
    "wiz_test_ok":         {"de": "✓ Binary funktioniert",        "en": "✓ Binary works"},
    "wiz_test_fail":       {"de": "✗ {msg}",                      "en": "✗ {msg}"},
    "wiz_no_path":         {"de": "Kein Pfad angegeben.",         "en": "No path specified."},
    "wiz_build_label":     {"de": "<b>Binary nicht gefunden?</b> Direkt hier in einem Distrobox-Container bauen:", "en": "<b>Binary not found?</b> Build it here inside a Distrobox container:"},
    "btn_build_lwe":       {"de": "⚙  linux-wallpaperengine jetzt bauen…", "en": "⚙  Build linux-wallpaperengine now…"},
    "wiz_binary_exists":   {"de": "Binary bereits vorhanden ✓",   "en": "Binary already present ✓"},
    "wiz_assets_title":    {"de": "Assets-Verzeichnis",           "en": "Assets directory"},
    "wiz_assets_sub":      {"de": "Pfad zum Wallpaper Engine Assets-Ordner (aus Steam)", "en": "Path to the Wallpaper Engine assets folder (from Steam)"},
    "wiz_assets_hint":     {"de": "Das Assets-Verzeichnis befindet sich normalerweise unter:\n~/.local/share/Steam/steamapps/common/wallpaper_engine/assets", "en": "The assets directory is usually located at:\n~/.local/share/Steam/steamapps/common/wallpaper_engine/assets"},
    "wiz_assets_placeholder":{"de": "Pfad zum assets/-Ordner",   "en": "Path to assets/ folder"},
    "wiz_assets_detect_fail":{"de": "Nicht gefunden. Bitte Wallpaper Engine in Steam installieren.", "en": "Not found. Please install Wallpaper Engine on Steam."},
    "wiz_assets_ok":       {"de": "✓ Assets-Verzeichnis gefunden","en": "✓ Assets directory found"},
    "wiz_assets_not_dir":  {"de": "✗ Verzeichnis nicht gefunden: {p}", "en": "✗ Directory not found: {p}"},
    "wiz_assets_invalid":  {"de": "✗ Kein gültiges Assets-Verzeichnis (fehlt: {missing})", "en": "✗ Not a valid assets directory (missing: {missing})"},
    "wiz_finish_title":    {"de": "Einrichtung abgeschlossen",    "en": "Setup complete"},
    "wiz_finish_sub":      {"de": "Konfiguration wird gespeichert", "en": "Saving configuration"},
    "wiz_finish_config":   {"de": "<b>Konfiguration:</b><br>",    "en": "<b>Configuration:</b><br>"},
    "wiz_finish_mode":     {"de": "Modus: {v}",                   "en": "Mode: {v}"},
    "wiz_finish_container":{"de": "Container: {v}",               "en": "Container: {v}"},
    "wiz_finish_binary":   {"de": "Binary: {v}",                  "en": "Binary: {v}"},
    "wiz_finish_assets":   {"de": "Assets: {v}",                  "en": "Assets: {v}"},
    "wiz_finish_done":     {"de": "<br>Klicke <b>Fertigstellen</b> um die Konfiguration zu speichern.", "en": "<br>Click <b>Finish</b> to save the configuration."},

    # ── WallpaperConfigDialog — bool fields ───────────────────────────────────
    "cb_fullscreen_pause_short": {"de": "Vollbild-Pause",         "en": "Fullscreen pause"},
    "cb_disable_particles_short":{"de": "Partikel deaktivieren",  "en": "Disable particles"},
    "cb_disable_mouse_short":    {"de": "Maus-Interaktion deaktivieren", "en": "Disable mouse interaction"},
    "cb_no_audio_short":         {"de": "Audio-Verarbeitung deaktivieren", "en": "Disable audio processing"},

    # ── Cards ─────────────────────────────────────────────────────────────────
    "card_loading":        {"de": "lädt…",                        "en": "loading…"},
    "card_no_image":       {"de": "kein Bild",                    "en": "no image"},
    "card_cfg_tooltip":    {"de": "Eigene Konfiguration",         "en": "Custom configuration"},
    "card_cfg_active":     {"de": "Eigene Konfiguration (aktiv)", "en": "Custom configuration (active)"},

    # ── Workers (user-visible messages) ──────────────────────────────────────
    "worker_fetch_fail":   {"de": "Fetch fehlgeschlagen — Internetverbindung prüfen.", "en": "Fetch failed — check internet connection."},
    "worker_reset_fail":   {"de": "Reset fehlgeschlagen.",        "en": "Reset failed."},
    "worker_update_ok":    {"de": "Update erfolgreich — App wird neu gestartet.", "en": "Update successful — restarting app."},
    "worker_apply_ok":     {"de": "Wallpaper angewendet.",        "en": "Wallpaper applied."},
    "worker_timeout":      {"de": "Timeout — Service antwortet nicht.", "en": "Timeout — service is not responding."},
    "worker_systemctl_err":{"de": "systemctl Fehler: {e}",        "en": "systemctl error: {e}"},
    "worker_err":          {"de": "Fehler: {e}",                  "en": "Error: {e}"},
}


def set_language(lang: str) -> None:
    global _lang
    if lang in ("de", "en"):
        _lang = lang


def get_language() -> str:
    return _lang


def t(key: str, **kwargs) -> str:
    entry = _strings.get(key)
    if entry is None:
        return key
    s = entry.get(_lang) or entry.get("de") or key
    return s.format(**kwargs) if kwargs else s
