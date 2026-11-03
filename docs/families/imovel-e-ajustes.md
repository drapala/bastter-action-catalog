# Family: real estate (imóvel) and per-item settings

Result: two scenarios pass. They verify 13 write actions of this family, plus `salvar` and `excluir_item`. They also use the 3 read actions of the family (`imovel_movimentacao_obter`, `imovel_aluguel_listar`, `obter_anotacoes`) after every write. 6 actions of the family are not verified. The imovel and acao tabs are empty again, and the IR reads for 2026 are empty.

| Scenario | Run id | Steps | Failures |
|---|---|---|---|
| `scenarios/archive/imovel_ciclo.yaml` | `imovel-ciclo-1793730098` | 43 | 0 |
| `scenarios/item_ajustes.yaml` | `item-ajustes-1793730162` | 23 | 0 |

Development calls on items that I created are in `evidence/runs.jsonl` under the run prefix `dev-imovel-ajustes-`.

## Verified write actions

### `imovel_ciclo.yaml` (screen /bs2/ativos/imovel, tipo `imovel`)

| Action | What the read-back shows |
|---|---|
| `bastter.ativos.salvar` | `obter_itens` imovel has the `ZZTESTE imovel <ts>` item with TipoImovelID 12, Valor 10.0, InquilinoTipo PF. |
| `bastter.ativos.imovel_movimentacao_salvar` | `imovel_movimentacao_obter` has AquisicaoData `2026-11-03T00:00:00` and AquisicaoValor 10.0. A second write clears the aquisição (AquisicaoData null). |
| `bastter.ativos.imovel_benfeitoria_salvar` | The benfeitoria is in `Benfeitorias` with the sent data. An edit with the same BenfeitoriaID changes Valor 5 to 6 and does not add a row. |
| `bastter.ativos.imovel_benfeitoria_deletar` | The BenfeitoriaID is gone from `Benfeitorias`. |
| `bastter.ativos.imovel_despesa_salvar` | The despesa is in `Despesas`. An edit with the same DespesaID changes Valor 3 to 4 and DedutivelIR to true, without a new row. |
| `bastter.ativos.imovel_despesa_deletar` | The DespesaID is gone from `Despesas`. |
| `bastter.ativos.imovel_aluguel_salvar` | `imovel_aluguel_listar` has the rent with Valor 2.0 and Data `/Date(1793674800000)/` (3 Nov 2026). An edit with the same AluguelID changes Valor to 3.0 without a new row. |
| `bastter.ativos.imovel_aluguel_deletar` | The AluguelID is gone from `Itens`. |
| `bastter.ativos.imovel_aluguel_salvar_inquilino` | `obter_itens` shows InquilinoTipo PJ and Nome `ZZTESTE inquilino <ts>`. The restore write brings back PF, Nome null, CNPJ null. |
| `bastter.ativos.imovel_aluguel_automatico_salvar` | `Automatico` shows Ativo true, Dia 28, Periodo 1, Valor 2.0. The restore write brings back Ativo false with Dia, Periodo and Valor null. |
| `bastter.ativos.excluir_item` | The imovel is gone from `obter_itens` and from `obter_posicao_anual_ativos` imovel 2026. |

The scenario also reads `imovel_movimentacao_obter` and `imovel_aluguel_listar` after every write. Extra reads show the side effects in the IR screens: `obter_posicao_anual_ativos` (imovel 2026) lists the imovel while it has an aquisição, and `obter_ir_imovel_aluguel` (2026) lists the rent while it exists.

### `item_ajustes.yaml` (item ITUB4 in the acao tab)

| Action | What the read-back shows |
|---|---|
| `bastter.ativos.salvar` | `obter_itens` acao has ITUB4 with the search ReferenciaID, Classificacao Comprar, DataFreio null. |
| `bastter.ativos.salvar_anotacoes` | `obter_anotacoes` returns the sent text. The restore write brings back an empty text. |
| `bastter.ativos.alterar_categoria` | Classificacao changes from Comprar (2) to Estudo (7), then back to Comprar. |
| `bastter.ativos.ativar_freio` | Classificacao becomes Quarentena (6) and DataFreio is set. `alterar_categoria` back to Comprar clears DataFreio. |
| `bastter.ativos.excluir_item` | ITUB4 is gone from `obter_itens` acao. |
| `bastter.ativos.restaurar_item` | After `excluir_item`, ITUB4 is back in `obter_itens` with the same AtivoID. The scenario then deletes it again. |

## Actions not verified

| Action | Status | Reason |
|---|---|---|
| `bastter.ativos.alterar_pais` | Run once on my own item, no visible change | Run `dev-imovel-ajustes-1793729616`. The answer is `{"Return": true}`, but `obter_itens` still shows Pais null, and `listar_global_pais` is empty. The UI shows the country menu only for manual items in the stock, reit, europa and bond tabs, and for ETF. A read-back is possible only on an item in one of those tabs, outside this family. |
| `bastter.ativos.atualizar_preco` | Run once on my own item, no visible change | Run `dev-imovel-ajustes-1793729656`. The answer is `{"Return": true}`, but Valor stays at the market quote. The UI calls this method only for a moeda `[OUTRO]` item (MoedaAtivoID 0) and for manual stock, reit, europa and bond items. |
| `bastter.ativos.salvar_objetivo_ativos` | Not run | The method acts on the whole tab. The UI sends every item of the tab plus the `tipoObjetivo` of the tab. The tab also keeps an `AtualizacaoObjetivo` marker that the UI uses for its "you changed the weights X ago" warning. That marker is empty now, and I cannot set it back to empty after a write. |
| `bastter.ativos.copiar_item` | Not run | The UI builds the destination list from the other carteiras only. `bs2_init` shows one carteira (2000002, Principal). A second carteira needs `carteira_excluir` for cleanup, which needs the account password (rule 5). |
| `bastter.ativos.mover_item` | Not run | Same reason as `copiar_item`. |
| `bastter.ativos.incluir_grupo` | Not run | The method adds a whole group to the tab (all viable ações, all Super #PAS, or the ranking Top 20). It creates many items, not one own item. |

## Surprises

1. `Salvar` for tipo `imovel` answers `AtivoID: 0` (also `PaisID: 0`), but it creates the item. The scenario gets the id from `obter_itens` by the ZZTESTE description.
2. Date formats differ per method. The aquisição, benfeitoria and despesa writes take `yyyy-mm-dd` (the JS converts the form date). `ImovelAluguelSalvar` takes the raw form text `dd/mm/yyyy`, and the server reads `03/11/2026` as 3 November 2026. This is not the `mm/dd/yyyy` default of the guide.
3. An alienação date in `ImovelMovimentacaoSalvar` marks the imovel as sold, removes it from the patrimônio and turns off the automatic rent (UI confirm text). The scenario never sends an alienação date.
4. The imovel appears in IR Bens e Direitos as soon as it has an aquisição, and the rent appears in the IR rent screen. The scenario clears the aquisição and deletes the rent before it deletes the item, and reads both IR screens after.
5. Some restores do not give the exact original value. A cleared aquisição has AquisicaoValor 0.0 (original null). Automatic rent turned off has ContrPrev and ImpostoRetido 0.0 (original null), and the UI sends 0 too. After an empty note, `obter_anotacoes` keeps the Data of the last save. All of these values belong to the item, and the scenario deletes the item.
6. The tenant name goes to the item field `Nome` in `obter_itens`. There is no `InquilinoNome` field. An empty CNPJ is stored as null.
7. Automatic rent with Dia 28 did not add a rent at once.
8. `alterar_categoria` to Estudo sets the item Objetivo to 0. Back to Comprar sets it to 100 (the acao tab uses automatic weights).
9. `excluir_item` is a soft delete. `restaurar_item` brings back the same AtivoID. Each delete in this family leaves a hidden row, the same as `acao_ciclo_completo`. The hidden rows are acao 1755463 (development) and 1755466 (scenario), imovel 41241 (development) and 41242 (scenario). None of them is in `obter_itens` or in the IR reads. None has a movement. I did not run `excluir_movimentacao_ativo` (the UI "delete permanently" action), because it is not in this family.
10. The server was slow while other agents used the same session. Some calls took about 50 s, and two calls timed out on the client. The first development `Salvar` for ITUB4 timed out on the client, but the server still created item 1755463. The log has no line for that call, because the timeout came before the log write. A later read found the item, and I deleted it.

## Nothing left on the account

Final read, run `dev-imovel-ajustes-1793730192`:

- `obter_itens` imovel: `Items: []`, TipoObjetivo 1, AtualizacaoObjetivo `''` (same as before the work).
- `obter_itens` acao: `Items: []`, TipoObjetivo 2, AtualizacaoObjetivo `''` (same as before the work).
- `obter_posicao_anual_ativos` imovel 2026: `[]`. The same read for acao 2026: `[]`.
- `obter_ir_imovel_aluguel` 2026: `[]`.

The only remains are the four soft-deleted rows in surprise 9. No read in the app shows them.

## Update after the audit (2026-11-03)

The four hidden rows listed in surprise 9 (acao 1755463 and 1755466, imovel 41241 and 41242) were deleted for good in run `purge-hidden-items-1793730986`. Each first delete answered `Return: OK`. Nothing from this family is left on the account.

## Update after audit round 2 (2026-11-03)

The update above is wrong about the imóveis. `excluir_movimentacao_ativo` answers `Return: OK` for an imóvel, also when repeated, and the imóvel is still there: `ImovelMovimentacaoObter` on 41242 returns its `Movimentacao`, while an unknown ID returns `Movimentacao: null`. The app has no other method that deletes an imóvel for good. So the 5 hidden ZZTESTE imóveis (41241 to 41245, read back on 2026-11-03) stay hidden. They show on no screen. `purge_hidden_items.py` now skips imóveis, and `imovel_ciclo.yaml` moved to `scenarios/archive/` so that new runs do not add more.
