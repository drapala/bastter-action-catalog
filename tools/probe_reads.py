"""Calls every read action whose status is seen, once, with inputs inferred from the field names.

The server hides error details (correction C005), so a refused call cannot tell which field was wrong. A read that
answers 200 with no Error, with no fake ID in its inputs, becomes verified in the next build. A call that needed
a fake ID (0 or empty) is marked placeholder and proves nothing. Methods in the never-run list are excluded and
never probed.

Writes evidence/runs.jsonl (one line per call, run id probe-reads-<time>).
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import bastter_exec
import httpx
import session

PARAMS = ROOT / "sources/discover/params.json"
ASSET_TYPES = {
    "acao",
    "fii",
    "stock",
    "reit",
    "rendafixa",
    "moeda",
    "europa",
    "bond",
    "imovel",
    "etf",
    "bdr",
    "re",
    "outro",
    "fixo",
}
MISSING_RE = bastter_exec.MISSING_RE
SESSION_IDS = {"carteiraID", "usuarioID", "usuarioIDMeta", "carteirasID"}
CONVERT_RE = re.compile(
    r"Cannot convert (?:object of type|null to a value of type) '?([^' ]+)'?(?: to type '([^']+)')?",
    re.IGNORECASE,
)


def account_ids(http) -> dict:
    _status, payload, error = bastter_exec.raw_call(
        http, "/mercado/WebServices/WS_Carteira.asmx/BS2Init", {}
    )
    if error:
        raise RuntimeError(f"BS2Init failed: {error}")
    return {
        "usuarioID": payload["UsuarioID"],
        "carteiraID": payload["Carteiras"][0]["CarteiraID"],
    }


def screen_type(action: dict) -> str:
    for src in action["sources"]:
        parts = src["ref"].split("/")
        for p in parts:
            if p in ASSET_TYPES:
                return p
    return "acao"


def infer(name: str, action: dict, ids: dict):
    n = name.lower()
    if n in ("usuarioid", "usuarioidmeta"):
        return ids["usuarioID"]
    if n == "carteiraid":
        return ids["carteiraID"]
    if n == "carteirasid":
        return [ids["carteiraID"]]
    if n in ("tipo", "classe", "tipoativo"):
        return screen_type(action)
    if n == "ano":
        return 2026
    if n == "mes":
        return 11
    if n in ("page", "pagina"):
        return 1
    if n in ("pagesize", "top", "quantidade", "limite"):
        return 10
    if n.startswith(("is", "somente")) or n in ("automatico", "dolar"):
        return False
    if n in ("termo", "busca", "texto", "codigo", "ativo", "ticker"):
        return "PETR4"
    if n in ("classes", "hashs", "ids", "itens"):
        return []
    if n in ("data", "datainicio", "datafim", "dia", "datareferencia"):
        return "2026-11-03"
    if n.endswith(("id", "ids")):
        return 0
    if n in ("periodo", "ordenacao", "ordem", "aba"):
        return 0
    return ""


def probe(action: dict, ids: dict, http, run: str) -> dict:
    keys = list(action["inputs"]["schema"].get("properties", {}))
    inputs = {k: infer(k, action, ids) for k in keys}
    asked, retried = [], False
    for _ in range(10):
        out = bastter_exec.call(
            action["id"],
            inputs,
            run=run,
            http=http,
            catalog={action["id"]: action},
            note="placeholder" if bastter_exec.placeholder_ids(inputs) else "",
        )
        m = MISSING_RE.search(out["error"] or "")
        if m and m.group(1) not in inputs:
            asked.append(m.group(1))
            inputs[m.group(1)] = infer(m.group(1), action, ids)
            continue
        conv = CONVERT_RE.search(out["error"] or "")
        if conv and not retried:
            swapped = {
                k: (str(v) if isinstance(v, int) and not isinstance(v, bool) else v)
                for k, v in inputs.items()
            }
            if "Int" in (conv.group(2) or conv.group(1)):
                swapped = {k: (0 if v == "" else v) for k, v in inputs.items()}
            if swapped != inputs:
                inputs, retried = swapped, True
                continue
        return {
            "inputs": inputs,
            "asked": asked,
            "ok": out["ok"],
            "error": out["error"],
        }
    return {
        "inputs": inputs,
        "asked": asked,
        "ok": False,
        "error": "gave up after 10 calls",
    }


def main() -> None:
    http = session.client()
    if not session.logged_in(http):
        sys.exit("The Bastter session expired.")
    ids = account_ids(http)
    catalog = bastter_exec.load_catalog()
    only = set(sys.argv[1:])
    run = f"probe-reads-{int(time.time())}"
    params = json.loads(PARAMS.read_text()) if PARAMS.exists() else {}
    results = {"ok": 0, "error": 0}
    for aid, action in sorted(catalog.items()):
        if (
            action["operation_class"] != "read"
            or action["verification"]["status"] == "excluded"
        ):
            continue
        if only and aid not in only:
            continue
        try:
            res = probe(action, ids, http, run)
        except httpx.RequestError as error:
            bastter_exec.log(
                {
                    "run": run,
                    "action": aid,
                    "status": None,
                    "ok": False,
                    "error": f"no answer: {error!r}",
                }
            )
            res = {"inputs": {}, "ok": False, "error": f"no answer: {error!r}"}
        method = ".".join(
            bastter_exec.api_route(action)["url"].rsplit("/", 2)[-2:]
        ).replace(".asmx", "")
        params[method] = sorted(res["inputs"])
        results["ok" if res["ok"] else "error"] += 1
        print(
            f"{'OK ' if res['ok'] else 'ERR'} {aid} {json.dumps(res['inputs'], ensure_ascii=False)[:120]} {(res['error'] or '')[:120]}"
        )
    PARAMS.write_text(json.dumps(params, indent=2, sort_keys=True) + "\n")
    print(f"run {run}: {results}")


if __name__ == "__main__":
    main()
