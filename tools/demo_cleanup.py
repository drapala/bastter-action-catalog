"""Removes only what the agent demo created, by matching the account against the demo's own MCP calls.

demo/run_agent_demo.py calls snapshot() before the first request and saves .cache/demo_before.json. The demo's
calls are in logs/mcp-runs.jsonl. A record is removed only when it is new since the snapshot AND a demo call
created it:
- an acao movement, when the demo created at least as many movements on that item as there are new ones;
- an acao item, when the demo added that ticker. The item is only hidden, never deleted for good, because salvar
  can return (and show again) an item the user hid before. Hiding puts such an item back where it was;
- a finance entry or category, when the demo created one with that description.
Anything else that looks new is reported as LEFT and not touched. Every delete is checked, and the account is
read again. A snapshot older than MAX_AGE_S, or without a time, is refused. After a clean pass the snapshot
is deleted, so a second run cannot act on later records.

Run after the demo: .venv/bin/python tools/demo_cleanup.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bastter_exec
import session

SNAPSHOT = ROOT / ".cache/demo_before.json"
MAX_AGE_S = 3 * 3600
ITENS = {
    "tipo": "acao",
    "ordenacao": 1,
    "classificacao": "0",
    "categoria": 0,
    "setor": "0",
    "segmento": 0,
    "country": 0,
    "gestorID": 0,
    "classificacao2": 0,
    "exchange": None,
    "mandatoID": 0,
}
FINANCAS = {
    "mes": None,
    "tipo": "0",
    "categoriaID": "0",
    "ordenacao": 1,
    "periodo": "0",
    "status": "0",
}


def read_state(call) -> dict:
    items = call("ativos.obter_itens", ITENS)["payload"]["Items"]
    movements = {}
    for item in items:
        movs = call(
            "ativos.obter_movimentacao",
            {
                "codigo": item.get("Descricao") or "",
                "tipo": "acao",
                "ativoID": item["AtivoID"],
                "mes": 0,
                "ano": 0,
            },
        )
        movements[str(item["AtivoID"])] = [
            {"id": m["MovimentacaoID"], "tipo": m["Tipo"]}
            for m in movs["payload"]["Itens"]
        ]
    fin = call("financeiro.financa_obter_itens", FINANCAS)["payload"]
    return {
        "items": {str(i["AtivoID"]): i.get("Descricao") for i in items},
        "movements": movements,
        "entries": {
            str(e["LancamentoID"]): e.get("Descricao")
            for e in fin.get("Lancamentos") or []
        },
        "categories": {
            str(c["CategoriaID"]): c.get("Descricao")
            for c in fin.get("Categorias") or []
        },
    }


def demo_creates(lines: list[dict], since: float) -> dict:
    """What the demo's MCP calls created after `since`: tickers, movements per item, entry and category names."""
    made = {"tickers": set(), "movements": {}, "entries": set(), "categories": set()}
    for line in lines:
        if not str(line.get("run", "")).startswith("mcp-") or not line.get("ok"):
            continue
        if datetime.fromisoformat(line["at"]).timestamp() < since:
            continue
        action, inputs = line.get("action"), line.get("inputs") or {}
        if action == "bastter.ativos.salvar" and inputs.get("ativoID") == 0:
            made["tickers"].add(inputs.get("descricao"))
        elif (
            action == "bastter.ativos.salvar_movimentacao"
            and inputs.get("movimentacaoID") == 0
        ):
            key = str(inputs.get("ativoID"))
            made["movements"][key] = made["movements"].get(key, 0) + 1
        elif action == "bastter.financeiro.financa_salvar" and not inputs.get(
            "lancamentoID"
        ):
            made["entries"].add(inputs.get("descricao"))
            if not inputs.get("categoriaID") and inputs.get("categoriaDescricao"):
                made["categories"].add(inputs["categoriaDescricao"])
    return made


def caller(run: str, note: str):
    http, catalog = session.client(), bastter_exec.load_catalog()
    return lambda action, body: bastter_exec.call(
        f"bastter.{action}", body, run=run, http=http, catalog=catalog, note=note
    )


def snapshot() -> None:
    state = read_state(caller(f"demo-snapshot-{int(time.time())}", "demo snapshot"))
    SNAPSHOT.write_text(json.dumps({**state, "taken_at": time.time()}))


def clean(before: dict, call, made: dict) -> list[str]:
    """Removes the new records the demo made (see the module docstring) and returns what is left."""
    now = read_state(call)
    problems, untouched = [], set()

    def must(out, what):
        if not out["ok"]:
            problems.append(f"{what}: {out['error']}")
        return out["ok"]

    for item_id, movs in now["movements"].items():
        known = {m["id"] for m in before["movements"].get(item_id, [])}
        new = [m for m in movs if m["id"] not in known]
        if not new:
            continue
        if len(new) > made["movements"].get(item_id, 0):
            untouched.add(item_id)
            problems.append(
                f"item {item_id} has {len(new)} new movements and the demo created {made['movements'].get(item_id, 0)}: not touched"
            )
            continue
        for m in new:
            body = {
                "tipo": "acao",
                "tipomov": m["tipo"].lower(),
                "movimentacaoID": m["id"],
                "ativoID": int(item_id),
            }
            if must(call("ativos.excluir_movimentacao", body), f"movement {m['id']}"):
                print(f"movement {m['id']} on item {item_id} deleted")
    for item_id, code in now["items"].items():
        if item_id in before["items"]:
            continue
        if code not in made["tickers"] or item_id in untouched:
            problems.append(
                f"item {item_id} ({code}) is new but the demo did not add it: not touched"
            )
            continue
        if must(
            call(
                "ativos.excluir_item",
                {"tipo": "acao", "ativoID": int(item_id), "carteiraID": 0},
            ),
            f"hide item {item_id}",
        ):
            print(f"item {item_id} ({code}) hidden")
    for entry, text in now["entries"].items():
        if entry in before["entries"]:
            continue
        if text not in made["entries"]:
            problems.append(
                f"finance entry {entry} is new but the demo did not create it: not touched"
            )
        elif must(
            call(
                "financeiro.financa_deletar",
                {"lancamentoID": int(entry), "excluirRecorrentes": False},
            ),
            f"finance entry {entry}",
        ):
            print(f"finance entry {entry} deleted")
    for cat, text in now["categories"].items():
        if cat in before["categories"]:
            continue
        if text not in made["categories"]:
            problems.append(
                f"finance category {cat} is new but the demo did not create it: not touched"
            )
        elif must(
            call("financeiro.financa_excluir_categoria", {"categoriaID": int(cat)}),
            f"category {cat}",
        ):
            print(f"finance category {cat} deleted")

    after = read_state(call)
    differs = [
        k
        for k in ("items", "entries", "categories")
        if sorted(after[k]) != sorted(before[k])
    ]
    differs += [
        f"movements of {i}"
        for i in after["movements"]
        if after["movements"][i] != before["movements"].get(i)
    ]
    return problems + [f"{d} differ from the snapshot" for d in differs]


def usable_snapshot(now: float) -> dict:
    """The snapshot taken before the demo. Exits when it is missing or older than MAX_AGE_S."""
    if not SNAPSHOT.exists():
        sys.exit(
            "No snapshot from before the demo (.cache/demo_before.json). Nothing was deleted."
        )
    before = json.loads(SNAPSHOT.read_text())
    if "taken_at" not in before:
        sys.exit(
            "The snapshot has no time, so its age is unknown. Nothing was deleted."
        )
    age = now - before["taken_at"]
    if age > MAX_AGE_S:
        sys.exit(
            f"The snapshot is {int(age // 60)} minutes old. Records added since then would look new. Nothing was deleted."
        )
    return before


def main() -> int:
    before = usable_snapshot(time.time())
    lines = (
        [
            json.loads(x)
            for x in bastter_exec.PRIVATE_LOG.read_text().splitlines()
            if x.strip()
        ]
        if bastter_exec.PRIVATE_LOG.exists()
        else []
    )
    made = demo_creates(lines, before["taken_at"])
    problems = clean(
        before, caller(f"demo-cleanup-{int(time.time())}", "demo cleanup"), made
    )
    for problem in problems:
        print("LEFT", problem)
    if problems:
        print("NOT CLEAN")
        return 1
    SNAPSHOT.unlink()
    print("nothing left. The snapshot was deleted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
