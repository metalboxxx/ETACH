# PyInstaller spec of the frozen sidecar (plan step 21, PRD §11 / R5).
#
# FOLDER mode (onedir), never one-file: a one-file exe unpacks itself into %TEMP%\_MEI* on every
# start (slow, and an AppData write), and draws more antivirus false alarms. The folder build runs
# in place: `dist\etach-sidecar\etach-sidecar.exe` + `dist\etach-sidecar\_internal\`, which the Tauri release config ships as
# resources into `<app>\sidecar\`.
#
# Build (from `sidecar/`; `npm run freeze:sidecar` in `app/` does this with PyInstaller's cache
# kept in `sidecar/build/` instead of %LOCALAPPDATA%):
#     uv run pyinstaller etach.spec --noconfirm --clean --distpath dist --workpath build
# PyInstaller is a dev dependency only (pyproject `[dependency-groups] dev`).
# ruff: noqa
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

hiddenimports = (
    # `etach.cli` imports its subcommands lazily; the routes, graphs and adapters load by name.
    collect_submodules("etach")
    # uvicorn picks its loop / protocol / lifespan implementations by name at run time.
    + collect_submodules("uvicorn")
    + collect_submodules("langgraph")
    + collect_submodules("langgraph.checkpoint.sqlite")
)

datas = (
    # Prompts (`etach/prompts/**.md`, the taxonomy) and the SQL migrations, read through
    # importlib.resources.
    collect_data_files("etach", excludes=["**/__pycache__/**"])
    # `etach.__version__` comes from the installed metadata (`importlib.metadata.version("etach")`).
    + copy_metadata("etach")
)

a = Analysis(
    ["freeze_entry.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Development and test tools never ship.
    excludes=["tkinter", "pytest", "_pytest", "mypy", "ruff", "IPython", "matplotlib"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # folder mode
    name="etach-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed binaries are a common antivirus false alarm
    # A console program: the shell reads the `{"port","token"}` line from stdout. The shell
    # starts it with CREATE_NO_WINDOW, so no console window shows.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="etach-sidecar",
)
