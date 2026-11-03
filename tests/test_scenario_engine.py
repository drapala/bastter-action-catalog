"""Scenario checks: the read-back logic that decides verified or failed."""

from pathlib import Path

import bastter_exec as bx


def out(payload, ok=True):
    return {
        "ok": ok,
        "status": 200 if ok else 500,
        "error": None if ok else "boom",
        "payload": payload,
    }


def test_empty_path_means_the_whole_answer():
    """Correction C008: a check on a top-level list."""
    assert bx.lookup([{"Codigo": "VALE3"}], "") == [{"Codigo": "VALE3"}]
    ok, _ = bx.check(
        {"list_contains": {"path": "", "where": {"Codigo": "VALE3"}}},
        out([{"Codigo": "VALE3"}]),
        {},
    )
    assert ok


def test_a_200_answer_with_an_error_field_fails():
    ok, why = bx.check({}, out({"Error": "Ativo não encontrado"}), {})
    assert not ok and "Error" in why


def test_list_excludes_fails_while_the_item_is_still_there():
    ctx = {"mov": 5}
    ok, _ = bx.check(
        {"list_excludes": {"path": "Itens", "where": {"MovimentacaoID": "${mov}"}}},
        out({"Itens": [{"MovimentacaoID": 5}]}),
        ctx,
    )
    assert not ok
    ok, _ = bx.check(
        {"list_excludes": {"path": "Itens", "where": {"MovimentacaoID": "${mov}"}}},
        out({"Itens": []}),
        ctx,
    )
    assert ok


def test_render_keeps_the_type_of_a_full_reference():
    ctx = {"item": 1755458, "f": {"tipo": "acao"}}
    assert bx.render("${item}", ctx) == 1755458
    assert bx.render("${f}", ctx) == {"tipo": "acao"}
    assert bx.render("ZZTESTE ${item}", ctx) == "ZZTESTE 1755458"


def test_shape_keeps_types_and_sizes_not_values():
    shape = bx.shape(
        {"Nome": "PETROBRAS", "Itens": [{"Valor": 50.76}], "CNPJ": "33.000.167/0001-01"}
    )
    assert shape == {
        "Nome": "str",
        "Itens": ["list(1)", "object(1 keys)"],
        "CNPJ": "str",
    }
    assert "PETROBRAS" not in str(shape)


def test_placeholder_ids_are_detected():
    """Correction C012: a read called with a fake ID must not count as verified."""
    assert bx.placeholder_ids({"ativoID": 0, "tipo": "acao"}) == ["ativoID"]
    assert bx.placeholder_ids({"carteiraID": 2000002, "ativoID": 1755458}) == []
    assert bx.placeholder_ids({"comunicadoID": "", "carteirasID": []}) == [
        "comunicadoID"
    ]


def test_a_call_without_answer_is_still_logged(monkeypatch, tmp_path):
    """Correction C013: a timed-out write may run on the server, so the call must leave a log line."""
    import httpx
    import pytest

    monkeypatch.setattr(bx, "EVIDENCE", tmp_path / "runs.jsonl")

    def timeout(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(bx, "raw_call", timeout)
    action = {
        "id": "x.y.z",
        "routes": [
            {
                "kind": "undocumented_api",
                "url": "https://bastter.com/mercado/WebServices/WS_Carteira.asmx/Salvar",
            }
        ],
    }
    with pytest.raises(httpx.ReadTimeout):
        bx.call(
            "x.y.z",
            {"descricao": "ZZTESTE"},
            run="t",
            http=object(),
            catalog={"x.y.z": action},
        )
    line = (tmp_path / "runs.jsonl").read_text()
    assert '"ok": false' in line and "may have run" in line


def test_a_200_answer_with_error_is_logged_as_not_ok(monkeypatch, tmp_path):
    """Correction C015: Bastter answers 200 with {"Error": ...} when it refuses a write."""
    monkeypatch.setattr(bx, "EVIDENCE", tmp_path / "runs.jsonl")
    monkeypatch.setattr(
        bx,
        "raw_call",
        lambda *a, **k: (200, {"Error": "Erro ao excluir movimentações."}, None),
    )
    action = {
        "id": "x.y.z",
        "routes": [
            {
                "kind": "undocumented_api",
                "url": "https://bastter.com/mercado/WebServices/WS_Carteira.asmx/ExcluirMovimentacaoAtivo",
            }
        ],
    }
    out = bx.call(
        "x.y.z",
        {"tipo": "acao", "ativoID": 1},
        run="t",
        http=object(),
        catalog={"x.y.z": action},
    )
    assert out["ok"] is False and "Erro ao excluir" in out["error"]


def _fake_run(monkeypatch, tmp_path, answers, catalog):
    import contextlib  # noqa: F401

    import session

    calls = []

    def fake_call(action_id, inputs, run, http=None, catalog=None, note=""):
        calls.append((note, action_id, inputs))
        payload = answers[note]
        return {"ok": True, "status": 200, "error": None, "payload": payload}

    monkeypatch.setattr(bx, "call", fake_call)
    monkeypatch.setattr(bx, "load_catalog", lambda: catalog)
    monkeypatch.setattr(bx, "EVIDENCE", tmp_path / "runs.jsonl")
    monkeypatch.setattr(session, "client", lambda: None)
    return calls


CATALOG = {
    "a.b.criar": {"operation_class": "create"},
    "a.b.ler": {"operation_class": "read"},
    "a.b.editar": {"operation_class": "update"},
    "a.b.apagar": {"operation_class": "delete"},
    "a.b.apagar_unico": {"operation_class": "delete"},
}


def test_a_failed_step_runs_only_the_deletes_that_use_this_runs_ids(
    monkeypatch, tmp_path
):
    """Audit finding: a failed run used to stop before its delete steps and leave test records."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: criar, action: a.b.criar, save: {item: AtivoID}}\n"
        "  - {name: ler, action: a.b.ler, assert: {equals: {Quantidade: 3}}}\n"
        "  - {name: editar, action: a.b.editar}\n"
        "  - {name: apagar, action: a.b.apagar, inputs: {ativoID: '${item}'}}\n"
    )
    answers = {
        "criar": {"AtivoID": 7},
        "ler": {"Quantidade": 2},
        "editar": {},
        "apagar": {"Return": True},
        "apagar_unico": {},
    }
    calls = _fake_run(monkeypatch, tmp_path, answers, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["criar", "ler", "apagar"], (
        "the update and the delete with no ID are skipped"
    )
    assert calls[-1][2] == {"ativoID": 7}


def test_a_failed_guard_runs_no_cleanup(monkeypatch, tmp_path):
    """Audit finding: a guard that found the owner's real goals started deletes that take no ID."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: antes, action: a.b.ler, guard: true, assert: {equals: {'': 'null'}}}\n"
        "  - {name: criar, action: a.b.criar}\n"
        "  - {name: apagar_unico, action: a.b.apagar_unico, undoes: criar}\n"
    )
    calls = _fake_run(monkeypatch, tmp_path, {"antes": {"SemanaPontos": 9}}, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["antes"]


def test_a_failed_guard_after_a_create_still_runs_no_cleanup(monkeypatch, tmp_path):
    """Audit finding: salvar returns an existing item, so a failed freshness check must not hide it."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: criar, action: a.b.criar, save: {item: AtivoID}}\n"
        "  - {name: sem_movimentacao, action: a.b.ler, guard: true, assert: {empty: [Itens]}}\n"
        "  - {name: apagar, action: a.b.apagar, inputs: {ativoID: '${item}'}}\n"
    )
    answers = {
        "criar": {"AtivoID": 7},
        "sem_movimentacao": {"Itens": [{"MovimentacaoID": 1}]},
    }
    calls = _fake_run(monkeypatch, tmp_path, answers, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["criar", "sem_movimentacao"]


def test_no_cleanup_step_runs_past_a_guard_that_did_not_run(monkeypatch, tmp_path):
    """Audit round 3: a read-back failed between salvar and the guard, and the cleanup hid an unchecked item."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: criar, action: a.b.criar, save: {item: AtivoID}}\n"
        "  - {name: na_aba, action: a.b.ler, assert: {equals: {Ok: true}}}\n"
        "  - {name: sem_movimentacao, action: a.b.ler, guard: true, assert: {empty: [Itens]}}\n"
        "  - {name: apagar, action: a.b.apagar, inputs: {ativoID: '${item}'}}\n"
    )
    answers = {"criar": {"AtivoID": 7}, "na_aba": {"Ok": False}}
    calls = _fake_run(monkeypatch, tmp_path, answers, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["criar", "na_aba"]


def test_a_guard_cannot_be_told_to_continue():
    spec = {
        "steps": [
            {"name": "antes", "action": "a.b.ler", "guard": True, "stop_on_fail": False}
        ]
    }
    assert bx.scenario_problems(spec, CATALOG) == ["antes: a guard must stop the run"]


def test_a_ticker_add_without_guards_around_it_is_a_problem():
    """Positive control for the C027 guards: an asset scenario shaped as it was before them."""
    salvar = {
        "name": "incluir_ativo",
        "action": "bastter.ativos.salvar",
        "inputs": {"ativoID": 0, "descricao": "${ticker}"},
    }
    read = {"name": "itens_com_ativo", "action": "a.b.ler"}
    guard = {"name": "guarda", "action": "a.b.ler", "guard": True}
    catalog = {**CATALOG, "bastter.ativos.salvar": {"operation_class": "update"}}
    assert bx.scenario_problems({"steps": [salvar, read, guard]}, catalog)
    assert bx.scenario_problems({"steps": [guard, salvar, read]}, catalog), (
        "the guard after salvar is missing"
    )
    assert bx.scenario_problems({"steps": [read, salvar, guard]}, catalog), (
        "the guard before salvar is missing"
    )
    assert bx.scenario_problems({"steps": [guard, salvar, guard]}, catalog) == []
    test_record = {
        **salvar,
        "inputs": {"ativoID": 0, "descricao": "${prefix} imovel ${ts}"},
    }
    assert bx.scenario_problems({"steps": [test_record, read]}, catalog) == [], (
        "a ZZTESTE name cannot be the user's"
    )


def test_equals_fails_on_a_missing_path():
    """Audit round 3: {X: null} passed when X was not in the answer."""
    assert not bx.check(
        {"equals": {"Personalizado.Rotulo": None}}, out({"Personalizado": None}), {}
    )[0]
    assert bx.check(
        {"equals": {"Personalizado.Rotulo": None}},
        out({"Personalizado": {"Rotulo": None}}),
        {},
    )[0]


def test_undoes_restores_a_setting_after_a_failed_read_back(monkeypatch, tmp_path):
    """Audit finding: restores were skipped after a failure, so a real setting stayed changed."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: antes, action: a.b.ler, save: {antes: Nome}}\n"
        "  - {name: mudar, action: a.b.editar, inputs: {nome: ZZTESTE}}\n"
        "  - {name: mudou, action: a.b.ler, assert: {equals: {Nome: ZZTESTE}}}\n"
        "  - {name: restaurar, action: a.b.editar, undoes: mudar, inputs: {nome: '${antes}'}}\n"
    )
    answers = {
        "antes": {"Nome": "Principal"},
        "mudar": {},
        "mudou": {"Nome": "Principal"},
        "restaurar": {},
    }
    calls = _fake_run(monkeypatch, tmp_path, answers, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["antes", "mudar", "mudou", "restaurar"]
    assert calls[-1][2] == {"nome": "Principal"}


def test_a_save_that_finds_nothing_fails_the_step(monkeypatch, tmp_path):
    """Audit finding: a None saved value made later list_excludes checks pass with nothing proved."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n  - {name: criar, action: a.b.criar, save: {item: AtivoID}}\n"
    )
    calls = _fake_run(monkeypatch, tmp_path, {"criar": {"Return": True}}, CATALOG)
    assert bx.scenario(str(spec)) == 1 and len(calls) == 1


def test_a_saved_null_needs_nullable_and_a_missing_path_always_fails():
    """Live finding: InsightsClasses is a real null that a settings scenario must save to restore."""
    step = {"save": {"antes": "Opcoes.Insights"}}
    assert bx.save_values(step, {"Opcoes": {"Insights": None}}, {})[1]
    step = {"save": {"antes": {"path": "Opcoes.Insights", "nullable": True}}}
    assert bx.save_values(step, {"Opcoes": {"Insights": None}}, {}) == (
        {"antes": None},
        None,
    )
    assert bx.save_values(step, {"Opcoes": {}}, {})[1], (
        "a path that does not exist is never a null"
    )


def test_list_excludes_with_an_empty_reference_is_not_a_pass():
    ok, why = bx.check(
        {"list_excludes": {"path": "Items", "where": {"AtivoID": "${item}"}}},
        out({"Items": []}),
        {"item": None},
    )
    assert not ok and "nothing to check" in why


def test_list_excludes_accepts_a_literal_null():
    """Live finding: {AtivoID: X, DataFreio: null} checks that the brake date is no longer empty."""
    assertion = {
        "list_excludes": {
            "path": "Items",
            "where": {"AtivoID": "${item}", "DataFreio": None},
        }
    }
    ok, _ = bx.check(
        assertion,
        out({"Items": [{"AtivoID": 7, "DataFreio": "2026-11-03"}]}),
        {"item": 7},
    )
    assert ok
    ok, _ = bx.check(
        assertion, out({"Items": [{"AtivoID": 7, "DataFreio": None}]}), {"item": 7}
    )
    assert not ok


def test_empty_passes_only_for_an_empty_list_or_null_that_exists():
    assert bx.check({"empty": ["Itens"]}, out({"Itens": []}), {})[0]
    assert bx.check({"empty": ["Itens"]}, out({"Itens": None}), {})[0]
    assert not bx.check(
        {"empty": ["Itens"]}, out({"Itens": [{"MovimentacaoID": 1}]}), {}
    )[0]
    assert not bx.check({"empty": ["Itens"]}, out({"Outra": []}), {})[0]


def test_a_read_back_that_could_not_run_is_logged_as_unknown(monkeypatch, tmp_path):
    """Audit finding: a timeout on a read-back marked the write failed for a network reason."""
    import json

    import httpx

    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n  - {name: ler, action: a.b.ler, postcondition_of: a.b.criar}\n"
    )
    _fake_run(monkeypatch, tmp_path, {}, CATALOG)

    def timeout(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(bx, "call", timeout)
    assert bx.scenario(str(spec)) == 1
    line = json.loads((tmp_path / "runs.jsonl").read_text().splitlines()[-1])
    assert line["check"] == "read_back" and line["passed"] is None


def test_every_scenario_file_follows_the_cleanup_rules():
    import glob

    import yaml

    catalog = bx.load_catalog()
    for path in glob.glob(str(bx.ROOT / "scenarios/*.yaml")):
        assert (
            bx.scenario_problems(yaml.safe_load(Path(path).read_text()), catalog) == []
        ), path


def test_the_cleanup_rules_catch_a_delete_with_no_id():
    """Positive control for the test above: the race scenario before the fix."""
    spec = {
        "steps": [
            {"name": "antes", "action": "a.b.ler", "guard": True},
            {"name": "criar", "action": "a.b.criar"},
            {"name": "apagar_unico", "action": "a.b.apagar_unico"},
            {"name": "restaurar", "action": "a.b.editar", "undoes": "depois"},
            {"name": "guarda_errada", "action": "a.b.editar", "guard": True},
        ]
    }
    problems = bx.scenario_problems(spec, CATALOG)
    assert len(problems) == 3 and "needs undoes" in problems[0]


def test_undo_blocker_skips_unsafe_cleanup_steps():
    assert (
        bx.undo_blocker({"name": "x", "action": "a.b.apagar_unico"}, set(), {}, CATALOG)
        == "it uses no value this run saved"
    )
    assert "was not reached" in bx.undo_blocker(
        {"name": "x", "action": "a.b.editar", "undoes": "mudar"}, set(), {}, CATALOG
    )
    assert (
        bx.undo_blocker(
            {"name": "x", "action": "a.b.apagar", "inputs": {"id": "${item}"}},
            {"g"},
            {"item": 7},
            CATALOG,
            ["g"],
        )
        is None
    )
    assert "did not run" in bx.undo_blocker(
        {"name": "x", "action": "a.b.apagar", "inputs": {"id": "${item}"}},
        set(),
        {"item": 7},
        CATALOG,
        ["g"],
    )


def test_a_file_that_breaks_the_cleanup_rules_makes_no_call(monkeypatch, tmp_path):
    """Audit round 4: scenario() ran files that only the test suite checked."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n  - {name: criar, action: a.b.criar}\n  - {name: apagar_unico, action: a.b.apagar_unico}\n"
    )
    calls = _fake_run(monkeypatch, tmp_path, {}, CATALOG)
    assert bx.scenario(str(spec)) == 1 and calls == []


def test_a_skipped_cleanup_step_blocks_later_steps_on_the_same_record(
    monkeypatch, tmp_path
):
    """Audit round 4: the buy was not deleted (its ID was not saved), and the item was hidden with the buy inside."""
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n"
        "  - {name: criar, action: a.b.criar, save: {item: AtivoID}}\n"
        "  - {name: compra, action: a.b.criar, inputs: {ativoID: '${item}'}}\n"
        "  - {name: compra_lida, action: a.b.ler, save: {mov: Id}}\n"
        "  - {name: apagar_compra, action: a.b.apagar, inputs: {ativoID: '${item}', movID: '${mov}'}}\n"
        "  - {name: apagar_item, action: a.b.apagar, inputs: {ativoID: '${item}'}}\n"
    )
    answers = {"criar": {"AtivoID": 7}, "compra": {}, "compra_lida": {"Outro": 1}}
    calls = _fake_run(monkeypatch, tmp_path, answers, CATALOG)
    assert bx.scenario(str(spec)) == 1
    assert [c[0] for c in calls] == ["criar", "compra", "compra_lida"]


def test_a_failed_guard_leaves_a_log_line(monkeypatch, tmp_path):
    import json

    spec = tmp_path / "s.yaml"
    spec.write_text(
        "name: t\nsteps:\n  - {name: antes, action: a.b.ler, guard: true, assert: {empty: [Itens]}}\n"
    )
    _fake_run(monkeypatch, tmp_path, {"antes": {"Itens": [1]}}, CATALOG)
    assert bx.scenario(str(spec)) == 1
    line = json.loads((tmp_path / "runs.jsonl").read_text().splitlines()[-1])
    assert (
        line["check"] == "guard" and line["passed"] is False and line["step"] == "antes"
    )
