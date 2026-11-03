"""Runs every scenario one at a time, then deletes for good the items the scenarios hid, then runs the state checks.

One at a time on purpose: calls from several clients on the same session got slow (up to 65 s).
Scenarios in scenarios/archive/ are not run again: one-off cleanups, and the activity diary scenario,
whose write feeds a public ranking.

Run: .venv/bin/python tools/run_all_scenarios.py
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_CHECKS = {
    "ativos_classes_vazias.yaml",
    "pas_config_estado_final.yaml",
    "saude_leituras.yaml",
}
PY = str(ROOT / ".venv/bin/python")


KEEP = ("FAIL", "CLEANUP", "GUARD", "saved values", "LEFT", "Traceback")


def run(args: list[str]) -> tuple[int, str]:
    """Exit code and the last output line. Failure, cleanup and saved-value lines are printed after the scenario ends."""
    out = subprocess.run(
        [PY, *args], check=False, cwd=ROOT, capture_output=True, text=True
    )
    lines = (out.stdout + out.stderr).strip().splitlines()
    for line in lines[:-1]:
        if line.startswith(KEEP):
            print(f"    {line}", flush=True)
    return out.returncode, lines[-1] if lines else ""


def main() -> int:
    files = sorted(p.name for p in (ROOT / "scenarios").glob("*.yaml"))
    order = [f for f in files if f not in STATE_CHECKS]
    failures = []
    started = time.time()
    for name in order:
        code, last = run(["tools/bastter_exec.py", "scenario", f"scenarios/{name}"])
        print(f"{'PASS' if code == 0 else 'FAIL'} {name:40} {last}", flush=True)
        if code:
            failures.append(name)
    code, last = run(["tools/purge_hidden_items.py"])
    print(
        f"{'PASS' if code == 0 else 'FAIL'} {'purge_hidden_items':40} {last}",
        flush=True,
    )
    if code:
        failures.append("purge_hidden_items")
    for name in sorted(STATE_CHECKS):
        code, last = run(["tools/bastter_exec.py", "scenario", f"scenarios/{name}"])
        print(f"{'PASS' if code == 0 else 'FAIL'} {name:40} {last}", flush=True)
        if code:
            failures.append(name)
    print(
        f"done in {int(time.time() - started)} s: {len(order) + len(STATE_CHECKS) + 1 - len(failures)} passed, {len(failures)} failed {failures}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
