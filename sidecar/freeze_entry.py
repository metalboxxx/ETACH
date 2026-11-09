"""The entry point of the frozen sidecar (plan step 21; PyInstaller folder mode, ``etach.spec``).

The release shell runs ``<app>\\sidecar\\etach-sidecar.exe serve ...``; this is ``etach``
(``etach.cli:main``) with every subcommand, so ``etach-sidecar.exe --version`` equals
``etach --version`` (R21.2).
"""

from __future__ import annotations

import multiprocessing

from etach.cli import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
