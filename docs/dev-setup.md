# Dev setup (Windows)

The repository has two parts: `sidecar/` (Python 3.12 with uv: the LangGraph pipeline, the FastAPI sidecar, the `etach`
CLI, tests and cassettes) and `app/` (the Tauri 2 shell in `src-tauri/` and the React/TypeScript frontend in `src/`).
The full map is [`structure.md`](structure.md).

## Standard commands

Run them from the repository root. Plans name them by these names.

| Name | Command |
|---|---|
| `TEST` | `cd sidecar && uv run pytest -m "not live" -q` |
| `LINT` | `cd sidecar && uv run ruff check . && uv run ruff format --check . && uv run mypy src` |
| `LIVE` | `cd sidecar && uv run pytest -m live -q` (Ollama + models; teacher's laptop) |
| `APP_TEST` | `cd app && npm test -- --run && npm run lint && npm run typecheck` |
| `E2E` | `cd app && npm run e2e` (Playwright on the web build + `etach serve --replay`) |
| `E2E_SHELL` | `cd app && npm run e2e:shell` (WebDriver via `tauri-driver` on the real Tauri app + replay sidecar) |
| `TAURI_BUILD` | `cd app && npm run tauri build` |

## Sidecar

Install [uv](https://docs.astral.sh/uv/) (`winget install --id astral-sh.uv -e`), then:

    cd sidecar
    uv sync --frozen        # uv fetches Python 3.12 if it is missing
    uv run etach --version

## Tauri 2 toolchain

What the developer machine needs to build and test the Tauri shell (`app/src-tauri/`, plan step 14).
The teacher approved these installs and chose where each one goes. Installed 2026-10-02.

### What is installed, and where

| Tool | Location | Version (at install) |
|---|---|---|
| Rust (rustup, cargo, rustc), stable MSVC toolchain, `minimal` profile | `D:\DevTools\rust\rustup` (`RUSTUP_HOME`), `D:\DevTools\rust\cargo` (`CARGO_HOME`) | rustc 1.99.0, cargo 1.99.0, toolchain `stable-x86_64-pc-windows-msvc` |
| Visual Studio 2022 Build Tools, workload `Microsoft.VisualStudio.Workload.VCTools` + recommended (MSVC linker, Windows SDK) | default: `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools` | Build Tools 2022 17.14 (17.14.37710.0); MSVC 14.44.35207 (`link.exe` in `VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64`); Windows SDK 10.0.26100.0 |
| msedgedriver (WebDriver for Edge / WebView2) | `D:\DevTools\msedgedriver\msedgedriver.exe` | 154.0.4258.48 (matches Edge 154.0.4258.48) |
| `tauri-driver` (`cargo install tauri-driver --locked`) | `D:\DevTools\rust\cargo\bin\tauri-driver.exe` | 2.1.0 |
| WebView2 Runtime | part of Windows 11, not installed by us: `C:\Program Files (x86)\Microsoft\EdgeWebView\Application` | 154.0.4258.48 |

Environment changes (user scope only, nothing system-wide):

- `RUSTUP_HOME=D:\DevTools\rust\rustup` (user variable)
- `CARGO_HOME=D:\DevTools\rust\cargo` (user variable)
- `D:\DevTools\rust\cargo\bin` added to the user `PATH` by the rustup installer.

`D:\DevTools\msedgedriver` is **not** on `PATH`. Point `tauri-driver` at it with
`--native-driver D:\DevTools\msedgedriver\msedgedriver.exe`.

### After the install

**Restart VS Code fully (end all Code.exe processes) after the install.** Terminals started from an old
VS Code process keep the old environment and will not see `RUSTUP_HOME`, `CARGO_HOME` or the new `PATH`.

### How to verify each tool

Run in a new PowerShell window:

```powershell
rustc -V                        # rustc 1.99.0 ...
cargo -V                        # cargo 1.99.0 ...
rustup show home                # D:\DevTools\rust\rustup
rustup show active-toolchain    # stable-x86_64-pc-windows-msvc (default)

# MSVC linker and Windows SDK
& "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\Lib"   # one folder per installed SDK version

& D:\DevTools\msedgedriver\msedgedriver.exe --version   # must equal the Edge version below
(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}').pv

tauri-driver --help             # prints USAGE; tauri-driver has no --version flag

# WebView2 Runtime version
(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}').pv
```

### Keeping msedgedriver in step with Edge

msedgedriver must match the installed Edge version **exactly**. Edge updates itself, so after an Edge
update the WebDriver tests fail with a "session not created" / version mismatch error. To update:

```powershell
$v = (Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}').pv
Invoke-WebRequest "https://msedgedriver.microsoft.com/$v/edgedriver_win64.zip" -OutFile "$env:TEMP\edgedriver.zip" -UseBasicParsing
Expand-Archive "$env:TEMP\edgedriver.zip" -DestinationPath D:\DevTools\msedgedriver -Force
& D:\DevTools\msedgedriver\msedgedriver.exe --version
```

### Running E2E_SHELL (`npm run e2e:shell`)

The WebDriver tests of the real app (plan step 14, R14.4 and R14.5). Offline: the sidecar replays
`sidecar/tests/cassettes/s1`, `ollama` is a stub (`app/e2e-shell/stub-bin/ollama.cmd`, put first on
PATH by the runner), and every request goes to 127.0.0.1. The real Ollama is never started.

```powershell
cd app
npm run build                    # app/dist (the frontend the debug build embeds)
npm run tauri:build -- --debug   # src-tauri\target\debug\ETACH.exe
npm run e2e:shell                # starts tauri-driver itself (port 4444)
```

- tauri-driver must be on PATH (`D:\DevTools\rust\cargo\bin`); msedgedriver is read from
  `D:\DevTools\msedgedriver\msedgedriver.exe` (override with `$env:MSEDGEDRIVER`). It is not on PATH.
- `$env:ETACH_SHELL_EXE` overrides the exe path (e.g. a release build).
- Each run uses a fresh app folder in `%TEMP%` (`ETACH_APP_DIR`) and deletes it afterwards.
- Close other WebView2/Edge automation first: port 4444 must be free.
- R14.5 lists every AppData path newer than the start. It fails on a path that names the app
  (identifier, product or exe name) or on a new folder at the first two levels of `%APPDATA%` /
  `%LOCALAPPDATA%`. It excludes `%LOCALAPPDATA%\Temp` (system temp) and `%LOCALAPPDATA%\uv` (the
  dev launcher's cache); writes by other running programs inside their own existing folders are
  printed as "other programs", not failed.
- R15.2 (step 15) performs a **real OLE drop** of 3 synthetic JPGs onto the app window
  (`app/e2e-shell/real-drop.ps1`). It needs an **unlocked, interactive desktop** (not headless, not a
  locked RDP session) and takes over the real mouse for about 4 s, with the app window topmost: don't
  touch the mouse or keyboard while it runs.
- Run it from PowerShell so that `tauri-driver` resolves to `D:\DevTools\rust\cargo\bin`; a run from
  Git Bash with another `~/.cargo/bin` first on PATH failed with an `about:blank` page.

### Uninstall

1. Rust (removes rustup, cargo, toolchains, `tauri-driver` and the `PATH` entry):
   ```powershell
   rustup self uninstall
   [Environment]::SetEnvironmentVariable("RUSTUP_HOME", $null, "User")
   [Environment]::SetEnvironmentVariable("CARGO_HOME", $null, "User")
   ```
   Then delete `D:\DevTools\rust` if anything is left.
2. msedgedriver: delete `D:\DevTools\msedgedriver`.
3. Build Tools: "Settings → Apps → Installed apps → Visual Studio Build Tools 2022 → Uninstall", or open the
   Visual Studio Installer and choose "Uninstall" on Build Tools 2022.
4. WebView2 is part of Windows; leave it.
