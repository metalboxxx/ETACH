//! The Tauri shell (plan step 14, llm-design §2).
//!
//! On start: resolve the app folder (nothing in AppData), create a kill-on-close Job Object,
//! read `settings.json`, spawn `ollama serve` and the sidecar into the job, wait for the
//! sidecar's `{"port","token"}` line, and only then open the main window with
//! `window.__ETACH__` injected and the WebView2 data folder in `<app>\webview`.
//! A sidecar that exits unexpectedly is restarted (bounded) and the page reloads.
//!
//! Step 21: a release build runs the frozen sidecar (`<exe dir>\sidecar\etach-sidecar.exe`, PyInstaller
//! folder mode, shipped as Tauri resources); a debug build keeps `uv run etach serve`. A missing
//! Ollama no longer stops the shell: the sidecar then reports `unreachable` and the frontend shows
//! the first-run setup screen (install Ollama, update it, or download the models).

pub mod job;
pub mod paths;
pub mod spawn;

use std::fs::OpenOptions;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{mpsc, Arc, Mutex};
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};

use paths::{AppDirInputs, ShellSettings};
use spawn::{build_spawn_plan, ChildSpec, SidecarMode, SpawnInputs, SpawnPlan};

/// `ETACH_SIDECAR_REPLAY=<cassettes dir>`: the dev sidecar replays cassettes (E2E_SHELL tests).
pub const SIDECAR_REPLAY_ENV: &str = "ETACH_SIDECAR_REPLAY";
/// `ETACH_WEBVIEW_DEVTOOLS=1`: enable the WebView2 DevTools in a release build. A release build
/// turns them off (`AreDevToolsEnabled = false`), which also hides the page from the Chrome
/// DevTools Protocol that msedgedriver / tauri-driver use, so `E2E_SHELL --release` sets this.
/// Debug builds always have them.
pub const WEBVIEW_DEVTOOLS_ENV: &str = "ETACH_WEBVIEW_DEVTOOLS";
const SIDECAR_START_TIMEOUT: Duration = Duration::from_secs(180);
const SIDECAR_MAX_RESTARTS: u32 = 3;
const MAIN_WINDOW: &str = "main";
/// The frozen sidecar, relative to the folder of the shell's executable (Tauri resources).
pub const FROZEN_SIDECAR: &str = r"sidecar\etach-sidecar.exe";
/// Opened in the teacher's browser by the first-run screen. The app itself never requests it.
const OLLAMA_DOWNLOAD_URL: &str = "https://ollama.com/download";

/// The sidecar's first stdout line.
#[derive(Debug, Clone, serde::Deserialize, PartialEq, Eq)]
pub struct SidecarHello {
    pub port: u16,
    pub token: String,
}

/// The JSON for `window.__ETACH__` (matches `app/src/api/config.ts`).
pub fn etach_config_json(hello: &SidecarHello) -> String {
    serde_json::json!({
        "baseUrl": format!("http://127.0.0.1:{}", hello.port),
        "token": hello.token,
    })
    .to_string()
}

/// The initialization script. After a sidecar restart the shell stores the new config in
/// `sessionStorage` and reloads; this script prefers that copy over the one it was built with.
pub fn init_script(hello: &SidecarHello) -> String {
    format!(
        "(function(){{var c={cfg};try{{var s=sessionStorage.getItem('__ETACH__');if(s)c=JSON.parse(s);}}catch(e){{}}window.__ETACH__=c;}})();",
        cfg = etach_config_json(hello)
    )
}

struct Shell {
    plan: SpawnPlan,
    /// `false`: no Ollama was found; `ollama serve` is not started (first-run screen).
    ollama_found: bool,
    logs: PathBuf,
    job: Mutex<Option<job::Job>>,
    ollama: Mutex<Option<Child>>,
    sidecar: Mutex<Option<Child>>,
    shutting_down: AtomicBool,
}

impl Shell {
    fn assign(&self, child: &Child) {
        if let Some(job) = self.job.lock().unwrap().as_ref() {
            if let Err(e) = job.assign(child) {
                eprintln!("etach shell: cannot assign pid {} to the job: {e}", child.id());
            }
        }
    }

    fn log_file(&self, name: &str) -> Stdio {
        OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.logs.join(name))
            .map(Stdio::from)
            .unwrap_or_else(|_| Stdio::null())
    }

    fn spawn_ollama(&self) -> Result<(), String> {
        if !self.ollama_found {
            eprintln!("etach shell: Ollama is not installed; the first-run screen asks for it");
            return Ok(());
        }
        let child = command(&self.plan.ollama)
            .stdin(Stdio::null())
            .stdout(self.log_file("ollama-serve.log"))
            .stderr(self.log_file("ollama-serve.log"))
            .spawn()
            .map_err(|e| format!("cannot start {}: {e}", self.plan.ollama.program.display()))?;
        self.assign(&child);
        *self.ollama.lock().unwrap() = Some(child);
        Ok(())
    }

    /// Start the sidecar and wait for its `{"port","token"}` line; keep draining stdout after.
    fn spawn_sidecar(&self) -> Result<SidecarHello, String> {
        let mut child = command(&self.plan.sidecar)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(self.log_file("sidecar-shell.log"))
            .spawn()
            .map_err(|e| format!("cannot start the sidecar: {e}"))?;
        self.assign(&child);
        let stdout = child.stdout.take().expect("piped stdout");
        *self.sidecar.lock().unwrap() = Some(child);

        let (tx, rx) = mpsc::channel::<Result<SidecarHello, String>>();
        std::thread::spawn(move || {
            let mut lines = BufReader::new(stdout).lines();
            let first = match lines.next() {
                Some(Ok(line)) => serde_json::from_str::<SidecarHello>(line.trim())
                    .map_err(|e| format!("the sidecar's first line is not {{port, token}}: {e}")),
                _ => Err("the sidecar exited before printing its port".to_string()),
            };
            let _ = tx.send(first);
            // Keep draining so the sidecar never blocks on a full pipe.
            for _ in lines.map_while(Result::ok) {}
        });
        match rx.recv_timeout(SIDECAR_START_TIMEOUT) {
            Ok(Ok(hello)) => Ok(hello),
            Ok(Err(e)) => Err(e),
            Err(_) => Err("the sidecar did not print its port in time".to_string()),
        }
    }

    fn kill_children(&self) {
        for slot in [&self.sidecar, &self.ollama] {
            if let Some(mut child) = slot.lock().unwrap().take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
        // Closing the job kills anything left, e.g. the Python process under `uv run`.
        self.job.lock().unwrap().take();
    }
}

fn command(spec: &ChildSpec) -> Command {
    let mut cmd = Command::new(&spec.program);
    cmd.args(&spec.args).envs(&spec.env);
    if let Some(cwd) = &spec.cwd {
        cmd.current_dir(cwd);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

/// `ollama` on PATH first (tests put a stub there), else the per-user install folder
/// (`%LOCALAPPDATA%\Programs\Ollama\ollama.exe`; read-only use).
pub fn find_ollama() -> Option<PathBuf> {
    if let Some(path) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&path) {
            for name in ["ollama.exe", "ollama.cmd", "ollama.bat"] {
                let candidate = dir.join(name);
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }
    let local = std::env::var_os("LOCALAPPDATA")?;
    let candidate = Path::new(&local).join(r"Programs\Ollama\ollama.exe");
    candidate.is_file().then_some(candidate)
}

fn free_loopback_port() -> Result<u16, String> {
    TcpListener::bind("127.0.0.1:0")
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .map_err(|e| format!("no free loopback port: {e}"))
}

fn prepare() -> Result<Arc<Shell>, String> {
    let app = paths::resolve_app_dir(&AppDirInputs::from_process())?;
    let logs = app.data_dir().join("logs");
    for dir in [app.models_dir(), app.webview_dir(), logs.clone()] {
        std::fs::create_dir_all(&dir).map_err(|e| format!("cannot create {}: {e}", dir.display()))?;
    }
    let settings = ShellSettings::load(&app);
    let job = job::Job::new_kill_on_close().map_err(|e| format!("cannot create the job: {e}"))?;
    // Without Ollama the shell still starts: the sidecar reports `unreachable` and the frontend
    // shows the first-run screen. The placeholder program is never started.
    let ollama_exe = find_ollama();
    let ollama_found = ollama_exe.is_some();
    let plan = build_spawn_plan(&SpawnInputs {
        app: app.clone(),
        ollama_exe: ollama_exe.unwrap_or_else(|| PathBuf::from("ollama")),
        ollama_port: free_loopback_port()?,
        gpu_index: settings.gpu_index,
        sidecar: sidecar_mode()?,
    });
    Ok(Arc::new(Shell {
        plan,
        ollama_found,
        logs,
        job: Mutex::new(Some(job)),
        ollama: Mutex::new(None),
        sidecar: Mutex::new(None),
        shutting_down: AtomicBool::new(false),
    }))
}

fn replay_dir() -> Option<PathBuf> {
    std::env::var_os(SIDECAR_REPLAY_ENV)
        .filter(|v| !v.is_empty())
        .map(|v| std::path::absolute(&v).unwrap_or_else(|_| PathBuf::from(v)))
}

/// Debug: `uv run etach serve` in `<repo>\sidecar`. Release: the frozen sidecar next to the
/// executable (`<exe dir>\sidecar\etach-sidecar.exe`), whatever the app folder is.
fn sidecar_mode() -> Result<SidecarMode, String> {
    if cfg!(debug_assertions) {
        let repo = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        return Ok(SidecarMode::Dev {
            sidecar_dir: std::path::absolute(repo.join("sidecar")).unwrap_or(repo.join("sidecar")),
            replay: replay_dir(),
        });
    }
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(Path::to_path_buf))
        .ok_or("cannot find the folder of the executable")?;
    let exe = exe_dir.join(FROZEN_SIDECAR);
    if !exe.is_file() {
        return Err(format!("the sidecar is missing: {}", exe.display()));
    }
    Ok(SidecarMode::Frozen {
        exe,
        replay: replay_dir(),
    })
}

/// DevTools (and with them WebDriver access to the page): always in a debug build; in a release
/// build only with `ETACH_WEBVIEW_DEVTOOLS=1`.
pub fn devtools_enabled(debug: bool, env: Option<&str>) -> bool {
    debug || env == Some("1")
}

/// The first-run screen's "Install Ollama" / "Update Ollama": the download page in the default
/// browser (a fixed address; nothing from the page is passed through).
#[tauri::command]
fn open_ollama_download() -> Result<(), String> {
    Command::new("explorer.exe")
        .arg(OLLAMA_DOWNLOAD_URL)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("cannot open the browser: {e}"))
}

/// "Open folder" after a save as Word (step 22.1.6): `<app>\exports` in Explorer. The command
/// takes no argument, so the page can open this one folder and nothing else.
#[tauri::command]
fn open_exports_folder() -> Result<(), String> {
    let app = paths::resolve_app_dir(&AppDirInputs::from_process())?;
    let dir = app.exports_dir();
    std::fs::create_dir_all(&dir).map_err(|e| format!("cannot create {}: {e}", dir.display()))?;
    Command::new("explorer.exe")
        .arg(&dir)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("cannot open the folder: {e}"))
}

/// Watch the sidecar; restart it (at most [`SIDECAR_MAX_RESTARTS`] times) and reload the page
/// with the new port/token (SSE event ids restart with the sidecar).
fn supervise_sidecar(shell: Arc<Shell>, app: tauri::AppHandle) {
    std::thread::spawn(move || {
        let mut restarts = 0;
        loop {
            std::thread::sleep(Duration::from_millis(500));
            if shell.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            let exited = match shell.sidecar.lock().unwrap().as_mut() {
                Some(child) => !matches!(child.try_wait(), Ok(None)),
                None => false,
            };
            if !exited {
                continue;
            }
            if restarts >= SIDECAR_MAX_RESTARTS {
                eprintln!("etach shell: the sidecar keeps exiting; not restarting it again");
                shell.sidecar.lock().unwrap().take();
                return;
            }
            restarts += 1;
            eprintln!("etach shell: the sidecar exited; restart {restarts}/{SIDECAR_MAX_RESTARTS}");
            match shell.spawn_sidecar() {
                Ok(hello) => {
                    if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
                        let cfg = etach_config_json(&hello);
                        let js = format!(
                            "try{{sessionStorage.setItem('__ETACH__',JSON.stringify({cfg}));}}catch(e){{}}window.__ETACH__={cfg};location.reload();"
                        );
                        let _ = window.eval(&js);
                    }
                }
                Err(e) => eprintln!("etach shell: sidecar restart failed: {e}"),
            }
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let shell = match prepare() {
        Ok(shell) => shell,
        Err(e) => {
            eprintln!("etach shell: {e}");
            std::process::exit(2);
        }
    };
    let setup_shell = shell.clone();
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![open_ollama_download, open_exports_folder])
        .setup(move |app| {
            let shell = setup_shell;
            shell.spawn_ollama()?;
            let hello = shell.spawn_sidecar()?;
            WebviewWindowBuilder::new(app, MAIN_WINDOW, WebviewUrl::App("index.html".into()))
                .title("ETACH")
                // The app is light only (PRD §10.1), so the title bar and frame are light too, even when
                // Windows is dark: on a dark frame the navy logo is hard to see (step22.6-plan D18).
                .theme(Some(tauri::Theme::Light))
                .inner_size(1280.0, 820.0)
                .min_inner_size(900.0, 600.0)
                .data_directory(shell.plan.webview_dir.clone())
                .devtools(devtools_enabled(
                    cfg!(debug_assertions),
                    std::env::var(WEBVIEW_DEVTOOLS_ENV).ok().as_deref(),
                ))
                .initialization_script(init_script(&hello))
                .disable_drag_drop_handler()
                .build()?;
            supervise_sidecar(shell, app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!());
    let app = match app {
        Ok(app) => app,
        Err(e) => {
            eprintln!("etach shell: {e}");
            shell.kill_children();
            std::process::exit(1);
        }
    };
    app.run(move |_handle, event| {
        if let RunEvent::Exit = event {
            shell.shutting_down.store(true, Ordering::SeqCst);
            shell.kill_children();
        }
    });
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn init_script_matches_config_ts() {
        let hello = SidecarHello {
            port: 8765,
            token: "abc".into(),
        };
        assert_eq!(
            etach_config_json(&hello),
            r#"{"baseUrl":"http://127.0.0.1:8765","token":"abc"}"#
        );
        assert!(init_script(&hello).contains("window.__ETACH__=c"));
    }

    #[test]
    fn devtools_only_in_debug_or_when_asked() {
        assert!(devtools_enabled(true, None));
        assert!(!devtools_enabled(false, None));
        assert!(!devtools_enabled(false, Some("0")));
        assert!(devtools_enabled(false, Some("1")));
    }

    #[test]
    fn hello_line_parses() {
        let h: SidecarHello = serde_json::from_str(r#"{"port": 1234, "token": "t"}"#).unwrap();
        assert_eq!(h.port, 1234);
    }
}
