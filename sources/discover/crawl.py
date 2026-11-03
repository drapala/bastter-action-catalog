"""Crawls every BS2 screen and the scripts it loads, then lists each web service method the scripts call.

Run from the repo root: .venv/bin/python sources/discover/crawl.py
Only GET requests. Raw HTML and JS go to .cache/ (not committed), because pages show account data.

Writes:
- sources/discover/pages.json: per screen, the title, the BS2 scripts, the HTML fragments it loads, and its buttons.
- sources/discover/ws_calls.json: per web service method, the scripts and screens that call it, and the code around each call.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import session

CACHE = ROOT / ".cache/discover"
OUT = ROOT / "sources/discover"
PAGES = [
    p.strip() for p in (OUT / "bs2_pages.txt").read_text().splitlines() if p.strip()
]

SCRIPT_RE = re.compile(r'<script[^>]+src="([^"]+)"', re.IGNORECASE)
FRAGMENT_RE = re.compile(r'["\'](/mercado/[cC]ontrols/[^"\'?#]+\.(?:html|aspx))', re.IGNORECASE)
WS_RE = re.compile(r"(WS_[A-Za-z0-9]+)\.asmx/([A-Za-z0-9_]+)")
BUTTON_RE = re.compile(r"<(button|a)\b([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

SERVICE_VARS = {"webServiceCarteira": "WS_Carteira"}
PROXY_RE = re.compile(r"ajaxProxy\(\s*([A-Za-z_$][A-Za-z0-9_$]*|[\"'][A-Za-z_]+[\"'])\s*,\s*[\"']([A-Za-z0-9_]+)[\"']\s*,")


def balanced_arg(text: str, start: int) -> str:
    """Returns the JS expression that starts at `start` and ends at the next top-level comma or closing paren."""
    depth, i, quote = 0, start, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        i += 1
    return text[start:i].strip()


def extract_calls(text: str) -> list[dict]:
    """Finds web service calls made through the ajaxProxy helper or a direct $.ajax url."""
    out = []
    for m in PROXY_RE.finditer(text):
        svc = m.group(1).strip("\"'")
        svc = SERVICE_VARS.get(svc, svc)
        if not svc.lower().startswith("ws"):
            continue
        out.append({"service": svc, "method": m.group(2), "data": balanced_arg(text, m.end())[:600], "snippet": text[max(0, m.start() - 300) : m.end() + 500]})
    for m in WS_RE.finditer(text):
        data = re.search(r"data:\s*", text[m.end() : m.end() + 200])
        arg = balanced_arg(text, m.end() + data.end()) if data else ""
        out.append({"service": m.group(1), "method": m.group(2), "data": arg[:600], "snippet": text[max(0, m.start() - 300) : m.end() + 500]})
    return out


def fetch(http, path: str) -> str:
    key = CACHE / (hashlib.sha1(path.encode()).hexdigest() + ".txt")
    if key.exists():
        return key.read_text()
    r = http.get(path)
    time.sleep(0.4)
    if r.status_code != 200:
        return f"__HTTP_{r.status_code}__ {r.headers.get('location', '')}"
    key.write_text(r.text)
    return r.text


def own_script(src: str) -> str | None:
    src = src.split("?")[0]
    src = src.removeprefix("https://bastter.com")
    if not src.startswith("/"):
        return None
    name = src.rsplit("/", 1)[-1].lower()
    return src if name.startswith("site.") else None


def buttons(html: str) -> list[dict]:
    out = []
    for _, attrs, inner in BUTTON_RE.findall(html):
        text = re.sub(r"\s+", " ", TAG_RE.sub(" ", inner)).strip()
        hook = re.search(
            r'(onclick|data-acao|data-action|id|class)="([^"]{1,120})"', attrs
        )
        if (
            text
            and len(text) < 60
            and ("onclick" in attrs or "data-" in attrs or "btn" in attrs)
        ):
            out.append(
                {
                    "text": text,
                    "hook": f"{hook.group(1)}={hook.group(2)}" if hook else "",
                }
            )
    return out


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    http = session.client()
    if not session.logged_in(http):
        sys.exit(
            "The Bastter session expired. Log in again in the browser and store the cookies."
        )
    pages, scripts, fragments = {}, {}, {}
    for path in PAGES:
        html = fetch(http, path)
        if html.startswith("__HTTP_"):
            pages[path] = {"error": html}
            continue
        title = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        own = sorted({s for s in (own_script(x) for x in SCRIPT_RE.findall(html)) if s})
        frags = sorted(set(FRAGMENT_RE.findall(html)))
        inline_ws = sorted({f"{s}.{m}" for s, m in WS_RE.findall(html)})
        pages[path] = {
            "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
            "scripts": own,
            "fragments": frags,
            "inline_ws_calls": inline_ws,
            "buttons": buttons(html),
        }
        for s in own:
            scripts.setdefault(s, set()).add(path)
        for f in frags:
            fragments.setdefault(f, set()).add(path)
        for call in inline_ws:
            scripts.setdefault(f"inline:{path}", set()).add(path)

    calls: dict[str, dict] = {}
    sources = [(src, src.removeprefix("inline:"), used_on) for src, used_on in scripts.items()]
    sources += [(frag, frag, used_on) for frag, used_on in fragments.items()]
    for label, url, used_on in sorted(sources):
        for call in extract_calls(fetch(http, url)):
            key = f"{call['service']}.{call['method']}"
            entry = calls.setdefault(
                key, {"service": call["service"], "method": call["method"], "scripts": set(), "screens": set(), "data_args": [], "snippets": []}
            )
            entry["scripts"].add(label)
            entry["screens"].update(used_on)
            if call["data"] not in entry["data_args"] and len(entry["data_args"]) < 4:
                entry["data_args"].append(call["data"])
            if len(entry["snippets"]) < 2:
                entry["snippets"].append(call["snippet"])

    (OUT / "pages.json").write_text(
        json.dumps(pages, indent=2, ensure_ascii=False) + "\n"
    )
    serial = {
        k: {**v, "scripts": sorted(v["scripts"]), "screens": sorted(v["screens"])}
        for k, v in sorted(calls.items())
    }
    (CACHE / "ws_snippets.json").write_text(
        json.dumps(serial, indent=2, ensure_ascii=False)
    )
    slim = {
        k: {kk: vv for kk, vv in v.items() if kk != "snippets"}
        for k, v in serial.items()
    }
    (OUT / "ws_calls.json").write_text(
        json.dumps(slim, indent=2, ensure_ascii=False) + "\n"
    )
    services = {}
    for v in serial.values():
        services[v["service"]] = services.get(v["service"], 0) + 1
    print(
        f"screens {len(pages)} (errors {sum('error' in p for p in pages.values())}), scripts {len(scripts)}, fragments {len(fragments)}"
    )
    print(f"web service methods {len(serial)}: {services}")


if __name__ == "__main__":
    main()
