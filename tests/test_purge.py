"""The permanent delete only touches items that a scenario run hid and that were not restored or already purged."""

import purge_hidden_items as ph

SCENARIOS = {"acao-ciclo-completo", "fii-ciclo"}


def line(
    action, tipo, ativo, run="acao-ciclo-completo-1793731132", ok=True, shape=None
):
    return {
        "run": run,
        "action": f"bastter.ativos.{action}",
        "ok": ok,
        "inputs": {"tipo": tipo, "ativoID": ativo},
        "shape": shape or {"Return": "str"},
    }


def test_only_items_hidden_by_scenarios_are_selected():
    runs = [
        line("excluir_item", "acao", 1),
        line("excluir_item", "fii", 2, run="fii-ciclo-1793731200"),
        line("restaurar_item", "fii", 2, run="fii-ciclo-1793731200"),
        line("excluir_item", "stock", 3),
        {
            **line("excluir_movimentacao_ativo", "stock", 3),
            "ok": False,
            "error": "the answer has Error: Erro ao excluir movimentações.",
        },
        line("excluir_item", "reit", 6),
        line("excluir_movimentacao_ativo", "reit", 6),
        line("excluir_item", "etf", 4, ok=False),
        line("salvar", "reit", 5),
        {
            "run": "acao-ciclo-completo-1793731132",
            "action": "bastter.ativos.excluir_item",
            "ok": True,
            "inputs": {"tipo": "bdr"},
        },
    ]
    assert ph.hidden_items(runs, SCENARIOS) == [("acao", 1), ("reit", 6)], (
        "an OK delete with no proof keeps the item listed"
    )


def test_items_hidden_through_mcp_cli_or_dev_runs_are_never_selected():
    """Audit finding: a real asset the user hid through the MCP server must never be deleted for good."""
    runs = [
        line("excluir_item", "acao", 10, run="mcp-1793731888"),
        line("excluir_item", "acao", 11, run="cli-1793731027"),
        line("excluir_item", "acao", 12, run="dev-ativos-classes-1793730358"),
    ]
    assert ph.hidden_items(runs, SCENARIOS) == []


def test_a_refusal_logged_as_ok_before_the_error_check_does_not_count():
    """Audit finding: lines logged before C015 say ok true with an Error-shaped answer."""
    runs = [line("excluir_item", "acao", 20, shape={"Error": "str"})]
    assert ph.hidden_items(runs, SCENARIOS) == []


def answer(ok, error=None):
    return {"ok": ok, "error": error}


def test_the_purge_verdict_needs_the_not_found_error():
    """Audit finding: a purge whose repeat also answered OK was counted as done."""
    not_found = "the answer has Error: Erro ao excluir movimentações."
    assert ph.verdict(answer(True), answer(False, not_found)) == "GONE"
    assert ph.verdict(answer(False, not_found), None) == "ALREADY GONE"
    assert ph.verdict(answer(True), answer(True)) == "LEFT"
    assert (
        ph.verdict(
            answer(False, "500 There was an error processing the request."), None
        )
        == "LEFT"
    )


def test_hidden_imoveis_are_skipped():
    """Live finding: excluir_movimentacao_ativo answers OK on an imóvel and the imóvel still reads back."""
    assert ph.hidden_items([line("excluir_item", "imovel", 41242)], SCENARIOS) == []


def test_prechecks_reuse_the_reads_of_the_run_that_hid_the_item():
    run = "fii-ciclo-1793731200"
    tab = {
        "run": run,
        "action": "bastter.ativos.obter_itens",
        "ok": True,
        "inputs": {"tipo": "fii", "ordenacao": 1},
        "shape": {},
    }
    mov = {
        "run": run,
        "action": "bastter.ativos.obter_movimentacao",
        "ok": True,
        "inputs": {"tipo": "fii", "ativoID": 2},
        "shape": {},
    }
    other = {**tab, "run": "fii-ciclo-1793739999"}
    assert ph.prechecks([tab, mov, other], run, "fii", 2) == (
        tab["inputs"],
        ("bastter.ativos.obter_movimentacao", mov["inputs"]),
    )
    assert ph.prechecks([other], run, "fii", 2) == (None, None)


def test_an_item_that_is_visible_again_or_has_movements_is_not_deleted():
    """Audit round 3: the user may add the same ticker later, and salvar then shows the hidden scenario item."""
    assert (
        ph.unsafe(2, {"Items": [{"AtivoID": 2}]}, {"Itens": []})
        == "the item is visible again (the ticker was added since)"
    )
    assert "movements" in ph.unsafe(
        2, {"Items": []}, {"Itens": [{"MovimentacaoID": 9}]}
    )
    assert ph.unsafe(2, None, None) == "the tab read gave no list"
    assert ph.unsafe(2, {"Items": [{"AtivoID": 3}]}, {"Itens": []}) is None
    assert (
        ph.unsafe(2, {"Items": []}, None)
        == "the item has movements, or no movement read could check it"
    )


def test_only_movement_reads_proven_for_past_years_can_clear_an_item():
    """Audit round 5: a read counts only after a scenario reads back a buy dated 2019 with it."""
    import yaml

    proven = set()
    for name in ("acao_ciclo_completo", "stock_ciclo"):
        steps = yaml.safe_load((ph.ROOT / f"scenarios/{name}.yaml").read_text())[
            "steps"
        ]
        proven |= {
            s["action"] for s in steps if "1546394400000" in str(s.get("assert"))
        }
    assert ph.MOVEMENT_READS == proven


def test_purge_one_never_deletes_an_unsafe_item():
    """Audit round 5: replacing the safety branch of main() with a no-op left every test green."""
    run = "fii-ciclo-1793731200"
    tab = {
        "run": run,
        "action": "bastter.ativos.obter_itens",
        "ok": True,
        "inputs": {"tipo": "fii"},
        "shape": {},
    }
    mov = {
        "run": run,
        "action": "bastter.ativos.obter_movimentacao",
        "ok": True,
        "inputs": {"tipo": "fii", "ativoID": 2},
        "shape": {},
    }
    not_found = {
        "ok": False,
        "error": "the answer has Error: Erro ao excluir movimentações.",
        "payload": None,
    }

    def account(items, movements):
        sent = []

        def call(action_id, body, note):
            sent.append(action_id)
            if action_id == "bastter.ativos.obter_itens":
                return {"ok": True, "error": None, "payload": {"Items": items}}
            if action_id == "bastter.ativos.obter_movimentacao":
                return {"ok": True, "error": None, "payload": {"Itens": movements}}
            first = sent.count("bastter.ativos.excluir_movimentacao_ativo") == 1
            return (
                {"ok": True, "error": None, "payload": {"Return": "OK"}}
                if first
                else not_found
            )

        return call, sent

    call, sent = account([{"AtivoID": 2}], [])
    assert ph.purge_one(call, [tab, mov], "fii", 2, run)[0] == "SKIPPED"
    assert "bastter.ativos.excluir_movimentacao_ativo" not in sent
    call, sent = account([], [{"MovimentacaoID": 9}])
    assert ph.purge_one(call, [tab, mov], "fii", 2, run)[0] == "SKIPPED"
    assert "bastter.ativos.excluir_movimentacao_ativo" not in sent
    call, sent = account([], [])
    assert ph.purge_one(call, [tab], "fii", 2, run)[0] == "SKIPPED", (
        "no movement read logged"
    )
    call, sent = account([], [])
    assert ph.purge_one(call, [tab, mov], "fii", 2, run)[0] == "GONE"
