"""Builds the base catalog entries from the web service calls found in the BS2 scripts.

Input: .cache/discover/ws_snippets.json (written by sources/discover/crawl.py).
Output: catalog/generated.json, one base entry per in-scope method, all with status `seen` or `excluded`.
tools/build_catalog.py adds the live evidence and the curation on top.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNIPPETS = ROOT / ".cache/discover/ws_snippets.json"
PAGES = ROOT / "sources/discover/pages.json"
OUT = ROOT / "catalog/generated.json"
WS_URL = "https://bastter.com/mercado/WebServices/{service}.asmx/{method}"

SITE_SHELL_SCRIPTS = {
    "/mercado/js/site.util-min.js",
    "/mercado/js/site.bs2.notificacoes-min.js",
}

READ = {
    "Obter",
    "Listar",
    "List",
    "Get",
    "Carregar",
    "Consultar",
    "Pega",
    "Buscar",
    "Pesquisa",
    "Search",
    "Init",
    "Resumo",
    "Rank",
    "Ranking",
    "Historico",
    "Indice",
    "Exists",
    "Possui",
    "Filtrar",
    "Stats",
    "Cotar",
    "Simular",
    "Consolidado",
    "Graficos",
    "Dados",
    "Variacao",
    "Percentuais",
    "Eventos",
    "Postagens",
    "Detalhes",
    "Is",
}
CREATE = {
    "Criar",
    "Incluir",
    "Adicionar",
    "Inserir",
    "Cadastrar",
    "Copiar",
    "Importar",
    "Solicitar",
    "Sortear",
}
SAVE = {
    "Salvar",
    "Save",
    "Alternar",
    "Atualizar",
    "Update",
    "Alterar",
    "Marcar",
    "Mover",
    "Ordena",
    "Habilitar",
    "Desabilitar",
    "Ocultar",
    "Lido",
}
DELETE = {"Excluir", "Deletar", "Delete", "Remover", "Limpar", "Zerar"}
NOTIFY = ("Notificacao", "EnviarEmail", "Email", "Compartilha", "Topico")
ACCOUNT = ("Auth", "Token", "B3", "Integracao", "Importar", "Strava", "Senha")
ADMIN = ("FAQSalvar", "FAQDeletar", "AlertaCriticoRegrasSave")

AREA_BY_SEGMENT = {
    "patrimonio": "Patrimônio",
    "ativos": "Ativos",
    "financeiro": "Financeiro",
    "imposto-de-renda": "Imposto de Renda",
    "consolidado": "Consolidado",
    "saude": "Saúde",
    "pas": "PAS",
    "ferramentas": "Ferramentas",
    "configuracoes": "Configurações",
    "modos": "Configurações",
    "faq": "FAQ",
    "home-custom": "Home",
    "exportar": "Ferramentas",
}

AREA_SLUG = {
    "Patrimônio": "patrimonio",
    "Ativos": "ativos",
    "Financeiro": "financeiro",
    "Imposto de Renda": "imposto_de_renda",
    "Consolidado": "consolidado",
    "Saúde": "saude",
    "PAS": "pas",
    "Ferramentas": "ferramentas",
    "Configurações": "configuracoes",
    "FAQ": "faq",
    "Home": "home",
    "Bastter System": "geral",
}


def words(method: str) -> list[str]:
    """Method name words, split the same way the lint splits them (catalog_lint.camel_words)."""
    return [
        w
        for w in re.split(
            r"\s+",
            re.sub(
                r"([A-Z]+)([A-Z][a-z])",
                r"\1 \2",
                re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", method),
            ),
        )
        if w
    ]


def snake(method: str) -> str:
    return "_".join(w.lower() for w in words(method))


def classify(method: str) -> str:
    ws = words(method)
    if any(w in DELETE for w in ws):
        return "delete"
    if any(w in CREATE for w in ws):
        return "create"
    if any(w in SAVE for w in ws):
        return "update"
    if any(w in READ for w in ws):
        return "read"
    return "action"


def entity_of(method: str) -> str:
    verbs = READ | CREATE | SAVE | DELETE
    rest = [
        w for w in words(method) if w not in verbs and w not in {"BS2", "Um", "Pega"}
    ]
    return "_".join(w.lower() for w in rest) or snake(method)


def area_of(screens: list[str]) -> str:
    segs = [s.split("/")[2] for s in screens if s.count("/") >= 2]
    for seg in segs:
        if seg in AREA_BY_SEGMENT:
            return AREA_BY_SEGMENT[seg]
    return "Bastter System"


OBJ_RE = re.compile(r"^JSON\.stringify\(\{(.*)\}\)$", re.DOTALL)


def literal_keys(data: str) -> list[str] | None:
    """Keys of a JSON.stringify({...}) argument, or None when the payload is built elsewhere."""
    data = data.strip()
    if data in ("", "{}", "'{}'", '"{}"', "JSON.stringify({})"):
        return []
    m = OBJ_RE.match(data)
    if not m:
        return None
    body, keys, depth, token = m.group(1), [], 0, ""
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0 and ch == ",":
            token = ""
            continue
        token += ch
        if (
            depth == 0
            and ch == ":"
            and re.fullmatch(r"\s*[A-Za-z_$][A-Za-z0-9_$]*\s*:", token)
        ):
            keys.append(token.strip()[:-1])
    return keys


def input_schema(data_args: list[str]) -> tuple[dict, list[str]]:
    keysets = [k for k in (literal_keys(d) for d in data_args) if k is not None]
    if not keysets:
        return {
            "type": "object",
            "additionalProperties": True,
            "description": "The scripts build this payload elsewhere. See `routes[0].notes` for the JS expression.",
        }, []
    keys = sorted(set().union(*keysets))
    props = {}
    for k in keys:
        if re.search(r"(ID|Id)$", k):
            props[k] = {"type": "integer", "description": f"ID of the {k[:-2]}."}
        elif k in {"ano", "mes", "dia", "page", "pageSize", "top", "periodo", "tipo"}:
            props[k] = {"type": ["integer", "string"]}
        else:
            props[k] = {}
    return {
        "type": "object",
        "properties": props,
        "required": keys,
        "additionalProperties": False,
    }, keys


def label_of(method: str, op: str) -> str:
    verb = {
        "read": "Ler",
        "create": "Criar",
        "update": "Salvar",
        "delete": "Excluir",
        "action": "Executar",
    }[op]
    ent = " ".join(
        w.lower()
        for w in words(method)
        if w not in READ | CREATE | SAVE | DELETE and w != "BS2"
    )
    return f"{verb} {ent}".strip() if ent else method


def exclusion(entry: dict) -> str | None:
    if entry["scripts"] and set(entry["scripts"]) <= SITE_SHELL_SCRIPTS:
        return (
            "site-wide shell script (cookies, notifications, email), not a BS2 feature"
        )
    if entry["method"] in ADMIN:
        return "admin-only method (edits content for every user)"
    forbidden = next((t for t in FORBIDDEN if t in entry["method"]), None)
    if forbidden:
        return f"never run: '{forbidden}' methods reach other people, security, integrations or imports, or need the account password (docs/SCENARIO_GUIDE.md rule 6)"
    return None


# Name parts of methods that no script or agent may call, reads included (docs/SCENARIO_GUIDE.md rule 6).
FORBIDDEN = (
    "Notificacao",
    "CarteiraExcluir",
    "EnviarEmail",
    "Token",
    "AuthApp",
    "IntegracaoB3",
    "RemessaOnline",
    "Importar",
    "Strava",
    "SolicitarAnalise",
    "PedirBDR",
    "PedirETF",
    "Topico",
    "Compartilha",
    "Sorteio",
)


def side_effects(method: str, op: str) -> dict:
    notify = op != "read" and any(t in method for t in NOTIFY)
    account = op != "read" and any(t in method for t in ACCOUNT)
    effect = "notifies_people" if notify else "changes_account" if account else "none"
    irreversible = op == "delete" or method in {"CarteiraExcluir"}
    return {
        "reversible": op == "read" or not irreversible,
        "undo_with": None,
        "external_effect": effect,
        "idempotent": True if op == "read" else None,
        "requires_confirmation": op != "read" and (irreversible or effect != "none"),
    }


SESSION_IDS = {"carteiraID", "usuarioID", "usuarioIDMeta"}
# Lists that return the IDs other actions need. A finder must not need an unknown ID itself.
FINDERS = {
    "ativo": "bastter.ativos.bs2_list_ativos",
    "carteira": "bastter.ativos.bs2_init",
    "carteiras": "bastter.ativos.bs2_init",
}


def needs_unknown_id(entry: dict) -> bool:
    required = entry["inputs"]["schema"].get("required") or []
    return any(re.search(r"(ID|Id)$", k) and k not in SESSION_IDS for k in required)


def main() -> None:
    snippets = json.loads(SNIPPETS.read_text())
    for path in sorted((ROOT / "evidence").glob("ui-capture-*.jsonl")):
        for line in path.read_text().splitlines():
            c = json.loads(line)
            service, method = c["url"].rstrip("/").rsplit("/", 2)[-2:]
            key = f"{service.replace('.asmx', '')}.{method}"
            if key not in snippets:
                snippets[key] = {
                    "service": key.split(".")[0],
                    "method": method,
                    "scripts": [],
                    "screens": [c["screen"]],
                    "data_args": [],
                    "snippets": [],
                    "capture_only": True,
                }
            elif (
                snippets[key].get("capture_only")
                and c["screen"] not in snippets[key]["screens"]
            ):
                snippets[key]["screens"].append(c["screen"])
    pages = json.loads(PAGES.read_text())
    entries = []
    for key, e in sorted(snippets.items()):
        method, service = e["method"], e["service"]
        op = classify(method)
        screens = sorted(e["screens"])
        schema, keys = input_schema(e["data_args"])
        excluded = exclusion(e)
        titles = sorted(
            {
                pages[s]["title"].replace("Bastter System - ", "")
                for s in screens
                if pages.get(s, {}).get("title")
            }
        )
        entry = {
            "id": f"bastter.{AREA_SLUG[area_of(screens)]}.{snake(method)}",
            "product": "bastter",
            "area": area_of(screens),
            "entity": entity_of(method),
            "operation_class": op,
            "label": label_of(method, op),
            "description": f"{service}.{method}. Called from: {', '.join(titles[:6]) or ', '.join(screens[:3])}.",
            "inputs": {
                "schema": schema,
                "entity_refs": [],
                "credential_ref": "bastter_session_cookie",
            },
            "routes": [
                {
                    "kind": "undocumented_api",
                    "method": "POST",
                    "url": WS_URL.format(service=service, method=method),
                    "auth": "web session cookie (SessionV3)",
                    "params": {k: "body" for k in keys},
                    "success_status": [200],
                    "notes": 'ASP.NET web service. Body is JSON with every parameter, the answer is {"d": ...}. '
                    f"JS payload: {e['data_args'][0][:300] if e['data_args'] else '(none)'}",
                },
                {
                    "kind": "ui_path",
                    "start_url": f"https://bastter.com{screens[0]}"
                    if screens
                    else "https://bastter.com/bs2",
                },
            ],
            "preconditions": [],
            "postcondition": None,
            "side_effects": side_effects(method, op),
            "availability": {"status": "unknown", "requires": []},
            "verification": {
                "status": "excluded" if excluded else "seen",
                "route_kind": None,
                "checked_at": None,
                "evidence": None,
                "notes": excluded
                or f"Found in {', '.join(sorted(e['scripts']))}. Not run yet.",
            },
            "sources": [{"kind": "js_bundle", "ref": s} for s in sorted(e["scripts"])]
            + (
                [
                    {
                        "kind": "network_capture",
                        "ref": "evidence/ui-capture (found only in the browser capture)",
                    }
                ]
                if e.get("capture_only")
                else []
            )
            + [{"kind": "ui_walk", "ref": s} for s in screens[:5]],
        }
        entries.append(entry)

    by_id = {en["id"]: en for en in entries}
    assert set(FINDERS.values()) <= set(by_id), (
        f"unknown finders {set(FINDERS.values()) - set(by_id)}"
    )
    by_entity_read: dict[str, list[str]] = {}
    for en in entries:
        if (
            en["operation_class"] == "read"
            and en["verification"]["status"] != "excluded"
        ):
            by_entity_read.setdefault(en["entity"], []).append(en["id"])

    def ranked(entity: str, known: set[str]) -> list[str]:
        """Readers of an entity whose required IDs are all known, curated finder first, then lists."""
        usable = [
            i
            for i in by_entity_read.get(entity, [])
            if all(
                k in known or k in SESSION_IDS
                for k in by_id[i]["inputs"]["schema"].get("required") or []
                if re.search(r"(ID|Id)$", k)
            )
        ]
        usable.sort(key=lambda i: ("listar" not in i and "list" not in i, i))
        curated = FINDERS.get(entity)
        return [curated] + [i for i in usable if i != curated] if curated else usable

    for en in entries:
        for k in en["inputs"]["schema"].get("properties", {}):
            if re.search(r"(ID|Id)$", k):
                target = re.sub(r"(ID|Id)$", "", k).lower()
                finders = ranked(target, set())
                en["inputs"]["entity_refs"].append(
                    {
                        "input": k,
                        "entity": target,
                        "find_with": finders[0] if finders else None,
                        "create_with": None,
                    }
                )
        if en["operation_class"] in {"create", "update", "delete"}:
            finders = ranked(
                en["entity"], set(en["inputs"]["schema"].get("properties", {}))
            )
            if finders:
                en["postcondition"] = {
                    "check_with": finders[0],
                    "assert": {
                        "create": "the new item is in the list with the fields that were sent",
                        "update": "the item in the list shows the new values",
                        "delete": "the item is no longer in the list",
                    }[en["operation_class"]],
                }
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids)), "duplicate ids"
    OUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    counts = {}
    for e in entries:
        k = (e["verification"]["status"], e["operation_class"])
        counts[k] = counts.get(k, 0) + 1
    print(f"wrote {len(entries)} entries to {OUT.relative_to(ROOT)}")
    for k in sorted(counts):
        print(" ", k, counts[k])


if __name__ == "__main__":
    main()
