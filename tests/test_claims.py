"""Every number in catalog/claims.json must match its recompute command, so the write-up cannot drift from the data."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("jq") is None, reason="the recompute commands use jq")
def test_every_claim_matches_its_recompute_command():
    claims = json.loads((ROOT / "catalog/claims.json").read_text())["claims"]
    for claim in claims:
        out = subprocess.run(
            claim["recompute"],
            shell=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert int(out.stdout.strip()) == claim["value"], claim["id"]
    by_id = {c["id"]: c["value"] for c in claims}
    assert by_id["lint_errors"] == 0
    assert by_id["verified_writes"] <= by_id["writes_with_passing_read_back"]


def test_agent_doc_shows_the_current_claims():
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import make_claims

    claims = json.loads((ROOT / "catalog/claims.json").read_text())["claims"]
    assert make_claims.table(claims) in (ROOT / "AGENT.md").read_text()


def test_the_scenarios_claim_counts_files_with_a_read_back_step():
    """Correction C036: the grep once counted a file that only mentions postcondition_of in its description."""
    import yaml

    files = sorted(ROOT.glob("scenarios/*.yaml")) + sorted(
        ROOT.glob("scenarios/archive/*.yaml")
    )
    real = sum(
        any("postcondition_of" in s for s in yaml.safe_load(f.read_text())["steps"])
        for f in files
    )
    claim = next(
        c
        for c in json.loads((ROOT / "catalog/claims.json").read_text())["claims"]
        if c["id"] == "scenarios"
    )
    assert claim["value"] == real
