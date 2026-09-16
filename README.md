# Agente Inteligente de Triagem de Chamados Técnicos

[![CI](https://github.com/ldebatin/sctec-projeto-recuperacao/actions/workflows/ci.yml/badge.svg)](https://github.com/ldebatin/sctec-projeto-recuperacao/actions/workflows/ci.yml)

Agente construído com **LangGraph** que recebe um chamado técnico (título e descrição), analisa o conteúdo com um LLM (Google Gemini), classifica o risco com **regras determinísticas**, decide por ramificação condicional se consulta uma **base de conhecimento** (rota simples) ou uma **tool de catálogo de serviços** (rota crítica) e devolve uma triagem **estruturada**: categoria, prioridade, resumo, ação sugerida e se precisa de revisão humana.

Projeto avaliativo de recuperação do módulo 2 de *IA para Desenvolvedores [T1]* (SENAI), por Luiz Fernando Debatin. O guia de implementação, com requisitos e decisões, está em [`docs/PRD.md`](docs/PRD.md).

**Sumário:** [Objetivo](#1-objetivo-da-triagem) · [Arquitetura](#2-arquitetura-do-grafo) · [State, nodes e decisões](#3-state-nodes-e-decisões-condicionais) · [Tool](#4-tool-consultar_catalogo_servicos) · [Contexto](#5-estratégia-de-contexto) · [Instalação e execução](#6-instalação-configuração-execução-e-testes) · [Cenários](#7-cenários-demonstrados-com-saídas-reais) · [Observabilidade](#8-observabilidade-como-ler-os-logs) · [QA com IA e prompts](#9-qa-com-ia-refinamento-de-prompt-e-diário) · [Extensões](#10-extensões-e1-e-e2) · [Limitações](#11-limitações-conhecidas) · [Vídeo](#12-vídeo-de-demonstração) · [Estrutura](#13-estrutura-do-repositório)

## 1. Objetivo da triagem

Equipes de suporte recebem chamados heterogêneos (software, infraestrutura, suporte ao usuário) e gastam tempo entendendo o problema, classificando, definindo prioridade, descobrindo a equipe responsável e sugerindo o primeiro passo. Erros de triagem atrasam incidentes críticos e sobrecarregam equipes com chamados triviais.

O agente faz a primeira passada dessa triagem e entrega ao atendente humano um `ResultadoTriagem` (Pydantic, serializado em JSON) com:

| Campo | O que é |
|---|---|
| `categoria` | `software`, `infraestrutura`, `suporte` ou `indefinido` |
| `prioridade` | `baixa`, `media`, `alta` ou `critica`, já com as elevações das regras |
| `resumo`, `acao_sugerida`, `justificativa` | texto gerado pelo modelo **a partir do contexto recuperado** (artigo da base ou runbook do catálogo) |
| `requer_revisao_humana`, `motivo_revisao` | flag e lista de motivos (`rota_critica`, `categoria_indefinida`, `confianca_baixa`, `tool_falhou`, `possivel_prompt_injection`, `falha_tratada`) |
| `rota` | `simples`, `critico` ou `falha` |
| `fontes_contexto`, `tool_resultado` | ids dos artigos usados ou o retorno tipado da tool |
| `alertas`, `erros`, `caminho_percorrido`, `run_id`, `modelo` | rastreabilidade da execução |

Princípio central: **o modelo interpreta e sugere; as regras da aplicação decidem** roteamento, prioridade final e revisão humana. Nenhuma falha (entrada inválida, LLM fora do ar, tool com erro) derruba a aplicação: todas produzem saída estruturada com `requer_revisao_humana = true`.

## 2. Arquitetura do grafo

Diagrama gerado pelo próprio grafo compilado (`uv run triagem grafo`). Arestas tracejadas são decisões condicionais.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	validar_entrada(validar_entrada)
	analisar_chamado(analisar_chamado)
	classificar_risco(classificar_risco)
	consultar_base(consultar_base)
	consultar_tool(consultar_tool)
	gerar_resposta(gerar_resposta)
	tratar_falha(tratar_falha)
	__end__([<p>__end__</p>]):::last
	__start__ --> validar_entrada;
	analisar_chamado -.-> classificar_risco;
	analisar_chamado -.-> tratar_falha;
	classificar_risco -.-> consultar_base;
	classificar_risco -.-> consultar_tool;
	consultar_base --> gerar_resposta;
	consultar_tool --> gerar_resposta;
	validar_entrada -.-> analisar_chamado;
	validar_entrada -.-> tratar_falha;
	gerar_resposta --> __end__;
	tratar_falha --> __end__;
	analisar_chamado -.-> analisar_chamado;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

Fluxo de referência da especificação: *Entrada → analisar_chamado → classificar_risco → [simples → consultar_base | crítico → consultar_tool] → gerar_resposta → END*. O grafo acrescenta `validar_entrada` (antes de gastar uma chamada de LLM com entrada inválida) e `tratar_falha` (saída de fallback para qualquer falha), e um único ciclo: o retry limitado de `analisar_chamado`.

Camadas do código em [`src/triagem/`](src/triagem/): `grafo.py` (StateGraph, edges, roteamento, `executar_triagem`), `nodes.py` (funções dos nodes), `regras.py` (rota, elevação de prioridade, revisão humana, detector de injeção), `retrieval.py` (BM25), `tools/catalogo.py` (tool), `prompts.py` (instruções do agente), `observabilidade.py` (logs), `modelos.py` e `estado.py` (Pydantic e state), `config.py`, `llm.py`, `cli.py`.

## 3. State, nodes e decisões condicionais

**State** (`EstadoTriagem`, TypedDict em [`estado.py`](src/triagem/estado.py)): `run_id`, `entrada_bruta`, `chamado`, `analise`, `tentativas_llm`, `rota`, `prioridade_final`, `contexto`, `tool_resultado`, `alertas`, `erros`, `caminho_percorrido` e `resultado`. As listas `alertas`, `erros` e `caminho_percorrido` usam reducer de concatenação, então cada node só acrescenta. O state é a memória de curto prazo da execução: a análise do modelo feita no segundo node é lida pelo terceiro, o contexto recuperado no quarto é lido pelo quinto.

**Nodes** ([`nodes.py`](src/triagem/nodes.py)):

| Node | Tipo | Faz | Falha tratada |
|---|---|---|---|
| `validar_entrada` | determinístico | valida o `Chamado` com Pydantic (título 5–200, descrição 20–8000 caracteres, `ambiente` em enum) e roda o detector de prompt injection | entrada inválida → `erros`, vai para `tratar_falha` sem chamar o LLM |
| `analisar_chamado` | **LLM** com `with_structured_output(AnaliseChamado)` | categoria, prioridade sugerida, impacto, serviço mencionado, palavras-chave, resumo técnico e confiança | timeout, quota (com backoff), saída fora do schema → `erros`, retry limitado |
| `classificar_risco` | determinístico | aplica as regras de elevação de prioridade e define `rota` e `prioridade_final` | — |
| `consultar_base` | determinístico (BM25) | recupera até 3 artigos da base acima de `LIMIAR_BM25` | base ilegível ou nada relevante → contexto vazio e alerta `sem_contexto_relevante` |
| `consultar_tool` | determinístico, invoca a tool | consulta o catálogo pelo serviço identificado | qualquer falha vira `tool_resultado.ok = false`, o fluxo segue |
| `gerar_resposta` | **LLM** com `with_structured_output(RespostaLLM)` + montagem determinística | resumo, ação e justificativa a partir do contexto; redige segredos; monta o `ResultadoTriagem` | falha do LLM → resposta de fallback montada com o contexto, sem modelo (alerta `resposta_fallback`) |
| `tratar_falha` | determinístico | monta o `ResultadoTriagem` de fallback com `rota = falha` e `requer_revisao_humana = true` | — |

**As três decisões condicionais** ([`grafo.py`](src/triagem/grafo.py)), cada uma registrando o evento `roteamento` no log com `origem`, `decisao` e `motivo`:

| Após | Decisão | Critério |
|---|---|---|
| `validar_entrada` | `analisar_chamado` ou `tratar_falha` | o `Chamado` validou? |
| `analisar_chamado` | `classificar_risco`, `analisar_chamado` (retry) ou `tratar_falha` | análise ok? senão, ainda há tentativa (`tentativas_llm < MAX_TENTATIVAS_LLM`)? |
| `classificar_risco` | `consultar_base` ou `consultar_tool` | rota `simples` ou `critico` |

**Regras determinísticas** ([`regras.py`](src/triagem/regras.py)), aplicadas sobre a análise do modelo e o texto do chamado:

- **Elevação de prioridade** (nunca rebaixa; cada uma gera um alerta): (a) produção + prioridade sugerida `media` + impacto além de um usuário → `alta`; (b) termo de indisponibilidade no texto ("fora do ar", "ninguém consegue", "perda de dados"…) → pelo menos `alta`; (c) produção com impacto amplo → pelo menos `alta`.
- **Rota**: `critico` se a prioridade final é `alta` ou `critica`; senão `simples`. O motivo no log cita a regra que elevou.
- **Revisão humana**: rota crítica, **ou** categoria `indefinido`, **ou** confiança abaixo de `LIMIAR_CONFIANCA` (0.6), **ou** tool falhou, **ou** suspeita de injeção, **ou** falha tratada.

**Condição de parada.** O grafo é acíclico exceto pelo retry de `analisar_chamado`, limitado por `MAX_TENTATIVAS_LLM` (padrão 2). Todo caminho termina em `END` por `gerar_resposta` ou `tratar_falha`. `recursion_limit = 10` fica como rede de segurança (o caminho mais longo tem 7 passos). O teste `test_retry_respeita_limite_e_termina_em_tratar_falha` prova que, com o LLM sempre falhando, o node roda exatamente `MAX_TENTATIVAS_LLM` vezes e o fluxo termina em `tratar_falha`; outro teste prova estruturalmente que o único retrocesso do grafo é `analisar_chamado → analisar_chamado`.

## 4. Tool: `consultar_catalogo_servicos`

Função Python empacotada como `StructuredTool` do LangChain ([`tools/catalogo.py`](src/triagem/tools/catalogo.py)), com schema de argumentos Pydantic inspecionável e saída tipada.

```python
class ParametrosCatalogo(BaseModel):
    servico: str = Field(min_length=1, max_length=100)   # normalizado: minúsculas, sem espaços extras
    ambiente: Ambiente | None = None                     # producao | homologacao | desenvolvimento

def consultar_catalogo_servicos(servico, ambiente=None) -> ResultadoCatalogo:
    # ok, erro, mensagem, servico_id, nome, equipe_responsavel, criticidade,
    # status_atual, runbook, contato_escalonamento
```

**Quando é chamada.** Só na rota `critico`, por decisão da regra de rota (não do modelo): o node `consultar_tool` usa o `servico_mencionado` da análise ou o campo `servico` do chamado. Na rota simples a tool não é acionada (há teste para isso).

**Fonte de dados.** [`data/catalogo_servicos.json`](data/catalogo_servicos.json): 8 serviços fictícios (Portal de Clientes, ERP, API de Pagamentos, VPN, Servidor de Arquivos, Banco de Dados, Active Directory, E-mail) com apelidos, equipe responsável, criticidade, status atual, ambientes, runbook e contato de escalonamento. A resolução é por nome ou apelido, inclusive apelido contido na frase.

**Falhas tratadas** (todas viram `ok = false`, `requer_revisao_humana = true`, e o fluxo segue para `gerar_resposta`):

| Situação | `erro` |
|---|---|
| Parâmetro vazio, só espaços ou com mais de 100 caracteres | `parametro_invalido` |
| Análise não identificou serviço e o chamado não informou | `servico_nao_identificado` |
| Nome ou apelido inexistente no catálogo | `servico_nao_encontrado` |
| Arquivo ausente, JSON corrompido, lista vazia, id ou apelido duplicado | `catalogo_indisponivel` |
| `SIMULAR_FALHA_TOOL=1` (demonstração de falha de integração) | `catalogo_indisponivel` |

Quando a tool tem sucesso, o runbook e a equipe entram no prompt de `gerar_resposta`, e a ação sugerida segue o runbook passo a passo citando o contato (ver cenário 02 abaixo).

## 5. Estratégia de contexto

Duas camadas de memória, ambas usadas de fato na resposta:

1. **State do grafo** carrega análise, rota, contexto e resultado da tool até `gerar_resposta` (memória da execução).
2. **Base de conhecimento local** em [`data/base_conhecimento/`](data/base_conhecimento/): 10 artigos Markdown com front-matter (`id`, `titulo`, `categoria`, `tags`, `servicos`) e corpo com sintomas, causa provável, procedimento e escalonamento. Cobre senha do AD, VPN, erro 500 no portal, lentidão do ERP, disco cheio, e-mail, impressora de rede, certificado TLS, deploy em homologação e acesso negado a pasta.

**Recuperação** ([`retrieval.py`](src/triagem/retrieval.py)): BM25 lexical (`rank-bm25`) com tokenização simples e stopwords pt-BR, índice em memória construído no início da execução. A consulta é título + descrição + `palavras_chave` da análise. Ficam até 3 artigos com `score >= LIMIAR_BM25`. O limiar 12.0 foi calibrado com execuções reais: o artigo certo pontua 35 a 46, o ruído até 11 e um chamado fora do domínio 4,8 (detalhes em [`docs/evidencias/execucoes/prompt-v1/README.md`](docs/evidencias/execucoes/prompt-v1/README.md)).

**Uso na resposta.** Os artigos (id, título, procedimento) vão ao modelo no bloco `<contexto>` do prompt de `gerar_resposta`, que é obrigado a basear a ação neles e a não nomear equipe ou departamento fora do contexto; os ids saem em `fontes_contexto`. Sem artigo relevante, o resultado recebe o alerta `sem_contexto_relevante` e a resposta encaminha para triagem manual em vez de inventar um procedimento. Se o modelo falhar nessa etapa, ação e justificativa são montadas sem LLM a partir do próprio contexto.

Por que não RAG com embeddings: a base é pequena e em português técnico, BM25 resolve sem custo nem dependência de API de embeddings, e a decisão deixa a extensão "RAG com embeddings" disponível para o futuro sem se confundir com o requisito obrigatório de contexto (decisão D5 do PRD).

## 6. Instalação, configuração, execução e testes

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Git. O Python (3.12, fixado em `.python-version`) é baixado pelo próprio uv se não existir; o projeto suporta 3.10 ou superior. Sem uv: `pip install uv` ou `curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
git clone https://github.com/ldebatin/sctec-projeto-recuperacao.git
cd sctec-projeto-recuperacao
uv sync                                   # cria .venv e instala dependências do uv.lock
cp .env.example .env                      # edite e preencha GOOGLE_API_KEY
```

A chave é gratuita no [Google AI Studio](https://aistudio.google.com/app/apikey). O `.env` está no `.gitignore`; nunca versione uma chave real.

**Variáveis de configuração** ([`.env.example`](.env.example)). Valores do `.env` e do ambiente do processo são lidos, o ambiente prevalece:

| Variável | Padrão | Para que serve |
|---|---|---|
| `LLM_PROVIDER`, `LLM_MODEL` | `google_genai`, `gemini-2.5-flash` | provedor e modelo, no formato do `init_chat_model` do LangChain |
| `GOOGLE_API_KEY` | (obrigatória) | chave do provedor |
| `LLM_TIMEOUT_SEGUNDOS`, `MAX_TENTATIVAS_LLM` | `30`, `2` | tempo máximo por chamada e limite do retry em `analisar_chamado` |
| `LLM_BACKOFF_BASE_SEGUNDOS` | `2` | espera antes de nova tentativa em erro de quota (dobra, máximo 30 s) |
| `LIMIAR_BM25` | `12.0` | score mínimo para um artigo contar como contexto |
| `LIMIAR_CONFIANCA` | `0.6` | abaixo disso, revisão humana |
| `LOG_NIVEL`, `LOG_FORMATO` | `INFO`, `json` | nível e formato dos logs em stderr (`json` ou `texto`); o arquivo é sempre JSON Lines |
| `SIMULAR_FALHA_TOOL` | `0` | `1` simula catálogo indisponível |

**Executar**

```bash
uv run triagem exemplos                                                   # lista os 7 chamados de exemplo
uv run triagem triar --arquivo data/exemplos/01_reset_senha.json          # saída JSON + logs em stderr
uv run triagem triar --arquivo data/exemplos/02_portal_fora_do_ar.json --formato texto
uv run triagem triar --titulo "VPN não conecta" --descricao "Desde ontem o cliente VPN fica em 'conectando' e cai. Já reiniciei o notebook." --ambiente producao
uv run triagem triar --arquivo data/exemplos/01_reset_senha.json --salvar saida.json --sem-logs
uv run triagem grafo                                                      # diagrama Mermaid do grafo compilado
uv run triagem --help                                                     # todas as opções
```

Cada execução grava `logs/<run_id>.jsonl` (pasta ignorada pelo Git) e imprime o caminho em stderr. Uma linha de aviso da biblioteca do Google sobre *automatic function calling* pode aparecer em stderr nas execuções reais; é inofensiva e não afeta a saída. Código de saída `0` para triagem concluída, inclusive fallback controlado; `2` para erro de configuração ou de uso (por exemplo, `GOOGLE_API_KEY` ausente: a mensagem cita a variável e o grafo não é executado).

O cenário 04 (entrada inválida) não chama o modelo, então roda até sem chave válida: `GOOGLE_API_KEY=qualquer uv run triagem triar --arquivo data/exemplos/04_entrada_invalida.json --formato texto`.

**Testar e verificar qualidade**

```bash
uv run pytest                     # 372 testes; os 2 marcados `live` são pulados sem chave
uv run pytest -m "not live" -v    # o que o CI roda (370)
uv run pytest -m live -v          # só os 2 ponta a ponta com o Gemini real
uv run ruff check . && uv run ruff format --check .
```

A suíte não precisa de rede nem de chave: os nodes recebem o modelo por injeção (`executar_triagem(..., llm=...)` via `Runtime[ContextoExecucao]` do LangGraph) e os testes usam o `FakeLLM` de [`llm.py`](src/triagem/llm.py) com uma fila de respostas ou exceções. A saída integral da última rodada está em [`docs/evidencias/testes.txt`](docs/evidencias/testes.txt).

| Arquivo | Testes | Cobre |
|---|---|---|
| `tests/test_grafo.py` | 10 | fluxo simples e crítico, entrada inválida, retry exato e parada, prova estrutural do único ciclo, reconstrução do caminho pelo log |
| `tests/test_tool.py` | 41 | contrato, validação de parâmetros, catálogo corrompido ou ausente, falha simulada, tool no fluxo |
| `tests/test_regras.py` | 153 | rota, elevações, revisão humana (128 combinações parametrizadas), termos, caso real do exemplo 01 |
| `tests/test_seguranca.py` | 25 | detector de injeção (positivos e falsos positivos controlados), prioridade não rebaixada, redação de segredos |
| `tests/test_retrieval.py`, `tests/test_resposta.py` | 17, 12 | BM25 e limiar, uso do contexto na resposta, fallback sem LLM |
| `tests/test_observabilidade.py`, `tests/test_pii.py` | 10, 8 | eventos, formatos, `resumir_eventos`, mascaramento de e-mail e CPF |
| `tests/test_modelos.py`, `tests/test_config.py`, `tests/test_cli.py`, `tests/test_exemplos.py`, `tests/test_llm.py`, `tests/test_backoff.py`, `tests/test_prompts_docs.py` | 26, 20, 13, 13, 10, 10, 2 | validação, `.env`, CLI e códigos de saída, exemplos, fábrica do LLM, backoff de quota, documentação dos prompts igual ao código |
| `tests/test_live.py` | 2 | ponta a ponta com o Gemini (exemplos 01 e 02) |

## 7. Cenários demonstrados com saídas reais

Os 7 chamados de exemplo ficam em [`data/exemplos/`](data/exemplos/) (dados fictícios). A tabela resume a **execução real com o Gemini** de 16/09/2026 com os prompts v2; saídas e logs completos estão em [`docs/evidencias/execucoes/prompt-v2/`](docs/evidencias/execucoes/prompt-v2/README.md), e a descrição de cada cenário em [`docs/cenarios.md`](docs/cenarios.md).

| Exemplo | Demonstra | Rota | Categoria / prioridade | Revisão humana | Contexto |
|---|---|---|---|---|---|
| `01_reset_senha` | fluxo principal | simples | suporte / media | não | artigo `kb-001-reset-senha-ad` |
| `02_portal_fora_do_ar` | rota crítica com tool | critico | software / critica | sim (`rota_critica`) | catálogo `portal-clientes`, runbook usado |
| `03_vpn_intermitente` | ambiente não informado | simples | infraestrutura / media | não | artigo `kb-002-vpn-nao-conecta` |
| `04_entrada_invalida` | **falha**: descrição vazia | falha | indefinido / — | sim (`falha_tratada`) | LLM não é chamado |
| `05_servico_desconhecido` | **falha da tool** | critico | software / alta | sim (`rota_critica`, `tool_falhou`) | `servico_nao_encontrado` |
| `06_prompt_injection` | extensão E2 | critico | infraestrutura / alta | sim (`rota_critica`, `possivel_prompt_injection`) | catálogo `servidor-arquivos` |
| `07_fora_do_dominio` | pedido não técnico | simples | indefinido / baixa | sim (`categoria_indefinida`, `confianca_baixa`) | nenhum, alerta `sem_contexto_relevante` |

**Cenário principal (01), rota simples.** Entrada: "Esqueci minha senha e a conta bloqueou", um usuário do Financeiro, ambiente `producao`. Saída real (trecho do JSON):

```json
{
  "categoria": "suporte",
  "prioridade": "media",
  "resumo": "O usuário esqueceu a senha e sua conta foi bloqueada após múltiplas tentativas, impedindo o acesso a sistemas essenciais como e-mail e intranet.",
  "acao_sugerida": "1. Confirmar a identidade do solicitante pelo canal padrão (ramal cadastrado ou gestor).\n2. No portal de autoatendimento, orientar o uso de \"Esqueci minha senha\"; se indisponível, resetar pelo console do AD.\n3. Desbloquear a conta e exigir troca de senha no próximo logon.\n4. Orientar a atualizar a senha no celular e em aplicativos que a armazenam para evitar novo bloqueio.",
  "requer_revisao_humana": false,
  "rota": "simples",
  "fontes_contexto": ["kb-001-reset-senha-ad"],
  "caminho_percorrido": ["validar_entrada", "analisar_chamado", "classificar_risco", "consultar_base", "gerar_resposta"]
}
```

**Rota crítica (02), com a tool.** Saída real em `--formato texto`:

```text
Rota: critico | Categoria: software | Prioridade: critica
Revisão humana: sim (rota_critica)
Resumo: O Portal de Clientes está inacessível, retornando erro 500 em todas as páginas e impedindo que múltiplos clientes realizem login e consultem faturas, gerando mais de 40 reclamações.
Ação sugerida: 1. Acionar a Squad Portal via plantao-portal@empresa.exemplo ou ramal 4100.
2. Verificar health check em /saude e o painel do gateway.
3. Checar deploy nas últimas 4h e acionar rollback se necessário.
4. Verificar pool de conexões com o banco e a API de Pagamentos.
5. Comunicar no canal #status-portal a cada 30 min.
Justificativa: A ação sugerida é baseada no runbook do serviço 'Portal de Clientes' (id portal-clientes) e direciona o acionamento para a equipe responsável, a Squad Portal, conforme o catálogo de serviços.
Fontes de contexto: portal-clientes
Tool catálogo: ok | equipe: Squad Portal
Caminho: validar_entrada -> analisar_chamado -> classificar_risco -> consultar_tool -> gerar_resposta
```

**Cenário de falha (04), entrada inválida.** Descrição só com espaços. A validação rejeita antes de qualquer chamada ao modelo, e a aplicação termina com código 0 e saída estruturada:

```text
Rota: falha | Categoria: indefinido | Prioridade: media
Revisão humana: sim (falha_tratada)
Resumo: Não foi possível triar automaticamente: entrada inválida.
Ação sugerida: Encaminhar para triagem manual. Último erro: entrada_invalida: descricao: String should have at least 20 characters
Erros: entrada_invalida: descricao: String should have at least 20 characters
Caminho: validar_entrada -> tratar_falha
```

**Falha da tool (05).** O chamado cita um "Sistema XPTO" que não existe no catálogo. A tool devolve `ok = false`, `erro = servico_nao_encontrado`, o fluxo segue e a resposta pede confirmação do nome do sistema em vez de inventar uma equipe: `motivo_revisao = ["rota_critica", "tool_falhou"]`, `erros = ["tool_servico_nao_encontrado: Serviço 'Sistema XPTO' não consta no catálogo. Confirme o nome do sistema afetado."]`.

Outros cenários de falha reproduzíveis (JSON malformado, catálogo indisponível com `SIMULAR_FALHA_TOOL=1`, chave ausente, LLM fora do schema) estão descritos em [`docs/cenarios.md`](docs/cenarios.md#cenários-de-falha). Um retry diante de um erro **real** do provedor (`403` durante a regularização da cobrança do projeto Google) ficou registrado em [`docs/evidencias/execucoes/prompt-v1/01_reset_senha_retry_apos_403.jsonl`](docs/evidencias/execucoes/prompt-v1/01_reset_senha_retry_apos_403.jsonl).

## 8. Observabilidade: como ler os logs

Cada execução recebe um `run_id` (uuid4) e gera eventos JSON Lines em `logs/<run_id>.jsonl` e em stderr (`LOG_FORMATO=texto` deixa o stderr legível). Todo evento tem `timestamp`, `run_id`, `nivel` e `evento`; e-mails e CPFs são mascarados antes de gravar.

| Evento | Campos além dos fixos |
|---|---|
| `execucao_iniciada` / `execucao_finalizada` | `titulo`, `origem` / `rota`, `prioridade`, `requer_revisao_humana`, `duracao_total_ms` |
| `node_inicio` / `node_fim` | `node`, `duracao_ms` e um resumo do node (`tentativa`, `limiar`, scores, `valida`, `suspeita_injecao`) |
| `roteamento` | `origem`, `decisao`, `motivo` |
| `llm_chamada` | `node`, `modelo`, `tentativa`, `duracao_ms`, `sucesso`, `erro` |
| `tool_chamada` / `tool_erro` | `tool`, `parametros` / `tool`, `erro`, `mensagem` |
| `alerta_seguranca` | `tipo`, `padroes` |
| `erro` | `node`, `tipo`, `mensagem`, traceback |

Trecho real do log do cenário 02 (`docs/evidencias/execucoes/prompt-v2/02_portal_fora_do_ar.jsonl`):

```json
{"timestamp": "2026-09-16T00:24:27.086Z", "run_id": "d82a18a7f8224a23b5eefd33eeb83a06", "nivel": "INFO", "evento": "execucao_iniciada", "titulo": "Portal de Clientes fora do ar", "origem": "arquivo:02_portal_fora_do_ar.json"}
{"timestamp": "2026-09-16T00:24:27.092Z", "run_id": "d82a18a7f8224a23b5eefd33eeb83a06", "nivel": "INFO", "evento": "node_fim", "node": "validar_entrada", "duracao_ms": 0.2, "valida": true, "suspeita_injecao": false}
{"timestamp": "...", "run_id": "d82a18a7f8224a23b5eefd33eeb83a06", "nivel": "INFO", "evento": "roteamento", "origem": "classificar_risco", "decisao": "consultar_tool", "motivo": "prioridade critica (sugerida pelo modelo)"}
{"timestamp": "...", "run_id": "d82a18a7f8224a23b5eefd33eeb83a06", "nivel": "INFO", "evento": "tool_chamada", "tool": "consultar_catalogo_servicos", "parametros": {"servico": "Portal de Clientes", "ambiente": "producao"}}
```

A função `resumir_eventos` de [`observabilidade.py`](src/triagem/observabilidade.py) reconstrói, a partir do JSONL, os nodes percorridos, as decisões de roteamento, as chamadas de tool e de LLM, erros e alertas; um teste usa isso para conferir que o log conta a mesma história que o `caminho_percorrido` da saída. Índice de todos os logs e saídas guardados como evidência, com o que cada um prova: [`docs/evidencias/README.md`](docs/evidencias/README.md).

## 9. QA com IA, refinamento de prompt e diário

- [`docs/instrucoes-agente.md`](docs/instrucoes-agente.md): os system prompts dos dois nodes de LLM (análise e resposta), gerados a partir das constantes de `prompts.py`, com o racional de cada regra e a ligação com os requisitos. Um teste falha se a documentação divergir do código.
- [`docs/refinamento-prompt.md`](docs/refinamento-prompt.md): ciclo real de refinamento v1 → v2. Problemas observados na primeira rodada com o Gemini (confiança saturada em 1.0 até para um pedido de férias, passos da ação colados sem separador, equipe "Recursos Humanos" inventada), o diff do prompt e o antes/depois medido nos 7 exemplos (confiança 1.0 → 0.95 nos técnicos e 0.5 no fora do domínio; nenhuma ação colada; nenhuma equipe inventada; rotas e prioridades inalteradas como controle).
- [`docs/qa-com-ia.md`](docs/qa-com-ia.md): revisão crítica de `regras.py` e da tool feita com IA a partir das execuções reais, com cada hipótese confirmada empiricamente antes de ser apresentada. Quatro decisões do aluno (três aceitas, uma **rejeitada** com motivo), 140 testes novos, e a correção da regra de elevação comprovada com o modelo real (o reset de senha de um usuário deixou de virar rota crítica).
- [`docs/prompts.md`](docs/prompts.md): diário cronológico de todos os prompts de desenvolvimento usados com o assistente de IA, inclusive os reconstruídos quando a decisão foi tomada por iniciativa do assistente, com objetivo e resultado de cada um.

## 10. Extensões E1 e E2

Duas extensões distintas do item 4.9 da especificação; nenhuma delas cumpre requisito obrigatório. Detalhes em [`docs/extensoes.md`](docs/extensoes.md).

**E1. Pipeline de CI (GitHub Actions).** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda a cada push na `main` e a cada pull request, em matriz Python 3.10 e 3.12: `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest -m "not live"` e `uv build`. Actions pinadas por hash de commit, com Dependabot para atualizá-las. Evidências: badge no topo deste README, aba [Actions](https://github.com/ldebatin/sctec-projeto-recuperacao/actions/workflows/ci.yml), registros gerados da API em [`docs/evidencias/ci/`](docs/evidencias/ci/) (primeira execução verde e execução #36 na `main` com o código final: 370 testes nas duas versões; 34 das 36 execuções verdes, as 2 falhas em PR e corrigidas antes do merge). Cada issue do projeto foi desenvolvida em branch própria e integrada por PR só com o CI verde.

**E2. Cenário adversarial de prompt injection.** O exemplo [`06_prompt_injection.json`](data/exemplos/06_prompt_injection.json) embute instruções para rebaixar a prioridade e exfiltrar a chave de API, em cima de um incidente real. Controles em camadas: detector determinístico com 10 padrões em `validar_entrada` (alerta e revisão humana **antes** de qualquer chamada ao LLM, sem bloquear o chamado); delimitadores `<chamado>` e regra explícita de "isto é dado, não instrução" nos dois prompts; rota, prioridade e revisão decididas por regras fora do alcance do texto; redação de segredos na saída; saída estruturada. Evidência real: nos logs de [`prompt-v1`](docs/evidencias/execucoes/prompt-v1/06_prompt_injection.jsonl) e [`prompt-v2`](docs/evidencias/execucoes/prompt-v2/06_prompt_injection.jsonl) o `alerta_seguranca` lista 6 padrões antes da primeira `llm_chamada`, o modelo manteve `infraestrutura`/`alta`, e nem a chave nem o system prompt apareceram na saída. 25 testes em `tests/test_seguranca.py`.

## 11. Limitações conhecidas

- **Detector de injeção lexical.** Uma injeção parafraseada ou em outro idioma pode passar sem alerta; por isso as demais camadas (delimitadores, regras, redação, schema) valem mesmo sem detecção.
- **Termos de indisponibilidade por substring.** "O portal **não** está fora do ar" também eleva a prioridade. Decisão consciente, registrada e fixada por teste em `docs/qa-com-ia.md`: o erro é na direção segura (revisão humana a mais).
- **Confiança autoavaliada.** O valor vem do próprio modelo; serve como sinal para revisão, nunca como decisão isolada. O limiar 0.6 foi confirmado com apenas 7 amostras.
- **Saída do modelo não é determinística.** Rotas e prioridades são garantidas pelas regras, mas categoria, impacto, resumo e formato dos passos podem variar entre execuções (o cenário 02 variou o impacto entre as rodadas; o 06 devolveu os passos em uma linha).
- **Recuperação lexical.** BM25 não entende sinônimos nem paráfrases; um chamado com vocabulário diferente do artigo pode ficar sem contexto. A base tem 10 artigos e o catálogo 8 serviços, ambos fictícios; a resolução por apelido é por substring.
- **Escopo de execução única.** Sem memória entre execuções, checkpointer ou human-in-the-loop real: "revisão humana" é uma flag na saída, não uma pausa do grafo. Sem interface gráfica, fila, multiusuário ou integração com ferramenta de chamados.
- **Dependência de um provedor.** Um único LLM (Gemini), sujeito a quota e cobrança; latência típica de 4 a 13 s por chamado (duas chamadas ao modelo). Os testes `live` não rodam no CI.
- **Privacidade parcial.** O mascaramento cobre e-mail e CPF, só nos logs; a saída da triagem mantém os contatos das equipes (fictícios aqui) porque o atendente precisa deles.

## 12. Vídeo de demonstração

> Link do vídeo (não listado, até 10 minutos): **a preencher na issue #20**.

Roteiro com blocos, tempos, comandos exatos e o mapeamento para os 8 itens do item 5.4 da especificação: [`docs/roteiro-video.md`](docs/roteiro-video.md).

## 13. Estrutura do repositório

```
sctec-projeto-recuperacao/
├── README.md                  # este guia
├── pyproject.toml, uv.lock    # dependências (langgraph 1.2, langchain 1.4, langchain-google-genai 4.4, pydantic 2.13, rank-bm25, typer)
├── .env.example               # variáveis de configuração (copiar para .env)
├── .python-version            # 3.12 (requires-python >= 3.10)
├── .github/workflows/ci.yml   # extensão E1
├── src/triagem/               # grafo.py, nodes.py, regras.py, retrieval.py, tools/catalogo.py, prompts.py,
│                              # observabilidade.py, modelos.py, estado.py, contexto.py, config.py, llm.py, cli.py
├── tests/                     # 16 arquivos, 372 testes (FakeLLM; 2 live)
├── data/
│   ├── base_conhecimento/     # 10 artigos Markdown com front-matter
│   ├── catalogo_servicos.json # 8 serviços consultados pela tool
│   └── exemplos/              # 7 chamados de demonstração
├── docs/
│   ├── PRD.md                 # requisitos, decisões, rastreabilidade com a rubrica
│   ├── cenarios.md            # o que cada exemplo demonstra e como reproduzir falhas
│   ├── instrucoes-agente.md   # system prompts documentados (espelho testado do código)
│   ├── refinamento-prompt.md  # ciclo v1 → v2 com medições
│   ├── qa-com-ia.md           # revisão com IA e decisões do aluno
│   ├── extensoes.md           # E1 e E2
│   ├── prompts.md             # diário de prompts de desenvolvimento
│   ├── roteiro-video.md       # blocos, tempos e comandos do vídeo
│   ├── checklist-entrega.md   # revisão final item a item da especificação
│   └── evidencias/            # índice, saídas e logs reais, testes.txt, registros do CI
└── logs/                      # gerado em execução, ignorado pelo Git
```
