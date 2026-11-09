//! The app folder and the paths inside it (PRD §11, data-model §5.5).
//!
//! Everything the app writes lives in one app folder; nothing resolves into AppData. The rules
//! mirror `sidecar/src/etach/appdir.py`:
//! - `ETACH_APP_DIR` overrides the app folder (development and tests);
//! - otherwise a release build uses the folder holding the executable, and a debug build uses
//!   `<repo>\.devdata` (gitignored);
//! - a folder inside `%APPDATA%` or `%LOCALAPPDATA%` is refused (the system temp folder, which
//!   tests use, is the one exception).

use std::path::{Component, Path, PathBuf};

/// The environment variable that overrides the app folder.
pub const APP_DIR_ENV: &str = "ETACH_APP_DIR";

/// The paths inside one app folder. `root` is absolute.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppPaths {
    pub root: PathBuf,
}

impl AppPaths {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }
    /// `<app>\data`: the sidecar's data folder (it gets `ETACH_APP_DIR=<app>`, no `--data`).
    pub fn data_dir(&self) -> PathBuf {
        self.root.join("data")
    }
    /// `<app>\data\models`: `OLLAMA_MODELS`.
    pub fn models_dir(&self) -> PathBuf {
        self.data_dir().join("models")
    }
    /// `<app>\webview`: the WebView2 user data folder.
    pub fn webview_dir(&self) -> PathBuf {
        self.root.join("webview")
    }
    /// `<app>\settings.json`.
    pub fn settings_json(&self) -> PathBuf {
        self.root.join("settings.json")
    }
    /// `<app>\exports`: where "Save as Word (.docx)" saves (step 22.1.6), next to `data\`.
    pub fn exports_dir(&self) -> PathBuf {
        self.root.join("exports")
    }
}

/// The inputs of [`resolve_app_dir`], gathered from the process so the rules stay testable.
#[derive(Debug, Clone, Default)]
pub struct AppDirInputs {
    /// `ETACH_APP_DIR`, if set and non-empty.
    pub override_dir: Option<PathBuf>,
    /// The folder holding the executable.
    pub exe_dir: Option<PathBuf>,
    /// A debug build: use `<repo>\.devdata`.
    pub debug: bool,
    /// The repository root (known at compile time).
    pub repo_dir: PathBuf,
    /// `%APPDATA%`, `%LOCALAPPDATA%` (refused) and the temp folder (allowed).
    pub appdata: Option<PathBuf>,
    pub local_appdata: Option<PathBuf>,
    pub temp: Option<PathBuf>,
}

impl AppDirInputs {
    pub fn from_process() -> Self {
        let env_path = |name: &str| {
            std::env::var_os(name)
                .filter(|v| !v.is_empty())
                .map(PathBuf::from)
        };
        Self {
            override_dir: env_path(APP_DIR_ENV),
            exe_dir: std::env::current_exe()
                .ok()
                .and_then(|p| p.parent().map(Path::to_path_buf)),
            debug: cfg!(debug_assertions),
            repo_dir: Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join(".."),
            appdata: env_path("APPDATA"),
            local_appdata: env_path("LOCALAPPDATA"),
            temp: Some(std::env::temp_dir()),
        }
    }
}

/// Pick the app folder (see the module docs). Pure apart from making the path absolute.
pub fn resolve_app_dir(inputs: &AppDirInputs) -> Result<AppPaths, String> {
    let chosen = if let Some(dir) = &inputs.override_dir {
        dir.clone()
    } else if inputs.debug {
        inputs.repo_dir.join(".devdata")
    } else {
        inputs
            .exe_dir
            .clone()
            .ok_or_else(|| "cannot find the folder of the executable".to_string())?
    };
    let root = normalize(&absolute(&chosen));
    refuse_appdata(&root, inputs)?;
    Ok(AppPaths::new(root))
}

fn refuse_appdata(path: &Path, inputs: &AppDirInputs) -> Result<(), String> {
    if let Some(temp) = &inputs.temp {
        if is_within(path, &normalize(&absolute(temp))) {
            return Ok(());
        }
    }
    for (name, value) in [
        ("APPDATA", &inputs.appdata),
        ("LOCALAPPDATA", &inputs.local_appdata),
    ] {
        if let Some(value) = value {
            if is_within(path, &normalize(&absolute(value))) {
                return Err(format!(
                    "the app folder may not be inside %{name}% (PRD §11): {}",
                    path.display()
                ));
            }
        }
    }
    Ok(())
}

fn absolute(path: &Path) -> PathBuf {
    std::path::absolute(path).unwrap_or_else(|_| path.to_path_buf())
}

/// Resolve `.` and `..` without touching the disk.
fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for part in path.components() {
        match part {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// Case-insensitive prefix test by path components (Windows paths).
fn is_within(path: &Path, parent: &Path) -> bool {
    let lower = |p: &Path| -> Vec<String> {
        p.components()
            .map(|c| c.as_os_str().to_string_lossy().to_lowercase())
            .collect()
    };
    let (path, parent) = (lower(path), lower(parent));
    path.len() >= parent.len() && path[..parent.len()] == parent[..]
}

/// The few settings the shell reads from `settings.json`. Missing or invalid → defaults; the
/// shell never writes the file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ShellSettings {
    /// The NVIDIA GPU index for `CUDA_VISIBLE_DEVICES`.
    pub gpu_index: u32,
}

impl Default for ShellSettings {
    fn default() -> Self {
        Self { gpu_index: 0 }
    }
}

impl ShellSettings {
    pub fn parse(text: &str) -> Self {
        let value: serde_json::Value = match serde_json::from_str(text) {
            Ok(v) => v,
            Err(_) => return Self::default(),
        };
        let gpu_index = value
            .get("gpu_index")
            .and_then(serde_json::Value::as_u64)
            .and_then(|n| u32::try_from(n).ok())
            .unwrap_or(0);
        Self { gpu_index }
    }

    pub fn load(paths: &AppPaths) -> Self {
        std::fs::read_to_string(paths.settings_json())
            .map(|t| Self::parse(&t))
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exports_dir_is_next_to_data() {
        let app = AppPaths::new(r"D:\ETACH");
        assert_eq!(app.exports_dir(), PathBuf::from(r"D:\ETACH\exports"));
        assert_eq!(app.exports_dir().parent(), app.data_dir().parent());
    }

    fn inputs() -> AppDirInputs {
        AppDirInputs {
            override_dir: None,
            exe_dir: Some(PathBuf::from(r"D:\ETACH")),
            debug: false,
            repo_dir: PathBuf::from(r"D:\Projects\ETACH\app\src-tauri\..\.."),
            appdata: Some(PathBuf::from(r"C:\Users\T\AppData\Roaming")),
            local_appdata: Some(PathBuf::from(r"C:\Users\T\AppData\Local")),
            temp: Some(PathBuf::from(r"C:\Users\T\AppData\Local\Temp")),
        }
    }

    #[test]
    fn release_uses_the_exe_folder() {
        let p = resolve_app_dir(&inputs()).unwrap();
        assert_eq!(p.root, PathBuf::from(r"D:\ETACH"));
        assert_eq!(p.data_dir(), PathBuf::from(r"D:\ETACH\data"));
        assert_eq!(
            p.models_dir(),
            PathBuf::from(r"D:\ETACH\data\models")
        );
        assert_eq!(p.webview_dir(), PathBuf::from(r"D:\ETACH\webview"));
        assert_eq!(
            p.settings_json(),
            PathBuf::from(r"D:\ETACH\settings.json")
        );
    }

    #[test]
    fn debug_uses_repo_devdata() {
        let mut i = inputs();
        i.debug = true;
        let p = resolve_app_dir(&i).unwrap();
        assert_eq!(
            p.root,
            PathBuf::from(r"D:\Projects\ETACH\.devdata")
        );
    }

    #[test]
    fn override_wins() {
        let mut i = inputs();
        i.debug = true;
        i.override_dir = Some(PathBuf::from(r"E:\Elsewhere"));
        assert_eq!(resolve_app_dir(&i).unwrap().root, PathBuf::from(r"E:\Elsewhere"));
    }

    #[test]
    fn appdata_is_refused_but_temp_is_allowed() {
        let mut i = inputs();
        i.override_dir = Some(PathBuf::from(r"c:\users\t\appdata\local\ETACH"));
        assert!(resolve_app_dir(&i).unwrap_err().contains("LOCALAPPDATA"));
        i.override_dir = Some(PathBuf::from(r"C:\Users\T\AppData\Roaming\ETACH"));
        assert!(resolve_app_dir(&i).unwrap_err().contains("%APPDATA%"));
        i.override_dir = Some(PathBuf::from(r"C:\Users\T\AppData\Local\Temp\etach-test"));
        assert!(resolve_app_dir(&i).is_ok());
    }

    #[test]
    fn settings_defaults_and_gpu_index() {
        assert_eq!(ShellSettings::parse("not json"), ShellSettings::default());
        assert_eq!(ShellSettings::parse("{}").gpu_index, 0);
        assert_eq!(ShellSettings::parse(r#"{"gpu_index": 2}"#).gpu_index, 2);
        assert_eq!(ShellSettings::parse(r#"{"gpu_index": "x"}"#).gpu_index, 0);
    }
}
