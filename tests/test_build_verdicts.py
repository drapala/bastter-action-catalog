"""Write status comes from the latest run of each scenario, so a failed development run does not stick."""

import build_catalog as bc

SCEN = {"bond-ciclo", "acao-ciclo", "config-abas-salvar"}


def rb(run, checks, passed, step=None):
    line = {
        "run": run,
        "at": "2026-11-03T18:00:00+00:00",
        "check": "read_back",
        "checks": checks,
        "passed": passed,
    }
    return {**line, "step": step} if step else line


def test_older_failed_run_is_ignored():
    runs = [
        rb("bond-ciclo-1793730000", "w", False),
        rb("bond-ciclo-1793730139", "w", True),
    ]
    assert bc.read_back_verdicts(runs, SCEN)["w"]["status"] == "verified"


def test_latest_failure_in_any_scenario_wins():
    runs = [
        rb("acao-ciclo-1793730000", "w", True),
        rb("bond-ciclo-1793730139", "w", False),
    ]
    assert bc.read_back_verdicts(runs, SCEN)["w"]["status"] == "failed"


def test_dashes_in_scenario_names():
    runs = [
        rb("config-abas-salvar-1793730355", "w", False),
        rb("config-abas-salvar-1793730999", "w", True),
    ]
    verdict = bc.read_back_verdicts(runs, SCEN)["w"]
    assert verdict["status"] == "verified" and verdict["evidence"].endswith(
        "1793730999"
    )


def test_a_field_the_app_sends_as_null_accepts_null():
    """Correction C016: the demo agent's null despesaDedutivel was refused by an inferred object type."""
    from jsonschema import Draft7Validator

    schema = bc.schema_from_bodies(
        [{"despesaDedutivel": {"a": 1}}, {"despesaDedutivel": None}], {}
    )
    assert schema["properties"]["despesaDedutivel"]["type"] == ["object", "null"]
    assert not list(Draft7Validator(schema).iter_errors({"despesaDedutivel": None}))


def test_development_runs_do_not_count():
    """Audit finding: a dev run with a later stamp or a non-numeric stamp must not decide the status."""
    runs = [
        rb("bond-ciclo-1793730139", "w", True),
        rb("dev-bond-1793739999", "w", False),
        rb("dev-pas-config", "w", False),
    ]
    assert bc.read_back_verdicts(runs, SCEN)["w"]["status"] == "verified"


def test_stamps_compare_as_numbers():
    runs = [
        rb("acao-ciclo-999999999", "w", False),
        rb("acao-ciclo-1000000000", "w", True),
    ]
    assert bc.read_back_verdicts(runs, SCEN)["w"]["status"] == "verified"


def test_a_read_from_a_refusal_logged_before_the_error_check_is_not_verified():
    """Audit finding: 22 lines said ok true with an Error-shaped answer."""
    assert not bc.proves_read(
        {"ok": True, "shape": {"Error": "str"}, "inputs": {"tipo": "acao"}}
    )
    assert bc.proves_read(
        {"ok": True, "shape": {"Return": "bool"}, "inputs": {"tipo": "acao"}}
    )


def test_a_read_sent_with_a_fake_id_is_not_verified():
    """Correction C012."""
    assert not bc.proves_read(
        {"ok": True, "shape": {"Itens": "list(0)"}, "inputs": {"ativoID": 0}}
    )


def test_a_run_that_stopped_early_keeps_the_verdicts_of_writes_it_never_reached():
    """Audit finding: a partial latest run moved 11 verified writes back to seen."""
    runs = [
        rb("ir-ciclo-1793730000", "darf", True),
        rb("ir-ciclo-1793730000", "stock", True),
        rb("ir-ciclo-1793734010", "darf", True),
    ]
    verdicts = bc.read_back_verdicts(runs, {"ir-ciclo"})
    assert verdicts["stock"]["status"] == "verified"
    assert verdicts["darf"]["evidence"].endswith("1793734010")


def test_a_read_back_that_could_not_run_counts_for_neither():
    runs = [
        rb("bond-ciclo-1793730000", "w", True),
        rb("bond-ciclo-1793730139", "w", None),
    ]
    verdict = bc.read_back_verdicts(runs, SCEN)["w"]
    assert verdict["status"] == "verified" and verdict["evidence"].endswith(
        "1793730000"
    )


def test_retype_widens_a_type_to_the_values_that_worked():
    prop = {"type": "string"}
    bc.retype(prop, ["2026-11-03", 5, None])
    assert prop["type"] == ["integer", "null", "string"]
    same = {"type": "string"}
    bc.retype(same, ["a", "b"])
    assert same == {"type": "string"}


def test_mcp_calls_never_change_the_catalog():
    assert not bc.trusted({"run": "mcp-1793734000"})
    assert bc.trusted({"run": "acao-ciclo-completo-1793734000"})


def test_repeated_flow_lines_are_dropped_but_screen_loads_are_kept():
    """Correction C006: three listeners logged the same SalvarMovimentacao call three times."""
    flow = {
        "flow": "acao-lancar-compra",
        "screen": "/bs2/ativos/acao",
        "url": "/x/SalvarMovimentacao",
        "body": "{}",
    }
    load = {"screen": "/bs2/", "url": "/x/BS2Init", "body": None}
    assert bc.dedupe_captures([flow, dict(flow), dict(flow), load, dict(load)]) == [
        flow,
        load,
        load,
    ]


def test_the_newest_passing_run_is_the_evidence():
    """Audit finding: excluir_item pointed at an archived cleanup run while its read-back came from acao-ciclo."""
    runs = [
        rb("acao-ciclo-1793730000", "w", True),
        rb("config-abas-salvar-1793720000", "w", True),
    ]
    assert bc.read_back_verdicts(runs, SCEN)["w"]["evidence"].endswith(
        "acao-ciclo-1793730000"
    )


def test_a_later_run_that_stopped_early_does_not_hide_a_failed_second_read_back():
    """Audit round 3: the edit read-back failed, then a run stopped after the first read-back of the same write."""
    runs = [
        rb("bdr-ciclo-100", "w", True, "compra_gravada"),
        rb("bdr-ciclo-100", "w", False, "compra_editada"),
        rb("bdr-ciclo-200", "w", True, "compra_gravada"),
    ]
    assert bc.read_back_verdicts(runs, {"bdr-ciclo"})["w"]["status"] == "failed"
