"""Keep-awake and power source (PRD D23, llm-design §7 "Sleep").

:class:`Power` is the interface the run manager uses: keep-awake is on while a run is
``running`` and off otherwise. :func:`default_power` gives :class:`WindowsPower` on Windows and
:class:`NullPower` elsewhere; tests use :class:`FakePower`.

``SetThreadExecutionState`` applies to the calling **thread**, and the state lapses when that
thread exits. :class:`WindowsPower` therefore owns one dedicated long-lived thread that makes
every call; it is never called from the event loop or a thread-pool thread.
"""

from __future__ import annotations

import ctypes
import queue
import sys
import threading
from dataclasses import dataclass, field
from typing import Literal, Protocol

__all__ = [
    "FakePower",
    "NullPower",
    "Power",
    "PowerSource",
    "WindowsPower",
    "default_power",
]

PowerSource = Literal["ac", "battery", "unknown"]

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class Power(Protocol):
    def set_keep_awake(self, on: bool) -> None:
        """Block idle sleep (``on``) or allow it again; idempotent."""

    @property
    def keep_awake(self) -> bool:
        """Whether idle sleep is currently blocked."""

    def power_source(self) -> PowerSource:
        """AC or battery (``unknown`` when the system cannot tell)."""

    def close(self) -> None:
        """Allow sleep again and release resources."""


class NullPower:
    """Does nothing (non-Windows development machines)."""

    def __init__(self) -> None:
        self._on = False

    def set_keep_awake(self, on: bool) -> None:
        self._on = on

    @property
    def keep_awake(self) -> bool:
        return self._on

    def power_source(self) -> PowerSource:
        return "unknown"

    def close(self) -> None:
        self._on = False


@dataclass
class FakePower:
    """Records every keep-awake change (plan R7.6); the power source is settable."""

    source: PowerSource = "ac"
    changes: list[bool] = field(default_factory=list)
    _on: bool = False

    def set_keep_awake(self, on: bool) -> None:
        self.changes.append(on)
        self._on = on

    @property
    def keep_awake(self) -> bool:
        return self._on

    def power_source(self) -> PowerSource:
        return self.source

    def close(self) -> None:
        self._on = False


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


class WindowsPower:
    """``SetThreadExecutionState`` on one dedicated thread; ``GetSystemPowerStatus`` for the
    power source."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("WindowsPower needs Windows")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.SetThreadExecutionState.restype = ctypes.c_uint32
        self._kernel32.SetThreadExecutionState.argtypes = [ctypes.c_uint32]
        self._requests: queue.Queue[bool | None] = queue.Queue()
        self._on = False
        self._closed = False
        self._thread = threading.Thread(target=self._serve, name="etach-keep-awake", daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        while True:
            request = self._requests.get()
            if request is None:
                self._kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                return
            flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if request else 0)
            self._kernel32.SetThreadExecutionState(flags)

    def set_keep_awake(self, on: bool) -> None:
        if self._closed or on == self._on:
            return
        self._on = on
        self._requests.put(on)

    @property
    def keep_awake(self) -> bool:
        return self._on

    def power_source(self) -> PowerSource:
        status = _SystemPowerStatus()
        if not self._kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return "unknown"
        return {0: "battery", 1: "ac"}.get(status.ACLineStatus, "unknown")  # type: ignore[return-value]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._on = False
        self._requests.put(None)
        self._thread.join(timeout=5)


def default_power() -> Power:
    return WindowsPower() if sys.platform == "win32" else NullPower()
