# Family: movements and income of the asset classes other than Brazilian stocks

Date: 2026-11-03. Scope: the 12 class tabs `fii`, `stock`, `reit`, `etf`, `bdr`, `europa`, `bond`, `rendafixa`, `moeda`, `re`, `outro`, `fixo`.

Result: all 12 classes pass a full cycle on the live account. The cycles verify 15 write actions. One write action in scope was not run (`salvar_provento`). The final read shows that the 12 class tabs and the 2026 Bens e Direitos lists of these classes are empty.

## Scenarios and run ids

Each scenario adds an item, adds a movement, reads it back, edits it, reads it back, deletes the movement, reads it back, deletes the item and reads it back. Income steps (create, read, edit, read, delete, read) are in the classes where the app has them.

| Class | Scenario | Run id | Steps | Failures | Movement path | Income |
|---|---|---|---|---|---|---|
| fii | `scenarios/fii_ciclo.yaml` | `fii-ciclo-1793729342` | 12 | 0 | Brazilian | automatic only |
| stock | `scenarios/stock_ciclo.yaml` | `stock-ciclo-1793729709` | 12 | 0 | foreign | automatic only |
| reit | `scenarios/reit_ciclo.yaml` | `reit-ciclo-1793729724` | 12 | 0 | foreign | automatic only |
| europa | `scenarios/europa_ciclo.yaml` | `europa-ciclo-1793729737` | 12 | 0 | foreign | automatic only |
| etf (VOO) | `scenarios/etf_ciclo.yaml` | `etf-ciclo-1793729961` | 18 | 0 | foreign | manual provento |
| bond | `scenarios/bond_ciclo.yaml` | `bond-ciclo-1793730158` | 18 | 0 | foreign | bond cupom |
| bdr | `scenarios/bdr_ciclo.yaml` | `bdr-ciclo-1793730183` | 12 | 0 | Brazilian | automatic only |
| rendafixa | `scenarios/rendafixa_ciclo.yaml` | `rendafixa-ciclo-1793730275` | 16 | 0 | Brazilian | renda fixa cupom |
| re | `scenarios/re_ciclo.yaml` | `re-ciclo-1793730294` | 10 | 0 | Brazilian | none in the UI |
| outro | `scenarios/outro_ciclo.yaml` | `outro-ciclo-1793730304` | 16 | 0 | Brazilian | outro provento |
| fixo | `scenarios/fixo_ciclo.yaml` | `fixo-ciclo-1793730319` | 10 | 0 | Brazilian | none in the UI |
| moeda | `scenarios/moeda_ciclo.yaml` | `moeda-ciclo-1793730329` | 10 | 0 | Brazilian | none in the UI |
| fii (soft delete) | `scenarios/fii_excluir_definitivo.yaml` | `fii-excluir-definitivo-1793730403` | 11 | 0 | Brazilian | none |
| final read | `scenarios/ativos_classes_vazias.yaml` | `ativos-classes-vazias-1793730427` | 24 | 0 | read only | read only |

Development calls are in `evidence/runs.jsonl` under the run prefix `dev-ativos-classes-`.

## Verified write actions

| Action | Scenarios | What the read-back shows |
|---|---|---|
| `bastter.ativos.salvar` | all 13 cycles | `obter_itens` of the class has the new AtivoID with the ticker or the `ZZTESTE` description. |
| `bastter.ativos.save_movement` | stock, reit, europa, etf, bond | `get_movement` has a `Buy` with Quantidade 1.0, OperacaoReal 10.0, OperacaoEstrangeiro 2.0. The edit keeps the same MovimentacaoID with Quantidade 2.0, 20.0 and 4.0. |
| `bastter.ativos.delete_movement` | stock, reit, europa, etf, bond | The MovimentacaoID is gone from `get_movement`. |
| `bastter.ativos.salvar_movimentacao` | fii, bdr, rendafixa, re, outro, fixo, moeda, fii soft delete | `obter_movimentacao` has the entry with the sent quantity and total. The edit keeps the same MovimentacaoID. A sale (`tipomov: venda`, quantity -1) gives QtdTotal 0.0. |
| `bastter.ativos.excluir_movimentacao` | fii, bdr, rendafixa, re, outro, fixo, moeda | The MovimentacaoID is gone from `obter_movimentacao`. |
| `bastter.ativos.excluir_item` | all 13 cycles | The AtivoID is gone from `obter_itens` of the class. |
| `bastter.ativos.provento_manual_salvar` | etf | `provento_manual_listar` (tipoClasse `etf`) has the EarningID with Valor 1.5, Imposto 0.45, pay date 2026-10-15. The edit keeps the EarningID with 2.5, 0.75, 2026-10-16. |
| `bastter.ativos.provento_manual_deletar` | etf | The EarningID is gone from `provento_manual_listar`. |
| `bastter.ativos.bond_cupom_salvar` | bond | `bond_cupom_listar` has a cupom with Valor 2.0. The edit keeps the CupomID with Valor 3.0. |
| `bastter.ativos.bond_cupom_deletar` | bond | The CupomID is gone from `bond_cupom_listar`. |
| `bastter.ativos.renda_fixa_cupom_salvar` | rendafixa | `renda_fixa_cupom_listar` has the CupomID with Valor 2.0 and Data 2026-11-01. The edit keeps the CupomID with 3.0 and 2026-11-02. |
| `bastter.ativos.renda_fixa_cupom_deletar` | rendafixa | The CupomID is gone from `renda_fixa_cupom_listar`. |
| `bastter.ativos.outro_provento_salvar` | outro | `outro_provento_listar` has a ProventoID with Valor 2.0. The edit keeps the ProventoID with Valor 3.0. |
| `bastter.ativos.outro_provento_deletar` | outro | The ProventoID is gone from `outro_provento_listar`. |
| `bastter.ativos.excluir_movimentacao_ativo` | fii soft delete | The AtivoID is gone from `obter_posicao_anual_ativos` (fii, 2026), and `obter_movimentacao` has no entries for it. |

The scenarios also use these reads: `pesquisar`, `obter_itens`, `get_movement`, `obter_movimentacao`, `provento_manual_listar`, `bond_cupom_listar`, `renda_fixa_cupom_listar`, `outro_provento_listar` and `bastter.imposto_de_renda.obter_posicao_anual_ativos`.

## Actions not run

| Action | Reason |
|---|---|
| `bastter.ativos.salvar_provento` | It edits the pay date or the foreign tax of an automatic provento in the Proventos screen. The id it sends (`earningID`) belongs to an automatic provento that the market data creates, not to an object that the scenario creates. I cannot prove that the write stays in this account and does not change shared earnings data. The method also has no delete, so rule 1 and rule 3 apply. |
| `bastter.ativos.provento_manual_*` on stock, reit, europa | The UI shows the manual provento button only for manual items (`IsManual` true) in these tabs, and for foreign ETFs. AAPL, O and ASML.AS are not manual. The ETF scenario covers the three actions. |

The Brazilian ETF path (IVVB11, PaisID 227) was not run. It uses `salvar_movimentacao`, which the fii and bdr scenarios already verify.

## How the app picks the movement methods

1. The foreign form (`SaveMovement`, `GetMovement`, `DeleteMovement`) is for `stock`, `reit`, `bond`, `europa`, an `etf` with PaisID other than 227, and a `moeda` with origemID 2. The JS list is `movExterior`.
2. All other classes use `SalvarMovimentacao`, `ObterMovimentacao` and `ExcluirMovimentacao`.
3. `SaveMovement` body: `{movimentacaoID, tipo, ativoID, quantidade, data (mm/dd/yyyy), totalOperacao, totalOperacaoEstrangeiro, corretagem}`. A sale sends a negative quantity.
4. For an ETF, `Salvar` needs `paisID` from the search result (29 for VOO). The bond needs `moedaAtivoID` 319.
5. For `rendafixa`, `re`, `outro`, `fixo` and `moeda`, the description is free text. `re`, `outro` and `fixo` send `valor: "0"` and `moedaAtivoID: "0"`. `rendafixa` and `re` also send `instituicao`, `cnpj` and `destinoID` (form default `"2"`). `outro` sends `codIRPF: "0"`.
6. A `moeda` with free text uses the `[OUTRO]` option: `moedaAtivoID: 0` and the text as `descricao`. For this item the JS sends the money total as the quantity.

## Surprises

1. `ProventoManualDeletar` is very slow. In the passing ETF run it took about 145 seconds (18:19:33 to 18:22:00 UTC). The CLI HTTP timeout in `tools/session.py` is 60 seconds. So `bastter_exec.py scenario scenarios/etf_ciclo.yaml` stops with `ReadTimeout` at `excluir_provento`. The delete still completes on the server. While it runs, other calls with the same session wait. I ran the ETF scenario with the same engine (`bastter_exec.scenario`) and an HTTP client with a 300 second timeout, set at runtime from outside the repo. To run it from the CLI, the timeout must be about 200 seconds or more.
2. The first ETF run, `etf-ciclo-1793729774`, stopped at `excluir_provento` because of this timeout. I cleaned up by hand: the provento list was empty, I deleted movement 86914 and item 55738, and both read back empty. The dev probe before it had the same timeout. Its provento 1057 was also gone on the next read.
3. `excluir_item` answers HTTP 200 with `{"Error": "Este ativo possui movimentações..."}` when the item still has an open position. The item stays.
4. After a full sale (position 0), `excluir_item` is a soft delete. The item leaves the tab, but `obter_posicao_anual_ativos` still lists it with `Excluido: true`, and its movements stay. `excluir_movimentacao_ativo` removes the item and its movements. The cycles delete the movement first, so they leave no soft-deleted item.
5. For a bond, `obter_itens` shows the bond name in `Descricao` ("US TREASURY 2030"). The CUSIP that `Salvar` received is in `AtivoRelacionado`. My first bond run, `bond-ciclo-1793730139`, failed its read-back because it checked `Descricao`. Its item 6757 had no movement. I deleted it with `excluir_item` and read the bond tab back empty. The scenario now checks `AtivoRelacionado`.
6. For VOO, `Salvar` returned AtivoID 55738 in all three runs. The id is the same each time, so for this ETF it is the asset id, not a new row id. `excluir_item` with it works.
7. `get_movement` names a buy `Buy` (English). `obter_movimentacao` names it `Compra`, `Aplicação` (rendafixa) or `Venda`. `DeleteMovement` and `ExcluirMovimentacao` answer `{"Return": "OK"}`.
8. Income dates go as `yyyy-mm-dd`, but movement dates go as `mm/dd/yyyy`. The cupom save answer has Data as `/Date(ms)/`. The cupom list has it as `2026-11-01T00:00:00`.
9. For `rendafixa`, the item keeps `DestinoID` 0 although the body sends `"2"`. The app uses that field only for poupança. An empty `cnpj` comes back as null.
10. The scenario engine does not fill `${...}` inside a value in `vars:`. A var `"${prefix} CDB ${ts}"` stays as literal text. The free-text scenarios write the template in each step.

## What is left on the account

Nothing that I created. The run `ativos-classes-vazias-1793730427` shows:

1. `obter_itens` returns `Items: []` for each of the 12 tabs: fii, stock, reit, etf, bdr, europa, bond, rendafixa, moeda, re, outro, fixo.
2. `obter_posicao_anual_ativos` (2026) returns `[]` for fii, etf, etfext, rendafixa, bond, stock, europa, bdr, moeda (destino 1, 2 and 3) and outro. So no soft-deleted item is left.

In each scenario, the income list (manual provento, bond cupom, renda fixa cupom, outro provento) read back without the created id before the item was deleted. The dev probes also read these lists back empty before they deleted their items.

## Update after the audit (2026-11-03)

The cycles did leave hidden rows: `excluir_item` only hides an item. `tools/purge_hidden_items.py` deleted them for good in run `purge-hidden-items-1793730986` (fii 722627, stock 746012, 746014 and 746017, bdr 17131, etf 55738, and the others it lists). A hidden item with no movements shows on no screen, so the final `obter_posicao_anual_ativos` read above could not prove they were gone. The proof is the purge answer: the first delete answers `Return: OK` and a repeat answers `Error`.

## Update after audit round 2 (2026-11-03)

- Surprise 1 is out of date for the tools: the route of `provento_manual_deletar` sets `timeout_s` 300, and the ETF cycle passes.
- The earlier purge runs counted a first `Return: OK` as proof. They had no repeat call. Run `purge-hidden-items-1793735050` repeated the check with the current rule (gone only after the not-found Error): 48 items gone, 34 of them already gone from the earlier runs.
- Every asset scenario now has two guard steps before it writes: the tab does not hold the ticker, and the item that `salvar` returns has no movements. `salvar` with `ativoID: 0` returns the existing item for a ticker, even a hidden one (the ETF runs reused item 55738).
- Correction after audit round 3: the second guard (no movements) runs right after `salvar`, before any other step, and the cleanup never runs past a guard that has not run. The guards cannot tell a hidden item of the user that has no movements from a new one. The purge reads each item again before it deletes it.
