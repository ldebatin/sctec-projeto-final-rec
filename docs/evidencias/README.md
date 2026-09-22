# Evidências de execução

Provas de funcionamento exigidas pela rubrica: saídas e logs reais com o Gemini, saída da suíte de testes e registros do pipeline de CI. Tudo aqui foi gerado pela própria aplicação ou pela API do GitHub e copiado sem edição, exceto onde indicado. Os dados dos chamados, contatos e equipes são fictícios (`empresa.exemplo`).

## Mapa da pasta

| Caminho | O que é | Como foi gerado |
|---|---|---|
| [`testes.txt`](testes.txt) | Saída integral de `uv run pytest -v` em 16/09/2026: **372 testes verdes**, inclusive os 2 `live` que chamam o Gemini real | `uv run pytest -v`; caminho local da máquina substituído por `<repo>` |
| [`ci/primeira-execucao-verde.md`](ci/primeira-execucao-verde.md) | Primeira execução verde do workflow (11/09, PR #22), com a falha da execução #1 explicada | API do GitHub Actions |
| [`ci/execucao-main-2026-09-16.md`](ci/execucao-main-2026-09-16.md) | Execução #36 na `main` sobre o código final: 370 testes em Python 3.10 e 3.12, lint, formatação e build; histórico das 36 execuções | API do GitHub Actions |
| [`execucoes/prompt-v1/`](execucoes/prompt-v1/README.md) | Rodada dos 7 exemplos com os prompts **v1** (linha de base do refinamento), mais a falha simulada da tool (`02_portal_tool_indisponivel`), o retry após um erro real do provedor (`01_reset_senha_retry_apos_403.jsonl`) e duas re-execuções: [`pos-calibracao-bm25/`](execucoes/prompt-v1/pos-calibracao-bm25/) e [`pos-qa-regras/`](execucoes/prompt-v1/pos-qa-regras/) | `uv run triagem triar --arquivo ... --salvar` |
| [`execucoes/prompt-v2/`](execucoes/prompt-v2/README.md) | Rodada dos 7 exemplos com os prompts **v2**, o código final: os 7 cenários batem com [`docs/cenarios.md`](../cenarios.md) | idem |

O PRD previa `logs/` e `saidas/` separados. O layout adotado é um par por cenário, agrupado pela versão do prompt, porque o refinamento da issue #16 compara antes e depois arquivo a arquivo (seções 9 e 13 do PRD revisadas na issue #19).

## Como ler um par `.json` / `.jsonl`

Cada cenário em `execucoes/` tem dois arquivos com o mesmo nome e o mesmo `run_id`:

- `NN_nome.json` é o `ResultadoTriagem` gravado por `--salvar`: `categoria`, `prioridade`, `resumo`, `acao_sugerida`, `justificativa`, `requer_revisao_humana` e `motivo_revisao`, `rota`, `fontes_contexto`, `tool_resultado`, `alertas`, `erros`, `caminho_percorrido` e `modelo`.
- `NN_nome.jsonl` é o log JSON Lines da mesma execução (cópia de `logs/<run_id>.jsonl`), um evento por linha, todos com `timestamp`, `run_id`, `nivel` e `evento`.

Eventos que aparecem nos logs (seção 9 do PRD) e o que cada um prova:

| Evento | O que prova | Onde ver |
|---|---|---|
| `execucao_iniciada` / `execucao_finalizada` | id da execução, origem do chamado, rota e prioridade finais, duração total | qualquer `.jsonl` |
| `node_inicio` / `node_fim` | nodes percorridos e duração de cada um; o `node_fim` carrega o resumo do node (`tentativa` em `analisar_chamado`, `limiar` e scores em `consultar_base`, `valida` e `suspeita_injecao` em `validar_entrada`) | qualquer `.jsonl` |
| `roteamento` | cada edge condicional com `origem`, `decisao` e `motivo` legível, por exemplo `prioridade critica (sugerida pelo modelo)` ou `prioridade alta (elevada por regra)` | `prompt-v2/02_portal_fora_do_ar.jsonl`, `prompt-v1/01_reset_senha.jsonl` |
| `llm_chamada` | modelo, tentativa, duração, sucesso e erro de cada chamada ao Gemini | todos com rota `simples` ou `critico` |
| `tool_chamada` / `tool_erro` | parâmetros validados enviados à tool e a falha tipada quando há | `prompt-v2/05_servico_desconhecido.jsonl` (`servico_nao_encontrado`), `prompt-v1/02_portal_tool_indisponivel.jsonl` (`catalogo_indisponivel`) |
| `alerta_seguranca` | detector de prompt injection disparando **antes** da primeira `llm_chamada`, com a lista de padrões | `prompt-v1/06_prompt_injection.jsonl`, `prompt-v2/06_prompt_injection.jsonl` |
| `llm_chamada` com `sucesso: false` seguida de `roteamento` de nova tentativa | retry limitado com condição de parada, aqui diante de um `403` real do provedor | `prompt-v1/01_reset_senha_retry_apos_403.jsonl` |

Caminhos observados nos logs da rodada v2, que cobrem as três ramificações do grafo:

| Exemplos | `caminho_percorrido` |
|---|---|
| 01, 03, 07 | `validar_entrada → analisar_chamado → classificar_risco → consultar_base → gerar_resposta` |
| 02, 05, 06 | `validar_entrada → analisar_chamado → classificar_risco → consultar_tool → gerar_resposta` |
| 04 | `validar_entrada → tratar_falha` (sem nenhuma `llm_chamada`) |

## Privacidade e segredos

- Nenhum arquivo contém `GOOGLE_API_KEY` nem outro segredo. O log nunca grava valores da configuração, e `gerar_resposta` redige qualquer fragmento da chave que apareça na saída (`[REDIGIDO]`).
- E-mails e CPFs são mascarados pela aplicação antes de gravar o log (RF-70, issue #15). Os e-mails visíveis nos `.json` de saída são contatos fictícios das equipes do catálogo (`@empresa.exemplo`), vindos de `data/catalogo_servicos.json`: a saída da triagem não é mascarada por desenho, porque o atendente precisa do contato.
- Em `prompt-v1/01_reset_senha_retry_apos_403.jsonl` o id numérico do projeto Google foi substituído por `<id-do-projeto>`. Em `testes.txt` o caminho absoluto da máquina local foi substituído por `<repo>`. Nenhum outro arquivo foi editado.
- Verificação feita em 16/09/2026 (issue #19) varrendo a pasta com busca por padrões de chave (`AIza…`, `ghp_…`, `sk-…`), e-mails, CPFs formatados e sem formatação, caminhos `/home/` e ids de projeto. Únicos achados: os e-mails fictícios acima e os ids numéricos de execução do GitHub Actions.

## Rastreabilidade com a rubrica

Complementa a seção 15 do [PRD](../PRD.md): para cada critério, o arquivo desta pasta que o comprova.

| Critério | Evidência nesta pasta |
|---|---|
| 1. Vídeo | não se aplica (link no README, issue #20); o vídeo reproduz as execuções desta pasta |
| 2. GitHub | `ci/` registra os PRs e commits verificados pelo pipeline; o histórico completo está no repositório e no Project |
| 3. README | não se aplica (raiz do repositório) |
| 4. Aplicação funcional | `execucoes/prompt-v2/*.json`: saída estruturada dos 7 exemplos com o modelo real, sem exceção em nenhum |
| 5. LangGraph | `caminho_percorrido` em cada `.json` e eventos `node_*` e `roteamento` em cada `.jsonl`: ramificação `consultar_base` (01, 03, 07), `consultar_tool` (02, 05, 06) e `tratar_falha` (04); retry limitado em `prompt-v1/01_reset_senha_retry_apos_403.jsonl` |
| 6. Tool | `prompt-v2/02_portal_fora_do_ar.*` (sucesso, runbook do catálogo usado na resposta), `prompt-v2/05_servico_desconhecido.*` (`servico_nao_encontrado`), `prompt-v1/02_portal_tool_indisponivel.*` (indisponibilidade simulada); 41 testes de `test_tool.py` em `testes.txt` |
| 7. Contexto | `fontes_contexto` e scores BM25 em `prompt-v2/01_reset_senha.*` e `03_vpn_intermitente.*`; `sem_contexto_relevante` em `07_fora_do_dominio.*`; calibração de `LIMIAR_BM25` em `prompt-v1/README.md` |
| 8. Segurança e falhas | `prompt-v2/04_entrada_invalida.*` (validação rejeita sem chamar o LLM), `prompt-v2/05_*` (falha da tool não interrompe), `prompt-v1/01_reset_senha_retry_apos_403.jsonl` (falha real do provedor); logs sem segredo e com PII mascarada |
| 9. Observabilidade | qualquer `.jsonl` de `execucoes/`: `run_id`, nodes, roteamento com motivo, tool, erro |
| 10. QA com IA e testes | `testes.txt` (372 testes); `prompt-v1/pos-qa-regras/01_reset_senha.*` prova com o modelo real a correção decidida em [`docs/qa-com-ia.md`](../qa-com-ia.md) |
| 11. Prompts e refinamento | `prompt-v1/` (antes) e `prompt-v2/` (depois), comparados em [`docs/refinamento-prompt.md`](../refinamento-prompt.md) |
| 12. Extensão E1 (CI) | `ci/primeira-execucao-verde.md`, `ci/execucao-main-2026-09-16.md` |
| 13. Extensão E2 (prompt injection) | `prompt-v1/06_prompt_injection.*` e `prompt-v2/06_prompt_injection.*`: `alerta_seguranca` com 6 padrões antes do LLM, prioridade `alta` e categoria `infraestrutura` mantidas, chave não vazou; 25 testes de `test_seguranca.py` em `testes.txt`; análise em [`docs/extensoes.md`](../extensoes.md) |

## Como regenerar

```bash
cp .env.example .env                                   # preencher GOOGLE_API_KEY
uv run pytest -v > docs/evidencias/testes.txt          # suíte completa, inclusive os testes live
for n in 01_reset_senha 02_portal_fora_do_ar 03_vpn_intermitente 04_entrada_invalida 05_servico_desconhecido 06_prompt_injection 07_fora_do_dominio; do
  uv run triagem triar --arquivo data/exemplos/$n.json --salvar /tmp/$n.json --sem-logs > /dev/null
done                                                   # o log de cada execução fica em logs/<run_id>.jsonl; o run_id está no .json
SIMULAR_FALHA_TOOL=1 uv run triagem triar --arquivo data/exemplos/02_portal_fora_do_ar.json
```

Os registros de `ci/` vêm da API do GitHub Actions (`gh api repos/ldebatin/sctec-projeto-final-rec/actions/runs/<id>` e `/jobs`).
