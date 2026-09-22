# Checklist final de entrega

Revisão final feita em **16/09/2026** sobre a `main` (commit `56f9d51`, merge do PR #41), percorrendo item a item a seção 7 da especificação ("Checklist final de entrega"). Prazo de submissão no AVA: **18/09/2026 às 22h**, com o link do repositório e o link do vídeo.

Legenda: ✅ atendido e verificado · ⏳ depende de ação do aluno · ⚠️ atenção.

## 1. Revisão em clone limpo

Clone da `main` em pasta vazia, sem `.env`, seguindo só o [README](../README.md):

| Passo | Resultado |
|---|---|
| `git clone` + `uv sync` | ok, Python 3.12 baixado pelo uv a partir de `.python-version` |
| `uv run pytest -q` (sem chave) | `370 passed, 2 skipped` (os 2 `live` são pulados sem chave) |
| `uv run pytest -v` (com chave, no repositório de trabalho) | `372 passed`, saída em [`evidencias/testes.txt`](evidencias/testes.txt) |
| `uv run ruff check .` e `uv run ruff format --check .` | limpos |
| `uv run triagem grafo` | diagrama igual ao do README §2 |
| `uv run triagem triar --arquivo data/exemplos/01_reset_senha.json` sem chave | código de saída 2, mensagem cita `GOOGLE_API_KEY` |
| Cenário 04 com `GOOGLE_API_KEY=qualquer`, sem `.env` | rota `falha`, código 0, nenhuma chamada ao modelo |

Os **7 exemplos executados com o Gemini real** (`gemini-2.5-flash`) no clone limpo, todos com código de saída 0 e saída estruturada válida, batendo com [`cenarios.md`](cenarios.md):

| Exemplo | Rota | Categoria / prioridade | Revisão humana | Fontes / tool | Alertas |
|---|---|---|---|---|---|
| 01_reset_senha | simples | suporte / media | não | `kb-001-reset-senha-ad` | — |
| 02_portal_fora_do_ar | critico | software / critica | sim (`rota_critica`) | `portal-clientes` | — |
| 03_vpn_intermitente | simples | infraestrutura / media | não | `kb-002-vpn-nao-conecta` | — |
| 04_entrada_invalida | falha | indefinido / — | sim (`falha_tratada`) | — (LLM não chamado) | — |
| 05_servico_desconhecido | critico | software / alta | sim (`rota_critica`, `tool_falhou`) | tool: `servico_nao_encontrado` | — |
| 06_prompt_injection | critico | infraestrutura / alta | sim (`rota_critica`, `possivel_prompt_injection`) | `servidor-arquivos` | `possivel_prompt_injection` |
| 07_fora_do_dominio | simples | indefinido / baixa | sim (`categoria_indefinida`, `confianca_baixa`) | — | `sem_contexto_relevante` |

## 2. Varredura do histórico por segredos

Comandos executados sobre **todos** os commits e branches (`git log --all -p`):

- Arquivos `.env` (exceto `.env.example`) adicionados em qualquer commit: **nenhum**.
- Padrões de chave e token nas adições de todo o histórico (`AIza…`, `ghp_…`, `github_pat_…`, `sk-…`, `AKIA…`, blocos `PRIVATE KEY`): um único achado, `AIzaSyEXEMPLO0123456789abcdefghijklmnopq`, valor **fictício** usado em `tests/test_seguranca.py` para provar a redação de segredos na saída.
- `GOOGLE_API_KEY=` com valor em todo o histórico: só `k-arquivo`, em um teste de leitura do `.env`.
- Arquivos rastreados hoje com nome sugestivo (`.env`, `.pem`, `.key`, `secret`, `credential`, `token`): **nenhum**. `.env` está no `.gitignore` (verificado com `git check-ignore`).
- Evidências em `docs/evidencias/`: varridas na issue #19; e-mails só os fictícios `@empresa.exemplo`, id do projeto Google e caminho local substituídos por marcadores.

## 3. Checklist da especificação, item a item

### Repositório e organização

| Item | Status | Evidência |
|---|---|---|
| Repositório no GitHub com acesso garantido ao professor | ✅ | Repositório **público** desde 21/09/2026, confirmado sem autenticação (`GET /repos/ldebatin/sctec-projeto-final-rec` → `private: false`). O [Project](https://github.com/users/ldebatin/projects/6) também é público. |
| Commits incrementais com mensagens claras | ✅ | 48 commits na `main` (29 sem contar merges) de 11/09 a 16/09, 19 pull requests mergeados, um por issue, com o kanban do [Project](https://github.com/users/ldebatin/projects/6) percorrido. Prefixos `feat:`, `fix:`, `docs:`, `ci:`. |
| Versão final e funcional na `main` | ✅ | Seção 1 acima; CI verde na `main` ([`evidencias/ci/`](evidencias/ci/)). |
| Nenhuma chave, token, senha, `.env` ou dado sensível versionado | ✅ | Seção 2 acima. |
| `.env.example`, dependências e comandos de execução e testes | ✅ | [`.env.example`](../.env.example), `pyproject.toml` + `uv.lock`, README §6. |

### Aplicação e LangGraph

| Item | Status | Evidência |
|---|---|---|
| Tema obrigatório: triagem de chamados técnicos | ✅ | README §1; [`PRD.md`](PRD.md) §1. |
| Executa de ponta a ponta e produz saída estruturada | ✅ | 7 exemplos na seção 1; `ResultadoTriagem` Pydantic ([`src/triagem/modelos.py`](../src/triagem/modelos.py)). |
| Fluxo principal e cenário de falha demonstrados | ✅ | 01 (principal), 04 (entrada inválida), 05 (falha da tool) em [`cenarios.md`](cenarios.md) e [`evidencias/execucoes/prompt-v2/`](evidencias/execucoes/prompt-v2/README.md). |
| LangGraph com state, nodes e edges explícitas | ✅ | [`grafo.py`](../src/triagem/grafo.py), [`estado.py`](../src/triagem/estado.py), [`nodes.py`](../src/triagem/nodes.py); README §2 e §3. |
| Pelo menos uma ramificação condicional e uma condição de parada | ✅ | 3 edges condicionais; retry limitado por `MAX_TENTATIVAS_LLM` mais `recursion_limit`; testes `test_retry_respeita_limite_e_termina_em_tratar_falha` e `test_unico_ciclo_e_o_retry_de_analisar_chamado`. |

### Tool e contexto

| Item | Status | Evidência |
|---|---|---|
| Tool funcional com chamada demonstrada no fluxo | ✅ | `consultar_catalogo_servicos` ([`tools/catalogo.py`](../src/triagem/tools/catalogo.py)); evento `tool_chamada` em `evidencias/execucoes/prompt-v2/02_portal_fora_do_ar.jsonl`. |
| Parâmetros validados e pelo menos uma falha tratada | ✅ | Schema Pydantic (`servico` 1–100 caracteres, `ambiente` em enum); falhas `parametro_invalido`, `servico_nao_identificado`, `servico_nao_encontrado` (exemplo 05), `catalogo_indisponivel` (falha simulada, `prompt-v1/02_portal_tool_indisponivel.*`); 41 testes em `tests/test_tool.py`. |
| Estratégia de memória, contexto ou RAG usada de fato | ✅ | State do grafo + base de conhecimento com BM25 ([`retrieval.py`](../src/triagem/retrieval.py)); `fontes_contexto` preenchido nos exemplos 01 e 03 e ação baseada no artigo; limiar calibrado com execuções reais. |

### Segurança e observabilidade

| Item | Status | Evidência |
|---|---|---|
| Segredos fora do repositório e entradas validadas | ✅ | Seção 2; `validar_entrada` com Pydantic (exemplo 04). |
| Pelo menos uma falha tratada de forma controlada | ✅ | Exemplos 04 e 05; retry diante de `403` real em `evidencias/execucoes/prompt-v1/01_reset_senha_retry_apos_403.jsonl`; fallback sem LLM em `gerar_resposta`. |
| Logs com execução, nodes, roteamento, tool e erros | ✅ | `run_id` em todo evento; `node_inicio`/`node_fim`, `roteamento` com motivo, `tool_chamada`/`tool_erro`, `llm_chamada`, `alerta_seguranca`, `erro`; índice em [`evidencias/README.md`](evidencias/README.md). |

### QA, prompts e refinamento

| Item | Status | Evidência |
|---|---|---|
| Pelo menos três testes automatizados | ✅ | 372 testes em 16 arquivos ([`evidencias/testes.txt`](evidencias/testes.txt)). |
| Testes cobrem sucesso, falha ou entrada inválida e comportamento do grafo ou da tool | ✅ | `tests/test_grafo.py` (fluxo simples e crítico, entrada inválida, retry), `tests/test_tool.py`. |
| IA usada para revisar alteração real ou gerar/refinar teste, com decisão documentada | ✅ | [`qa-com-ia.md`](qa-com-ia.md): 4 decisões do aluno (3 aceitas, 1 rejeitada), 140 testes novos, correção comprovada com o modelo real. |
| Principais instruções do agente documentadas | ✅ | [`instrucoes-agente.md`](instrucoes-agente.md), gerado do código e protegido por `tests/test_prompts_docs.py`. |
| Pelo menos um refinamento de prompt com problema, alteração e resultado | ✅ | [`refinamento-prompt.md`](refinamento-prompt.md): v1 → v2 com diff e antes/depois nos 7 exemplos. |

### Extensões técnicas

| Item | Status | Evidência |
|---|---|---|
| Duas extensões diferentes do item 4.9 | ✅ | E1 pipeline de CI e E2 cenário adversarial de prompt injection ([`extensoes.md`](extensoes.md)); nenhuma cumpre requisito obrigatório. |
| Funcionais, integradas, documentadas e demonstráveis | ✅ | E1: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml), 34 de 36 execuções verdes, registros em `evidencias/ci/`. E2: exemplo 06 com `alerta_seguranca` antes do LLM em `prompt-v1` e `prompt-v2`, 25 testes em `tests/test_seguranca.py`. |

### README, vídeo e submissão

| Item | Status | Evidência |
|---|---|---|
| README permite compreender, configurar, executar, testar e avaliar | ✅ | Validado em clone limpo na issue #18 e novamente hoje (seção 1). |
| README inclui arquitetura, tool, contexto, cenários, evidências de QA, extensões e limitações | ✅ | README §2 a §11. |
| Vídeo de até 10 minutos publicado como não listado | ⏳ aluno | Roteiro pronto em [`roteiro-video.md`](roteiro-video.md) (issue #20). |
| Vídeo demonstra fluxo principal, decisão condicional, tool, contexto, falha, testes e extensões | ⏳ aluno | Mapeamento dos 8 itens do item 5.4 na tabela do roteiro. |
| Links do repositório e do vídeo submetidos no AVA antes do prazo | ⏳ aluno | 18/09/2026 às 22h. |

## 4. O que falta antes da submissão

1. **Vídeo** (issue #20): ensaio cronometrado, gravação, publicação no YouTube como não listado, teste do link em janela anônima.
2. **Link do vídeo no README §12**, por branch e PR que fecha a #20 (o assistente pode fazer ao receber o link), com a entrada correspondente em [`prompts.md`](prompts.md).
3. **Submissão no AVA**: link do repositório (`https://github.com/ldebatin/sctec-projeto-final-rec`) e link do vídeo, até 18/09/2026 às 22h.
4. Depois da submissão: fechar as issues #20 e #21, mover para Done e encerrar a milestone "Fase 6 · Vídeo e entrega".
