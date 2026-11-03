"""The crawler finds calls made through the ajaxProxy helper (correction C001) and splits names like the lint (C002)."""

import crawl
import gen_catalog


def test_extracts_calls_made_through_the_helper():
    js = 'f(){ajaxProxy(webServiceCarteira,"CarteiraCriar",JSON.stringify({nome:$.trim(x.val())}),function(n){})}'
    calls = crawl.extract_calls(js)
    assert [(c["service"], c["method"]) for c in calls] == [
        ("WS_Carteira", "CarteiraCriar")
    ]
    assert calls[0]["data"] == "JSON.stringify({nome:$.trim(x.val())})"


def test_extracts_direct_ajax_urls_and_quoted_services():
    js = '$.ajax({type:"POST",url:"/mercado/WebServices/WS_Carteira.asmx/ObterDetalhesAtivo",data:JSON.stringify({tipo:n,ativoID:1}),x:1});ajaxProxy(\'WS_Perfil\',"ConfigSalvar",d)'
    found = {(c["service"], c["method"]) for c in crawl.extract_calls(js)}
    assert found == {
        ("WS_Carteira", "ObterDetalhesAtivo"),
        ("WS_Perfil", "ConfigSalvar"),
    }


def test_ignores_helper_calls_to_non_service_names():
    assert crawl.extract_calls('ajaxProxy(rootThing,"X",{})') == []


def test_literal_keys_reads_object_payloads_only():
    assert gen_catalog.literal_keys(
        'JSON.stringify({tipo:n,ativoID:t.data("a,b")})'
    ) == ["tipo", "ativoID"]
    assert gen_catalog.literal_keys("JSON.stringify(l)") is None
    assert gen_catalog.literal_keys("{}") == []


def test_method_names_split_like_the_lint():
    import catalog_lint

    for name, snake in [
        ("BS2OndeRetirarCarregar", "bs2_onde_retirar_carregar"),
        ("ListarPASPercentual", "listar_pas_percentual"),
        ("PSFGList", "psfg_list"),
    ]:
        assert gen_catalog.snake(name) == snake
        assert "_".join(catalog_lint.camel_words(name)) == snake


def test_capture_only_method_is_not_excluded():
    """Correction C011: an empty script list is not 'only site-wide scripts'."""
    assert (
        gen_catalog.exclusion(
            {"scripts": [], "method": "ListarDiversificacaoPercentualGeral"}
        )
        is None
    )
    assert (
        gen_catalog.exclusion(
            {"scripts": ["/mercado/js/site.util-min.js"], "method": "SaveCookieConsent"}
        )
        is not None
    )


def test_never_run_methods_are_excluded_even_when_they_read():
    """Correction C025."""
    for method in (
        "IntegracaoB3Init",
        "RemessaOnlineGetAuthorization",
        "SorteioAtivosList",
        "TokenValidarSessao",
        "CarteiraExcluir",
    ):
        assert gen_catalog.exclusion(
            {"scripts": ["/mercado/js/site.bs2.ativos-min.js"], "method": method}
        )
