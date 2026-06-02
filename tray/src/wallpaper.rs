use serde::Deserialize;
use std::path::PathBuf;

use crate::config::home_dir;

#[derive(Debug, Clone)]
pub struct Wallpaper {
    pub id: String,
    pub title: String,
}

fn workshop_dir() -> PathBuf {
    home_dir().join(".local/share/Steam/steamapps/workshop/content/431960")
}

#[derive(Deserialize)]
struct ProjectJson {
    title: Option<String>,
}

pub fn title_for(id: &str) -> String {
    let project = workshop_dir().join(id).join("project.json");
    let Ok(data) = std::fs::read_to_string(project) else {
        return id.to_string();
    };
    serde_json::from_str::<ProjectJson>(&data)
        .ok()
        .and_then(|p| p.title)
        .unwrap_or_else(|| id.to_string())
}

pub fn resolve_recents(ids: &[String]) -> Vec<Wallpaper> {
    ids.iter()
        .map(|id| Wallpaper {
            title: title_for(id),
            id: id.clone(),
        })
        .collect()
}

pub fn all_installed() -> Vec<Wallpaper> {
    let dir = workshop_dir();
    let Ok(entries) = std::fs::read_dir(&dir) else {
        return vec![];
    };
    let mut result: Vec<Wallpaper> = entries
        .flatten()
        .filter(|e| e.path().is_dir())
        .map(|e| {
            let id = e.file_name().to_string_lossy().to_string();
            let title = title_for(&id);
            Wallpaper { id, title }
        })
        .collect();
    result.sort_by(|a, b| a.title.cmp(&b.title));
    result
}
