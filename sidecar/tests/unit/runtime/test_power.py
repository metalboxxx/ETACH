"""Keep-awake and power source: the fake, and the Windows implementation's thread rule."""

from __future__ import annotations

import sys
import threading

import pytest

from etach.runtime import power as power_mod
from etach.runtime.power import FakePower, NullPower, default_power


def test_fake_records_changes() -> None:
    p = FakePower(source="battery")
    p.set_keep_awake(True)
    p.set_keep_awake(False)
    assert p.changes == [True, False] and p.keep_awake is False
    assert p.power_source() == "battery"


def test_null_power() -> None:
    p = NullPower()
    p.set_keep_awake(True)
    assert p.keep_awake and p.power_source() == "unknown"
    p.close()
    assert not p.keep_awake


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_windows_power_calls_from_one_dedicated_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    p = power_mod.WindowsPower()
    calls: list[tuple[int, str]] = []
    done = threading.Event()
    real = p._kernel32

    class Spy:
        def __init__(self) -> None:
            self.GetSystemPowerStatus = real.GetSystemPowerStatus

        def SetThreadExecutionState(self, flags: int) -> int:
            calls.append((flags, threading.current_thread().name))
            if len(calls) == 3:
                done.set()
            return 0x80000000

    p._kernel32 = Spy()  # type: ignore[assignment]
    p.set_keep_awake(True)
    p.set_keep_awake(True)  # no change: not sent again
    p.set_keep_awake(False)
    p.close()
    assert done.wait(5)
    es_continuous, es_system = power_mod.ES_CONTINUOUS, power_mod.ES_SYSTEM_REQUIRED
    assert [f for f, _ in calls] == [es_continuous | es_system, es_continuous, es_continuous]
    assert {name for _, name in calls} == {"etach-keep-awake"}
    assert p.power_source() in ("ac", "battery", "unknown")


def test_default_power_kind() -> None:
    p = default_power()
    try:
        expected = power_mod.WindowsPower if sys.platform == "win32" else NullPower
        assert isinstance(p, expected)
    finally:
        p.close()
