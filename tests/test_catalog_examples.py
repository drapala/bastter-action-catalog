"""Every body that worked on the live account passes the MCP input check (audit finding: 15 such bodies were refused)."""

import json
from pathlib import Path

import bastter_exec
import mcp_server

ROOT = Path(__file__).resolve().parent.parent


def test_working_bodies_pass_the_mcp_input_check():
    actions = {
        json.loads(p.read_text())["id"]: json.loads(p.read_text())
        for p in (ROOT / "catalog/actions").glob("*.json")
    }
    refused = set()
    for raw in (ROOT / "evidence/runs.jsonl").read_text().splitlines():
        line = json.loads(raw)
        action = actions.get(line.get("action"))
        if (
            not action
            or not isinstance(line.get("inputs"), dict)
            or not bastter_exec.succeeded(line)
        ):
            continue
        if line["run"].startswith("mcp-") or (
            action["operation_class"] == "read"
            and bastter_exec.placeholder_ids(line["inputs"])
        ):
            continue
        if mcp_server.input_errors(action, line["inputs"]):
            refused.add(action["id"])
    assert refused == set()


def test_curation_has_no_duplicate_keys():
    """A duplicated key silently drops the first patch."""
    keys = [
        line.split(":")[0]
        for line in (ROOT / "catalog/curation.yaml").read_text().splitlines()
        if line.startswith("bastter.")
    ]
    assert len(keys) == len(set(keys))
