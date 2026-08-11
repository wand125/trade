from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "methods/next_bar/scripts/run_low_priority_worker.sh"


def worker_environment(tmp_path: Path) -> dict[str, str]:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemAvailable: 67108864 kB\n", encoding="utf-8")
    loadavg = tmp_path / "loadavg"
    loadavg.write_text("0.10 0.10 0.10 1/1 1\n", encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    flock = fake_bin / "flock"
    flock.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"$1\" == \"-n\" ]]; then shift; fi\n"
        "shift\n"
        "exec \"$@\"\n",
        encoding="utf-8",
    )
    flock.chmod(flock.stat().st_mode | stat.S_IXUSR)

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "TRADE_MEMINFO_PATH": str(meminfo),
            "TRADE_LOADAVG_PATH": str(loadavg),
            "TRADE_WORKER_LOCK": str(tmp_path / "worker.lock"),
        }
    )
    for name in (
        "TRADE_ENABLE_GPU",
        "TRADE_REQUIRE_IDLE_GPU",
        "TRADE_GPU_EXCLUSIVE_WINDOW",
        "CUDA_VISIBLE_DEVICES",
    ):
        environment.pop(name, None)
    return environment


def run_worker(tmp_path: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            str(WORKER),
            "bash",
            "-c",
            'printf "%s" "${CUDA_VISIBLE_DEVICES-unset}"',
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cpu_worker_hides_shared_gpu_by_default(tmp_path: Path) -> None:
    result = run_worker(tmp_path, worker_environment(tmp_path))

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_gpu_worker_requires_idle_gate_and_exclusive_window(tmp_path: Path) -> None:
    environment = worker_environment(tmp_path)
    environment["TRADE_ENABLE_GPU"] = "1"
    result = run_worker(tmp_path, environment)

    assert result.returncode == 64
    assert "TRADE_REQUIRE_IDLE_GPU=1" in result.stderr

    environment["TRADE_REQUIRE_IDLE_GPU"] = "1"
    result = run_worker(tmp_path, environment)

    assert result.returncode == 75
    assert "exclusive GPU window" in result.stderr
