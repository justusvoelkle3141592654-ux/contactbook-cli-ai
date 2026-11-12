"""Low-overhead system readings for the status line and the system monitor."""

from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class Snapshot:
    cpu_percent: float
    memory_used: int
    memory_total: int
    battery_percent: float | None
    battery_charging: bool | None


def prime() -> None:
    """The first CPU reading is always 0; call once at start-up to establish a baseline."""
    psutil.cpu_percent(interval=None)


def snapshot() -> Snapshot:
    memory = psutil.virtual_memory()
    battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    return Snapshot(
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_used=int(memory.total - memory.available),
        memory_total=int(memory.total),
        battery_percent=float(battery.percent) if battery is not None else None,
        battery_charging=bool(battery.power_plugged) if battery is not None else None,
    )
