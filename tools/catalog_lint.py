"""Mechanical checks over the catalog. Each check targets a class of error that already happened once.

A finding with severity "error" fails the build (tools/build_catalog.py exits 1) and the tests.
Severity "gap" marks missing work and goes to catalog/lint.json only.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parent.parent
ID_FILLERS = {"a", "an", "the"}
SESSION_IDS = {"carteiraID", "usuarioID", "usuarioIDMeta"}
WEAK_ENTITY_NAMES = {
    "detail",
    "metric",
    "request",
    "group",
    "limit",
    "object",
    "message",
    "data",
    "info",
    "report",
}


@dataclass(frozen=True)
class Finding:
    check: str
    target: str
    severity: str
    message: str


def camel_words(text: str) -> list[str]:
    """Splits a method name into words: BS2OndeRetirar -> bs2 onde retirar, PSFGList -> psfg list."""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", text)]


def operation_id(action: dict) -> str | None:
    """The web service method name, the last part of the API route URL."""
    for route in action.get("routes", []):
        if route["kind"] == "undocumented_api":
            return route["url"].rsplit("/", 1)[-1]
    return None


def check_id_keeps_words(action: dict) -> list[Finding]:
    """L001: every word of the web service method name survives in the action ID."""
    op = operation_id(action)
    if not op:
        return []
    id_words = set(action["id"].split(".")[-1].split("_"))
    missing = [w for w in camel_words(op) if w not in ID_FILLERS and w not in id_words]
    if missing:
        return [
            Finding(
                "L001",
                action["id"],
                "error",
                f"ID drops {missing} from operationId {op}",
            )
        ]
    return []


def check_finder_is_callable(action: dict, actions: dict[str, dict]) -> list[Finding]:
    """L002: the action named to look up a referenced ID needs no other unknown ID."""
    out = []
    for ref in action["inputs"].get("entity_refs", []):
        finder_id = ref.get("find_with")
        if not finder_id or finder_id not in actions:
            continue
        finder = actions[finder_id]
        required = finder["inputs"]["schema"].get("required", [])
        blocking = [
            p for p in required if re.search(r"(ID|Id)$", p) and p not in SESSION_IDS
        ]
        if blocking:
            out.append(
                Finding(
                    "L002",
                    f"{action['id']}#{ref['input']}",
                    "error",
                    f"finder {finder_id} itself needs {blocking}",
                )
            )
    return out


def check_effect_needs_confirmation(action: dict) -> list[Finding]:
    """L003: anything that reaches people or the account asks first."""
    se = action["side_effects"]
    if se["external_effect"] != "none" and not se["requires_confirmation"]:
        return [
            Finding(
                "L003",
                action["id"],
                "error",
                f"{se['external_effect']} without requires_confirmation",
            )
        ]
    return []


DESTRUCTIVE_NAME = re.compile(
    r"(^|_)(delete|deletar|excluir|remover|limpar|zerar|desabilitar|disable)(_|$)"
)


def check_destructive_needs_confirmation(action: dict) -> list[Finding]:
    """L007: an action that deletes, removes, clears, zeroes or disables something asks first, whatever its class."""
    name = action["id"].split(".")[-1]
    if (
        action["operation_class"] == "read"
        or action["side_effects"]["requires_confirmation"]
    ):
        return []
    if action["operation_class"] == "delete" or DESTRUCTIVE_NAME.search(name):
        return [
            Finding(
                "L007",
                action["id"],
                "error",
                "deletes or cancels without requires_confirmation",
            )
        ]
    return []


def check_irreversible_needs_confirmation(action: dict) -> list[Finding]:
    """L008: a write that the catalog cannot undo asks first."""
    se = action["side_effects"]
    if (
        action["operation_class"] != "read"
        and not se["reversible"]
        and not se["requires_confirmation"]
    ):
        return [
            Finding(
                "L008",
                action["id"],
                "error",
                "irreversible write without requires_confirmation",
            )
        ]
    return []


def check_input_schema_is_valid(action: dict) -> list[Finding]:
    """L009: the input schema is a valid JSON Schema, so the executor can check inputs against it."""
    try:
        Draft7Validator.check_schema(action["inputs"]["schema"])
    except SchemaError as error:
        return [
            Finding(
                "L009",
                action["id"],
                "error",
                f"input schema is not valid JSON Schema: {error.message}",
            )
        ]
    return []


def check_verified_has_evidence(action: dict) -> list[Finding]:
    """L004: no 'verified' status without an evidence pointer and a date."""
    v = action["verification"]
    if v["status"] == "verified" and not (v.get("evidence") and v.get("checked_at")):
        return [
            Finding("L004", action["id"], "error", "verified without evidence or date")
        ]
    return []


def check_undo_points_to_real_action(
    action: dict, actions: dict[str, dict]
) -> list[Finding]:
    """L005: an undo or postcondition reference names an action that exists."""
    out = []
    undo = action["side_effects"].get("undo_with")
    if undo and undo not in actions:
        out.append(
            Finding("L005", action["id"], "error", f"undo_with {undo} does not exist")
        )
    post = action.get("postcondition") or {}
    if post.get("check_with") and post["check_with"] not in actions:
        out.append(
            Finding(
                "L005",
                action["id"],
                "error",
                f"postcondition check_with {post['check_with']} does not exist",
            )
        )
    return out


def check_inputs_match_capture(action: dict) -> list[Finding]:
    """L010: an observed or verified entry takes exactly the fields the app sent in the captured call."""
    captured = action["verification"].get("captured_keys")
    if (
        action["verification"]["status"] not in ("observed", "verified")
        or captured is None
    ):
        return []
    props = set(action["inputs"]["schema"].get("properties") or {})
    if props != set(captured):
        return [
            Finding(
                "L010",
                action["id"],
                "error",
                f"input fields {sorted(props)} differ from the captured call {sorted(captured)}",
            )
        ]
    return []


def check_runnable_write_has_typed_inputs(action: dict) -> list[Finding]:
    """L011: an observed or verified write lists its input fields, so an agent knows what to send."""
    schema = action["inputs"]["schema"]
    if action["operation_class"] == "read" or action["verification"]["status"] not in (
        "observed",
        "verified",
    ):
        return []
    if (
        not schema.get("properties")
        and schema.get("additionalProperties", True) is not False
    ):
        return [
            Finding(
                "L011",
                action["id"],
                "error",
                "runnable write with no input fields in its schema",
            )
        ]
    return []


DATE_LIKE = re.compile(r"^\d{2,4}[-/]\d{1,2}[-/]\d{2,4}$")


def check_date_fields_state_format(action: dict) -> list[Finding]:
    """L012: a runnable write with a date field says the date format in that field's description."""
    if action["operation_class"] == "read" or action["verification"]["status"] not in (
        "observed",
        "verified",
    ):
        return []
    out = []
    for name, prop in (action["inputs"]["schema"].get("properties") or {}).items():
        dated = []
        for example in prop.get("examples") or []:
            if isinstance(example, str) and DATE_LIKE.match(example):
                dated.append(name)
            elif isinstance(example, dict):
                dated += [
                    f"{name}.{k}"
                    for k, v in example.items()
                    if isinstance(v, str) and DATE_LIKE.match(v)
                ]
        if dated and "Date format" not in prop.get("description", ""):
            out.append(
                Finding(
                    "L012",
                    action["id"],
                    "error",
                    f"date field {min(set(dated))} has no stated format",
                )
            )
    return out


def check_verified_write_has_read_back(action: dict) -> list[Finding]:
    """L013: a verified write names the read that proves it, so run_action can hand the agent the read-back."""
    if (
        action["operation_class"] != "read"
        and action["verification"]["status"] == "verified"
        and not action.get("postcondition")
    ):
        return [
            Finding(
                "L013", action["id"], "error", "verified write with no postcondition"
            )
        ]
    return []


def check_write_has_postcondition(action: dict) -> list[Finding]:
    """G001 (gap): a write without a way to prove it took effect."""
    if action["operation_class"] != "read" and not action.get("postcondition"):
        return [Finding("G001", action["id"], "gap", "write with no postcondition")]
    return []


def check_entity_name(action: dict) -> list[Finding]:
    """G002 (gap): entity named after a URL word, not a business object."""
    if action["entity"] in WEAK_ENTITY_NAMES:
        return [
            Finding(
                "G002", action["id"], "gap", f"weak entity name '{action['entity']}'"
            )
        ]
    return []


def lint(actions: dict[str, dict]) -> list[Finding]:
    findings: list[Finding] = []
    for action in actions.values():
        findings += check_id_keeps_words(action)
        findings += check_finder_is_callable(action, actions)
        findings += check_effect_needs_confirmation(action)
        findings += check_destructive_needs_confirmation(action)
        findings += check_irreversible_needs_confirmation(action)
        findings += check_input_schema_is_valid(action)
        findings += check_verified_has_evidence(action)
        findings += check_undo_points_to_real_action(action, actions)
        findings += check_inputs_match_capture(action)
        findings += check_runnable_write_has_typed_inputs(action)
        findings += check_date_fields_state_format(action)
        findings += check_verified_write_has_read_back(action)
        findings += check_write_has_postcondition(action)
        findings += check_entity_name(action)
    return findings


def as_dicts(findings: list[Finding]) -> list[dict]:
    return [asdict(f) for f in findings]


def main() -> int:
    actions = {
        a["id"]: a
        for a in (
            json.loads(f.read_text())
            for f in sorted((ROOT / "catalog/actions").glob("*.json"))
        )
    }
    findings = lint(actions)
    for f in findings:
        if f.severity == "error":
            print(f"{f.check} {f.target}: {f.message}")
    (ROOT / "catalog/lint.json").write_text(
        json.dumps(as_dicts(findings), indent=2, ensure_ascii=False) + "\n"
    )
    errors = sum(1 for f in findings if f.severity == "error")
    gaps = sum(1 for f in findings if f.severity == "gap")
    print(f"{len(actions)} actions: {errors} errors, {gaps} gaps")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
