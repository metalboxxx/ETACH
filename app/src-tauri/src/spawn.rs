//! The pure spawn-args builder (plan step 14, R14.1): the program, arguments, environment and
//! working folder of both children (`ollama serve` and the sidecar), and the WebView2 data folder.
//! No I/O here; `lib.rs` turns a [`SpawnPlan`] into processes.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use crate::paths::{AppPaths, APP_DIR_ENV};

/// One child process to start.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChildSpec {
    pub program: PathBuf,
    pub args: Vec<String>,
    /// Added to the inherited environment.
    pub env: BTreeMap<String, String>,
    pub cwd: Option<PathBuf>,
}

/// How the sidecar is started.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SidecarMode {
    /// Development: `uv run etach serve` in `<repo>\sidecar`.
    Dev {
        sidecar_dir: PathBuf,
        /// `ETACH_SIDECAR_REPLAY`: replay these cassettes instead of calling Ollama.
        replay: Option<PathBuf>,
    },
    /// Release (plan step 21): the frozen PyInstaller folder build, `<exe dir>\sidecar\etach-sidecar.exe
    /// serve …`, started in the app folder. It gets `ETACH_APP_DIR=<app>` like the dev sidecar, so
    /// its data folder is `<app>\data`, never the folder it was unpacked to.
    Frozen {
        exe: PathBuf,
        /// `ETACH_SIDECAR_REPLAY`: replay these cassettes instead of calling Ollama (E2E_SHELL
        /// `--release`).
        replay: Option<PathBuf>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpawnInputs {
    pub app: AppPaths,
    pub ollama_exe: PathBuf,
    pub ollama_port: u16,
    pub gpu_index: u32,
    pub sidecar: SidecarMode,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SpawnPlan {
    pub ollama: ChildSpec,
    pub sidecar: ChildSpec,
    /// The WebView2 user data folder (`<app>\webview`).
    pub webview_dir: PathBuf,
}

fn path_str(p: &Path) -> String {
    p.to_string_lossy().into_owned()
}

/// Build both children's command lines. Pure.
pub fn build_spawn_plan(inputs: &SpawnInputs) -> SpawnPlan {
    let host = format!("127.0.0.1:{}", inputs.ollama_port);
    let ollama_env: BTreeMap<String, String> = [
        ("OLLAMA_HOST", host.clone()),
        ("OLLAMA_MODELS", path_str(&inputs.app.models_dir())),
        ("OLLAMA_MAX_LOADED_MODELS", "1".to_string()),
        ("OLLAMA_FLASH_ATTENTION", "1".to_string()),
        ("OLLAMA_KV_CACHE_TYPE", "q8_0".to_string()),
        ("CUDA_VISIBLE_DEVICES", inputs.gpu_index.to_string()),
    ]
    .into_iter()
    .map(|(k, v)| (k.to_string(), v))
    .collect();
    let ollama = ChildSpec {
        program: inputs.ollama_exe.clone(),
        args: vec!["serve".to_string()],
        env: ollama_env,
        cwd: None,
    };

    // No `--data`: `ETACH_APP_DIR=<app>` gives the sidecar the app layout, so it uses
    // `<app>\data` and shares `<app>\settings.json` with the shell (PRD §11).
    let serve_args = |replay: &Option<PathBuf>| -> Vec<String> {
        let mut args = vec!["serve".to_string()];
        match replay {
            // `--replay` and `--ollama` are mutually exclusive in `etach serve`.
            Some(dir) => {
                args.push("--replay".to_string());
                args.push(path_str(dir));
            }
            None => {
                args.push("--ollama".to_string());
                args.push(format!("http://{host}"));
            }
        }
        args
    };
    let sidecar_env = BTreeMap::from([(APP_DIR_ENV.to_string(), path_str(&inputs.app.root))]);
    let sidecar = match &inputs.sidecar {
        SidecarMode::Dev {
            sidecar_dir,
            replay,
        } => {
            let mut args: Vec<String> = vec!["run".to_string(), "etach".to_string()];
            args.extend(serve_args(replay));
            ChildSpec {
                program: PathBuf::from("uv"),
                args,
                env: sidecar_env,
                cwd: Some(sidecar_dir.clone()),
            }
        }
        SidecarMode::Frozen { exe, replay } => ChildSpec {
            program: exe.clone(),
            args: serve_args(replay),
            env: sidecar_env,
            // The app folder: a relative path anywhere in the sidecar resolves inside it.
            cwd: Some(inputs.app.root.clone()),
        },
    };

    SpawnPlan {
        ollama,
        sidecar,
        webview_dir: inputs.app.webview_dir(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn inputs(replay: Option<PathBuf>) -> SpawnInputs {
        SpawnInputs {
            app: AppPaths::new(r"D:\ETACH"),
            ollama_exe: PathBuf::from(r"C:\Ollama\ollama.exe"),
            ollama_port: 49152,
            gpu_index: 1,
            sidecar: SidecarMode::Dev {
                sidecar_dir: PathBuf::from(r"D:\repo\sidecar"),
                replay,
            },
        }
    }

    /// R14.1: exactly these env vars for a given app folder and GPU index.
    #[test]
    fn ollama_env_is_exactly_the_plan_set() {
        let plan = build_spawn_plan(&inputs(None));
        let expected: BTreeMap<String, String> = [
            ("OLLAMA_HOST", "127.0.0.1:49152"),
            ("OLLAMA_MODELS", r"D:\ETACH\data\models"),
            ("OLLAMA_MAX_LOADED_MODELS", "1"),
            ("OLLAMA_FLASH_ATTENTION", "1"),
            ("OLLAMA_KV_CACHE_TYPE", "q8_0"),
            ("CUDA_VISIBLE_DEVICES", "1"),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();
        assert_eq!(plan.ollama.env, expected);
        assert_eq!(plan.ollama.program, PathBuf::from(r"C:\Ollama\ollama.exe"));
        assert_eq!(plan.ollama.args, vec!["serve"]);
    }

    /// R14.1: the webview data folder is `<app>\webview`.
    #[test]
    fn webview_dir_is_in_the_app_folder() {
        let plan = build_spawn_plan(&inputs(None));
        assert_eq!(plan.webview_dir, PathBuf::from(r"D:\ETACH\webview"));
    }

    #[test]
    fn gpu_index_feeds_cuda_visible_devices() {
        let mut i = inputs(None);
        i.gpu_index = 0;
        assert_eq!(build_spawn_plan(&i).ollama.env["CUDA_VISIBLE_DEVICES"], "0");
    }

    #[test]
    fn dev_sidecar_uses_the_private_ollama() {
        let plan = build_spawn_plan(&inputs(None));
        assert_eq!(plan.sidecar.program, PathBuf::from("uv"));
        assert_eq!(
            plan.sidecar.args,
            vec![
                "run",
                "etach",
                "serve",
                "--ollama",
                "http://127.0.0.1:49152"
            ]
        );
        assert_eq!(plan.sidecar.cwd, Some(PathBuf::from(r"D:\repo\sidecar")));
        // R14.1: the sidecar gets the app folder, not `--data`, so it uses `<app>\data` and
        // shares `<app>\settings.json` with the shell.
        let expected_env: BTreeMap<String, String> =
            BTreeMap::from([("ETACH_APP_DIR".to_string(), r"D:\ETACH".to_string())]);
        assert_eq!(plan.sidecar.env, expected_env);
        assert!(!plan.sidecar.args.iter().any(|a| a == "--data"));
    }

    fn frozen(replay: Option<PathBuf>) -> SpawnInputs {
        let mut i = inputs(None);
        i.sidecar = SidecarMode::Frozen {
            exe: PathBuf::from(r"D:\ETACH\sidecar\etach-sidecar.exe"),
            replay,
        };
        i
    }

    /// Step 21: the release shell runs the frozen sidecar directly (no uv), in the app folder,
    /// with the same `ETACH_APP_DIR` and no `--data`.
    #[test]
    fn frozen_sidecar_runs_etach_exe_in_the_app_folder() {
        let plan = build_spawn_plan(&frozen(None));
        assert_eq!(
            plan.sidecar.program,
            PathBuf::from(r"D:\ETACH\sidecar\etach-sidecar.exe")
        );
        assert_eq!(
            plan.sidecar.args,
            vec!["serve", "--ollama", "http://127.0.0.1:49152"]
        );
        assert_eq!(plan.sidecar.cwd, Some(PathBuf::from(r"D:\ETACH")));
        let expected_env: BTreeMap<String, String> =
            BTreeMap::from([("ETACH_APP_DIR".to_string(), r"D:\ETACH".to_string())]);
        assert_eq!(plan.sidecar.env, expected_env);
        assert!(!plan.sidecar.args.iter().any(|a| a == "--data"));
    }

    #[test]
    fn frozen_sidecar_can_replay() {
        let plan = build_spawn_plan(&frozen(Some(PathBuf::from(r"D:\cassettes\s1"))));
        assert_eq!(plan.sidecar.args, vec!["serve", "--replay", r"D:\cassettes\s1"]);
    }

    #[test]
    fn replay_replaces_the_ollama_url() {
        let plan = build_spawn_plan(&inputs(Some(PathBuf::from(r"D:\cassettes\s1"))));
        assert_eq!(
            &plan.sidecar.args[3..],
            &[
                "--replay".to_string(),
                r"D:\cassettes\s1".to_string()
            ]
        );
    }
}
