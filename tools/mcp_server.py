"""MCP server that lets an AI agent use the catalog to operate the Bastter System (BS2).

The agent finds an action, reads its entry, runs it, and checks the effect. Two more tools give public market
data that BS2 does not have, when tools/market.py is present: index members from B3 (small caps) and total
returns from Yahoo Finance. The server applies the
catalog's rules on every call:
  - inputs that break the entry's input schema do not run;
  - an action that needs confirmation runs only with confirmed=true;
  - a seen, gated or excluded action does not run, and the reply says why;
  - an action that publishes or notifies other people never runs, even when confirmed;
  - inputs with two keys that differ only in case do not run;
  - every refused call is logged to the private log (logs/mcp-runs.jsonl);
  - a run returns the read-back to do before reporting success, when the entry has one;
  - a write that got no answer, or an answer other than 200 or Bastter's own refusal, is reported as
    unknown, with the check to do before a retry.
confirmed=true is the agent's statement that the user agreed. The server cannot check it, so the MCP
client's approval prompt for each tool call is where a person checks it.

Run: .venv/bin/python tools/mcp_server.py   (stdio)
The session cookies come from the macOS keychain (service bastter-session), as in session.py.
BASTTER_RUN_LABEL=demo makes the run id mcp-demo-<time>, so the demo cleanup can tell the demo's calls apart.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import bastter_exec
import httpx
import session
from fastmcp import FastMCP
from jsonschema import Draft7Validator

try:
    import market
except ImportError:
    market = None

ROOT = Path(__file__).resolve().parent.parent
ACTIONS = ROOT / "catalog/actions"
INDEX = ROOT / "catalog/index.json"
RUN_LABEL = re.sub(r"[^a-z0-9]", "", os.environ.get("BASTTER_RUN_LABEL", "").lower())
RUN = f"mcp-{RUN_LABEL + '-' if RUN_LABEL else ''}{int(time.time())}"
RUNNABLE = {"verified", "observed", "failed"}
NEVER_RUN = {"publishes", "notifies_people"}

mcp = FastMCP("bastter-catalog")


ACTION_ID = re.compile(r"^bastter\.[a-z0-9_]+\.[a-z0-9_]+$")


def load(action_id: str) -> dict | None:
    if not ACTION_ID.match(action_id or ""):
        return None
    path = ACTIONS / f"{action_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


# Words a user says, mapped to the words in action ids and labels.
SYNONYMS = {
    "compra": "movimentacao",
    "comprei": "movimentacao",
    "venda": "movimentacao",
    "vendi": "movimentacao",
    "operacao": "movimentacao",
    "lancamento": "movimentacao",
    "dividendo": "provento",
    "dividendos": "provento",
    "jcp": "provento",
    "rendimento": "provento",
    "apaga": "excluir",
    "apagar": "excluir",
    "remove": "excluir",
    "remover": "excluir",
    "deleta": "excluir",
    "cria": "criar",
    "adiciona": "salvar",
    "adicionar": "salvar",
    "registra": "salvar",
    "registrar": "salvar",
    "lanca": "salvar",
    "lancar": "salvar",
    "edita": "salvar",
    "altera": "salvar",
    "renomeia": "alterar",
    "mostra": "listar",
    "lista": "listar",
    "quais": "listar",
    "quanto": "obter",
    "ver": "listar",
    "despesa": "financa",
    "gasto": "financa",
    "receita": "financa",
    "imposto": "ir",
    "darf": "darf",
    "acoes": "acao",
    "fiis": "fii",
}
STOPWORDS = {
    "the",
    "and",
    "uma",
    "um",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "na",
    "no",
    "em",
    "pra",
    "para",
    "com",
    "que",
    "meu",
    "minha",
    "meus",
    "minhas",
    "por",
}


def strip_accents(text: str) -> str:
    table = str.maketrans("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ", "aaaaeeiooouc" + "AAAAEEIOOOUC")
    return text.translate(table)


def words(text: str) -> set[str]:
    out = set()
    for w in re.findall(
        r"[a-z0-9]+", strip_accents(re.sub(r"([a-z])([A-Z])", r"\1 \2", text)).lower()
    ):
        if len(w) <= 2 or w in STOPWORDS:
            continue
        out |= {w, SYNONYMS.get(w, w)}
        if w.endswith("s") and len(w) > 4:
            out.add(w[:-1])
    return out


def ui_paths(action: dict) -> list[dict]:
    return [
        {k: v for k, v in r.items() if k != "kind"}
        for r in action["routes"]
        if r["kind"] == "ui_path"
    ]


@mcp.tool
def find_actions(request: str, limit: int = 8) -> list[dict]:
    """Find catalog actions for a user's request (Portuguese or English), best match first.

    Each result has the id, label, area, verification status and the confirmation flag.
    Read the full entry with get_action before you run it.
    """
    wanted = words(request)
    scored = []
    for entry in json.loads(INDEX.read_text()):
        if entry["verification"] == "excluded":
            continue
        action = load(entry["id"]) or {}
        name = " ".join(
            [
                entry["id"].replace("_", " "),
                entry["label"],
                entry["entity"].replace("_", " "),
            ]
        )
        about = " ".join(
            [entry["area"], action.get("description", "")]
            + action.get("intent_examples", [])
        )
        score = 2 * len(wanted & words(name)) + len(wanted & words(about))
        if score:
            trust = {"verified": 3, "observed": 2, "failed": 1}.get(
                entry["verification"], 0
            )
            scored.append((score, trust, entry))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return [entry for *_, entry in scored[:limit]]


@mcp.tool
def get_action(action_id: str) -> dict:
    """Return the full catalog entry: inputs, where each ID comes from, routes, read-back, side effects, status."""
    action = load(action_id)
    if action is None:
        return {"error": f"unknown action {action_id}. Use find_actions."}
    return action


def case_duplicates(value, path: str = "inputs") -> list[str]:
    """Keys of one object that differ only in case. ASP.NET may read them as one key, and the last one wins."""
    found = []
    if isinstance(value, dict):
        groups: dict[str, list[str]] = {}
        for key in value:
            groups.setdefault(str(key).lower(), []).append(key)
        found += [
            f"{path}: keys {keys} differ only in case"
            for keys in groups.values()
            if len(keys) > 1
        ]
        for key, item in value.items():
            found += case_duplicates(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += case_duplicates(item, f"{path}.{i}")
    return found


def input_errors(action: dict, inputs: dict) -> list[str]:
    """Keys that differ only in case, inputs the action does not take, then every place the inputs break its schema."""
    duplicates = case_duplicates(inputs)
    if duplicates:
        return duplicates
    schema = action["inputs"]["schema"]
    props = schema.get("properties")
    if props is not None and schema.get("additionalProperties") is False:
        unknown = sorted(set(inputs) - set(props))
        if unknown:
            return [f"unknown inputs {unknown}. This action takes {sorted(props)}"]
    return [
        f"{'.'.join(map(str, e.absolute_path)) or 'inputs'}: {e.message}"
        for e in Draft7Validator(schema).iter_errors(inputs)
    ]


def refuse(action_id: str, inputs: dict, reason: str, **extra) -> dict:
    """The reply for a call the server does not send. The attempt goes to the private log."""
    bastter_exec.log(
        {
            "run": RUN,
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "action": action_id,
            "inputs": inputs,
            "status": None,
            "ok": False,
            "error": f"not sent: {reason}",
            "shape": None,
        }
    )
    return {"ran": False, "reason": reason, **extra}


def check_before_retry(action: dict) -> str:
    check = action.get("postcondition") or {}
    if check:
        return f"Before any retry, run {check['check_with']} and check: {check['assert']}. If it is already there, the action ran."
    return "Before any retry, look the item up and check whether the action already took effect."


@mcp.tool
def run_action(action_id: str, inputs: dict, confirmed: bool = False) -> dict:
    """Run a catalog action through the web service the Bastter app itself calls.

    Set confirmed=true only after the user agreed to this exact call. The reply holds the HTTP status,
    the answer, and, when the entry has one, the read-back to run before you report success.
    """
    action = load(action_id)
    if action is None:
        return refuse(
            action_id, inputs, f"unknown action {action_id}. Use find_actions."
        )
    status = action["verification"]["status"]
    if status not in RUNNABLE:
        return refuse(
            action_id,
            inputs,
            f"status is {status}: {action['verification'].get('notes')}",
            ui_paths=ui_paths(action),
        )
    effect = action["side_effects"].get("external_effect")
    if effect in NEVER_RUN:
        return refuse(
            action_id,
            inputs,
            f"this action {effect.replace('_', ' ')}: other users can see it. The user must do it in the app.",
            ui_paths=ui_paths(action),
        )
    errors = input_errors(action, inputs)
    if errors:
        return refuse(
            action_id,
            inputs,
            "the inputs do not match the catalog entry",
            errors=errors,
        )
    if action["side_effects"]["requires_confirmation"] and not confirmed:
        return refuse(
            action_id,
            inputs,
            "this action needs the user's confirmation. Ask the user, then call again with confirmed=true.",
            side_effects=action["side_effects"],
        )
    try:
        with session.client() as http:
            out = bastter_exec.call(
                action_id, inputs, run=RUN, http=http, catalog={action_id: action}
            )
    except bastter_exec.SessionExpired:
        return {
            "ran": False,
            "reason": "the Bastter session expired. The user must log in again and store the cookies (see README).",
        }
    except RuntimeError as error:
        return {"ran": False, "reason": str(error)}
    except (httpx.ConnectError, httpx.ConnectTimeout) as error:
        return {"ran": False, "reason": f"the request did not reach Bastter: {error!r}"}
    except httpx.RequestError as error:
        if action["operation_class"] == "read":
            return {
                "ran": False,
                "reason": f"no answer from Bastter: {error!r}. A read is safe to retry.",
            }
        return {
            "ran": "unknown",
            "reason": f"the request was sent but no usable answer came back: {error!r}. The action may have run.",
            "next_step": check_before_retry(action),
        }
    refused_by_bastter = "answer has Error" in (out["error"] or "")
    if not out["ok"] and action["operation_class"] != "read" and not refused_by_bastter:
        return {
            "ran": "unknown",
            "reason": f"the server answered {out['status']} ({out['error']}), not a result. The write may have run.",
            "next_step": check_before_retry(action),
        }
    if not out["ok"]:
        return {
            "ran": True,
            "http_status": out["status"],
            "error": out["error"],
            "catalog_status": status,
            "note": "Bastter refused the request. The error holds its message."
            if refused_by_bastter
            else "The server hides error details. Check the inputs against the entry and the ui_paths.",
        }
    reply = {
        "ran": True,
        "http_status": out["status"],
        "response": out["payload"],
        "catalog_status": status,
    }
    if status == "failed":
        reply["warning"] = action["verification"].get("notes")
    if action.get("postcondition"):
        reply["next_step"] = (
            f"Before you report success, run {action['postcondition']['check_with']} and confirm: {action['postcondition']['assert']}"
        )
    return reply


if market is not None:

    @mcp.tool
    def market_index_members(index: str = "SMLL") -> dict:
        """Today's members of a B3 index, from B3. SMLL is the Small Cap index: a stock in it is a small cap.

        Other indexes: IBOV, IBRA, IDIV, SMLL, MLCX. The Bastter System has no small cap mark, so cross the
        tickers of the user's items (run_action bastter.ativos.obter_itens) with this list.
        """
        with market.client() as http:
            return market.index_members(index, http)

    @mcp.tool
    def market_rank_returns(
        index: str = "SMLL", period: str = "1y", top: int = 10
    ) -> dict:
        """Ranks every current member of a B3 index by total return (dividends reinvested) and returns the top and bottom 3.

        period: 1mo, 3mo, 6mo, ytd, 1y, 2y, 5y, 10y or max. Prices come from Yahoo Finance. The list uses today's
        members, so a stock that left the index in the period is missing. A date under `check` had a daily move above
        40%: tell the user it may be an unrecorded split. A full index takes one to two minutes the first time each day.
        """
        with market.client() as http:
            members = market.index_members(index, http)
            result = market.rank(
                [m["ticker"] for m in members["members"]], period, http
            )
        return {
            "index": members["index"],
            "members_date": members["date"],
            "period": period,
            "top": result["ranked"][:top],
            "bottom": result["ranked"][-3:],
            "priced": len(result["ranked"]),
            "missing": result["missing"],
        }


if __name__ == "__main__":
    mcp.run()
