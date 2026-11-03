"""The demo cleanup removes only records that are new since the snapshot AND that the demo's own calls created."""

import json
from datetime import datetime

import demo_cleanup as dc
import pytest


class FakeAccount:
    def __init__(self):
        self.items = {"100": "ITSA4", "200": "ITSA4"}
        self.movements = {
            "100": [{"MovimentacaoID": 1, "Tipo": "Compra", "Quantidade": 5.0}],
            "200": [{"MovimentacaoID": 2, "Tipo": "Compra", "Quantidade": 3.0}],
        }
        self.entries = {10: "aluguel", 11: "ZZTESTE gasto de mercado"}
        self.categories = {5: "ZZTESTE mercado"}
        self.calls = []
        self.refuse = set()

    def __call__(self, action, body):
        self.calls.append((action, body))
        ok = {"ok": True, "error": None}
        assert action != "ativos.excluir_movimentacao_ativo", (
            "the demo cleanup never deletes an item for good"
        )
        if action == "ativos.excluir_movimentacao":
            assert body["tipomov"] in ("compra", "venda"), (
                "the server takes tipomov in lower case"
            )
        if (action, json.dumps(body, sort_keys=True)) in self.refuse:
            return {
                "ok": False,
                "error": "the answer has Error: Erro ao excluir.",
                "payload": {"Error": "Erro ao excluir."},
            }
        if action == "ativos.obter_itens":
            return {
                **ok,
                "payload": {
                    "Items": [
                        {"AtivoID": int(k), "Descricao": v}
                        for k, v in self.items.items()
                    ]
                },
            }
        if action == "ativos.obter_movimentacao":
            return {
                **ok,
                "payload": {"Itens": self.movements.get(str(body["ativoID"]), [])},
            }
        if action == "financeiro.financa_obter_itens":
            return {
                **ok,
                "payload": {
                    "Lancamentos": [
                        {"LancamentoID": k, "Descricao": v}
                        for k, v in self.entries.items()
                    ],
                    "Categorias": [
                        {"CategoriaID": k, "Descricao": v}
                        for k, v in self.categories.items()
                    ],
                },
            }
        if action == "ativos.excluir_movimentacao":
            m = str(body["ativoID"])
            self.movements[m] = [
                x
                for x in self.movements[m]
                if x["MovimentacaoID"] != body["movimentacaoID"]
            ]
        elif action == "ativos.excluir_item":
            self.items.pop(str(body["ativoID"]))
        elif action == "financeiro.financa_deletar":
            self.entries.pop(body["lancamentoID"])
        elif action == "financeiro.financa_excluir_categoria":
            self.categories.pop(body["categoriaID"])
        return {**ok, "payload": {"Return": True}}


BEFORE = {
    "items": {"100": "ITSA4"},
    "movements": {"100": [{"id": 1, "tipo": "Compra", "qtd": 5.0}]},
    "entries": {"10": "aluguel"},
    "categories": {},
}
MADE = {
    "tickers": {"ITSA4"},
    "movements": {"200": 1},
    "quantities": {"200": {3.0}},
    "entries": {"ZZTESTE gasto de mercado"},
    "categories": {"ZZTESTE mercado"},
}


def test_only_records_the_demo_created_are_removed():
    account = FakeAccount()
    assert dc.clean(BEFORE, account, MADE) == []
    assert account.items == {"100": "ITSA4"}, (
        "the item that existed before (same ticker) stays"
    )
    assert account.movements["100"] == [
        {"MovimentacaoID": 1, "Tipo": "Compra", "Quantidade": 5.0}
    ]
    assert account.entries == {10: "aluguel"} and account.categories == {}
    actions = [a for a, _ in account.calls]
    assert actions.index("ativos.excluir_movimentacao") < actions.index(
        "ativos.excluir_item"
    )


def test_a_returned_hidden_item_with_old_movements_is_not_touched():
    """Audit round 3: salvar can return the user's hidden ITSA4, whose old movements then look new."""
    account = FakeAccount()
    account.movements["200"].append(
        {"MovimentacaoID": 3, "Tipo": "Venda", "Quantidade": -3.0}
    )
    problems = dc.clean(BEFORE, account, MADE)
    assert any("item 200" in p for p in problems)
    assert len(account.movements["200"]) == 2 and "200" in account.items


def test_the_users_movement_on_a_returned_item_survives_a_demo_create_and_delete():
    """Audit round 4: the demo created and then deleted its own buy on the user's returned ITSA4."""
    account = FakeAccount()
    problems = dc.clean(BEFORE, account, {**MADE, "movements": {"200": 0}})
    assert any("item 200" in p for p in problems)
    assert account.movements["200"] == [
        {"MovimentacaoID": 2, "Tipo": "Compra", "Quantidade": 3.0}
    ]
    assert "200" in account.items


def test_a_new_movement_with_a_quantity_the_demo_never_sent_is_not_touched():
    account = FakeAccount()
    problems = dc.clean(BEFORE, account, {**MADE, "quantities": {"200": {7.0}}})
    assert any("item 200" in p for p in problems)
    assert len(account.movements["200"]) == 1


def test_a_new_record_the_demo_did_not_create_is_reported_not_deleted():
    account = FakeAccount()
    account.entries[12] = "conta de luz"
    problems = dc.clean(BEFORE, account, MADE)
    assert any(
        "finance entry 12 is new but the demo did not create it" in p for p in problems
    )
    assert 12 in account.entries


def test_a_refused_delete_is_reported_and_the_account_does_not_match():
    account = FakeAccount()
    account.refuse.add(
        (
            "financeiro.financa_deletar",
            json.dumps(
                {"excluirRecorrentes": False, "lancamentoID": 11}, sort_keys=True
            ),
        )
    )
    problems = dc.clean(BEFORE, account, MADE)
    assert "finance entry 11: the answer has Error: Erro ao excluir." in problems
    assert "entries differ from the snapshot" in problems


def test_demo_creates_reads_only_the_demo_runs_in_the_window():
    def line(at, action, inputs, run="mcp-demo-1"):
        return {"run": run, "at": at, "action": action, "ok": True, "inputs": inputs}

    lines = [
        line(
            "2026-11-03T10:00:00+00:00",
            "bastter.ativos.salvar",
            {"ativoID": 0, "descricao": "OLD3"},
        ),
        line(
            "2026-11-03T12:00:00+00:00",
            "bastter.ativos.salvar",
            {"ativoID": 0, "descricao": "ITSA4"},
        ),
        line(
            "2026-11-03T12:01:00+00:00",
            "bastter.ativos.salvar_movimentacao",
            {"movimentacaoID": 0, "ativoID": 200, "quantidade": 3},
        ),
        line(
            "2026-11-03T12:02:00+00:00",
            "bastter.ativos.salvar_movimentacao",
            {"movimentacaoID": 9, "ativoID": 200, "quantidade": 4},
        ),
        line(
            "2026-11-03T12:03:00+00:00",
            "bastter.financeiro.financa_salvar",
            {
                "descricao": "ZZTESTE x",
                "categoriaID": 0,
                "categoriaDescricao": "ZZTESTE c",
            },
        ),
        line(
            "2026-11-03T12:04:00+00:00",
            "bastter.financeiro.financa_salvar",
            {"descricao": "luz", "categoriaID": 0, "categoriaDescricao": "casa"},
        ),
        line(
            "2026-11-03T12:05:00+00:00",
            "bastter.ativos.salvar",
            {"ativoID": 0, "descricao": "MINE3"},
            run="mcp-1793700000",
        ),
        line(
            "2026-11-03T12:06:00+00:00",
            "bastter.ativos.excluir_movimentacao",
            {"ativoID": 300, "movimentacaoID": 1},
        ),
    ]
    since = datetime.fromisoformat("2026-11-03T11:00:00+00:00").timestamp()
    made = dc.demo_creates(lines, since)
    assert made == {
        "tickers": {"ITSA4"},
        "movements": {"200": 1, "300": -1},
        "quantities": {"200": {3.0, 4.0}},
        "entries": {"ZZTESTE x"},
        "categories": {"ZZTESTE c"},
    }, (
        "another MCP session and names without ZZTESTE never count; the demo's deletes are subtracted"
    )


def test_an_old_snapshot_is_refused(monkeypatch, tmp_path):
    """Audit finding: a snapshot kept for days made the user's later records look like demo records."""
    snap = tmp_path / "before.json"
    monkeypatch.setattr(dc, "SNAPSHOT", snap)
    snap.write_text(json.dumps({**BEFORE, "taken_at": 1000.0}))
    assert dc.usable_snapshot(1000.0 + 60)["items"] == BEFORE["items"]
    with pytest.raises(SystemExit):
        dc.usable_snapshot(1000.0 + dc.MAX_AGE_S + 1)
    snap.write_text(json.dumps(BEFORE))
    with pytest.raises(SystemExit):
        dc.usable_snapshot(1000.0)


def test_a_clean_pass_deletes_the_snapshot(monkeypatch, tmp_path):
    """Correction C032: a second run must not act on records added after the demo."""
    import time

    snap = tmp_path / "before.json"
    monkeypatch.setattr(dc, "SNAPSHOT", snap)
    monkeypatch.setattr(dc.bastter_exec, "PRIVATE_LOG", tmp_path / "none.jsonl")
    snap.write_text(json.dumps({**BEFORE, "taken_at": time.time()}))
    account = FakeAccount()
    account.items = {"100": "ITSA4"}
    account.movements = {
        "100": [{"MovimentacaoID": 1, "Tipo": "Compra", "Quantidade": 5.0}]
    }
    account.entries, account.categories = {10: "aluguel"}, {}
    monkeypatch.setattr(dc, "caller", lambda run, note: account)
    assert dc.main() == 0 and not snap.exists()
