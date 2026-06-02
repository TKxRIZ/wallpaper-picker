mod config;
mod service;
mod tray;
mod wallpaper;

use ksni::blocking::TrayMethods;

fn main() {
    let tray    = tray::WallpaperTray::new();
    let _handle = tray.spawn().expect("Tray konnte nicht gestartet werden");
    std::thread::park(); // block main thread; tray runs on background thread
}
