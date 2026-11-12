import os

from desktop_organizer.tools.system_monitor.logic import Sampler, disks, end_process, top_processes


def test_sampler_produces_sane_values() -> None:
    sampler = Sampler()
    reading = sampler.sample()
    assert 0 <= reading.cpu <= 100
    assert reading.memory_total > 0 and 0 < reading.memory_used <= reading.memory_total
    assert reading.net_down >= 0 and reading.net_up >= 0
    assert len(sampler.cpu_history) == 1


def test_disks_and_processes() -> None:
    assert all(d.total > 0 and 0 <= d.fraction <= 1 for d in disks())
    snapshot = top_processes(5, "memory")
    assert 0 < len(snapshot.processes) <= 5 and snapshot.total >= len(snapshot.processes)
    assert snapshot.processes == sorted(snapshot.processes, key=lambda p: (-p.memory, -p.cpu))
    assert any(p.pid == os.getpid() for p in top_processes(10_000).processes)


def test_end_missing_process() -> None:
    assert end_process(2**22 + 12345) == "gone"
