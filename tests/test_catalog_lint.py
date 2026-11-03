"""Lint checks on hand-made entries, and the built catalog has no lint error."""

import json
from pathlib import Path

import catalog_lint as cl

ROOT = Path(__file__).resolve().parent.parent


def entry(**over):
    e = {
        "id": "bastter.ativos.carteira_excluir",
        "operation_class": "delete",
        "entity": "carteira",
        "inputs": {
            "schema": {
                "type": "object",
                "properties": {"carteiraID": {}},
                "required": ["carteiraID"],
            },
            "entity_refs": [],
        },
        "routes": [
            {
                "kind": "undocumented_api",
                "url": "https://bastter.com/mercado/WebServices/WS_Carteira.asmx/CarteiraExcluir",
            }
        ],
        "side_effects": {
            "reversible": False,
            "external_effect": "none",
            "requires_confirmation": True,
            "undo_with": None,
        },
        "verification": {"status": "seen"},
        "postcondition": None,
    }
    e.update(over)
    return e


def test_delete_without_confirmation_is_an_error():
    e = entry(
        side_effects={
            "reversible": True,
            "external_effect": "none",
            "requires_confirmation": False,
            "undo_with": None,
        }
    )
    assert any(f.check == "L007" for f in cl.lint({e["id"]: e}))


def test_id_must_keep_the_method_words():
    e = entry(id="bastter.ativos.carteira_apagar")
    assert any(f.check == "L001" for f in cl.lint({e["id"]: e}))


def test_observed_entry_must_match_the_captured_fields():
    e = entry(
        verification={"status": "observed", "captured_keys": ["carteiraID", "senha"]}
    )
    assert any(f.check == "L010" for f in cl.lint({e["id"]: e}))


def test_finder_that_needs_an_unknown_id_is_an_error():
    finder = entry(
        id="bastter.ativos.obter_detalhes_ativo",
        operation_class="read",
        inputs={
            "schema": {"properties": {"ativoID": {}}, "required": ["ativoID"]},
            "entity_refs": [],
        },
        routes=[{"kind": "undocumented_api", "url": "x/ObterDetalhesAtivo"}],
    )
    user = entry(
        inputs={
            "schema": {"properties": {"ativoID": {}}, "required": ["ativoID"]},
            "entity_refs": [
                {"input": "ativoID", "entity": "ativo", "find_with": finder["id"]}
            ],
        }
    )
    assert any(
        f.check == "L002" for f in cl.lint({user["id"]: user, finder["id"]: finder})
    )


def test_built_catalog_has_no_lint_error():
    actions = {
        json.loads(p.read_text())["id"]: json.loads(p.read_text())
        for p in (ROOT / "catalog/actions").glob("*.json")
    }
    errors = [f for f in cl.lint(actions) if f.severity == "error"]
    assert errors == []


def test_date_field_without_format_is_an_error():
    """Correction C017: the demo agent sent dd/mm to a field that takes mm/dd, because the entry did not say."""
    props = {
        "data": {"type": "string", "examples": ["11/03/2026"]},
        "dia": {"type": "object", "examples": [{"data": "2026-11-03"}]},
    }
    e = entry(
        id="bastter.ativos.salvar_movimentacao",
        operation_class="update",
        inputs={"schema": {"properties": props}, "entity_refs": []},
        routes=[{"kind": "undocumented_api", "url": "x/SalvarMovimentacao"}],
        side_effects={
            "reversible": True,
            "external_effect": "none",
            "requires_confirmation": False,
            "undo_with": None,
        },
        verification={"status": "verified", "evidence": "e", "checked_at": "t"},
    )
    found = [f.message for f in cl.lint({e["id"]: e}) if f.check == "L012"]
    assert len(found) == 2
    props["data"]["description"] = "Date format: mm/dd/yyyy."
    props["dia"]["description"] = "Date format of data: yyyy-mm-dd."
    assert not [f for f in cl.lint({e["id"]: e}) if f.check == "L012"]


def test_verified_write_without_read_back_is_an_error():
    e = entry(
        operation_class="update",
        verification={"status": "verified", "evidence": "e", "checked_at": "t"},
        side_effects={
            "reversible": True,
            "external_effect": "none",
            "requires_confirmation": False,
            "undo_with": None,
        },
    )
    assert any(f.check == "L013" for f in cl.lint({e["id"]: e}))
