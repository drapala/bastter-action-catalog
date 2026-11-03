"""Deletes for good every item that a scenario hid with excluir_item, and proves each delete.

excluir_item only hides an item. A hidden item with no movements shows on no screen, so no read can see it.
The proof is the answer itself: excluir_movimentacao_ativo answers Error "Erro ao excluir movimentações." when
the item no longer exists. So an item is gone when the first call answers OK and the repeat answers that Error,
or when the first call already answers that Error. Stock item 746015 showed this pair (runs cli-1793733470
and cli-1793733471). An item counts as purged only after a logged call got that Error.
Only items hidden in scenario runs are touched, never items hidden through the MCP server or the CLI.
Imóvel items are skipped: excluir_movimentacao_ativo answers OK for them twice and the imóvel still reads back
(ImovelMovimentacaoObter returns its Movimentacao, while an unknown ID returns null). The app has no other
method that deletes an imóvel for good, so a hidden imóvel stays hidden.
Before the first delete, the purge reads the item again with the reads its own scenario run logged: the tab read
(the item must not be visible) and the movement read (the item must have no movements). If the user added the
same ticker since then, salvar made that item visible again, and the purge skips it.

Run: .venv/bin/python tools/purge_hidden_items.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bastter_exec
import session

NOT_FOUND = "Erro ao excluir"
NO_PERMANENT_DELETE = {"imovel"}
MOVEMENT_READS = {"bastter.ativos.obter_movimentacao", "bastter.ativos.get_movement"}


def hidden_items(runs: list[dict], scenarios: set[str]) -> list[tuple[str, int]]:
    """Items hidden by a successful excluir_item call in a scenario run, not restored since, and with no proof yet
    that they are gone.

    Calls from the MCP server, the CLI or development runs never hide an item here: those can hide the user's
    real assets.
    """
    return [key for key, _run in hidden_with_runs(runs, scenarios)]


def hidden_with_runs(
    runs: list[dict], scenarios: set[str]
) -> list[tuple[tuple[str, int], str]]:
    """hidden_items, each with the scenario run that hid it last."""
    hidden, purged = {}, set()
    for line in runs:
        inputs = line.get("inputs") or {}
        if "ativoID" not in inputs:
            continue
        key = (inputs.get("tipo"), inputs["ativoID"])
        action = line.get("action")
        if action == "bastter.ativos.excluir_item":
            if (
                bastter_exec.succeeded(line)
                and bastter_exec.scenario_of(line.get("run", "")) in scenarios
            ):
                hidden[key] = line["run"]
        elif action == "bastter.ativos.restaurar_item":
            if bastter_exec.succeeded(line):
                hidden.pop(key, None)
        elif action == "bastter.ativos.excluir_movimentacao_ativo" and NOT_FOUND in (
            line.get("error") or ""
        ):
            purged.add(key)
    return sorted(
        (k, run)
        for k, run in hidden.items()
        if k not in purged and k[0] not in NO_PERMANENT_DELETE
    )


def prechecks(
    runs: list[dict], run: str, tipo: str, ativo_id: int
) -> tuple[dict | None, tuple | None]:
    """The tab read and the movement read that the hiding run logged for this item, to call again."""
    tab, movements = None, None
    for line in runs:
        if line.get("run") != run or not bastter_exec.succeeded(line):
            continue
        inputs = line.get("inputs") or {}
        if (
            line.get("action") == "bastter.ativos.obter_itens"
            and inputs.get("tipo") == tipo
        ):
            tab = inputs
        if line.get("action") in MOVEMENT_READS and inputs.get("ativoID") == ativo_id:
            movements = (line["action"], inputs)
    return tab, movements


def unsafe(
    ativo_id: int, tab_answer: dict | None, movement_answer: dict | None
) -> str | None:
    """Why the item must not be deleted for good, or None. Both reads must have answered with a list."""
    if not isinstance(tab_answer, dict) or not isinstance(
        tab_answer.get("Items"), list
    ):
        return "the tab read gave no list"
    if any(
        isinstance(i, dict) and i.get("AtivoID") == ativo_id
        for i in tab_answer["Items"]
    ):
        return "the item is visible again (the ticker was added since)"
    if not isinstance(movement_answer, dict) or movement_answer.get("Itens") not in (
        None,
        [],
    ):
        return "the item has movements, or no movement read could check it"
    return None


def verdict(first: dict, again: dict | None) -> str:
    """GONE (OK, then the not-found Error), ALREADY GONE (the not-found Error at once), or LEFT."""
    if not first["ok"] and NOT_FOUND in (first["error"] or ""):
        return "ALREADY GONE"
    if (
        first["ok"]
        and again is not None
        and not again["ok"]
        and NOT_FOUND in (again["error"] or "")
    ):
        return "GONE"
    return "LEFT"


def main() -> int:
    runs = [
        json.loads(line)
        for line in bastter_exec.EVIDENCE.read_text().splitlines()
        if line.strip()
    ]
    items = hidden_with_runs(runs, bastter_exec.scenario_names())
    print(f"{len(items)} items hidden by scenario runs")
    if "--dry-run" in sys.argv:
        for (tipo, ativo_id), hid_in in items:
            print(" ", tipo, ativo_id, hid_in)
        return 0
    http, catalog = session.client(), bastter_exec.load_catalog()
    run = f"purge-hidden-items-{int(time.time())}"
    left, skipped = [], []
    for (tipo, ativo_id), hid_in in items:
        tab, movements = prechecks(runs, hid_in, tipo, ativo_id)
        if tab is None:
            reason = "its run logged no tab read to check against"
        else:
            tab_out = bastter_exec.call(
                "bastter.ativos.obter_itens",
                tab,
                run=run,
                http=http,
                catalog=catalog,
                note="purge check tab",
            )
            mov_out = None
            if movements:
                mov_out = bastter_exec.call(
                    movements[0],
                    movements[1],
                    run=run,
                    http=http,
                    catalog=catalog,
                    note="purge check movements",
                )
            reason = unsafe(
                ativo_id,
                tab_out["payload"] if tab_out["ok"] else None,
                mov_out["payload"] if mov_out and mov_out["ok"] else None,
            )
        if reason:
            print(f"{'SKIPPED':12} {tipo:10} {ativo_id}  {reason}")
            skipped.append((tipo, ativo_id))
            continue
        body = {"tipo": tipo, "ativoID": ativo_id}
        first = bastter_exec.call(
            "bastter.ativos.excluir_movimentacao_ativo",
            body,
            run=run,
            http=http,
            catalog=catalog,
            note="purge",
        )
        again = None
        if first["ok"]:
            again = bastter_exec.call(
                "bastter.ativos.excluir_movimentacao_ativo",
                body,
                run=run,
                http=http,
                catalog=catalog,
                note="purge proof",
            )
        result = verdict(first, again)
        print(
            f"{result:12} {tipo:10} {ativo_id}  first: {'OK' if first['ok'] else first['error']}  repeat: {again['error'] if again else '-'}"
        )
        if result == "LEFT":
            left.append((tipo, ativo_id))
    print(
        f"run {run}: {len(items) - len(left) - len(skipped)} gone, {len(left)} left, {len(skipped)} skipped"
    )
    return 1 if left or skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
