# Family: PAS and portfolio settings

Date: 2026-11-03. Scope: the PAS screens (`/bs2/pas/*`) and the portfolio settings (`/bs2/patrimonio/*`, `/bs2/`, `/bs2/configuracoes`, `/bs2/modos`).

Result: 21 write actions pass a full cycle on the live account (10 PAS, 11 settings). Six write actions in scope were not run as a change. The two notification methods were never run. Nothing that the scenarios created is left. Two settings are NOT back to the exact old value, see "Left changed on the account". Both differences are invisible on the screens, and no method in the app can write the old values back.

## Scenarios and run ids

| Scenario | Run id | Steps | Failures | Verifies |
|---|---|---|---|---|
| `scenarios/pas_metas_ciclo.yaml` | `pas-metas-ciclo-1793729732` | 17 | 0 | metas_salvar (create, edit), metas_salvar_concluido (mark, unmark), metas_arquivar (archive, unarchive), metas_excluir |
| `scenarios/archive/pas_diario_atividade_ciclo.yaml` | `pas-diario-atividade-ciclo-1793729934` | 9 | 0 | diario_atividade_salvar (create, edit), diario_atividade_excluir |
| `scenarios/pas_agradecer_privado_ciclo.yaml` | `pas-agradecer-privado-ciclo-1793730125` | 9 | 0 | agradecer_salvar (create, edit), agradecer_excluir |
| `scenarios/pas_sardinhagem_privado_ciclo.yaml` | `pas-sardinhagem-privado-ciclo-1793730146` | 9 | 0 | diario_sardinhagem_salvar (create, edit), diariosardinhagem_excluir |
| `scenarios/config_salvar_opcao.yaml` | `config-salvar-opcao-1793730341` | 5 | 0 | salvar_opcao |
| `scenarios/config_salvar_ordenacao.yaml` | `config-salvar-ordenacao-1793730349` | 5 | 0 | salvar_ordenacao |
| `scenarios/config_abas_salvar.yaml` | `config-abas-salvar-1793730355` | 5 | 1 | abas_salvar (restore read gave `[""]`, see below) |
| same | `config-abas-salvar-1793730787` | 5 | 0 | abas_salvar |
| `scenarios/config_colunas_salvar.yaml` | `config-colunas-salvar-1793730360` | 5 | 0 | colunas_salvar |
| `scenarios/config_carteira_alterar_nome.yaml` | `config-carteira-alterar-nome-1793730391` | 6 | 0 | carteira_alterar_nome |
| `scenarios/config_modo_onde_aportar.yaml` | `config-modo-onde-aportar-1793730397` | 5 | 0 | modo_onde_aportar_salvar |
| `scenarios/config_insights_classes.yaml` | `config-insights-classes-1793730496` | 5 | 0 | bs2_insights_classes_salvar |
| `scenarios/config_onde_retirar.yaml` | `config-onde-retirar-1793730501` | 5 | 0 | bs2_onde_retirar_salvar |
| `scenarios/config_modo_salvar.yaml` | `config-modo-salvar-1793730552` | 5 | 0 | modo_salvar |
| `scenarios/config_ocultar_financeiro.yaml` | `config-ocultar-financeiro-1793730566` | 5 | 0 | bs2_ocultar_financeiro |
| `scenarios/config_salvar_opcoes.yaml` | `config-salvar-opcoes-1793730613` | 3 | 1 | salvar_opcoes (stopped, see below) |
| same | `config-salvar-opcoes-1793730740` | 5 | 0 | salvar_opcoes |
| `scenarios/config_objetivo_classes_recusa.yaml` | `config-objetivo-classes-recusa-1793730777` | 3 | 0 | nothing (shows the refusal, no `postcondition_of`) |
| `scenarios/pas_config_estado_final.yaml` | `pas-config-estado-final-1793730859` | 11 | 0 | read only, final state |

Development calls are in `evidence/runs.jsonl` under the run `dev-pas-config`. Two earlier attempts (the activity and the thanks scenarios) stopped on a 30 s read timeout in their first step. That step is a read, so these attempts created nothing and logged nothing.

The account belongs to user 1000001. The portfolio id is 2000002.

## Verified write actions

PAS (`bastter.pas.`): `metas_salvar`, `metas_salvar_concluido`, `metas_arquivar`, `metas_excluir`, `diario_atividade_salvar`, `diario_atividade_excluir`, `agradecer_salvar`, `agradecer_excluir`, `diario_sardinhagem_salvar`, `diariosardinhagem_excluir`.

Settings: `bastter.ativos.salvar_opcao`, `bastter.ativos.salvar_ordenacao`, `bastter.ativos.abas_salvar`, `bastter.ativos.colunas_salvar`, `bastter.ativos.carteira_alterar_nome`, `bastter.ativos.modo_onde_aportar_salvar`, `bastter.patrimonio.bs2_insights_classes_salvar`, `bastter.patrimonio.bs2_onde_retirar_salvar`, `bastter.configuracoes.modo_salvar`, `bastter.ativos.bs2_ocultar_financeiro`, `bastter.ativos.salvar_opcoes`.

Reads used as read-backs (all answered 200 with the expected data): `metas_listar`, `metas_obter`, `metas_anotacoes_consolidado`, `diario_atividade_listar`, `diario_atividade_obter`, `agradecer_listar`, `agradecer_obter`, `agradecer_outros_listar`, `diariosardinhagem_listar`, `diariosardinhagem_obter`, `diariosardinhagem_outros_listar`, `diario_obter`, `bastter.ativos.bs2_init`, `bastter.patrimonio.obter_classes`, `bastter.patrimonio.bs2_onde_retirar_carregar`, `bastter.home.bs2_home_carregar`, `bastter.patrimonio.bs2_visao_geral_resumo`.

### Request bodies that work

- `metas_salvar`: `{meta: {metaID: 0, descricao, periodo: "5", dias: 0, dataInicio: null, notificar: false}}`. Use the MetaID to edit. Period 5 is "once".
- `metas_salvar_concluido`: `{concluido: {metaID, referencia, anotacao: null}}`. For period 5 the reference is the MetaID.
- `metas_arquivar`: `{metaID, arquivar: true|false}`. `metas_excluir`: `{metaID}`.
- `diario_atividade_salvar`: `{atividade: {atividadeID: 0, tipoAtividade: {tipoAtividadeID: 9}, data: "11/03/2026", quantidade: 1, anotacao}}`. `diario_atividade_excluir`: `{atividadeID}`.
- `agradecer_salvar`: `{agradecimento: {AgredecimentoID: 0, data: "11/03/2026", privado: true, Anotacoes}}` (the app spells the id `AgredecimentoID`). `agradecer_excluir`: `{itemID}`.
- `diario_sardinhagem_salvar`: `{sardinhagem: {ItemID: 0, data, privado: true, Anotacoes}}`. `diariosardinhagem_excluir`: `{itemID}`.
- `salvar_opcao`: `{parameter: "UltimosProventos", value: "2"}`. `salvar_ordenacao`: `{aba: "consolidadoproventos", ordenacaoID: 2}`.
- `abas_salvar`: `{tipo: 2, abas: ["meu-futuro-patrimonio"]}`. The types are 1 ativos, 2 patrimonio, 3 financeiro, 4 ir, 5 saude, 6 pas. The list holds the hidden tabs.
- `colunas_salvar`: `{tipo: "consolidado", colunas: ["% Mês", "% Ano", "Objetivo"]}`. The list holds the hidden columns.
- `carteira_alterar_nome`: `{carteiraID, nome}`. `modo_onde_aportar_salvar`: `{modo: "1"}`. `modo_salvar`: `{modo: "4"}`.
- `bs2_insights_classes_salvar`: `{classes: "acao,fii"}`. A null value is accepted and means all classes.
- `bs2_onde_retirar_salvar`: `{valorNecessario, saldoConta, salario, salarioExibir, outrasRendas, custosMensais}`. Null values are accepted.
- `bs2_ocultar_financeiro`: `{ocultar: true|false}`.
- `salvar_opcoes`: the whole `CarteiraOpcoes` object from `bs2_init`, flat. The server ignores keys that are not parameters.

## Old value of each setting and the read that shows the restore

| Setting | Old value | Test value | Restore read (step, run) |
|---|---|---|---|
| `CarteiraOpcoes.UltimosProventos` | `"1"` | `"2"` | `opcao_restaurada`, `config-salvar-opcao-1793730341`. The whole `CarteiraOpcoes` object equals the one read before. |
| `Ordenacao` | `[{Aba: consolidadoproventos, OrdenacaoID: 1}]` | OrdenacaoID 2 | `ordenacao_restaurada`, `config-salvar-ordenacao-1793730349` |
| `AbasPatrimonioExcluidas` | `[]` | `["meu-futuro-patrimonio"]` | NOT exact. It reads `[""]`, see below. `abas_restauradas` in `config-abas-salvar-1793730787` shows that the restore is exact from `[""]`. |
| `obter_classes.ColunasExcluidas` | `["% Mês", "% Ano"]` | plus `Objetivo` | `colunas_restauradas`, `config-colunas-salvar-1793730360` |
| Portfolio name (`Carteiras[CarteiraID=2000002].Nome`) | `Principal` | `ZZTESTE <ts>` | `nome_restaurado`, `config-carteira-alterar-nome-1793730391` |
| `CarteiraOpcoes.ModoOndeAportar` | `0` (and `ModoOndeAportarAlternado` false) | `1` | `modo_restaurado`, `config-modo-onde-aportar-1793730397`. The whole `CarteiraOpcoes` object is equal. |
| `CarteiraOpcoes.InsightsClasses` | `null` | `"acao,fii"` | `classes_restauradas`, `config-insights-classes-1793730496`. The whole `CarteiraOpcoes` object is equal. |
| `bs2_onde_retirar_carregar.Config` | all six fields null, `SalarioExibir` false | ValorNecessario 10, SaldoConta 5 | `config_restaurada`, `config-onde-retirar-1793730501` |
| `CarteiraOpcoes.Modo` | `2` (Normal) | `4` (Saúde e PAS) | `modo_restaurado`, `config-modo-salvar-1793730552`. The whole `CarteiraOpcoes` object and the three hidden-tab lists are equal. |
| `FinanceiroOcultoSessao` | `false` | `true` | `restaurado`, `config-ocultar-financeiro-1793730566`. The whole `CarteiraOpcoes` object is equal. |
| `CarteiraOpcoes.ExibirLogo` (through `salvar_opcoes`) | `true` | `false` | `opcoes_restauradas`, `config-salvar-opcoes-1793730740`. The whole object is equal. The first run changed two other fields, see below. |

## Not run, and why

- `bastter.pas.diario_salvar` (initial and current weight). `diario_obter` answers `"null"`, so the account has no weight record. The app has no method to delete this record, so the old value (no record) cannot come back. The weights also feed the public weight ranking `diario_peso_rank_listar` (830 users, with their logins).
- `bastter.home.bs2_home_salvar`. The old value of `bs2_home_carregar.Config` is null. The server refuses `config: null` with "Erro ao salvar a personalização da home: Personalização inválida." A dev call checked this and changed nothing. Any accepted write leaves a non-null config.
- `bastter.patrimonio.bs2_visao_geral_layout_salvar`. The layout was never saved (`{Ordem: [], Fechados: []}`). `abas_salvar` showed that this server can store an empty list as an empty string that reads back as `[""]`, and it refuses null. No call can show how the layout behaves without a write, so an exact restore is not certain. Run it only if the owner accepts that risk.
- `bastter.patrimonio.salvar_objetivo_classes`. All class objectives are 0 (sum 0). The server saves only when the sum is 100, or when `ajustarProporcional` is true. A write of Ações 10 answered `{Diferente100: true}` and changed nothing (`config-objetivo-classes-recusa-1793730777`). A restore to all zeros would get the same refusal, so a real change could not be undone.
- `bastter.ativos.carteira_criar` and `bastter.ativos.carteira_excluir`. A delete needs the account password, so a created portfolio cannot be removed.
- `agradecer_salvar_notificacao` and `diario_sardinhagem_salvar_notificacao`. These are notification methods, which the rules forbid.
- Public thanks and public sardinhagem entries (`privado: false`). They appear in the feed of other users (`agradecer_outros_listar`, `diariosardinhagem_outros_listar`). The scenarios write only private records.

## Safety notes for PAS

- Thanks and sardinhagem: the app marks a private record "Privado: só você pode ver". The other-users feed showed 10 of 10 items with `Privado: false`. Each scenario reads `Privado: true` back right after the write, and checks that the record is not on page 1 of the other-users feed. The read steps have `stop_on_fail: false`, so the delete runs in all cases.
- Diary activity: `diario_atividade_rank_listar` is a public top 50 per activity type. Type 9 (Meditação, minutes) had 50 users, and the lowest had 104 minutes. The scenario writes 1 and then 2 minutes, so the user cannot enter the visible ranking. A dev read after a save showed that user 1000001 was not in the type 9 ranking.
- Goals have `notificar: false`.

## Surprises

1. `metas_obter` always returns `Concluidos: null` and `DataArquivamento: null`. Only `metas_listar` and `metas_anotacoes_consolidado` show them. After a delete, `metas_obter` answers `{Error: "Erro ao obter meta."}`.
2. `metas_salvar_concluido` is a toggle. A second call with the same reference removes the mark. The answer has the list `Concluidos`, with `Referencia` as a string.
3. `metas_salvar`, `metas_arquivar`, `metas_excluir`, the activity, thanks and sardinhagem saves and deletes answer `{Return: true}` without the new id. The scenarios find the id in the list by the ZZTESTE text.
4. `diario_atividade_listar` returns a list at the top level. It shows `TemQuantidade: false` for type 9, but `diario_atividade_obter` shows `true`. After a delete, `diario_atividade_obter` answers the string `"null"` and no error. The delete is a hard delete.
5. `abas_salvar` with `abas: []` stores an empty string, which reads back as `[""]`, not `[]`. `abas: null` answers `{Error: "Erro ao salvar abas."}`.
6. `salvar_opcoes` writes 0 to `ProventosPizzaTipo` and `ProventosPizzaItem` whatever the body holds (tested with 1 and "1"). The Configurações screen sends the same body, so a save from the screen does the same. `salvar_opcao` refuses these names with "Parâmetro não permitido." It has an allow-list, and `UltimosProventos` is on it.
7. `bs2_ocultar_financeiro` changes only `FinanceiroOcultoSessao`. After the restore, `CarteiraOpcoes.ExibirFinanceiro` and all other options were equal to the old values.
8. Answer shapes differ by method. `bs2_insights_classes_salvar` and `salvar_opcoes` answer `{Return: "OK"}`. `bs2_onde_retirar_salvar` answers `{Sucesso: true}`. `salvar_objetivo_classes` answers `{Diferente100: true}` when it refuses.
9. `modo_onde_aportar_salvar` accepts the string `"1"` and stores the number 1.
10. Server latency changes a lot. `bs2_visao_geral_resumo` took 107 s once and 0.6 s later. The scenario engine has a 30 s timeout and does not catch it, so a timeout stops a run with a traceback.

## Left changed on the account

The scenarios created no records that are still on the account. Two settings are not at the exact old value.

1. `CarteiraOpcoes.ProventosPizzaTipo` and `CarteiraOpcoes.ProventosPizzaItem` changed from 1 to 0. Cause: the first `salvar_opcoes` run (`config-salvar-opcoes-1793730613`), see surprise 6. I tried `salvar_opcoes` with the old values and `salvar_opcao` with four parameter names. All failed. No app script reads these two fields except to copy them into `bs.opcoes`, so no screen changes. The only fix is on the server side, or a call that I did not find.
2. `AbasPatrimonioExcluidas` changed from `[]` to `[""]`. Cause: the first `abas_salvar` run (`config-abas-salvar-1793730355`), see surprise 5. No tab is hidden, so the menu looks the same. The API cannot store null.

All other values match a snapshot taken before the first write. The read-only scenario `pas_config_estado_final.yaml` (run `pas-config-estado-final-1793730859`) shows the final state:

- The goals, activities, thanks and sardinhagem lists are empty, and the weight diary is `"null"`.
- The portfolio is named `Principal`.
- `UltimosProventos`, `ExibirLogo`, `Modo`, `ModoOndeAportar`, `InsightsClasses`, `TipoExibicao`, `ExibirFinanceiro` and `ExibirFinanceiroRank` have their old values. `FinanceiroOcultoSessao` is false.
- The ordering list, the hidden columns of the Consolidado and the class objectives (all 0) have their old values.
- The Onde Retirar config is all null. The home config is null. The overview layout is `{Ordem: [], Fechados: []}`.

## Update after audit round 2 (2026-11-03)

- Surprise 10 is out of date for the tools: the session timeout is 60 s and the scenario engine catches a timeout. A read-back that times out is logged with `passed: null` and does not mark its write failed.
- `diario_atividade_salvar` is now marked `publishes` with confirmation, and the MCP server refuses it. Its scenario moved to `scenarios/archive/`, so `run_all_scenarios.py` does not write to the ranking again.
- The PAS dates: the app builds them with `toDateServerM`, which sends `yyyy-mm-dd`. The scenarios sent `11/03/2026`. For the activity diary the read-back showed 3 November. For thanks and sardinhagem no read-back checked the date.
- Each settings scenario restores the old value in a step with `undoes`, so the restore also runs when a later step fails. `config_insights_classes` saves the old filter with `nullable: true`, because the old value is null.
