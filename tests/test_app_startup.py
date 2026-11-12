"""Start the real application in a subprocess, as the packaged build does in CI."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_smoke_test_mode_exits_cleanly(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DESKTOP_ORGANIZER_DATA_DIR"] = str(tmp_path / "data")
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "desktop_organizer", "--smoke-test"],
        env=env,
        capture_output=True,
        timeout=60,
        check=False,
    )
    log = (tmp_path / "data" / "logs" / "desktop-organizer.log").read_text(encoding="utf-8")
    assert result.returncode == 0, log
    assert "SMOKE TEST OK" in log
    assert (tmp_path / "data" / "organizer.db").exists()
