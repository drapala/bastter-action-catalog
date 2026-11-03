# Family report: Saúde (`/bs2/saude/*`)

Date: 2026-11-03. Account user ID: 1000001. Scope: the `bastter.saude.*` actions named in the task.

Result: 17 write actions are verified on the live account. 13 write actions in scope were not run, because they publish to other users or cannot be undone. One setting row with empty values is left on the account (see "What is left on the account").

## Verified write actions

Each write has a read-back step with `postcondition_of` in the scenario. All runs ended with 0 failures.

| Action | Scenario | Run id |
|---|---|---|
| `gym_save_exercicio` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_delete_exercicio` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_save_favorito_exercicio` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_delete_favorito_exercicio` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_save_serie` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_save_nome_serie` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `gym_delete_serie` | `scenarios/saude_gym.yaml` | `saude-gym-1793729731` |
| `diario_humor_salvar` | `scenarios/saude_diarios.yaml` | `saude-diarios-1793729770` |
| `diario_humor_excluir` | `scenarios/saude_diarios.yaml` | `saude-diarios-1793729770` |
| `diario_saudavel_salvar` | `scenarios/saude_diarios.yaml` | `saude-diarios-1793729770` |
| `diario_saudavel_excluir` | `scenarios/saude_diarios.yaml` | `saude-diarios-1793729770` |
| `race_meta_salvar` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |
| `race_meta_excluir` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |
| `race_periodizacao_salvar` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |
| `race_periodizacao_excluir` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |
| `race_peso_salvar` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |
| `race_peso_excluir` | `scenarios/saude_race_privado.yaml` | `saude-race-privado-1793730171` |

The gym and diary scenarios also edit the record they created (same ID, new values) and read it back. This shows that a save with an existing ID updates the record and does not add a second one.

Meta and periodização are single settings per user. The scenario reads the current value first and stops if it is not `"null"`. It then saves, reads back, deletes, and reads `"null"` again. Deleting is the restore, because the value before the run was "no setting".

## Reads run

These reads ran inside the scenarios above or in `scenarios/saude_leituras.yaml` (run `saude-leituras-1793730214`, read only, 20 steps, 0 failures):

- Gym: `gym_list_musculo`, `gym_list_exercicio`, `gym_get_exercicio`, `gym_search_exercicio`, `gym_list_serie`, `gym_get_serie`, `gym_list_treino`, `gym_get_last_treino`, `gym_list_historico_exercicio`, `gym_list_historico_serie`, `gym_rank`, `gym_rank_grafico`.
- Diaries: `diario_humor_listar`, `diario_humor_obter`, `diario_humor_relatorio_listar`, `diario_saudavel_listar`, `diario_saudavel_obter`.
- Other: `psfg_list`, `parou_beber_get_stats`, `race_pendencia_listar`, `race_inspiracao_listar`, `race_peso_listar`, `race_meta_obter`, `race_periodizacao_obter`, `race_alimentacao_list`.

Reads not run: `gym_get_treino` and `gym_get_treino_exercicios`. They need a `treinoID`. The account has no treino, and creating one publishes to the Gym ranking.

## Write actions not run, and why

The evidence comes from the minified scripts in `.cache/discover/` and from live reads.

### Public: the record appears to other users

| Action | Why it is public |
|---|---|
| `gym_save_treino`, `gym_delete_treino` | `site.bs2.saude.gym-min.js` `getRank` renders `GymRank` as a list of all users with `Usuario.Login` and `Pontos`. The page text says "Halteres = pontuação do Bastter Gym calculada por treinos x séries" and, per exercise, "Volume = Séries x Repetições x Pesos". A saved treino adds points in this ranking. Live read: `GymRank.Rank.Pessoal.Posicao` is 0, so the account is not in the ranking now. |
| `race_atividade_salvar`, `race_atividade_excluir` | An activity is the scoring unit of Bastter Race (`site.bs2.saude.race-min.js`). `RaceRank` lists every participant with login, avatar and a "Ver treinos" link to `/#perfil_<id>,perfil-treinos`. `RaceRankDetalhes` shows "Últimos Exercícios" of a user to others. The activity modal also has the share setting `BSSaudeCompartilharTreino`, and `RaceAtividadeValidar` can answer `Exists8h`, which opens a forum topic for moderation. |
| `race_alimentacao_save`, `race_alimentacao_delete` | `site.bs2.saude.race.alimentacao-min.js` `listRanking` renders `RaceAlimentacaoRankingList` as a list of all users with position, `@login` and `Pontos`. A saved day gets `PontosTotal`. |
| `race_inspiracao_salvar`, `race_inspiracao_excluir` | In `site.bs2.saude.race-min.js`, the save stores another participant as "inspiração". `RaceInspiracaoRankQuemAdicionou` ("Me Escolheram") shows the chosen person who chose them. `RaceInspiracaoRankTopAdicionados` ranks the most chosen users. `RaceInspiracaoListar(usuarioID)` shows the choices of any user. The action reaches another person. |
| `parou_beber_save`, `parou_beber_delete` | `site.esporte.paroubeber-min.js` `list` renders `ParouBeberList` as avatar and `@login` of every user who marked "Parei de Beber", with a public counter "Juntos já somos N". Live read: `Count` is 424 and `Has` is false. The mark is also sensitive health data. |
| `race_pendencia_salvar`, `race_pendencia_excluir` | A pendência comes only from a Strava import or from moderation. The account has none (live read: `Pedencias` and `Fila` are empty), so there is nothing of ours to act on. `RacePendenciaSalvar` confirms the activity "e incluir no seu Bastter Race", so it publishes like `race_atividade_salvar`. `race_pendencia_excluir` would only touch a pre-existing item. |

### Cannot be restored

| Action | Why it was not run |
|---|---|
| `psfg_save` | Body `{parametro: "exercise-0".."exercise-9", nota: 1..5}`. The current value is "no rating" (`PSFGList.Items` is `[]`, `Media` 0). There is no PSFG delete method, so after a save the old state cannot be restored. Rules 3 and 5 of the guide apply. The record looks private (no rank reads it), but the change is permanent. |

Out of scope and not run: every action with Strava, Validar, Fila, Layout, Lembrete or PegaUm in the name, and `race_sequencia_meta_salvar`.

## Surprises

1. Every save answers `{"Return": true}` and does not return the new ID. The scenarios find the ID in the list read by the `ZZTESTE` name or anotação.
2. A new Gym program is saved with `serieID: -1`. This is the value the UI gives to a new program.
3. `GymListExercicio` shows the user's own exercise with `Editable: false` and always `Favorito: false`. `GymGetExercicio` shows the same exercise with `Editable: true`. A favorite is visible only in `GymSearchExercicio` with `favorito: true`. That search returns `UsuarioID: 0` and `MusculoID: 0` in its items.
4. `GymListExercicio` has 204 items, all with `UsuarioID` 2600. No exercise made by another user is visible. This is the evidence that a user-made exercise is private.
5. `GymListSerie` returns `UsuarioID: 0` and `Exercicios: null`. Only `GymGetSerie` returns the exercises.
6. `GymGetExercicio` for a system exercise (ID 92) did not answer within 90 seconds, two times. For the user's own exercise it answers in under 1 second. For a deleted ID it answers `{"Error": "Erro ao carregar exercício."}`.
7. `GymListHistoricoSerie` took 26 seconds once.
8. `RaceMetaObter`, `RacePeriodizacaoObter`, `GymGetLastTreino`, and the gets on a deleted ID answer the string `"null"`, not an object. The scenarios assert this with `equals: {"": "null"}`.
9. `RaceMetaExcluir` and `RacePeriodizacaoExcluir` take an empty body `{}`.
10. The forms send dates as `YYYY-MM-DD` (`$.toDateServerM`). The reads return `YYYY-MM-DDT00:00:00`.
11. In `DiarioHumorSalvar`, `acoes` is a string such as `"3;7;"`, not a list.
12. `RacePesoSalvar` always writes the custom label row (`personalizado`) together with the weight item. Before the first save, `RacePesoListar.Personalizado` was `null`. After it, `Personalizado` is an object with three `null` labels. The row stays after the weight item is deleted, and no method removes it.
13. A write can answer late and still land. During development a `RacePesoSalvar` did not answer within 120 seconds, and the tool stopped with `httpx.ReadTimeout`. The item (ItemID 27015) appeared in the list about two minutes later. The `RacePesoExcluir` for it also timed out at 60 seconds and landed later. A call that times out is not written to `evidence/runs.jsonl`. Other agents used the same session at that time. A possible cause is that ASP.NET runs requests of one session one at a time. This cause is not verified. The read-back steps for the weight now use `retry: {times: 6, every: 10}`.
14. Deletes are hard deletes. After the runs, `GymGetSerie`, `DiarioHumorObter` and `DiarioSaudavelObter` on the deleted IDs answer `"null"`, and `GymGetExercicio` answers the Error above.

## Development calls outside the scenarios

Before the scenarios, development calls created and deleted these `ZZTESTE` records. Each one was deleted and is gone in the final reads.

| Run id | Created | Deleted in |
|---|---|---|
| `dev-saude-gym-1793729573` | exercise 1355 | `dev-saude-gym-cleanup-1793729610` |
| `dev-saude-gym-1793729588` | favorite on exercise 1355 | `dev-saude-gym-cleanup-1793729610` |
| `dev-saude-gym-1793729601` | program 3943 | `dev-saude-gym-cleanup-1793729610` |
| `dev-saude-diarios-1793729655` | humor day 13437, saudável day 10937 | same run |
| `dev-saude-race-1793729668` | weight item 27014 | `dev-saude-race-1793729680` |
| `dev-saude-race-1793729692` | meta and periodização | same run |
| not logged (timeout) | weight item 27015 | `cli` call, not logged (timeout), landed later |

## What is left on the account

Nothing that this work created is left, with one exception.

The exception is the weight custom label row. `RacePesoListar.Personalizado` was `null` before the first weight save. It is now `{"UsuarioID": 0, "Personalizado1": null, "Personalizado2": null, "Personalizado3": null}`. All three labels have the old value (empty). The screen shows a label only when it is not null, so the user sees no change. No method deletes the row.

The final reads (run `saude-leituras-1793730214`, all steps pass) show:

- `gym_list_exercicio`: no item with `UsuarioID` 1000001.
- `gym_search_exercicio` with `favorito: true`: `[]`.
- `gym_list_serie`: `[]`. `gym_list_treino`: `[]`. `gym_get_last_treino`: `"null"`. `gym_list_historico_serie`: `[]`.
- `gym_rank`: `Rank.Pessoal.Posicao` is 0.
- `diario_humor_listar`: `Items` is `[]`. `diario_humor_relatorio_listar`: `Detalhado` is `[]`. `diario_saudavel_listar`: `Items` is `[]`.
- `psfg_list`: `Items` is `[]`. `parou_beber_get_stats`: `Has` is false.
- `race_pendencia_listar`: `Pedencias` and `Fila` are `[]`. `race_inspiracao_listar`: `Escolhidos` is `[]`. `race_alimentacao_list`: `[]`.
- `race_peso_listar`: `Items` is `[]`. `race_meta_obter`: `"null"`. `race_periodizacao_obter`: `"null"`.

These are the same values the account had before the work, apart from the label row above.

## Update after audit round 2 (2026-11-03)

- Surprise 13 is out of date for the tools: `bastter_exec.call` now logs a call that gets no answer ("A write may have run"), and the scenario engine catches it. The fact about the server stays: a write can land after the client gives up.
- `saude_race_privado.yaml` now has `guard: true` on `meta_antes`, `periodizacao_antes` and `peso_antes`, and `undoes` on the two deletes that take no ID. A guard that finds the user's real goals or periodização stops the run, and no delete runs.
