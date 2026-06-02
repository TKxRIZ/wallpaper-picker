use ksni::menu::StandardItem;
use ksni::{MenuItem, ToolTip, Tray};

use crate::{config, service, wallpaper};

pub struct WallpaperTray {
    pub service: String,
    pub recents: Vec<wallpaper::Wallpaper>,
    pub active:  bool,
}

impl WallpaperTray {
    pub fn new() -> Self {
        let cfg    = config::load();
        let active = service::is_active(&cfg.service_name);
        let recents = wallpaper::resolve_recents(&cfg.recent_wallpapers);
        Self { service: cfg.service_name, recents, active }
    }

    fn refresh(&mut self) {
        let cfg     = config::load();
        self.service = cfg.service_name.clone();
        self.active  = service::is_active(&cfg.service_name);
        self.recents = wallpaper::resolve_recents(&cfg.recent_wallpapers);
    }
}

impl Tray for WallpaperTray {
    fn id(&self) -> String {
        "wallpaper-tray".into()
    }

    fn icon_name(&self) -> String {
        "preferences-desktop-wallpaper".into()
    }

    fn tool_tip(&self) -> ToolTip {
        ToolTip {
            title: "Wallpaper Engine – Linux".into(),
            description: if self.active { "Service aktiv".into() } else { "Service inaktiv".into() },
            ..Default::default()
        }
    }

    fn menu(&self) -> Vec<MenuItem<Self>> {
        let mut items: Vec<MenuItem<Self>> = Vec::new();

        // Recent wallpapers
        if !self.recents.is_empty() {
            for wp in &self.recents {
                let id    = wp.id.clone();
                let title = wp.title.clone();
                let svc   = self.service.clone();
                items.push(MenuItem::Standard(StandardItem {
                    label: title,
                    activate: Box::new(move |this: &mut Self| {
                        service::apply_wallpaper(&svc, &id);
                        this.refresh();
                    }),
                    ..Default::default()
                }));
            }
            items.push(MenuItem::Separator);
        }

        // Random wallpaper
        items.push(MenuItem::Standard(StandardItem {
            label: "Zufälliges Wallpaper".into(),
            enabled: !wallpaper::all_installed().is_empty(),
            activate: Box::new(|this: &mut Self| {
                let all = wallpaper::all_installed();
                if all.is_empty() { return; }
                let idx = (std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .subsec_nanos() as usize) % all.len();
                service::apply_wallpaper(&this.service, &all[idx].id);
                this.refresh();
            }),
            ..Default::default()
        }));

        items.push(MenuItem::Separator);

        // Service status (disabled label)
        items.push(MenuItem::Standard(StandardItem {
            label: if self.active { "● Service aktiv".into() } else { "○ Service inaktiv".into() },
            enabled: false,
            ..Default::default()
        }));

        // Toggle service
        items.push(MenuItem::Standard(StandardItem {
            label: if self.active { "Service stoppen".into() } else { "Service starten".into() },
            activate: Box::new(|this: &mut Self| {
                service::toggle(&this.service);
                this.active = service::is_active(&this.service);
            }),
            ..Default::default()
        }));

        items.push(MenuItem::Separator);

        // Open GUI
        items.push(MenuItem::Standard(StandardItem {
            label: "Öffnen".into(),
            activate: Box::new(|_| {
                let _ = std::process::Command::new("wallpaper-picker").spawn();
            }),
            ..Default::default()
        }));

        // Quit
        items.push(MenuItem::Standard(StandardItem {
            label: "Beenden".into(),
            activate: Box::new(|_| std::process::exit(0)),
            ..Default::default()
        }));

        items
    }
}
