# Catálogo de ações do Bastter System

> **Aviso.** Projeto pessoal e não oficial, sem relação com a Bastter.com. Ele usa os web services internos que o
> app do BS2 chama, com a sessão do próprio usuário, para uso pessoal (ver os [termos do Bastter](https://bastter.com/regras)).
> Os cenários escrevem na conta de quem os roda. Leia `docs/SCENARIO_GUIDE.md` antes. Nesta cópia, o ID de usuário
> e o ID de carteira da conta usada no mapeamento viraram 1000001 e 2000002. Os IDs dos registros de teste
> continuam, então a Bastter consegue ligar esses registros à conta. A ferramenta de dados de mercado do repositório
> original ficou de fora.

Um catálogo das ações de negócio do Bastter System (bastter.com/bs2), feito para um agente de IA operar o BS2 por você. Exemplos: lançar uma compra, ver a posição de um ativo, registrar um gasto ou um DARF.

O BS2 não tem API pública. Cada ação aqui é um web service que o próprio app chama. O agente usa a sua sessão do navegador, guardada só no keychain do macOS.

Os números atuais (quantas ações, quantas verificadas, quantas chamadas ao vivo) ficam em `AGENT.md`, seção 0. O build gera essa tabela, e cada número tem o comando que o recalcula.

## Como foi feito

1. **Descoberta.** Um crawler buscou as 105 telas do BS2 com a sessão e leu o JavaScript de cada uma. Ele achou 424 métodos de web service.
2. **Captura.** Um navegador logado abriu cada tela e gravou as chamadas que o app fez, com o corpo exato. Isso deu os parâmetros de cada leitura.
3. **Verificação.** Um script repetiu cada leitura capturada. Cenários fazem cada escrita por completo: criar, ler de volta, editar, ler de volta, apagar e confirmar que sumiu.
4. **Regras.** Um lint roda sobre o catálogo. Os erros reais cometidos no caminho estão em `docs/corrections.jsonl`, cada um com o teste ou a regra que agora o pega.

## Usar com um agente

Configuração MCP:

```json
{"mcpServers": {"bastter": {"command": "<repo>/.venv/bin/python", "args": ["<repo>/tools/mcp_server.py"]}}}
```

O agente deve ler `AGENT.md` primeiro. Ele tem 3 ferramentas de catálogo: `find_actions`, `get_action` e `run_action`. `run_action` recusa ações `seen`, `gated` e `excluded`, e recusa sempre as ações que publicam ou avisam outras pessoas. Ele pede confirmação antes de apagar e antes de escritas que não dá para desfazer. Depois de uma escrita verificada, ele devolve a leitura que a comprova.

## Login

A sessão expira. O `login.py` mostra a data de expiração quando guarda a sessão. Para renovar:

```
.venv/bin/python tools/login.py
```

O Chrome abre na página de login. Você entra (email e senha, ou Google), e o script guarda os cookies no keychain (serviço `bastter-session`). Os cookies nunca vão para um arquivo do repositório.

## Segurança

- O agente nunca roda ações que notificam outras pessoas, mandam email, publicam na comunidade, mexem em 2FA/token ou na integração B3. Elas estão marcadas no catálogo, e o `run_action` recusa todas, mesmo com confirmação. Os diários de atividades e de peso entram nessa lista, porque alimentam rankings públicos.
- Os cenários criam registros próprios, com o prefixo `ZZTESTE`, e apagam no fim. Antes de mexer num ativo, o cenário confere que a aba não tem esse ticker e que o item não tem movimentação. Se a conferência acha um dado seu, o cenário para sem apagar nada. Se outro passo falha, só rodam os passos que desfazem o que a própria execução escreveu.
- Os cenários de configuração leem o valor atual, mudam, conferem e restauram. Duas opções não voltam ao valor exato, e nenhuma aparece na tela (`docs/families/pas-e-config.md`).
- Excluir um ativo só esconde a linha. `tools/purge_hidden_items.py` apaga de vez só o que os cenários esconderam. Antes, ele lê o item de novo e confere que continua escondido e sem movimentação. Um item que você escondeu sem nenhuma movimentação, com o ticker de um cenário, ainda pode ser reaproveitado pelo cenário e apagado. Imóvel não tem exclusão definitiva no BS2: 5 imóveis ZZTESTE (IDs 41241 a 41245) ficaram escondidos e não aparecem em nenhuma tela.
- As chamadas que um agente faz pelo MCP ficam em `logs/mcp-runs.jsonl`, fora do git, porque têm as suas operações reais.
- O log de evidência guarda o formato das respostas, nunca os valores. Os seus dados financeiros não ficam no repositório. Ele guarda as entradas enviadas: os IDs da sua conta, os valores de teste ZZTESTE e, nos passos que restauram uma configuração, o valor antigo dela (por exemplo o nome da carteira). A transcrição do demo (`demo/agent-demo-*.md`) é outra coisa: mostra as respostas reais das chamadas do demo, feitas com dados de teste.
- `tools/presubmit_check.py` roda em todo commit, pelo hook `tools/pre-commit` (instale com `ln -s ../../tools/pre-commit .git/hooks/pre-commit`). Ele falha se um valor de cookie aparecer em algum arquivo, mesmo codificado em URL ou base64.

## Instalar

```
uv venv && uv pip install -r requirements.txt
```

O login usa o Chrome instalado no Mac.

## Conferir

```
.venv/bin/python -m pytest -q                  # testes, sem chamar o Bastter
.venv/bin/python tools/catalog_lint.py         # lint do catálogo
.venv/bin/python tools/presubmit_check.py      # nenhum segredo nos arquivos
.venv/bin/python tools/build_catalog.py        # refaz o catálogo a partir das evidências
```

## Estrutura

| Caminho | O que é |
|---|---|
| `AGENT.md` | Guia para o agente: status, protocolo, respostas, comportamentos do Bastter, números. |
| `catalog/` | O catálogo: `index.json`, uma entrada por ação em `actions/`, schema, claims, cobertura, lint. |
| `evidence/` | Captura do navegador e log das chamadas e leituras de volta. |
| `scenarios/` | Ciclos de escrita ao vivo. |
| `sources/discover/` | Crawler, lista de telas e métodos achados no JavaScript. |
| `tools/` | Gerador, build, executor, servidor MCP, lint, login, checagem de segredos. |
| `docs/` | Registro de correções, guia de cenários e relatórios por família. |
