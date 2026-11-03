# Family: Financeiro, Imposto de Renda and donation records

Date: 2026-11-03. Screens: `/bs2/financeiro/financas`, `/bs2/financeiro/aportes`, `/bs2/financeiro/juros-compostos`, `/bs2/financeiro/dividas/exterminador`, `/bs2/imposto-de-renda/*`, `/bs2/pas/doacoes`.

Result: five scenarios pass on the live account with 0 failures. They verify 24 write actions of this family and 2 write actions of the asset family. One action in scope was not run (`calculadora_juros_save_topico`). The final reads show that nothing the scenarios or the development probes created is left, and the Aportes setting has its original value.

## Scenarios and run ids

| Sub-family | Scenario | Run id | Steps | Failures |
|---|---|---|---|---|
| Finanças + Aportes setting | `scenarios/financas_ciclo.yaml` | `financas-ciclo-1793730307` | 32 | 0 |
| Juros compostos | `scenarios/juros_ciclo.yaml` | `juros-ciclo-1793730356` | 8 | 0 |
| Exterminador de dívidas | `scenarios/exterminador_ciclo.yaml` | `exterminador-ciclo-1793730364` | 8 | 0 |
| Imposto de Renda | `scenarios/ir_ciclo.yaml` | `ir-ciclo-1793730438` | 46 | 0 |
| Doações | `scenarios/doacoes_ciclo.yaml` | `doacoes-ciclo-1793730507` | 17 | 0 |

Each write has a read-back step with `postcondition_of`. Every scenario edits the item it created, reads the edit back, deletes the item and reads the delete back. All read-back lines of these five runs in `evidence/runs.jsonl` have `"passed": true`.

## Verified write actions

| Action | Scenario | What the read-back shows |
|---|---|---|
| `bastter.financeiro.financa_salvar` | financas | A new expense is in `financa_obter_itens` (mes 11/2026) with Tipo 2, Valor 10.0. The edit keeps the LancamentoID with Valor 12.0 and DespesaDedutivel true. A monthly income has the same RecorrenciaID in 11/2026 and 12/2026. The new category is in `financa_obter_evolucao_categoria` with Total 10.0. |
| `bastter.financeiro.financa_save_pago` | financas | The expense has Pago true. |
| `bastter.financeiro.financa_save_recebido` | financas | The 11/2026 income has Recebido true. |
| `bastter.financeiro.financa_deletar` | financas | `excluirRecorrentes: true` removes every entry of the RecorrenciaID in all months. `false` removes the single expense. |
| `bastter.financeiro.financa_excluir_categoria` | financas | The CategoriaID is gone from `Categorias` and from the evolution chart. |
| `bastter.financeiro.salvar_opcoes_financeiro_aportes` | financas | `bs2_init` shows `FinanceiroAportesConsideraMoeda` true and the other four options unchanged. After the restore call, all five options equal the values read at the start. |
| `bastter.financeiro.calc_juros_save` | juros | The simulation is in `calc_juros_list` with the sent title and parameters. The edit keeps the SimulacaoID (`calc_juros_get`). |
| `bastter.financeiro.calc_juros_delete` | juros | The SimulacaoID is gone from the list. `calc_juros_get` answers `null`. |
| `bastter.financeiro.exterminador_divida_save` | exterminador | Same proof as `calc_juros_save`, with `exterminador_divida_list` and `exterminador_divida_get`. |
| `bastter.financeiro.exterminador_divida_delete` | exterminador | Same proof as `calc_juros_delete`. |
| `bastter.imposto_de_renda.irdarf_salvar` | ir | The DARF is in `irdarf_listar` with Codigo 6015, Periodo 2026-10-01, Valor 10.0. `irdarf_obter` for that code and month returns its DARFID. The edit keeps the DARFID with Valor 12.0. |
| `bastter.imposto_de_renda.irdarf_excluir` | ir | The DARFID is gone and `irdarf_obter` returns DARFID 0 again. |
| `bastter.imposto_de_renda.salvar_ir_rendimento_manual` | ir | The item is in `obter_posicao_anual_proventos` (2025) under `Manual.Isentos`. `obter_ir_rendimento_manual` returns Ano 2025, TipoRendimento 1, the CNPJ and the value. The edit keeps the ItemID. |
| `bastter.imposto_de_renda.excluir_ir_rendimento_manual` | ir | The ItemID is gone from `Manual.Isentos`. `obter_ir_rendimento_manual` answers `null`. |
| `bastter.imposto_de_renda.salvar_prejuizo_ano_anterior` | ir | `listar_prejuizo_ano_anterior` has Ano 2001 with AcaoValor 5.0, FIIValor 3.0. The edit keeps the ItemID with 7.0 and 2.0. |
| `bastter.imposto_de_renda.excluir_prejuizo_ano_anterior` | ir | The ItemID is gone. |
| `bastter.imposto_de_renda.ir_aluguel_rendimento_salvar` | ir | `ir_aluguel_rendimento_listar` has Ano 2019 with Valor 5.0. The edit keeps the ItemID with Valor 7.0. |
| `bastter.imposto_de_renda.ir_aluguel_rendimento_excluir` | ir | The ItemID is gone. |
| `bastter.imposto_de_renda.ir_save_bens_direitos_exterior` | ir | `obter_posicao_anual_ativos` (stock, 2025) shows the asset with AplFinLucroPrejuizo 2.0, AplFinImpostoPagoExterior 1.0, AtualizacaoUsuario true. |
| `bastter.imposto_de_renda.ir_delete_bens_direitos_exterior` | ir | AtualizacaoUsuario is false again and the value 2.0 is gone. The system calculates the values again. |
| `bastter.pas.doacao_instituicao_salvar` | doacoes | The institution is in `doacao_instituicao_listar`. `doacao_instituicao_obter` returns the name and the CNPJ. The edit keeps the InstituicaoID with the new name. |
| `bastter.pas.doacao_instituicao_excluir` | doacoes | The InstituicaoID is gone from the list. |
| `bastter.pas.doacao_salvar` | doacoes | The donation is in `doacao_listar` with Data 2025-06-16, Valor 5.0, CodIRPF 99. It is also in `doacao_listar_ir` (2025) and in `doacao_listar_consolidado`. The edit keeps the DoacaoID with Valor 7.0. |
| `bastter.pas.doacao_excluir` | doacoes | The DoacaoID is gone from `doacao_listar` and from `doacao_listar_ir`. |

Asset-family writes that the IR scenario needs, verified as a side effect: `bastter.ativos.save_movement` (a `Buy` of 1 KFY on 06/16/2025 in `get_movement`) and `bastter.ativos.delete_movement` (the MovimentacaoID is gone).

Reads that the scenarios run with assertions: `financa_obter_itens`, `financa_obter_evolucao_categoria`, `financa_obter_consolidado_data`, `financa_obter_despesa_dedutivel`, `financa_listar_sugestoes`, `imposto_de_renda.financa_listar_despesa_dedutivel`, `calc_juros_list`, `calc_juros_get`, `exterminador_divida_list`, `exterminador_divida_get`, `irdarf_listar`, `irdarf_obter`, `obter_posicao_anual_proventos`, `obter_ir_rendimento_manual`, `listar_prejuizo_ano_anterior`, `ir_aluguel_rendimento_listar`, `obter_posicao_anual_ativos`, `doacao_listar`, `doacao_obter`, `doacao_listar_consolidado`, `doacao_listar_ir`, `doacao_instituicao_listar`, `doacao_instituicao_obter`, `bs2_init`. The scenario also calls `financa_obter_dados_graficos` and `financa_obter_consolidado_categoria`, but only checks that the month bucket or the expense map exists, because their keys are the category name and the engine cannot render a variable in an `equals` path.

## Actions not run

| Action | Why |
|---|---|
| `bastter.financeiro.calculadora_juros_save_topico` | It posts the simulation as a forum topic (`WsForum`), which other users see. Safety rule 5. |

Reads in the Financeiro area that no write of this family changes, so the scenarios do not call them: `get_aportes_historico`, `listar_movimentacao`, `obter_dividas_dados_graficos`. Other IR writes that were not in the assigned list were not touched: `salvar_ir_imovel_aluguel_previdencia_dep`, `salvar_opcoes_ir_copiar_marcar`, `ir_marcar_linha`.

## Donations do not send money

I read `site.bs2.pas.doacoes` before any call (`.cache/discover/58d5c9a0...txt`). `DoacaoSalvar` sends only `{doacaoID, data, Instituicao: {InstituicaoID}, valor, codIRPF, anotacoes}` and then reloads the list. `DoacaoInstituicaoSalvar` sends only `{InstituicaoID, Nome, CPF}`. The script has no payment, PIX, e-mail or notification call. The records feed the user's own IR Doações screen.

The institution list also holds 8 global "Anjos" institutions. The same page shows a public Anjos campaign counter (`GetWorksInfoWeb`, worksID 62). The scenario does not record a donation to an Anjos institution. It creates its own `ZZTESTE` institution and records the donation there.

## Surprises

1. `FinancaSalvar` answers `{"Return": "Item salvo com sucesso."}` with no ID. The scenario reads the LancamentoID and the CategoriaID from `financa_obter_itens` by the `ZZTESTE` description.
2. Date formats differ per screen. Finanças takes `dd/mm/yyyy` (15/11/2026 was saved as 15 November). The value is a string with a comma (`"10,00"`). DARF takes `periodo: "yyyy-MM-01"`. Donations take `data: "yyyy-MM-dd"`. Stock movements take `mm/dd/yyyy`.
3. A finance entry with `categoriaID: 0` and a `categoriaDescricao` creates a new category. Deleting all its entries does not delete the category. Only `financa_excluir_categoria` does.
4. A monthly income created on 2026-11-03 for 16/11/2026 produced 14 entries (11/2026 to 12/2027) under one RecorrenciaID.
5. The deductible-expense CPF is stored without the mask (`111.444.777-35` becomes `11144477735`). Beneficiary suggestions come from the existing deductible expenses, so they disappear with the expense.
6. Reads of a deleted item do not all fail the same way. `calc_juros_get`, `exterminador_divida_get` and `obter_ir_rendimento_manual` answer the string `null` with status 200. `financa_obter_despesa_dedutivel` answers `{"Error": "Item inválido"}`. `doacao_obter` and `doacao_instituicao_obter` answer `{"Error": "Erro ao obter."}`.
7. The two calculators are on `WsWorks.asmx`, not on `WS_Carteira.asmx`.
8. `irdarf_obter` is a lookup by code and month. DARFID 0 means "not paid". A saved DARF makes the DARF modal show that month as paid.
9. `obter_posicao_anual_proventos` returns manual items with Ano 0 and TipoRendimento 0. Only `obter_ir_rendimento_manual` returns the real values.
10. Prejuízo de anos anteriores and aluguel rendimento have no free-text field, so the `ZZTESTE` prefix cannot mark them. The scenario first asserts that the owner has no item for 2001 and 2019, and then finds its item by year.
11. `ir_save_bens_direitos_exterior` needs a foreign asset with a position in the year. The scenario adds KFY to Stocks with one buy in 2025 and removes the buy and the asset at the end. With no movement left, KFY does not appear in Bens e Direitos 2025, not even as a deleted asset.
12. Lists mask the owner: `UsuarioID` and `CarteiraID` are 0 in list items. `doacao_instituicao_obter` and `doacao_obter` show the real UsuarioID.
13. `doacao_listar_ir` and `doacao_listar_consolidado` return rows grouped by institution with DoacaoID 0. The scenario matches the nested `Instituicao` object.
14. Other agents used the same session at the same time. Some calls took 65 s and four timed out on the client (twice at 30 s, twice at 120 s). One timed-out `DoacaoSalvar` was applied on the server. After a timeout on a write, read the list before retrying.

## Development probes

I built the bodies with direct `raw_call` probes before writing the scenarios. These calls do not write to `evidence/runs.jsonl`. Every item they created was deleted in the same session, and the final reads below confirm it. The probes created: finance entries 280321 and 280322 to 280335 (RecorrenciaID 6077), category 25631, juros simulation 98, exterminador simulation 138, DARF 6876, manual income 177, prejuízo 977, aluguel 1197, stock KFY (AtivoID 746015) with movement 735522, institution 750 and donation 2079. The probe also changed `FinanceiroAportesConsideraMoeda` once and restored it.

## Nothing created is left

Final reads after the last run (2026-11-03, after `doacoes-ciclo-1793730507`). None of the answers contains `ZZTESTE` or `KFY`.

| Read | Answer |
|---|---|
| `financa_obter_itens` (all months) | `{"Lancamentos": [], "Categorias": [], "Meses": []}` |
| `calc_juros_list` | `[]` |
| `exterminador_divida_list` | `[]` |
| `irdarf_listar` | `[]` |
| `irdarf_obter` (6015, 2026-10-01) | `{"DARFID": 0}` |
| `obter_posicao_anual_proventos` 2025, `Manual` | `{"Isentos": [], "Tributaveis": []}` |
| `listar_prejuizo_ano_anterior` | `[]` |
| `ir_aluguel_rendimento_listar` | `[]` |
| `obter_posicao_anual_ativos` stock 2025 | `[]` |
| `financa_listar_despesa_dedutivel` 2026 | `[]` |
| `financa_listar_sugestoes` (nome, `ZZTESTE`) | `[]` |
| `doacao_listar` | `[]` |
| `doacao_listar_consolidado` | `[]` |
| `doacao_listar_ir` 2025 | `[]` |
| `doacao_instituicao_listar` | the 8 global Anjos institutions only (ids 6, 61, 11, 9, 62, 8, 7, 10), the same as before the work |
| `ativos.obter_itens` stock | `{"Items": []}` |
| `bs2_init` Aportes options | all five false, the same as before the work |

## Update after the audit (2026-11-03)

The probe item KFY (stock, AtivoID 746015) was only hidden, not deleted: its probe calls were not logged, so the purge never saw it. It was deleted for good with `excluir_movimentacao_ativo` on 2026-11-03 (the first call answered `Return: OK`, a repeat answered `Error`). The other probe records listed above are finance entries, simulations and IR items, which their delete methods remove for good.
