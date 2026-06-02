use std::path::PathBuf;
use std::process::Command;

use crate::config::home_dir;

pub fn service_file() -> PathBuf {
    home_dir().join(".config/systemd/user/linux-wallpaperengine.service")
}

pub fn is_active(service: &str) -> bool {
    Command::new("systemctl")
        .args(["--user", "is-active", "--quiet", service])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

pub fn start(service: &str) {
    let _ = Command::new("systemctl").args(["--user", "start", service]).status();
}

pub fn stop(service: &str) {
    let _ = Command::new("systemctl").args(["--user", "stop", service]).status();
}

pub fn toggle(service: &str) {
    if is_active(service) { stop(service); } else { start(service); }
}

pub fn restart(service: &str) {
    let _ = Command::new("systemctl").args(["--user", "daemon-reload"]).status();
    let _ = Command::new("systemctl").args(["--user", "restart", service]).status();
}

/// Update the service file with the new wallpaper ID, then restart the service.
pub fn apply_wallpaper(service: &str, wp_id: &str) {
    let path = service_file();
    let Ok(content) = std::fs::read_to_string(&path) else { return; };
    let updated = replace_bg(&content, wp_id);
    let _ = std::fs::write(path.with_extension("bak"), &content);
    if std::fs::write(&path, &updated).is_ok() {
        restart(service);
    }
}

fn replace_bg(text: &str, new_id: &str) -> String {
    let mut result = String::with_capacity(text.len());
    let mut chars  = text.chars().peekable();
    while let Some(c) = chars.next() {
        result.push(c);
        if c == '-' && chars.peek() == Some(&'-') {
            let mut token = String::from("-");
            while let Some(&next) = chars.peek() {
                if next.is_whitespace() { break; }
                token.push(next);
                chars.next();
            }
            if token == "-bg" {
                result.push_str("-bg");
                while chars.peek().map(|c| c.is_whitespace()) == Some(true) {
                    result.push(chars.next().unwrap());
                }
                while chars.peek().map(|c| c.is_ascii_digit()) == Some(true) {
                    chars.next();
                }
                result.push_str(new_id);
            } else {
                result.push_str(&token);
            }
        }
    }
    result
}
