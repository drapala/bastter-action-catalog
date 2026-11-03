"""Checks that nothing secret or private is in the files git would commit.

1. No value of the Bastter session cookies (read from the keychain), plain, URL-encoded or base64, appears in a
   staged file (read from the index) or an untracked file.
2. The cache of raw pages (.cache/) and the private MCP log (logs/) are not tracked.
3. The evidence log keeps answer shapes, never answer payloads, and holds no MCP call.

Exit 1 on any failure. The repo pre-commit hook runs it (.git/hooks/pre-commit).
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bastter_exec
import session


def secret_forms(value: str) -> set[str]:
    """The plain cookie value and the encoded forms a script could write by accident."""
    raw = value.encode()
    return {
        value,
        quote(value, safe=""),
        base64.b64encode(raw).decode(),
        base64.urlsafe_b64encode(raw).decode(),
    }


def files_to_check() -> dict[str, str]:
    """Path -> content for every staged file (from the index) and every untracked, not ignored file (from disk)."""
    out = {}
    staged = subprocess.run(
        ["git", "ls-files", "--cached"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    for path in filter(None, staged):
        blob = subprocess.run(
            ["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=False
        )
        if blob.returncode == 0:
            out[path] = blob.stdout.decode("utf-8", errors="ignore")
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    for path in filter(None, untracked):
        file = ROOT / path
        if file.is_file():
            out[path] = file.read_bytes().decode("utf-8", errors="ignore")
    return out


def main() -> int:
    failures = []
    secrets = [
        form
        for v in session.load_cookies().values()
        if len(v) >= 12
        for form in secret_forms(v)
    ]
    files = files_to_check()
    for path, text in files.items():
        if any(secret in text for secret in secrets):
            failures.append(f"{path} holds a session cookie value (plain or encoded)")
    if any(p.startswith((".cache/", "logs/")) for p in files):
        failures.append(".cache/ or logs/ is tracked")
    runs = files.get("evidence/runs.jsonl", "")
    for n, line in enumerate(runs.splitlines(), 1):
        row = json.loads(line) if line.strip() else {}
        if "payload" in row:
            failures.append(f"evidence/runs.jsonl line {n} stores an answer payload")
            break
        if str(row.get("run", "")).startswith(bastter_exec.PRIVATE_RUNS):
            failures.append(
                f"evidence/runs.jsonl line {n} is a private run (MCP, demo or market): it can hold real trades"
            )
            break
    for f in failures:
        print("FAIL", f)
    print(
        f"checked {len(files)} files against {len(secrets)} secret forms: {'OK' if not failures else 'FAILED'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
