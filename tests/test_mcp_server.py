"""The MCP server applies the catalog rules before any call reaches Bastter. No test calls Bastter."""

import contextlib
import json
from pathlib import Path

import bastter_exec
import httpx
import mcp_server as srv
import pytest

ROOT = Path(__file__).resolve().parent.parent
tool = lambda t: getattr(t, "fn", t)


@pytest.fixture
def offline(monkeypatch, tmp_path):
    calls = []

    def fake_call(action_id, inputs, run, http=None, catalog=None, note=""):
        calls.append((action_id, inputs))
        return {"ok": True, "status": 200, "error": None, "payload": {"Return": True}}

    monkeypatch.setattr(bastter_exec, "call", fake_call)
    monkeypatch.setattr(bastter_exec, "PRIVATE_LOG", tmp_path / "mcp-runs.jsonl")
    monkeypatch.setattr(srv.session, "client", lambda: contextlib.nullcontext(None))
    return calls


def entry(action_id):
    return json.loads((ROOT / f"catalog/actions/{action_id}.json").read_text())


def by_status(status, op=None):
    for p in sorted((ROOT / "catalog/actions").glob("*.json")):
        e = json.loads(p.read_text())
        if e["verification"]["status"] == status and (
            op is None or e["operation_class"] == op
        ):
            return e
    pytest.skip(f"no {status} {op} action in the catalog")


def test_seen_action_does_not_run(offline):
    e = by_status("seen")
    reply = tool(srv.run_action)(e["id"], {})
    assert reply["ran"] is False and "status is seen" in reply["reason"]
    assert offline == []


def test_delete_needs_confirmation(offline):
    e = entry("bastter.ativos.excluir_movimentacao")
    inputs = {
        k: p["examples"][0] if p.get("examples") else 1
        for k, p in e["inputs"]["schema"]["properties"].items()
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert reply["ran"] is False and "confirmation" in reply["reason"]
    assert offline == []
    reply = tool(srv.run_action)(e["id"], inputs, confirmed=True)
    assert reply["ran"] is True and offline


def test_unknown_input_is_refused(offline):
    e = entry("bastter.ativos.salvar_movimentacao")
    reply = tool(srv.run_action)(e["id"], {"quantidadeX": 1})
    assert reply["ran"] is False and "unknown inputs" in reply["errors"][0]


def test_verified_write_returns_the_read_back(offline):
    e = entry("bastter.ativos.salvar_movimentacao")
    inputs = {
        k: p["examples"][0] for k, p in e["inputs"]["schema"]["properties"].items()
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert reply["ran"] is True
    assert e["postcondition"]["check_with"] in reply["next_step"]


def test_expired_session_is_explained(monkeypatch, offline):
    def expired(*a, **k):
        raise bastter_exec.SessionExpired("302")

    monkeypatch.setattr(bastter_exec, "call", expired)
    e = by_status("verified", "read")
    inputs = {
        k: p["examples"][0]
        for k, p in e["inputs"]["schema"].get("properties", {}).items()
        if p.get("examples")
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert reply["ran"] is False and "session expired" in reply["reason"]


def test_write_without_answer_is_unknown(monkeypatch, offline):
    def timeout(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(bastter_exec, "call", timeout)
    e = entry("bastter.ativos.salvar_movimentacao")
    inputs = {
        k: p["examples"][0] for k, p in e["inputs"]["schema"]["properties"].items()
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert reply["ran"] == "unknown" and "Before any retry" in reply["next_step"]


def test_portuguese_request_finds_the_buy_action():
    ids = [
        r["id"]
        for r in tool(srv.find_actions)("lança uma compra de VALE3 na minha carteira")
    ]
    assert "bastter.ativos.salvar_movimentacao" in ids[:5]


def test_a_refused_write_returns_the_error(monkeypatch, offline):
    """Audit test gap: the not-ok branch had no test."""
    monkeypatch.setattr(
        bastter_exec,
        "call",
        lambda *a, **k: {
            "ok": False,
            "status": 200,
            "error": "the answer has Error: Erro ao salvar.",
            "payload": {"Error": "Erro ao salvar."},
        },
    )
    e = entry("bastter.ativos.salvar_movimentacao")
    inputs = {
        k: p["examples"][0] for k, p in e["inputs"]["schema"]["properties"].items()
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert (
        reply["ran"] is True
        and "Erro ao salvar" in reply["error"]
        and "response" not in reply
    )


def test_a_write_answered_by_an_error_page_is_unknown(monkeypatch, offline):
    """Audit finding: an HTML 5xx after the POST does not prove the write did not run."""
    monkeypatch.setattr(
        bastter_exec,
        "call",
        lambda *a, **k: {
            "ok": False,
            "status": 503,
            "error": "HTML answer with status 503 (a server error page, not the web service)",
            "payload": None,
        },
    )
    e = entry("bastter.ativos.salvar_movimentacao")
    inputs = {
        k: p["examples"][0] for k, p in e["inputs"]["schema"]["properties"].items()
    }
    reply = tool(srv.run_action)(e["id"], inputs)
    assert reply["ran"] == "unknown" and "Before any retry" in reply["next_step"]


def test_ids_outside_the_catalog_pattern_are_rejected(offline):
    """Audit finding: "../index" used to load catalog/index.json."""
    assert tool(srv.get_action)("../index") == {
        "error": "unknown action ../index. Use find_actions."
    }
    assert tool(srv.run_action)("../../catalog/claims", {})["ran"] is False


def examples(e):
    return {
        k: p["examples"][0]
        for k, p in e["inputs"]["schema"].get("properties", {}).items()
        if p.get("examples")
    }


def test_a_write_that_did_not_reach_bastter_did_not_run(monkeypatch, offline):
    def refused(*a, **k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(bastter_exec, "call", refused)
    reply = tool(srv.run_action)(
        "bastter.ativos.salvar_movimentacao",
        examples(entry("bastter.ativos.salvar_movimentacao")),
    )
    assert reply["ran"] is False and "did not reach" in reply["reason"]


@pytest.mark.parametrize(
    "status,error",
    [
        (500, "InvalidOperationException: There was an error processing the request."),
        (502, "non-JSON answer (11 characters, content type text/plain)"),
    ],
)
def test_a_write_answered_by_a_server_error_is_unknown(
    monkeypatch, offline, status, error
):
    """Audit finding: a 500 or a non-JSON answer after the POST does not prove the write did not run."""
    monkeypatch.setattr(
        bastter_exec,
        "call",
        lambda *a, **k: {
            "ok": False,
            "status": status,
            "error": error,
            "payload": None,
        },
    )
    reply = tool(srv.run_action)(
        "bastter.ativos.salvar_movimentacao",
        examples(entry("bastter.ativos.salvar_movimentacao")),
    )
    assert reply["ran"] == "unknown" and "Before any retry" in reply["next_step"]


def test_a_public_write_never_runs_even_when_confirmed(offline):
    """Audit finding: the activity diary feeds a public ranking and ran with no question."""
    e = entry("bastter.pas.diario_atividade_salvar")
    assert e["side_effects"]["external_effect"] == "publishes"
    reply = tool(srv.run_action)(e["id"], examples(e), confirmed=True)
    assert reply["ran"] is False and "other users" in reply["reason"]
    assert offline == []


@pytest.mark.parametrize(
    "action,key",
    [
        ("bastter.pas.agradecer_salvar", "agradecimento"),
        ("bastter.pas.diario_sardinhagem_salvar", "sardinhagem"),
    ],
)
def test_a_private_entry_cannot_be_sent_as_public(offline, action, key):
    """Correction C021, and the audit finding that a key in other case could pass the pin."""
    e = entry(action)
    body = examples(e)
    assert tool(srv.run_action)(action, body)["ran"] is True
    public = {key: {**body[key], "privado": False}}
    assert tool(srv.run_action)(action, public)["ran"] is False
    mixed = {key: {**body[key], "Privado": False}}
    reply = tool(srv.run_action)(action, mixed)
    assert reply["ran"] is False and "differ only in case" in reply["errors"][0]
    extra = {key: {**body[key], "Publico": True}}
    assert tool(srv.run_action)(action, extra)["ran"] is False


def test_a_refused_call_is_logged_privately(offline):
    tool(srv.run_action)(by_status("seen")["id"], {})
    line = json.loads((bastter_exec.PRIVATE_LOG).read_text().splitlines()[-1])
    assert line["run"].startswith("mcp-") and line["error"].startswith(
        "not sent: status is seen"
    )


PUBLIC_WRITES = [
    "bastter.pas.diario_atividade_salvar",
    "bastter.pas.diario_atividade_excluir",
    "bastter.pas.diario_salvar",
    "bastter.saude.gym_save_treino",
    "bastter.saude.gym_delete_treino",
    "bastter.saude.race_atividade_salvar",
    "bastter.saude.race_atividade_excluir",
    "bastter.saude.race_alimentacao_save",
    "bastter.saude.race_inspiracao_salvar",
    "bastter.saude.parou_beber_save",
    "bastter.saude.race_pendencia_salvar",
]


@pytest.mark.parametrize("action_id", PUBLIC_WRITES)
def test_every_known_public_write_is_marked_and_never_runs(offline, action_id):
    """Corrections C030 and C036: each write that other users can see stays marked, whatever its status."""
    e = entry(action_id)
    assert e["side_effects"]["external_effect"] in srv.NEVER_RUN
    reply = tool(srv.run_action)(action_id, examples(e), confirmed=True)
    assert reply["ran"] is False and offline == []
