"""Builds catalog/actions/*.json, catalog/index.json and catalog/coverage.json.

Layers, in order:
1. catalog/generated.json: one base entry per web service method found in the BS2 scripts (status seen or excluded).
2. evidence/ui-capture-*.jsonl: calls the app made while a browser opened each screen or used a form.
   A call that answered 200 makes the action `observed`, and its body sets the input schema.
3. evidence/runs.jsonl: calls made by tools/bastter_exec.py. A read becomes `verified` when a call answered 200
   with no Error field and with no fake ID in its inputs. A write becomes `verified` when, for each scenario file
   that reads it back, the latest run that reached that read-back passed it, and `failed` when one did not.
   A read-back that could not run (no answer, expired session) counts for neither.
4. catalog/curation.yaml: hand edits, keyed by action id, merged last.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bastter_exec
import catalog_lint

GENERATED = ROOT / "catalog/generated.json"
ACTIONS = ROOT / "catalog/actions"
EVIDENCE = ROOT / "evidence"
CURATION = ROOT / "catalog/curation.yaml"
LABELS = ROOT / "catalog/labels.yaml"
DATE_FORMATS = ROOT / "catalog/date_formats.yaml"


def method_key(url: str) -> str:
    service, method = url.rstrip("/").rsplit("/", 2)[-2:]
    return f"{service.replace('.asmx', '')}.{method}"


def json_type(value) -> dict:
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        return {"type": "array"}
    if isinstance(value, dict):
        return {"type": "object"}
    return {}


def schema_from_bodies(bodies: list[dict], old: dict) -> dict:
    keys = sorted(set().union(*[set(b) for b in bodies]))
    always = set.intersection(*[set(b) for b in bodies]) if bodies else set()
    props = {}
    for k in keys:
        types = {
            json.dumps(json_type(b[k])) for b in bodies if k in b and b[k] is not None
        }
        prop = dict((old.get("properties") or {}).get(k) or {})
        prop.pop("type", None)
        if len(types) == 1:
            prop.update(json.loads(types.pop()))
            if any(k in b and b[k] is None for b in bodies):
                prop["type"] = [prop["type"], "null"]
        examples = [b[k] for b in bodies if k in b][:3]
        prop["examples"] = examples
        props[k] = prop
    return {
        "type": "object",
        "properties": props,
        "required": sorted(always),
        "additionalProperties": False,
    }


def load_jsonl(paths) -> list[dict]:
    out = []
    for p in paths:
        for line in p.read_text().splitlines():
            if line.strip():
                out.append({**json.loads(line), "_file": p.name})
    return out


def dedupe_captures(lines: list[dict]) -> list[dict]:
    """Drops repeated lines of the same flow, screen, method and body (correction C006: leftover listeners)."""
    out, seen = [], set()
    for c in lines:
        key = (c.get("flow"), c.get("screen"), c["url"], c.get("body"))
        if c.get("flow") and key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def trusted(line: dict) -> bool:
    """Lines that may change the catalog: script runs only. Calls an agent made through the MCP server never count."""
    return not str(line.get("run", "")).startswith(bastter_exec.PRIVATE_RUNS)


def retype(prop: dict, values: list) -> None:
    """Sets the field type from values that worked, when the guessed type rejects any of them."""
    kinds = sorted(
        {json_type(v)["type"] for v in values if v is not None and json_type(v)}
    )
    current = prop.get("type")
    allowed = current if isinstance(current, list) else [current] if current else []
    needed = kinds + (["null"] if any(v is None for v in values) else [])
    if current is not None and not set(needed) <= set(allowed):
        merged = sorted(set(allowed) | set(needed))
        prop["type"] = merged[0] if len(merged) == 1 else merged


def proves_read(line: dict) -> bool:
    """A logged call that makes a read verified: it worked, and it sent no fake ID."""
    return bastter_exec.succeeded(line) and not bastter_exec.placeholder_ids(
        line.get("inputs")
    )


def read_back_verdicts(
    runs: list[dict], scenarios: set[str] | None = None
) -> dict[str, dict]:
    """Status of each write from its read-backs in scenario runs.

    A run id is "<scenario>-<unix time>". Only runs of a scenario in scenarios/ count. For each scenario file
    and each read-back step of a write, only the latest run that reached that step counts, so a run that stopped
    early keeps the verdicts of the steps it never reached. Lines logged before the step name was logged share
    one key per scenario and write. A read-back with passed null could
    not run and is skipped. A write is failed if any counted read-back of it failed, else verified, with the
    newest passing run as its evidence.
    """
    scenarios = bastter_exec.scenario_names() if scenarios is None else scenarios
    checked = [
        line
        for line in runs
        if line.get("check") == "read_back"
        and line.get("passed") is not None
        and bastter_exec.scenario_of(line.get("run", "")) in scenarios
    ]
    latest: dict[tuple, int] = {}
    for line in checked:
        key = (bastter_exec.scenario_of(line["run"]), line["checks"], line.get("step"))
        latest[key] = max(latest.get(key, -1), int(line["run"].rpartition("-")[2]))
    verdicts: dict[str, dict] = {}
    for line in sorted(checked, key=lambda r: int(r["run"].rpartition("-")[2])):
        key = (bastter_exec.scenario_of(line["run"]), line["checks"], line.get("step"))
        if int(line["run"].rpartition("-")[2]) != latest[key]:
            continue
        old = verdicts.get(line["checks"])
        if old and old["status"] == "failed":
            continue
        verdicts[line["checks"]] = {
            "status": "verified" if line["passed"] else "failed",
            "route_kind": "undocumented_api",
            "checked_at": line["at"],
            "evidence": f"evidence/runs.jsonl#run={line['run']}",
            "notes": line.get("detail", ""),
        }
    return verdicts


def deep_merge(base: dict, patch: dict) -> dict:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def main() -> None:
    entries = {e["id"]: e for e in json.loads(GENERATED.read_text())}
    by_method = {
        method_key(
            next(r for r in e["routes"] if r["kind"] == "undocumented_api")["url"]
        ): e
        for e in entries.values()
    }

    captures = dedupe_captures(load_jsonl(sorted(EVIDENCE.glob("ui-capture-*.jsonl"))))
    captured: dict[str, list[dict]] = {}
    capture_file: dict[str, str] = {}
    for c in captures:
        key = method_key(c["url"])
        if key not in by_method or c.get("status") != 200 or c.get("error"):
            continue
        body = json.loads(c["body"]) if c.get("body") else {}
        captured.setdefault(key, []).append(
            {"body": body, "screen": c["screen"], "file": c["_file"]}
        )
        capture_file[key] = c["_file"]

    for key, items in captured.items():
        e = by_method[key]
        if e["verification"]["status"] == "excluded":
            continue
        bodies = [i["body"] for i in items]
        e["inputs"]["schema"] = schema_from_bodies(bodies, e["inputs"]["schema"])
        api = next(r for r in e["routes"] if r["kind"] == "undocumented_api")
        api["params"] = {k: "body" for k in e["inputs"]["schema"]["properties"]}
        api["notes"] = (
            f'ASP.NET web service. POST a JSON body with every field, the answer is {{"d": ...}}. Captured body: {json.dumps(bodies[0], ensure_ascii=False)[:300]}'
        )
        screens = sorted({i["screen"] for i in items})
        e["verification"].update(
            {
                "status": "observed",
                "route_kind": "undocumented_api",
                "evidence": f"evidence/{capture_file[key]}",
                "notes": f"The app made this call on {', '.join(screens[:4])} and it answered 200.",
                "captured_keys": sorted(e["inputs"]["schema"]["properties"]),
            }
        )
        e["sources"].append(
            {"kind": "network_capture", "ref": f"evidence/{capture_file[key]}"}
        )

    runs = (
        load_jsonl([EVIDENCE / "runs.jsonl"])
        if (EVIDENCE / "runs.jsonl").exists()
        else []
    )
    for target_id, verdict in read_back_verdicts(runs).items():
        target = entries.get(target_id)
        if (
            target
            and target["operation_class"] != "read"
            and target["verification"]["status"] != "excluded"
        ):
            target["verification"].update(verdict)
    runs = [line for line in runs if trusted(line)]
    for line in runs:
        e = entries.get(line.get("action"))
        if (
            not e
            or e["verification"]["status"] == "excluded"
            or line.get("check") == "read_back"
        ):
            continue
        if (
            e["operation_class"] == "read"
            and e["verification"]["status"] != "verified"
            and proves_read(line)
        ):
            e["verification"].update(
                {
                    "status": "verified",
                    "route_kind": "undocumented_api",
                    "checked_at": line["at"],
                    "evidence": f"evidence/runs.jsonl#run={line['run']}",
                    "notes": "A script call with the inputs in this entry answered 200 with no Error.",
                }
            )

    ran_bodies: dict[str, list[dict]] = {}
    for line in runs:
        e = entries.get(line.get("action"))
        is_read = bool(e) and e["operation_class"] == "read"
        if (
            bastter_exec.succeeded(line)
            and isinstance(line.get("inputs"), dict)
            and not (is_read and bastter_exec.placeholder_ids(line["inputs"]))
        ):
            ran_bodies.setdefault(line["action"], []).append(line["inputs"])
    for aid, bodies in ran_bodies.items():
        e = entries.get(aid)
        if not e:
            continue
        if e["inputs"]["schema"].get("properties"):
            for name, prop in e["inputs"]["schema"]["properties"].items():
                values = [b[name] for b in bodies if name in b]
                if values:
                    retype(prop, values)
                    prop.setdefault("examples", values[:3])
            continue
        e["inputs"]["schema"] = schema_from_bodies(bodies, e["inputs"]["schema"])
        api = next(r for r in e["routes"] if r["kind"] == "undocumented_api")
        api["params"] = {k: "body" for k in e["inputs"]["schema"]["properties"]}
        e["sources"].append(
            {
                "kind": "network_capture",
                "ref": "evidence/runs.jsonl (bodies of successful scenario calls)",
            }
        )

    scenario_files = sorted((ROOT / "scenarios").glob("*.yaml")) + sorted(
        (ROOT / "scenarios/archive").glob("*.yaml")
    )
    for path in scenario_files:
        for step in yaml.safe_load(path.read_text())["steps"]:
            target = entries.get(step.get("postcondition_of"))
            if (
                target
                and step["action"] in entries
                and not (target.get("postcondition") or {}).get("from_scenario")
            ):
                target["postcondition"] = {
                    "check_with": step["action"],
                    "assert": step.get("proves")
                    or f"the read shows the change (see {path.relative_to(ROOT)}, step {step['name']})",
                    "from_scenario": f"{path.relative_to(ROOT)}#{step['name']}",
                }

    if DATE_FORMATS.exists():
        for aid, fields in (yaml.safe_load(DATE_FORMATS.read_text()) or {}).items():
            props = (
                entries[aid]["inputs"]["schema"].get("properties") or {}
                if aid in entries
                else {}
            )
            for path, spec in fields.items():
                top, _, inner = path.partition(".")
                if top not in props:
                    continue
                note = (
                    f"Date format{' of ' + inner if inner else ''}: {spec['format']}."
                )
                if spec.get("confirmed") is False:
                    note += " Not confirmed by a read-back of the date."
                old_desc = props[top].get("description", "")
                if note not in old_desc:
                    props[top]["description"] = f"{old_desc} {note}".strip()

    if LABELS.exists():
        for aid, lab in (yaml.safe_load(LABELS.read_text()) or {}).items():
            if aid not in entries:
                continue
            entries[aid]["label"] = lab["label"]
            if lab.get("intent_examples"):
                entries[aid]["intent_examples"] = lab["intent_examples"]
            if lab.get("uncertain"):
                entries[aid]["description"] += (
                    " The label is a literal reading of the method name; the evidence does not show the effect."
                )

    if CURATION.exists():
        for aid, patch in (yaml.safe_load(CURATION.read_text()) or {}).items():
            if aid in entries:
                timeout = patch.pop("route_timeout_s", None)
                if timeout:
                    next(
                        r
                        for r in entries[aid]["routes"]
                        if r["kind"] == "undocumented_api"
                    )["timeout_s"] = timeout
                deep_merge(entries[aid], patch)

    ACTIONS.mkdir(parents=True, exist_ok=True)
    for aid, e in sorted(entries.items()):
        e["verification"].setdefault("checked_at", None)
        target = ACTIONS / f"{aid}.json"
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(e, indent=2, ensure_ascii=False) + "\n")
        tmp.replace(target)
    for old in ACTIONS.glob("*.json"):
        if old.stem not in entries:
            old.unlink()
    index = [
        {
            "id": e["id"],
            "label": e["label"],
            "area": e["area"],
            "entity": e["entity"],
            "operation_class": e["operation_class"],
            "verification": e["verification"]["status"],
            "availability": e["availability"]["status"],
            "requires_confirmation": e["side_effects"]["requires_confirmation"],
        }
        for e in sorted(entries.values(), key=lambda x: x["id"])
    ]
    (ROOT / "catalog/index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    )

    by_status, by_area = {}, {}
    for e in entries.values():
        s = e["verification"]["status"]
        by_status[s] = by_status.get(s, 0) + 1
        by_area.setdefault(e["area"], {}).setdefault(s, 0)
        by_area[e["area"]][s] += 1
    screens = json.loads((ROOT / "sources/discover/pages.json").read_text())
    coverage = {
        "actions": len(entries),
        "by_status": dict(sorted(by_status.items())),
        "by_area": dict(sorted(by_area.items())),
        "screens_walked": len(screens),
        "screens_with_captured_calls": len({c["screen"] for c in captures}),
        "captured_calls": len(captures),
    }
    (ROOT / "catalog/coverage.json").write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(coverage["by_status"]))
    code = catalog_lint.main()
    import make_claims

    make_claims.main()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
