"""Writes catalog/claims.json: every headline number in the docs, with the command that recomputes it.

An agent that checks the catalog can run each `recompute` command from the repo root
and compare the output with `value`. tests/test_claims.py does the same check.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "catalog/claims.json"

STATUS = "jq '[.[] | select(.verification == \"{s}\")] | length' catalog/index.json"
CLAIMS = [
    (
        "actions_total",
        "Business actions in the catalog, one JSON file each.",
        "jq length catalog/index.json",
    ),
    *[
        (
            f"status_{s}",
            f"Actions with status `{s}`. See AGENT.md for what each status means.",
            STATUS.format(s=s),
        )
        for s in ("verified", "observed", "gated", "failed", "seen", "excluded")
    ],
    (
        "verified_writes",
        "Verified actions that change data. Each one passed a read-back in a scenario.",
        'jq -s \'[.[] | select(.verification.status == "verified" and .operation_class != "read")] | length\' catalog/actions/*.json',
    ),
    (
        "writes_with_passing_read_back",
        "Write actions with at least one passing read-back line in the evidence log.",
        "jq -s '[.[] | select(.check == \"read_back\" and .passed) | .checks] | unique | length' evidence/runs.jsonl",
    ),
    (
        "requires_confirmation",
        "Actions that need the user's OK before they run: deletes, writes that cannot be undone or that change a whole tab or setting, and writes that reach people (those never run).",
        "jq '[.[] | select(.requires_confirmation)] | length' catalog/index.json",
    ),
    (
        "live_calls",
        "Calls made by the scripts to the live Bastter web services. Each is one line in the evidence log.",
        "jq -s '[.[] | select(.status != null)] | length' evidence/runs.jsonl",
    ),
    (
        "screens_walked",
        "BS2 screens the crawler fetched with the session (the browser capture opened the same screens).",
        "jq .screens_walked catalog/coverage.json",
    ),
    (
        "captured_calls",
        "Web service calls the app made while the browser opened the screens.",
        "jq .captured_calls catalog/coverage.json",
    ),
    (
        "scenarios",
        "Scenario files (in scenarios/ and scenarios/archive/) with at least one write proved by a read-back.",
        "grep -l '^ *postcondition_of:' scenarios/*.yaml scenarios/archive/*.yaml | wc -l",
    ),
    (
        "corrections",
        "Mistakes logged while building the catalog.",
        "wc -l < docs/corrections.jsonl",
    ),
    (
        "corrections_with_check",
        "Logged mistakes that name the automated check that now catches them.",
        "jq -s '[.[] | select(.now_checked_by != null)] | length' docs/corrections.jsonl",
    ),
    (
        "lint_errors",
        "Errors from the catalog lint. Must be 0.",
        "jq '[.[] | select(.severity == \"error\")] | length' catalog/lint.json",
    ),
]


def run(command: str) -> int:
    out = subprocess.run(
        command, shell=True, cwd=ROOT, capture_output=True, text=True, check=True
    )
    return int(out.stdout.strip())


AGENT_DOC = ROOT / "AGENT.md"
START, END = "<!-- claims:start -->", "<!-- claims:end -->"


def table(claims: list[dict]) -> str:
    rows = [f"| `{c['id']}` | {c['value']} | {c['meaning']} |" for c in claims]
    return "\n".join(
        [START, "| Claim | Value | Meaning |", "|---|---|---|", *rows, END]
    )


def main() -> None:
    claims = [
        {"id": i, "value": run(c), "meaning": m, "recompute": c} for i, m, c in CLAIMS
    ]
    OUT.write_text(
        json.dumps(
            {
                "how_to_check": "Run each recompute command from the repo root.",
                "claims": claims,
            },
            indent=2,
        )
        + "\n"
    )
    text = AGENT_DOC.read_text()
    AGENT_DOC.write_text(text.split(START)[0] + table(claims) + text.split(END)[1])
    print(f"wrote {len(claims)} claims to {OUT.relative_to(ROOT)} and {AGENT_DOC.name}")


if __name__ == "__main__":
    main()
