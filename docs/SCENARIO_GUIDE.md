# How to verify a family of write actions

This repository maps the Bastter System (bastter.com/bs2, a personal wealth manager) into a catalog of business actions for AI agents. Each action is one ASP.NET web service method. A write action becomes `verified` only when a scenario runs it on the live account and a later read shows the change.

The account is the owner's real account. Its portfolio was empty at the start. Treat it with care.

## Safety rules (hard)

1. Only change or delete what your own scenario created in the same run. Never touch an item that existed before.
2. Name every free-text field with the prefix `ZZTESTE` (for example `ZZTESTE gasto ${ts}`). Use small values (quantity 1 to 3, money 1 to 20).
3. Every scenario deletes what it created and reads back to confirm it is gone. If a family has a create but no delete, do NOT run the create. Report it instead.
4. Before a scenario adds an asset by ticker, a `guard` step right before `salvar` must check that the tab does not hold that ticker, and a `guard` step right after `salvar` must check that the item has no movements. `salvar` with `ativoID: 0` can return the user's existing item for that ticker, even a hidden one, instead of a new one. `scenario_problems` fails when either guard is missing.
5. A settings write (layout, options, objectives) must first read the current value, then change it, read it back, then restore the old value and read it back again. The restore step names the change step in `undoes`.
6. Never run a method that notifies or reaches other people, or that changes security or integrations: names with `Notificacao`, `Email`, `Token`, `Auth`, `B3`, `Importar`, `Strava`, `RemessaOnline`, `SolicitarAnalise`, `PedirBDR`, `PedirETF`, `Topico`, `Compartilha`, `Sorteio`, and `CarteiraExcluir` (it needs the account password). If something you plan to run could be public (a ranking, a timeline, a forum post), do not run it. Report it.
7. Do not edit anything under `tools/`, `catalog/` or `sources/`. Do not run `git`. Write only your own files in `scenarios/` and your report.
8. Do not use a browser. Use only the commands below.

## How to find a method's payload

- `catalog/actions/<id>.json` has the entry. `routes[0].url` is the method, `inputs.schema` the known fields, `routes[0].notes` the JS expression that builds the body.
- `.cache/discover/ws_snippets.json` has, per method (`WS_Carteira.Metodo`), up to 2 snippets of the minified JS around the call and the `data_args`. The `.cache/discover/` files exist only after `sources/discover/crawl.py` ran with a stored session.
- The full minified scripts are in `.cache/discover/*.txt` (one file per script). Find the function that builds the object, for example `grep -l '"FinancaSalvar"' .cache/discover/*.txt`, then read around it with python.
- `evidence/ui-capture-2026-11-03-screens.jsonl` has real request bodies the app sent when each screen loaded. The read methods of your family are usually there, with exact bodies.
- ASP.NET needs every parameter in the body. A missing or mistyped field gives `500 There was an error processing the request.` with no detail. Date formats change by screen: see `catalog/date_formats.yaml` (most fields take `yyyy-mm-dd`, movements take `mm/dd/yyyy`, finanças and rent take `dd/mm/yyyy`).
- A call can answer 200 and still fail: the answer may hold `{"Error": "..."}` or `{"Return": false}`. The scenario engine treats an `Error` field as a failure.

## How to run

```
.venv/bin/python tools/bastter_exec.py call <action_id> '<json body>'      # one call, logged
.venv/bin/python tools/bastter_exec.py scenario scenarios/<file>.yaml     # a scenario, logged
```

Every call is logged to `evidence/runs.jsonl` with the SHAPE of the answer, never its values. To look at real values while you develop, you may use `raw_call(http, url_path, body)` from `tools/bastter_exec.py` for READS only, and print only what you need. `raw_call` writes no log line, so every write must go through `call` or a scenario.

## Scenario format

See `scenarios/acao_ciclo_completo.yaml` (passes, 19 steps). Rules:

- `vars:` constants. `${ts}` is a run stamp, `${prefix}` is `ZZTESTE`.
- `save:` stores a value from the answer: `{name: "path.to.field"}` or `{name: {path: List, where: {Field: value}, field: IdField}}`. A save that finds nothing fails the step. A saved null fails too, unless the rule says `nullable: true` (for an old setting that is really null): `{name: {path: Opcoes.Campo, nullable: true}}`.
- `assert:` supports `equals`, `list_contains {path, where}`, `list_excludes {path, where}`, `present` and `empty` (the path exists and holds an empty list or null). An empty `path` means the whole answer. In `list_excludes`, a literal null in `where` is a value to match. A `${ref}` that has no value fails the check.
- A read-back step has `postcondition_of: <the write action id it proves>`. Only these steps make a write `verified` (or `failed` if the read-back does not pass). Put one after every write you want to verify.
- `guard: true` marks a read that checks the account holds no real data the scenario would touch. When a guard fails, the run stops and nothing else runs.
- `undoes: <step>` marks a step that undoes a write step (a restore, or a delete that takes no ID).
- Default `stop_on_fail: true`. When a step fails, the run stops and runs only the later steps that undo its own writes: a step with `undoes` whose write step was reached, and a delete step whose inputs use IDs this run saved. No cleanup step runs past a guard that has not run. A guard always stops the run. Every skipped step is printed. Check the saved values the run prints, and run any cleanup that is still needed by hand with `call`.
- `scenario_problems` checks six rules: a delete needs a saved ID or `undoes`; `undoes` names an earlier step; a guard is a read; a guard stops the run; a `salvar` that adds a ticker has a guard right before and right after it; a step that hides an item has `requires` on a read that asserts the item has no movements (unless a later step deletes the item for good). `bastter_exec.py scenario` refuses to run a file that breaks one, and `tests/test_scenario_engine.py::test_every_scenario_file_follows_the_cleanup_rules` checks every file in `scenarios/` (not `archive/`).
- `requires: <step>` makes a step run only after that step passed in this run. In a cleanup, a required read that has not passed runs first.

## Report

When done, write `docs/families/<family>.md` with: each action you verified (scenario file and run id), each action you did not run and why, every surprise (field that must be present, a write that answers 200 but changes nothing, a soft delete), and confirmation that nothing you created is left (the read that shows it).
