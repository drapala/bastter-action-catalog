"""Executor for Bastter System actions: calls the web service behind an action and logs the call.

Every call adds one line to a log. The line keeps the inputs, the HTTP status, the error message and the
SHAPE of the answer (types, keys, list sizes). It never keeps the values of the answer, because the answers
hold the user's financial data. Script runs log to evidence/runs.jsonl (tracked). Runs of the MCP server
(mcp-*), the demo (demo-*) and the market data tool (market-*) log to logs/mcp-runs.jsonl (not tracked),
because they touch real records. The inputs are logged as sent: a restore step sends an old setting it read before,
so that setting is in the log.

CLI:
  .venv/bin/python tools/bastter_exec.py call <action_id> '<json inputs>'
  .venv/bin/python tools/bastter_exec.py replay-observed
  .venv/bin/python tools/bastter_exec.py scenario scenarios/<name>.yaml
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import httpx
import session

EVIDENCE = ROOT / "evidence/runs.jsonl"
PRIVATE_LOG = ROOT / "logs/mcp-runs.jsonl"
PRIVATE_RUNS = ("mcp-", "demo-", "market-")
ACTIONS = ROOT / "catalog/actions"
GENERATED = ROOT / "catalog/generated.json"
MISSING_RE = re.compile(r"missing value for parameter: '([^']+)'", re.IGNORECASE)


class SessionExpired(RuntimeError):
    pass


def load_catalog() -> dict[str, dict]:
    if ACTIONS.exists() and any(ACTIONS.glob("*.json")):
        return {
            json.loads(p.read_text())["id"]: json.loads(p.read_text())
            for p in ACTIONS.glob("*.json")
        }
    return {e["id"]: e for e in json.loads(GENERATED.read_text())}


def api_route(action: dict) -> dict | None:
    return next((r for r in action["routes"] if r["kind"] == "undocumented_api"), None)


SESSION_IDS = {"carteiraID", "usuarioID", "usuarioIDMeta", "carteirasID"}


def succeeded(line: dict) -> bool:
    """A logged call worked: HTTP 200, no error, and no Error field in the answer.

    Lines logged before the executor checked the answer for Error can say ok true with an Error-shaped answer.
    """
    shape_ = line.get("shape")
    error_shaped = (
        isinstance(shape_, dict) and "Error" in shape_ and shape_["Error"] != "null"
    )
    return bool(line.get("ok")) and not error_shaped


def scenario_names() -> set[str]:
    """Names of every scenario file, including the archived ones that no longer run."""
    import yaml

    files = list((ROOT / "scenarios").glob("*.yaml")) + list(
        (ROOT / "scenarios/archive").glob("*.yaml")
    )
    return {yaml.safe_load(p.read_text())["name"] for p in files}


def scenario_of(run: str) -> str | None:
    """The scenario name of a scenario run id ("<name>-<unix time>"), or None for any other run."""
    name, _, stamp = run.rpartition("-")
    return name if stamp.isdigit() else None


def placeholder_ids(inputs: dict) -> list[str]:
    """ID inputs (other than the session's own IDs) sent with an empty value: 0, "", [] or null."""
    if not isinstance(inputs, dict):
        return []
    return [
        k
        for k, v in inputs.items()
        if re.search(r"(ID|Id)s?$", k)
        and k not in SESSION_IDS
        and v in (0, "", None, [])
    ]


def shape(value, depth: int = 0):
    """Types, keys and sizes of a value, without the values themselves."""
    if isinstance(value, dict):
        if depth >= 2:
            return f"object({len(value)} keys)"
        return {k: shape(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return (
            [f"list({len(value)})", shape(value[0], depth + 1)] if value else "list(0)"
        )
    if value is None:
        return "null"
    return type(value).__name__


def decode(body: str):
    data = json.loads(body)
    d = data.get("d", data) if isinstance(data, dict) else data
    if isinstance(d, str) and d[:1] in "[{":
        try:
            return json.loads(d)
        except json.JSONDecodeError:
            return d
    return d


def log(line: dict) -> None:
    """Appends one line to the evidence log. Calls made through the MCP server go to a private, untracked log,
    because they carry the user's real trades and amounts."""
    path = (
        PRIVATE_LOG if str(line.get("run", "")).startswith(PRIVATE_RUNS) else EVIDENCE
    )
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def raw_call(
    http, url: str, inputs: dict, timeout: float | None = None
) -> tuple[int, object, str | None]:
    extra = {"timeout": timeout} if timeout else {}
    r = http.post(
        url.replace(session.BASE_URL, ""),
        json=inputs,
        headers={"Content-Type": "application/json; charset=utf-8"},
        **extra,
    )
    time.sleep(0.3)
    if r.status_code in (301, 302, 401):
        raise SessionExpired(f"{r.status_code} {r.headers.get('location', '')}")
    if "text/html" in r.headers.get("content-type", ""):
        return (
            r.status_code,
            None,
            f"HTML answer with status {r.status_code} (a server error page, not the web service)",
        )
    try:
        payload = decode(r.text)
    except (json.JSONDecodeError, ValueError):
        ctype = r.headers.get("content-type", "none")
        return (
            r.status_code,
            None,
            f"non-JSON answer ({len(r.text)} characters, content type {ctype})",
        )
    if r.status_code >= 400:
        msg = (
            payload.get("Message")
            if isinstance(payload, dict)
            else f"a {shape(payload)} answer"
        )
        exc = payload.get("ExceptionType") if isinstance(payload, dict) else None
        return r.status_code, payload, f"{exc}: {msg}" if exc else msg
    return r.status_code, payload, None


def call(
    action_id: str,
    inputs: dict,
    run: str,
    http=None,
    catalog: dict | None = None,
    note: str = "",
) -> dict:
    catalog = catalog or load_catalog()
    action = catalog[action_id]
    route = api_route(action)
    http = http or session.client()
    try:
        status, payload, error = raw_call(
            http, route["url"], inputs, timeout=route.get("timeout_s")
        )
    except SessionExpired as exc:
        log(
            {
                "run": run,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "action": action_id,
                "method": route["url"].rsplit("/", 2)[-2:],
                "inputs": inputs,
                "status": None,
                "ok": False,
                "error": f"session expired: {exc}",
                "shape": None,
            }
        )
        raise
    except httpx.RequestError as exc:
        log(
            {
                "run": run,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "action": action_id,
                "method": route["url"].rsplit("/", 2)[-2:],
                "inputs": inputs,
                "status": None,
                "ok": False,
                "error": f"no answer: {exc!r}. A write may have run on the server.",
                "shape": None,
                **({"note": note} if note else {}),
            }
        )
        raise
    if error is None and isinstance(payload, dict) and payload.get("Error"):
        error = f"the answer has Error: {payload['Error']}"
    line = {
        "run": run,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "action": action_id,
        "method": route["url"].rsplit("/", 2)[-2:],
        "inputs": inputs,
        "status": status,
        "ok": status == 200 and error is None,
        "error": error,
        "shape": shape(payload) if error is None else None,
    }
    if note:
        line["note"] = note
    log(line)
    return {**line, "payload": payload}


def main() -> None:
    if sys.argv[1:2] == ["replay-observed"]:
        return replay_observed_reads()
    if sys.argv[1:2] == ["scenario"]:
        raise SystemExit(scenario(sys.argv[2]))
    if len(sys.argv) < 3 or sys.argv[1] != "call":
        sys.exit(__doc__)
    inputs = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    out = call(sys.argv[2], inputs, run=f"cli-{int(time.time())}")
    print(
        json.dumps(
            {k: v for k, v in out.items() if k != "payload"},
            indent=2,
            ensure_ascii=False,
        )
    )


FIXTURE_PREFIX = "ZZTESTE"


def render(value, ctx: dict):
    """Fills ${a.b.0.c} references from earlier steps. A string that is only a reference keeps the value's type."""

    def get(path: str):
        cur = ctx
        for part in path.split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        return cur

    if isinstance(value, str):
        full = re.fullmatch(r"\$\{([^}]+)\}", value)
        if full:
            return get(full.group(1))
        return re.sub(r"\$\{([^}]+)\}", lambda m: str(get(m.group(1))), value)
    if isinstance(value, dict):
        return {k: render(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    return value


ABSENT = object()
REF_RE = re.compile(r"\$\{([^}.]+)[^}]*\}")


def lookup(payload, path: str, default=None):
    """The value at a dotted path. A path that does not exist gives `default`, so ABSENT tells it from a null."""
    cur = payload
    for part in path.split(".") if path else []:
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def refs(value) -> set[str]:
    """Names of the ${name...} references in a step's raw inputs."""
    return set(REF_RE.findall(json.dumps(value, default=str)))


def find_item(items, where: dict):
    if not isinstance(items, list):
        return None
    return next(
        (
            i
            for i in items
            if isinstance(i, dict) and all(i.get(k) == v for k, v in where.items())
        ),
        None,
    )


def check(assertion: dict, out: dict, ctx: dict) -> tuple[bool, str]:
    if not out["ok"]:
        return False, f"call failed: {out['status']} {out['error']}"
    payload = out["payload"]
    if isinstance(payload, dict) and payload.get("Error"):
        return False, f"the answer has Error: {payload['Error']}"
    for path, expected in (assertion.get("equals") or {}).items():
        got, want = lookup(payload, path, ABSENT), render(expected, ctx)
        if got is ABSENT:
            return False, f"{path} is missing from the answer"
        if got != want:
            return (
                False,
                f"{path} is a {shape(got)}, not the expected {shape(want)} value",
            )
    contains = assertion.get("list_contains")
    if contains:
        where = render(contains["where"], ctx)
        if not find_item(lookup(payload, contains["path"]), where):
            return (
                False,
                f"no item in {contains['path'] or 'the answer'} matches {sorted(where)}",
            )
    excludes = assertion.get("list_excludes")
    if excludes:
        items = lookup(payload, excludes["path"])
        where = render(excludes["where"], ctx)
        empty_refs = [
            k for k, v in excludes["where"].items() if refs(v) and where[k] is None
        ]
        if empty_refs:
            return (
                False,
                f"nothing to check: {empty_refs} came from a reference with no value",
            )
        if not isinstance(items, list):
            return False, f"{excludes['path']} is not a list"
        if find_item(items, where):
            return (
                False,
                f"{excludes['path'] or 'the answer'} still has an item that matches {sorted(where)}",
            )
    for path in assertion.get("present") or []:
        if lookup(payload, path) in (None, "", 0):
            return False, f"{path} is missing or empty"
    for path in assertion.get("empty") or []:
        value = lookup(payload, path, ABSENT)
        if value is ABSENT or value not in (None, []):
            return (
                False,
                f"{path} is not an empty list: {shape(value) if value is not ABSENT else 'missing'}",
            )
    return True, "ok"


def undo_blocker(
    step: dict,
    reached: set[str],
    saved: dict,
    catalog: dict,
    guards_before: list[str] = (),
) -> str | None:
    """Why the cleanup after a failure must not run this step, or None when it may.

    No step runs past a guard that has not run: a record the guard would check may belong to the user.
    A step with `undoes: <write step>` may run when that write step was reached in this run. A delete step with
    no `undoes` may run only when its inputs use at least one value this run saved and every saved value it
    uses is set. Any other step never runs in a cleanup.
    """
    unchecked = [name for name in guards_before if name not in reached]
    if unchecked:
        return f"guard {unchecked[0]} did not run"
    target = step.get("undoes")
    if target:
        return None if target in reached else f"{target} was not reached in this run"
    if catalog.get(step["action"], {}).get("operation_class") != "delete":
        return "it is not a delete and names no undoes"
    used = refs(step.get("inputs") or {}) & set(saved)
    if not used:
        return "it uses no value this run saved"
    empty = sorted(name for name in used if saved[name] is None)
    return f"saved values {empty} are empty" if empty else None


def adds_existing_ticker(step: dict) -> bool:
    """A salvar that adds an asset by ticker. It returns the user's item when the user already has that ticker."""
    inputs = step.get("inputs") or {}
    return (
        step["action"] == "bastter.ativos.salvar"
        and isinstance(inputs, dict)
        and inputs.get("ativoID") == 0
        and "${prefix}" not in str(inputs.get("descricao", ""))
    )


def scenario_problems(spec: dict, catalog: dict) -> list[str]:
    """Breaks of the cleanup rules in a scenario file: what undo_blocker relies on.

    A salvar that adds an asset by ticker needs a guard right before it (the tab does not hold the ticker) and a
    guard right after it (the returned item has no movements), so no other step can touch the item first.
    """
    problems, names, saves = [], [], set()
    steps = spec["steps"]
    for i, step in enumerate(steps):
        if adds_existing_ticker(step):
            before = steps[i - 1] if i else {}
            after = steps[i + 1] if i + 1 < len(steps) else {}
            if not before.get("guard") or not after.get("guard"):
                problems.append(
                    f"{step['name']}: adding a ticker needs a guard right before and right after it"
                )
        kind = catalog.get(step["action"], {}).get("operation_class")
        if step.get("undoes") and step["undoes"] not in names:
            problems.append(
                f"{step['name']}: undoes {step['undoes']}, which is not an earlier step"
            )
        if step.get("guard") and kind != "read":
            problems.append(f"{step['name']}: a guard must be a read")
        if step.get("guard") and step.get("stop_on_fail") is False:
            problems.append(f"{step['name']}: a guard must stop the run")
        if (
            kind == "delete"
            and not step.get("undoes")
            and not refs(step.get("inputs") or {}) & saves
        ):
            problems.append(f"{step['name']}: a delete with no saved ID needs undoes")
        saves |= set(step.get("save") or {})
        names.append(step["name"])
    return problems


def save_values(step: dict, payload, ctx: dict) -> tuple[dict, str | None]:
    """The values a step saves, and an error when one is missing (or null without `nullable: true`)."""
    values, error = {}, None
    for name, rule in (step.get("save") or {}).items():
        rule = rule if isinstance(rule, dict) else {"path": rule}
        value = lookup(payload, render(rule["path"], ctx), ABSENT)
        if "where" in rule:
            item = (
                find_item(value, render(rule["where"], ctx))
                if value is not ABSENT
                else None
            )
            value = lookup(item, rule["field"], ABSENT) if item is not None else ABSENT
        if value is ABSENT or (value is None and not rule.get("nullable")):
            error = error or f"could not save {name}: nothing at {rule['path']}"
            value = None
        values[name] = value
    return values, error


def scenario(file: str) -> int:
    """Runs a scenario: each write is followed by a read-back step that names it in postcondition_of.

    When a step fails and the run stops:
    - a failed `guard: true` step means the account holds real data the scenario must not touch, so nothing
      else runs;
    - otherwise only the later steps that undo_blocker allows run, so the run undoes its own writes and
      never deletes a record it did not create.
    Every skipped undo and the values the run saved are printed for a manual check. A file that breaks the
    cleanup rules (scenario_problems) does not run at all.
    """
    import session as _session
    import yaml

    spec = yaml.safe_load(Path(file).read_text())
    problems = scenario_problems(spec, load_catalog())
    if problems:
        for problem in problems:
            print(f"RULE {problem}")
        print(f"{file} breaks the cleanup rules and did not run")
        return len(problems)
    run = f"{spec['name']}-{int(time.time())}"
    ctx: dict = {"run": run, "prefix": FIXTURE_PREFIX, "ts": str(int(time.time()))[-6:]}
    ctx.update(spec.get("vars") or {})
    catalog = load_catalog()
    http = _session.client()
    saved: dict = {}
    reached: set[str] = set()

    def run_step(step: dict) -> tuple[bool | None, str]:
        """True or False for a step that ran, None for a step that could not run (the write may have run)."""
        reached.add(step["name"])
        try:
            inputs = render(step.get("inputs") or {}, ctx)
            retry = step.get("retry") or {}
            for attempt in range(1, 2 + int(retry.get("times", 0))):
                out = call(
                    step["action"],
                    inputs,
                    run=run,
                    http=http,
                    catalog=catalog,
                    note=step["name"],
                )
                ok, why = check(step.get("assert") or {}, out, ctx)
                if ok or attempt > int(retry.get("times", 0)):
                    break
                time.sleep(float(retry.get("every", 2)))
        except (
            KeyError,
            IndexError,
            TypeError,
            httpx.RequestError,
            SessionExpired,
        ) as exc:
            why = f"step could not run: {exc!r}"
            if not isinstance(exc, (httpx.RequestError, SessionExpired)):
                log(
                    {
                        "run": run,
                        "at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "action": step["action"],
                        "inputs": None,
                        "status": None,
                        "ok": False,
                        "error": why,
                        "shape": None,
                        "note": step["name"],
                    }
                )
            return None, why
        ctx[step["name"]] = {"status": out["status"], "response": out["payload"]}
        values, error = save_values(step, out["payload"], ctx)
        ctx.update(values)
        saved.update(values)
        if error and ok:
            ok, why = False, error
        return ok, why

    failures = 0
    steps = spec["steps"]
    for i, step in enumerate(steps):
        ok, why = run_step(step)
        if step.get("postcondition_of"):
            log(
                {
                    "run": run,
                    "at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "action": step["action"],
                    "check": "read_back",
                    "checks": step["postcondition_of"],
                    "step": step["name"],
                    "passed": ok,
                    "detail": (step.get("proves") or "ok") if ok else why,
                }
            )
        elif not ok and (step.get("assert") or step.get("guard")):
            log(
                {
                    "run": run,
                    "at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "action": step["action"],
                    "check": "guard" if step.get("guard") else "assert",
                    "step": step["name"],
                    "passed": ok,
                    "detail": why,
                }
            )
        print(
            f"{'PASS' if ok else 'FAIL'} {step['name']:32} {step['action']} {'' if ok else why}"
        )
        if ok:
            time.sleep(step.get("wait", 0.4))
            continue
        failures += 1
        if not step.get("stop_on_fail", True) and not step.get("guard"):
            continue
        if step.get("guard"):
            print(
                f"GUARD {step['name']} failed: no cleanup runs. Steps this run reached: {sorted(reached)}"
            )
        else:
            blocked: set[str] = set()
            for j, later in enumerate(steps[i + 1 :], start=i + 1):
                guards_before = [s["name"] for s in steps[:j] if s.get("guard")]
                blocker = undo_blocker(later, reached, saved, catalog, guards_before)
                shared = refs(later.get("inputs") or {}) & blocked
                if not blocker and shared:
                    blocker = f"an earlier cleanup step on {sorted(shared)} was skipped"
                is_undo = (
                    later.get("undoes")
                    or catalog.get(later["action"], {}).get("operation_class")
                    == "delete"
                )
                if blocker and is_undo:
                    blocked |= {
                        n
                        for n in refs(later.get("inputs") or {})
                        if saved.get(n) is not None
                    }
                if blocker:
                    print(
                        f"CLEANUP skipped {later['name']:24} {later['action']}: {blocker}"
                    )
                    continue
                done, reason = run_step(later)
                print(
                    f"CLEANUP {'done' if done else 'FAILED'} {later['name']:24} {later['action']} {'' if done else reason}"
                )
        print(
            f"saved values of this run (check the account for them): {json.dumps(saved, ensure_ascii=False, default=str)}"
        )
        break
    print(f"run {run}: {failures} failures")
    return failures


def replay_observed_reads() -> None:
    """Calls every observed read once from this script, with the body the app sent, so its status can become verified."""
    import session as _session

    http = _session.client()
    catalog = load_catalog()
    run = f"replay-reads-{int(time.time())}"
    ok = bad = 0
    for aid, action in sorted(catalog.items()):
        v = action["verification"]
        if action["operation_class"] != "read" or v["status"] != "observed":
            continue
        body = {
            k: p["examples"][0]
            for k, p in action["inputs"]["schema"]["properties"].items()
            if p.get("examples")
        }
        out = call(aid, body, run=run, http=http, catalog=catalog)
        ok, bad = ok + out["ok"], bad + (not out["ok"])
        if not out["ok"]:
            print("ERR", aid, out["status"], out["error"])
    print(f"run {run}: {ok} ok, {bad} errors")


if __name__ == "__main__":
    main()
