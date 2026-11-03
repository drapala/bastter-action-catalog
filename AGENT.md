# AGENT.md: read this first if you are an AI agent

This repository is a catalog of Bastter System (BS2) business actions, built for AI agents. BS2 is the wealth manager at bastter.com/bs2: portfolios, buys and sells per asset class, dividends, debts, personal finances, income tax reports, plus health and habit diaries. It has no public API. Every action here is a web service method that the BS2 web app itself calls, run with the user's browser session.

## 0. Numbers and how to check them

The current values, generated from `catalog/claims.json` by the build (do not edit by hand):

<!-- claims:start -->
| Claim | Value | Meaning |
|---|---|---|
| `actions_total` | 425 | Business actions in the catalog, one JSON file each. |
| `status_verified` | 265 | Actions with status `verified`. See AGENT.md for what each status means. |
| `status_observed` | 19 | Actions with status `observed`. See AGENT.md for what each status means. |
| `status_gated` | 0 | Actions with status `gated`. See AGENT.md for what each status means. |
| `status_failed` | 0 | Actions with status `failed`. See AGENT.md for what each status means. |
| `status_seen` | 95 | Actions with status `seen`. See AGENT.md for what each status means. |
| `status_excluded` | 46 | Actions with status `excluded`. See AGENT.md for what each status means. |
| `verified_writes` | 90 | Verified actions that change data. Each one passed a read-back in a scenario. |
| `writes_with_passing_read_back` | 90 | Write actions with at least one passing read-back line in the evidence log. |
| `requires_confirmation` | 86 | Actions that need the user's OK before they run: deletes, writes that cannot be undone or that change a whole tab or setting, and writes that reach people (those never run). |
| `live_calls` | 6311 | Calls made by the scripts to the live Bastter web services. Each is one line in the evidence log. |
| `screens_walked` | 105 | BS2 screens the crawler fetched with the session (the browser capture opened the same screens). |
| `captured_calls` | 606 | Web service calls the app made while the browser opened the screens. |
| `scenarios` | 40 | Scenario files (in scenarios/ and scenarios/archive/) with at least one write proved by a read-back. |
| `corrections` | 47 | Mistakes logged while building the catalog. |
| `corrections_with_check` | 43 | Logged mistakes that name the automated check that now catches them. |
| `lint_errors` | 0 | Errors from the catalog lint. Must be 0. |
<!-- claims:end -->

Each value has a `recompute` command in `catalog/claims.json`. Run it from the repo root to check the value.

## 1. Files

| Path | What it is |
|---|---|
| `catalog/index.json` | One short entry per action: `id`, `label`, `area`, `entity`, `operation_class`, `verification`, `availability`, `requires_confirmation`. Read this first. |
| `catalog/actions/<id>.json` | The full entry for one action. Valid against `catalog/schema/business_action.schema.json`. |
| `catalog/claims.json` | Every headline number, with a `recompute` command. |
| `catalog/coverage.json` | Counts by status and by area, screens walked, captured calls. |
| `catalog/lint.json` | Lint findings. `severity: error` must be empty. `severity: gap` lists missing work. |
| `evidence/ui-capture-*.jsonl` | Calls the app made while a logged-in browser opened every BS2 screen or used a form: method, request body, status, answer shape. |
| `evidence/runs.jsonl` | One line per call made by the scripts, and one line per read-back check. Answers are stored as their shape only. The inputs are stored as sent. |
| `scenarios/*.yaml` | Live cycles: create, read back, update, read back, delete, confirm it is gone. |
| `sources/discover/` | The crawl: screens, scripts, and the web service calls found in them. |
| `docs/corrections.jsonl` | Every mistake made while building, what caught it, the fix, and, for most of them, the check that now catches it (`corrections_with_check` in section 0). |
| `tools/mcp_server.py` | MCP server with 3 catalog tools: `find_actions`, `get_action`, `run_action`. |
| `tools/bastter_exec.py` | Executor, scenario runner and evidence log. The MCP server calls the same code. |

## 2. Status: how much to trust an action

| `verification.status` | Meaning | What you should do |
|---|---|---|
| `verified` | A script called it on the live account. A read answered 200 with no Error, with real inputs (no fake ID). A write passed its read-back in the latest run of a scenario file, and `postcondition` names that read. | Run it. For a write, still run the read-back in `postcondition` before you report success. |
| `observed` | The app made this exact call while a browser opened a screen or used a form, and it answered 200. The body is in `routes[0].notes` and the field examples. No script read-back yet. | It can run. Treat a write as unconfirmed until you read it back. |
| `gated` | The account cannot use it (subscription, setup or permission). No action has this status today. | Do not offer it. Tell the user why. |
| `failed` | The latest scenario run read the write back and the read-back did not pass. | Do not report success from the answer. Run the read-back and report what it shows. |
| `seen` | Found in the app's JavaScript. No call counts as proof: some were called with fake IDs or during development. The input fields can be incomplete. | Do not run it. Give the user the screen in `routes[1].start_url`. |
| `excluded` | Out of scope: site-wide shell calls (cookies, notifications, email), admin methods, and the methods on the never-run list (notifications, email, tokens, 2FA, B3 and other integrations, imports, forum topics, raffles, portfolio delete), reads included. | Never run it. |

Some writes that publish or notify other users have status `seen`, and two have status `verified` (the activity diary save and delete). `run_action` refuses every action whose `side_effects.external_effect` is `publishes` or `notifies_people`, whatever its status.

## 3. Protocol for one user request

1. Find candidates in `catalog/index.json`, or call `find_actions(request)`. Requests in Portuguese work ("lança uma compra de VALE3").
2. Read the full entry (`get_action(id)`).
3. For each input in `inputs.entity_refs`, get the ID from the `find_with` action. Never guess an ID. Note: the ID of an item in the user's portfolio (`AtivoID` in `bastter.ativos.obter_itens` or `bastter.ativos.bs2_list_ativos`) is not the ID of the asset in the search (`AtivoID` in `bastter.ativos.pesquisar`, which is the item's `ReferenciaID`).
4. Send every field in `inputs.schema.required`. The server rejects a body with a missing field and hides the reason.
5. If `side_effects.requires_confirmation` is true, ask the user before the call.
6. Run it with `run_action(id, inputs, confirmed)`. Do not use `tools/bastter_exec.py call`: it is a development tool and skips the status, input and confirmation rules.
7. Run the `postcondition.check_with` action and check `postcondition.assert` before you tell the user it is done.

## 4. `run_action` replies

| Reply | Meaning |
|---|---|
| `{"ran": false, "reason": "status is seen: ...", "ui_paths": [...]}` | The status blocks the call. Same for `gated` and `excluded`. |
| `{"ran": false, "reason": "this action publishes: other users can see it ...", "ui_paths": [...]}` | The action reaches other users. It never runs here. Give the user the screen. |
| `{"ran": false, "reason": "the inputs do not match the catalog entry", "errors": [...]}` | Fix the inputs. Each error names the field. Two keys that differ only in case (`privado` and `Privado`) are refused, because the server may read them as one. |
| `{"ran": false, "reason": "this action needs the user's confirmation ..."}` | Ask the user, then call again with `confirmed=true`. |
| `{"ran": true, "http_status": 200, "response": ..., "next_step": "..."}` | The call ran. `next_step` is the read-back to do, present when the entry has a `postcondition`. |
| `{"ran": true, "http_status": 200, "error": "the answer has Error: ...", "note": "..."}` | Bastter refused the request and said why. Nothing changed. |
| `{"ran": true, "http_status": 500, "error": "...", "note": "..."}` | A read got an error. The server never says why. Compare your body with the entry's field examples. |
| `{"ran": "unknown", "reason": "...", "next_step": "..."}` | A write was sent and got no answer, an error page, a 500 or another answer that is not a result. It may have run. Do the check before any retry. |
| `{"ran": false, "reason": "the Bastter session expired ..."}` | Bastter redirected to the login (or answered 401) and did not run the request. The user must log in again (see README). |
| `{"ran": false, "reason": "No Bastter session in the keychain ..."}` | The session was never stored on this machine. The user must log in (see README). Nothing was sent. |

`confirmed=true` is your own statement that the user agreed. The server cannot check it. Set it only after the user agreed to this exact call.

## 5. Bastter behavior that the app does not tell you

| What | Detail | Source |
|---|---|---|
| Error details are hidden | A bad body answers `500 There was an error processing the request.` A missing field and a wrong type look the same. | `docs/corrections.jsonl` C005 |
| A 200 can be a refusal | Many writes answer 200 with `{"Error": "..."}`. `run_action` returns that as an error with the message. | C015 |
| Saves rarely return the new ID | Most saves return only `{"Return": true}`. Find the new record in the list by a field you sent (a description or code). `salvar` for imóvel returns `AtivoID: 0`. | `docs/families/*.md` |
| Item vs asset ID | `pesquisar` returns the asset ID, which is also the item's `ReferenciaID`. `salvar` adds the asset to a tab and returns the item ID. All movement actions use the item ID. | `scenarios/acao_ciclo_completo.yaml` (steps `pesquisar`, `incluir_ativo`, `itens_com_ativo`) |
| Date formats change by screen | Movements: `mm/dd/yyyy`. Finanças: `dd/mm/yyyy`. Imóvel rent: `dd/mm/yyyy`. Imóvel purchase, improvements, expenses and donations: `yyyy-mm-dd`. DARF: `yyyy-MM-01`. Use the format in the field description. The examples can hold another format that the server also took. | `docs/families/*.md` |
| Removing an item is two steps | `excluir_item` hides the item (`restaurar_item` brings it back). It refuses with `Error` while the item has an open position. `excluir_movimentacao_ativo` then deletes it for good. | `docs/families/ativos-classes.md`, `scenarios/item_ajustes.yaml`, `scenarios/fii_excluir_definitivo.yaml` |
| Adding an asset you already have can return your item | `salvar` with `ativoID: 0` and a ticker the tab already holds, even a hidden one, can return the existing item instead of a new one. It does not always: a probe on VALE3 got a new item while a hidden one existed. Look the ticker up in the tab first. | `evidence/runs.jsonl` (VOO item reused by `etf-ciclo` runs; new item in run `dev-data-probe-1793739096`) |
| An imóvel shows up in the income tax screens | Adding a purchase to an imóvel also creates IR rows. Deleting the purchase removes them. | `scenarios/archive/imovel_ciclo.yaml` |
| Bonds | Send the CUSIP as `descricao` in `salvar`. `obter_itens` then returns it in `AtivoRelacionado`, and `Descricao` holds the bond name. | `scenarios/bond_ciclo.yaml` |
| Slow methods | `provento_manual_deletar` takes about 145 s (its route sets `timeout_s` 300). Several clients on the same session made calls take 65 s to more than 120 s. Use one client at a time. | C013, `docs/families/ativos-classes.md`, `docs/families/financeiro-e-ir.md` |
| A timeout does not mean nothing happened | Writes that timed out on the client still landed on the server. After a write gets no answer, read the list before any retry. | C013 |
| Some settings cannot go back exactly | `salvar_opcoes` always writes 0 to two pie-chart options. `abas_salvar` stores an empty list as `[""]`. Neither shows on screen. | `docs/families/pas-e-config.md` |
| Some screens write on load | Opening `/ativos/proventos` calls `SalvarOrdenacao` to save the sort order. Opening `/imposto-de-renda/exterior` calls `ConfigSalvar` with `DisclaimerBSIR`. | `evidence/ui-capture-2026-11-03-screens.jsonl` |
| Public writes | Bastter Race activities, food entries, gym workouts, inspirations and the "Parou de Beber" list are public or notify other users. They were never run. The activity diary (`diario_atividade_salvar`) feeds a public top 50: a scenario ran it with 1 and 2 minutes, below the lowest ranked amount. The weight diary (`diario_salvar`) feeds a public ranking that shows logins and was never run. All of them are marked `publishes` or `notifies_people`, and `run_action` refuses them. | `catalog/curation.yaml`, `docs/families/pas-e-config.md` |

## 6. How to check the catalog

1. `jq -c '.claims[] | [.id, .value]' catalog/claims.json` lists the numbers. Run each `recompute` command to check it. `tests/test_claims.py` runs them all.
2. To trace one status: read `verification.evidence` in the entry (it ends with `#run=<run id>`), then `grep '<run id>' evidence/runs.jsonl`. For a write, `postcondition.from_scenario` names the scenario step that proved it.
3. To check the build: `.venv/bin/python -m pytest -q` and `.venv/bin/python tools/catalog_lint.py`. Neither calls Bastter.

## 7. Limits you must not infer past

- One account. `gated` would mean "this account cannot", not "no account can".
- No message reached anyone. Methods that notify people, send email or publish to the community were never run, except the activity diary (section 5), with amounts below the public ranking. Three reads that touch integrations or a raffle (`integracao_b3_init`, `remessa_online_get_authorization`, `sorteio_ativos_list`) were called by the bulk read probe, and two of them also by the replay of observed reads, before the never-run list excluded them.
- Calls an agent makes through the MCP server, the calls it refused, and the demo's calls are logged in `logs/mcp-runs.jsonl`, outside git, because they carry real trades. They never change the catalog.
- `evidence/runs.jsonl` keeps the inputs the scripts sent: the account's own IDs, the ZZTESTE test values and, for a restore step, the old setting it sends back (for example the portfolio name). It never keeps an answer.
- The account keeps 5 hidden ZZTESTE imóveis (41241 to 41245). No method deletes an imóvel for good, and they show on no screen.
- Reads were checked on a nearly empty portfolio. A `verified` read proves the call works. The scenarios prove that reads see the writes.
- `find_actions` is keyword matching. Read the entry before you act on the first result.

