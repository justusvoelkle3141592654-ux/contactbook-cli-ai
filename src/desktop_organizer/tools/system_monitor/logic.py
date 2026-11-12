"""System readings for the monitor: CPU, memory, disks, network, battery, processes."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import psutil


@dataclass
class DiskInfo:
    mount: str
    filesystem: str
    total: int
    used: int
    free: int

    @property
    def fraction(self) -> float:
        return self.used / self.total if self.total else 0.0


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu: float
    memory: int
    user: str


@dataclass
class Reading:
    cpu: float
    per_core: list[float]
    memory_used: int
    memory_total: int
    swap_used: int
    swap_total: int
    net_down: float  # bytes per second
    net_up: float
    battery_percent: float | None
    battery_plugged: bool | None
    battery_seconds_left: int | None
    uptime: float


class Sampler:
    """Keeps the previous counters so rates (network) can be computed."""

    def __init__(self, history: int = 60) -> None:
        self.cpu_history: deque[float] = deque(maxlen=history)
        self.memory_history: deque[float] = deque(maxlen=history)
        self.down_history: deque[float] = deque(maxlen=history)
        self.up_history: deque[float] = deque(maxlen=history)
        self._net = psutil.net_io_counters()
        self._net_time = time.monotonic()
        psutil.cpu_percent(interval=None, percpu=True)
        psutil.cpu_percent(interval=None)

    def sample(self) -> Reading:
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        cpu = sum(per_core) / len(per_core) if per_core else psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        now = time.monotonic()
        net = psutil.net_io_counters()
        elapsed = max(now - self._net_time, 1e-3)
        down = max(0, net.bytes_recv - self._net.bytes_recv) / elapsed
        up = max(0, net.bytes_sent - self._net.bytes_sent) / elapsed
        self._net, self._net_time = net, now
        battery = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
        seconds_left = None
        if battery is not None and battery.secsleft not in (
            psutil.POWER_TIME_UNLIMITED,
            psutil.POWER_TIME_UNKNOWN,
        ):
            seconds_left = int(battery.secsleft)
        used = int(memory.total - memory.available)
        self.cpu_history.append(cpu)
        self.memory_history.append(100 * used / memory.total if memory.total else 0)
        self.down_history.append(down)
        self.up_history.append(up)
        return Reading(
            cpu=cpu,
            per_core=list(per_core),
            memory_used=used,
            memory_total=int(memory.total),
            swap_used=int(swap.used),
            swap_total=int(swap.total),
            net_down=down,
            net_up=up,
            battery_percent=float(battery.percent) if battery else None,
            battery_plugged=bool(battery.power_plugged) if battery else None,
            battery_seconds_left=seconds_left,
            uptime=time.time() - psutil.boot_time(),
        )


def disks() -> list[DiskInfo]:
    result = []
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue  # removable drive without medium, or no access
        result.append(DiskInfo(part.mountpoint, part.fstype, usage.total, usage.used, usage.free))
    return result


@dataclass
class ProcessSnapshot:
    processes: list[ProcessInfo] = field(default_factory=list)
    total: int = 0


_primed: set[int] = set()


def top_processes(limit: int = 25, sort: str = "cpu") -> ProcessSnapshot:
    """Processes sorted by CPU or memory. CPU values need two calls to become meaningful."""
    found: list[ProcessInfo] = []
    cores = psutil.cpu_count() or 1
    total = 0
    for proc in psutil.process_iter(["pid", "name", "memory_info", "username"]):
        total += 1
        try:
            cpu = proc.cpu_percent(interval=None) / cores
            info = proc.info
            memory = info["memory_info"].rss if info.get("memory_info") else 0
            found.append(
                ProcessInfo(
                    info["pid"],
                    info.get("name") or "?",
                    cpu,
                    int(memory),
                    info.get("username") or "",
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    key = (lambda p: (-p.cpu, -p.memory)) if sort == "cpu" else (lambda p: (-p.memory, -p.cpu))
    found.sort(key=key)
    return ProcessSnapshot(found[:limit], total)


def end_process(pid: int) -> str | None:
    """Ask a process to end. Returns an error code or None."""
    try:
        psutil.Process(pid).terminate()
    except psutil.NoSuchProcess:
        return "gone"
    except psutil.AccessDenied:
        return "denied"
    return None
