"""Realistic user requests, written without looking at the labels, must find the right action in the top 5."""

import mcp_server as srv
import pytest

find = getattr(srv.find_actions, "fn", srv.find_actions)

CASES = [
    ("lança uma compra de 10 VALE3", {"bastter.ativos.salvar_movimentacao"}),
    (
        "apaga a compra de PETR4 que lancei errado",
        {"bastter.ativos.excluir_movimentacao"},
    ),
    ("adiciona HGLG11 na minha carteira de FIIs", {"bastter.ativos.salvar"}),
    ("quais ações eu tenho na carteira?", {"bastter.ativos.obter_itens"}),
    ("registra um gasto de 50 reais no mercado", {"bastter.financeiro.financa_salvar"}),
    ("lista meus DARFs", {"bastter.imposto_de_renda.irdarf_listar"}),
    (
        "quanto recebi de dividendos esse ano",
        {
            "bastter.ativos.consolidado_obter_proventos",
            "bastter.ativos.meu_bs_proventos",
        },
    ),
    (
        "onde devo aportar este mês",
        {
            "bastter.consolidado.onde_aportar_consolidado_obter",
            "bastter.patrimonio.bs2_visao_geral_onde_aportar",
        },
    ),
    ("anota meu humor de hoje", {"bastter.saude.diario_humor_salvar"}),
    ("cria uma meta de juntar 10 mil", {"bastter.pas.metas_salvar"}),
    ("busca o código do Itaú", {"bastter.ativos.pesquisar"}),
    ("registra meu treino de hoje na academia", {"bastter.saude.gym_save_treino"}),
]


@pytest.mark.parametrize("request_text,expected", CASES, ids=[c[0] for c in CASES])
def test_request_finds_the_action(request_text, expected):
    ids = [r["id"] for r in find(request_text, limit=5)]
    assert expected & set(ids), f"top 5 for {request_text!r}: {ids}"
