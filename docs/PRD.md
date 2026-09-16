# PRD — Agente Inteligente de Triagem de Chamados Técnicos

| Campo | Valor |
|---|---|
| Projeto | Situação de Aprendizagem (Recuperação) — IA para Desenvolvedores [T1], Módulo 2 |
| Autor | Luiz Fernando Debatin |
| Repositório | https://github.com/ldebatin/sctec-projeto-recuperacao |
| Prazo de entrega | **18/09/2026 às 22h** (submissão no AVA: link do repositório + link do vídeo) |
| Versão do PRD | 1.7 — 16/09/2026 (evidências consolidadas na #19: índice `docs/evidencias/README.md`, layout `execucoes/` por versão de prompt em vez de `logs/` + `saidas/`) |
| Status | Aprovado para implementação |

Este documento condensa a especificação do professor em um guia único de implementação. Toda decisão técnica deve ser rastreável a um requisito daqui, e todo requisito daqui deve ser rastreável a um critério da rubrica (seção 15).

---

## 1. Visão geral

### 1.1 Problema

Equipes de suporte recebem chamados técnicos heterogêneos (software, infraestrutura, suporte ao usuário) e gastam tempo na triagem manual: entender o problema, classificar, definir prioridade, descobrir a equipe responsável e sugerir o primeiro passo. Erros de triagem atrasam incidentes críticos e sobrecarregam equipes com chamados triviais.

### 1.2 Solução

Um agente construído com **LangGraph** que recebe um chamado (título + descrição, mais campos opcionais), analisa o conteúdo com um LLM, classifica o risco com regras determinísticas, decide por ramificação condicional o caminho de execução, consulta uma base de conhecimento (rota simples) ou uma tool de catálogo de serviços (rota crítica), e produz uma **saída estruturada** (Pydantic/JSON) pronta para apoiar a triagem humana.

### 1.3 Princípios

1. **Pequeno, funcional, reproduzível, explicável.** Cada componente precisa ser localizável no código e explicável em 30 segundos no vídeo.
2. **Modelo decide, regras controlam.** O LLM interpreta e sugere; regras determinísticas da aplicação decidem roteamento, prioridade final e necessidade de revisão humana.
3. **Falhar de forma controlada.** Nenhuma falha (entrada inválida, LLM indisponível, tool com erro) derruba a aplicação; todas produzem saída estruturada de fallback com `requer_revisao_humana = true`.
4. **Tudo rastreável.** Cada execução tem `run_id`, e os logs permitem reconstruir o caminho percorrido.
5. **Testável sem rede.** Testes usam LLM falso injetado; a suíte roda no CI sem chaves.

### 1.4 Fora de escopo

- Interface gráfica, deploy em nuvem, arquitetura distribuída, banco de dados relacional.
- Integração com sistemas reais de ticket (Jira, GLPI, ServiceNow).
- Multiusuário, autenticação, fila de chamados, histórico entre execuções.
- Extensões não escolhidas: MCP, RAG com embeddings, checkpointer persistente, human-in-the-loop, automação low-code, observabilidade com trace distribuído.

---

## 2. Decisões de arquitetura (registro)

Decisões tomadas em 11/09/2026 com o aluno. Alternativas consideradas ficam registradas para justificar no vídeo.

| # | Decisão | Escolha | Alternativas consideradas e motivo da rejeição |
|---|---|---|---|
| D1 | Provedor de LLM | **Google Gemini** (`langchain-google-genai`), modelo flash configurado por `.env` | OpenAI (custo, sem chave); Anthropic (custo, sem chave); Ollama local (saída estruturada menos confiável, lento na demo). Gemini tem tier gratuito e bom suporte a saída estruturada. |
| D2 | Formato da aplicação | **CLI** (Typer) | CLI + FastAPI (mais código sem ganho de nota); Streamlit (logs pouco visíveis, testes indiretos). |
| D3 | Extensões técnicas | **E1: Pipeline de CI** (GitHub Actions: ruff + pytest) e **E2: Cenário adversarial de prompt injection** | CI + HITL (exige checkpointer, mais risco de API); Injection + HITL (sem evidência automática de testes); CI + Observabilidade ampliada (menos visível no grafo). |
| D4 | Tool da rota crítica | **Catálogo de serviços local** (`data/catalogo_servicos.json`) via função Python decorada com `@tool` | Health check HTTP (dependência de rede na demo); webhook (sobrepõe extensão low-code). |
| D5 | Estratégia de contexto (requisito obrigatório) | **Base de conhecimento local** em Markdown com recuperação lexical **BM25** (`rank-bm25`) + **state** do grafo carregando análise entre nodes | RAG com embeddings (custo, dependência de API de embeddings, e inviabilizaria contabilizar como extensão futura); checkpointer (não agrega ao fluxo single-shot). |
| D6 | Quem decide chamar a tool | **Regra determinística** no node `classificar_risco` (rota `critico` → tool). O LLM não escolhe tools. | ReAct/tool-calling pelo modelo: menos determinístico, mais difícil de testar e de explicar. |
| D7 | Condição de parada | Grafo acíclico exceto **um loop limitado de retry** em `analisar_chamado` (`MAX_TENTATIVAS_LLM`, padrão 2) + `recursion_limit` do LangGraph como rede de segurança | Sem loop (não demonstra controle de parada); retry dentro do node (invisível no grafo). |
| D8 | Idioma dos identificadores | **Português** (`analisar_chamado`, `classificar_risco`), seguindo a Figura 1 da espec | Inglês: dificulta correlacionar com a espec no vídeo. |
| D9 | Gerenciador de pacotes | **uv** + `pyproject.toml` + `uv.lock` versionado; `requires-python >= 3.10` (máquina local tem 3.10.12) | pip + requirements.txt (sem lock reproduzível); poetry (não instalado). |
| D10 | Logs | `logging` da stdlib com formatter JSON Lines; saída em stderr + arquivo `logs/<run_id>.jsonl` (gitignored) | structlog (dependência extra sem necessidade). |
| D11 | Testes | **pytest** com `FakeLLM` injetado por fábrica; testes `live` opcionais marcados e pulados sem chave | Mock por monkeypatch em cada teste (repetitivo). |
| D12 | Saída estruturada | **Pydantic v2** (`ResultadoTriagem`), serializado como JSON na CLI | Dataclass + json (sem validação de enum/limites). |
| D13 | Diário de prompts | `docs/prompts.md` registra **todos os prompts de desenvolvimento** (inclusive os implícitos); instruções do agente ficam em `docs/instrucoes-agente.md` | Um único arquivo misturando os dois (confunde avaliador). |

---

## 3. Requisitos funcionais

Prioridade: **P0** = núcleo obrigatório da rubrica; **P1** = extensões escolhidas; **P2** = desejável se sobrar tempo.

### 3.1 Entrada e saída

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-01 | Receber um chamado com `titulo` e `descricao` obrigatórios e `servico`, `ambiente`, `solicitante` opcionais, via arquivo JSON ou argumentos de CLI. | P0 | 4 |
| RF-02 | Validar a entrada com Pydantic: título 5–200 caracteres, descrição 20–8000 caracteres, `ambiente` em enum, rejeição de campos vazios ou só espaços. | P0 | 8 |
| RF-03 | Produzir `ResultadoTriagem` estruturado contendo, no mínimo: `categoria`, `prioridade`, `resumo`, `acao_sugerida`, `requer_revisao_humana`. | P0 | 4 |
| RF-04 | Incluir na saída campos de rastreabilidade: `run_id`, `rota`, `caminho_percorrido`, `fontes_contexto`, `tool_resultado`, `alertas`, `erros`. | P0 | 9 |
| RF-05 | Imprimir a saída em JSON (padrão) ou em texto legível (`--formato texto`). | P0 | 4 |

### 3.2 Grafo LangGraph

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-10 | Implementar o fluxo com `StateGraph` do LangGraph, com state tipado compartilhado entre nodes. | P0 | 5 |
| RF-11 | Nodes com responsabilidade única: `validar_entrada`, `analisar_chamado`, `classificar_risco`, `consultar_base`, `consultar_tool`, `gerar_resposta`, `tratar_falha`. | P0 | 5 |
| RF-12 | Ramificação condicional após `classificar_risco`: rota `simples` → `consultar_base`; rota `critico` → `consultar_tool`. | P0 | 5 |
| RF-13 | Ramificação condicional após `validar_entrada`: entrada válida → `analisar_chamado`; inválida → `tratar_falha`. | P0 | 5, 8 |
| RF-14 | Ramificação condicional após `analisar_chamado`: sucesso → `classificar_risco`; falha com tentativas restantes → `analisar_chamado`; falha sem tentativas → `tratar_falha`. | P0 | 5 |
| RF-15 | Todo caminho termina em `END` a partir de `gerar_resposta` ou `tratar_falha`. Nenhum outro ciclo além do retry limitado. | P0 | 5 |
| RF-16 | Separar decisões do modelo (categoria sugerida, prioridade sugerida, impacto, serviço mencionado) das regras determinísticas (rota, prioridade final, revisão humana). | P0 | 5 |

### 3.3 Tool

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-20 | Tool `consultar_catalogo_servicos(servico, ambiente)` com schema de argumentos Pydantic e saída `ResultadoCatalogo` tipada. | P0 | 6 |
| RF-21 | Validar parâmetros: `servico` string não vazia, até 100 caracteres, normalizada (minúsculas, sem espaços extras); `ambiente` opcional em enum. | P0 | 6, 8 |
| RF-22 | Resolver o serviço por nome ou alias no `data/catalogo_servicos.json` e retornar equipe responsável, criticidade, status atual, runbook e contato de escalonamento. *Entregue na issue #9 com 8 serviços (API de Pagamentos com status `degradado`) e resolução também por alias contido na frase. Revisado em 15/09 (issue #17, QA com IA): apelido repetido entre serviços falha na carga (`catalogo_indisponivel`), e os apelidos genéricos "banco", "dominio" e "autenticacao" saíram do catálogo por resolverem frases fora do domínio.* | P0 | 6 |
| RF-23 | Tratar falhas: serviço não encontrado, serviço não identificado pela análise, catálogo indisponível ou corrompido, falha simulada (`SIMULAR_FALHA_TOOL=1`). A falha vira `tool_resultado.ok = false` e o fluxo segue para `gerar_resposta` com `requer_revisao_humana = true`. | P0 | 6, 8 |

### 3.4 Contexto e base de conhecimento

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-30 | Manter base de conhecimento em `data/base_conhecimento/*.md` com front-matter (`id`, `titulo`, `categoria`, `tags`, `servicos`) e corpo com sintomas, causa provável, procedimento e escalonamento. Mínimo de 8 artigos cobrindo as três categorias. *Entregue na issue #8 com 10 artigos.* | P0 | 7 |
| RF-31 | Node `consultar_base` recupera top-3 artigos por BM25 usando título + descrição + palavras-chave da análise, com limiar mínimo de score; abaixo do limiar, registra "sem artigos relevantes". *Calibrado em 15/09 (issue #11) com execuções reais: `LIMIAR_BM25 = 12.0`; artigo correto pontua 35–46, ruído até 11, fora do domínio 4,8 (`docs/evidencias/execucoes/prompt-v1/`).* | P0 | 7 |
| RF-32 | Node `gerar_resposta` usa **de fato** o contexto recuperado (artigos ou dados do catálogo) para compor `resumo` e `acao_sugerida`, citando os `id`s em `fontes_contexto`. *Entregue na issue #10: o contexto vai ao modelo no bloco `<contexto>`; se o modelo falhar, ação e justificativa são montadas sem LLM a partir do contexto (alerta `resposta_fallback`).* | P0 | 7 |
| RF-33 | State carrega a análise do LLM, a rota, o contexto e os erros entre nodes (memória de curto prazo da execução). | P0 | 7 |

### 3.5 Classificação e regras

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-40 | `categoria` ∈ {`software`, `infraestrutura`, `suporte`, `indefinido`}. | P0 | 4 |
| RF-41 | `prioridade` ∈ {`baixa`, `media`, `alta`, `critica`}. | P0 | 4 |
| RF-42 | `impacto` (da análise) ∈ {`usuario_unico`, `equipe`, `multiplos_usuarios`, `toda_organizacao`}. | P0 | 5 |
| RF-43 | Regra de rota em `classificar_risco`: `critico` se prioridade **final** ∈ {`alta`, `critica`}; senão `simples`. As condições "produção com impacto amplo" e "termos de indisponibilidade" (lista configurável em `regras.py`: "fora do ar", "indisponível", "todos os usuários", "ninguém consegue", "sistema parado", "queda geral", "perda de dados", "vazamento") levam à rota crítica por meio das elevações de RF-44, e o motivo registrado no log cita a regra que elevou. *Revisado em 11/09 (issue #5): "não acessa" saiu da lista por ser típico de problema de um único usuário. Revisado em 15/09 (issue #17, QA com IA): os ramos que repetiam as condições de RF-44 em `definir_rota` eram inalcançáveis e foram removidos; a comparação por substring dos termos foi mantida como limitação conhecida (erro na direção segura).* | P0 | 5 |
| RF-44 | Regras de elevação da prioridade (nunca rebaixam), cada uma com alerta próprio em `alertas`: (a) `ambiente = producao`, prioridade sugerida `media` **e impacto além de `usuario_unico`** → `alta`; (b) termo de indisponibilidade no texto → pelo menos `alta`; (c) `ambiente = producao` com impacto amplo → pelo menos `alta`. *Revisado em 11/09 (issue #5): (b) e (c) evitam rota crítica com prioridade baixa, que seria contraditória. Revisado em 15/09 (issue #17, QA com IA): (a) passou a exigir impacto além de um usuário; na execução real, o reset de senha de um usuário em produção (exemplo 01) virava rota crítica.* | P0 | 5 |
| RF-45 | Regra de revisão humana: `requer_revisao_humana = true` se rota `critico`, **ou** categoria `indefinido`, **ou** `confianca < 0.6`, **ou** tool falhou, **ou** suspeita de prompt injection, **ou** falha tratada. | P0 | 4 |

### 3.6 Extensão E1 — Pipeline de CI

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-50 | Workflow `.github/workflows/ci.yml` disparado em push e pull request para `main`. | P1 | 12 |
| RF-51 | Etapas: checkout, instalação do uv, `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -m "not live"`. | P1 | 12 |
| RF-52 | Badge de status no README e captura de tela de execução verde em `docs/evidencias/`. *Entregue nas issues #13 e #19 como registros gerados da API do Actions em `docs/evidencias/ci/` (dados da execução, jobs, etapas e contagem de testes), mais verificáveis que uma captura de tela.* | P1 | 12 |

### 3.7 Extensão E2 — Cenário adversarial de prompt injection

| ID | Requisito | Prioridade | Rubrica |
|---|---|---|---|
| RF-60 | Detector determinístico `detectar_injecao(texto)` com padrões (pt-BR e inglês): "ignore as instruções anteriores", "ignore previous instructions", "system prompt", "você agora é", "revele/mostre sua chave", "responda apenas com", "classifique como baixa" etc. Retorna lista de padrões encontrados. | P1 | 13 |
| RF-61 | Em `validar_entrada`, suspeita de injeção adiciona `possivel_prompt_injection` a `alertas`, gera log `alerta_seguranca` e força `requer_revisao_humana = true`, sem interromper o fluxo. *Entregue na issue #14, mais dois controles adicionais: aviso extra anexado aos prompts quando há suspeita e redação de segredos (`[REDIGIDO]`, alerta `segredo_redigido`) na saída. Revisado em 15/09 (issue #17): a redação também cobre fragmentos do segredo com 12 ou mais caracteres.* | P1 | 13 |
| RF-62 | Prompts do agente delimitam o conteúdo do chamado com marcadores explícitos e instruem o modelo a tratá-lo como dado, nunca como instrução. | P1 | 13 |
| RF-63 | Chamado adversarial em `data/exemplos/` e teste automatizado provando que a prioridade não é rebaixada pela instrução injetada e que o alerta é emitido. | P1 | 13 |

### 3.8 Desejáveis

| ID | Requisito | Prioridade |
|---|---|---|
| RF-70 | Mascarar e-mails e CPFs nos logs (regex simples) para não vazar dados pessoais em evidências. *Entregue na issue #15: aplicado a todos os detalhes de evento, inclusive aninhados; a saída da triagem não é alterada.* | P2 |
| RF-71 | Comando `triagem exemplos` que lista os chamados de exemplo com uma linha de descrição. | P2 |
| RF-72 | Comando `triagem grafo` que imprime o diagrama Mermaid do grafo gerado pelo LangGraph (`get_graph().draw_mermaid()`) para colar no README. | P2 |

---

## 4. Requisitos não funcionais

| ID | Requisito | Rubrica |
|---|---|---|
| RNF-01 | **Segredos:** nenhuma chave no repositório. `.gitignore` com `.env`, `logs/`, `.venv/`, `__pycache__/` no primeiro commit. `.env.example` com todas as variáveis e valores fictícios. | 8 |
| RNF-02 | **Falha rápida de configuração:** ausência de `GOOGLE_API_KEY` gera mensagem clara na inicialização, antes de montar o grafo. | 8 |
| RNF-03 | **Timeouts e retries do LLM:** timeout por chamada (padrão 30 s), `MAX_TENTATIVAS_LLM` (padrão 2), backoff simples para erros de quota do tier gratuito. | 8 |
| RNF-04 | **Determinismo:** `temperature = 0`; saída do modelo validada por Pydantic via `with_structured_output`. | 5 |
| RNF-05 | **Observabilidade:** eventos de log obrigatórios listados na seção 9, todos com `run_id`. | 9 |
| RNF-06 | **Reprodutibilidade:** `uv.lock` versionado; dados de exemplo no repositório para todos os cenários demonstrados; instruções de execução testadas do zero. | 2, 3 |
| RNF-07 | **Testes offline:** suíte padrão sem rede e sem chave; testes `live` opcionais. | 10, 12 |
| RNF-08 | **Qualidade de código:** ruff (lint + format) sem erros no CI; tipagem nos modelos e no state. | 12 |
| RNF-09 | **Custo:** no máximo 2 chamadas de LLM por chamado no caminho feliz (análise + resposta); respeitar limites de requisições por minuto do tier gratuito do Gemini. | — |

---

## 5. Modelo de domínio

### 5.1 Entrada — `Chamado`

```python
class Ambiente(str, Enum):
    producao = "producao"
    homologacao = "homologacao"
    desenvolvimento = "desenvolvimento"
    nao_informado = "nao_informado"

class Chamado(BaseModel):
    titulo: str            # 5–200 chars, strip, não vazio
    descricao: str         # 20–8000 chars, strip, não vazio
    servico: str | None    # até 100 chars
    ambiente: Ambiente = Ambiente.nao_informado
    solicitante: str | None  # até 100 chars
```

### 5.2 Saída do LLM (node `analisar_chamado`) — `AnaliseChamado`

```python
class AnaliseChamado(BaseModel):
    categoria: Categoria              # software | infraestrutura | suporte | indefinido
    prioridade_sugerida: Prioridade   # baixa | media | alta | critica
    impacto: Impacto                  # usuario_unico | equipe | multiplos_usuarios | toda_organizacao
    servico_mencionado: str | None    # nome do sistema/serviço citado, se houver
    palavras_chave: list[str]         # 3–8 termos para busca na base
    resumo_tecnico: str               # 1–2 frases
    confianca: float                  # 0.0–1.0
```

### 5.3 Saída da tool — `ResultadoCatalogo`

```python
class ResultadoCatalogo(BaseModel):
    ok: bool
    erro: str | None                  # servico_nao_encontrado | servico_nao_identificado | catalogo_indisponivel | parametro_invalido
    servico_id: str | None
    nome: str | None
    equipe_responsavel: str | None
    criticidade: str | None           # baixa | media | alta
    status_atual: str | None          # operacional | degradado | indisponivel | manutencao
    runbook: str | None
    contato_escalonamento: str | None
```

### 5.4 Saída final — `ResultadoTriagem`

```python
class ResultadoTriagem(BaseModel):
    run_id: str
    categoria: Categoria
    prioridade: Prioridade
    resumo: str
    acao_sugerida: str
    justificativa: str | None         # por que essa ação (adicionado na issue #10)
    requer_revisao_humana: bool
    motivo_revisao: list[str]         # ex.: ["rota_critica", "confianca_baixa"]
    rota: Literal["simples", "critico", "falha"]
    fontes_contexto: list[str]        # ids dos artigos ou do serviço do catálogo
    tool_resultado: ResultadoCatalogo | None
    alertas: list[str]                # ex.: ["possivel_prompt_injection", "prioridade_elevada_producao"]
    erros: list[str]
    caminho_percorrido: list[str]     # nodes na ordem executada
    modelo: str | None                # provedor:modelo usado
```

### 5.5 State do grafo — `EstadoTriagem` (TypedDict)

| Campo | Tipo | Preenchido por |
|---|---|---|
| `run_id` | `str` | inicialização |
| `entrada_bruta` | `dict` | inicialização (CLI) |
| `chamado` | `Chamado \| None` | `validar_entrada` |
| `analise` | `AnaliseChamado \| None` | `analisar_chamado` |
| `tentativas_llm` | `int` | `analisar_chamado` (incrementa) |
| `rota` | `str \| None` | `classificar_risco` |
| `prioridade_final` | `Prioridade \| None` | `classificar_risco` |
| `contexto` | `list[ArtigoRecuperado]` | `consultar_base` |
| `tool_resultado` | `ResultadoCatalogo \| None` | `consultar_tool` |
| `alertas` | `list[str]` (reducer: concatenação) | vários |
| `erros` | `list[str]` (reducer: concatenação) | vários |
| `caminho_percorrido` | `list[str]` (reducer: concatenação) | todos os nodes |
| `resultado` | `ResultadoTriagem \| None` | `gerar_resposta` / `tratar_falha` |

---

## 6. Arquitetura do grafo

```mermaid
flowchart TD
    START([START]) --> validar_entrada
    validar_entrada -->|válida| analisar_chamado
    validar_entrada -->|inválida| tratar_falha
    analisar_chamado -->|ok| classificar_risco
    analisar_chamado -->|erro e tentativas < MAX| analisar_chamado
    analisar_chamado -->|erro e tentativas >= MAX| tratar_falha
    classificar_risco -->|simples| consultar_base
    classificar_risco -->|critico| consultar_tool
    consultar_base --> gerar_resposta
    consultar_tool --> gerar_resposta
    gerar_resposta --> END([END])
    tratar_falha --> END
```

### 6.1 Responsabilidade de cada node

| Node | Tipo | Entrada do state | Saída para o state | Falhas tratadas |
|---|---|---|---|---|
| `validar_entrada` | determinístico | `entrada_bruta` | `chamado`, `alertas` (injeção), `erros` | `ValidationError` → `erros`, rota para `tratar_falha` |
| `analisar_chamado` | **LLM** (`with_structured_output(AnaliseChamado)`) | `chamado` | `analise`, `tentativas_llm` | timeout, quota, JSON inválido → `erros`, retry limitado |
| `classificar_risco` | determinístico | `analise`, `chamado` | `rota`, `prioridade_final`, `alertas` | — |
| `consultar_base` | determinístico (BM25) | `chamado`, `analise` | `contexto` | base vazia/ilegível → `erros`, contexto vazio |
| `consultar_tool` | determinístico (invoca tool) | `analise.servico_mencionado` ou `chamado.servico`, `chamado.ambiente` | `tool_resultado` | ver RF-23 |
| `gerar_resposta` | **LLM** (`with_structured_output(RespostaLLM)`) + montagem determinística | tudo | `resultado` | falha do LLM → resposta de fallback montada com dados do contexto, sem LLM |
| `tratar_falha` | determinístico | `erros`, `chamado` | `resultado` (fallback) | — |

### 6.2 Funções de roteamento (edges condicionais)

```python
def rotear_apos_validacao(state) -> Literal["analisar_chamado", "tratar_falha"]
def rotear_apos_analise(state) -> Literal["classificar_risco", "analisar_chamado", "tratar_falha"]
def rotear_apos_classificacao(state) -> Literal["consultar_base", "consultar_tool"]
```

Cada função registra o evento `roteamento` no log com `origem`, `decisao` e `motivo`.

### 6.3 Condição de parada

- Grafo acíclico exceto o retry de `analisar_chamado`, limitado por `tentativas_llm < MAX_TENTATIVAS_LLM`.
- `graph.invoke(..., config={"recursion_limit": 10})` como rede de segurança: o caminho mais longo possível tem 7 passos.
- Teste automatizado garante que, com LLM sempre falhando, o node é chamado exatamente `MAX_TENTATIVAS_LLM` vezes e o fluxo termina em `tratar_falha`.

---

## 7. Tool: `consultar_catalogo_servicos`

**Contrato**

```python
class ParametrosCatalogo(BaseModel):
    servico: str = Field(min_length=1, max_length=100)
    ambiente: Ambiente | None = None

@tool(args_schema=ParametrosCatalogo)
def consultar_catalogo_servicos(servico: str, ambiente: Ambiente | None = None) -> ResultadoCatalogo:
    """Consulta o catálogo interno de serviços e retorna equipe responsável, criticidade,
    status atual, runbook e contato de escalonamento."""
```

**Fonte de dados** — `data/catalogo_servicos.json`, lista de objetos:

```json
{
  "id": "portal-clientes",
  "nome": "Portal de Clientes",
  "aliases": ["portal", "portal web", "site de clientes"],
  "equipe_responsavel": "Squad Portal",
  "criticidade": "alta",
  "status_atual": "operacional",
  "ambientes": ["producao", "homologacao"],
  "runbook": "1. Verificar health check ... 2. Checar logs do gateway ...",
  "contato_escalonamento": "plantao-portal@empresa.exemplo"
}
```

Mínimo de 6 serviços cobrindo software (portal, ERP, API de pagamentos), infraestrutura (VPN, servidor de arquivos, banco de dados) e suporte (Active Directory / contas, e-mail corporativo). Um dos serviços deve ter `status_atual = "degradado"` para enriquecer a resposta na demo.

**Regras de falha**

| Situação | `erro` | Comportamento do fluxo |
|---|---|---|
| Análise não identificou serviço e `chamado.servico` vazio | `servico_nao_identificado` | segue para `gerar_resposta`; revisão humana |
| Nome/alias não existe | `servico_nao_encontrado` | segue; revisão humana; ação sugere confirmar nome do sistema |
| Arquivo ausente/JSON corrompido | `catalogo_indisponivel` | segue; revisão humana; log `tool_erro` |
| `SIMULAR_FALHA_TOOL=1` | `catalogo_indisponivel` | idem (para demo de falha de integração) |
| Parâmetro inválido (vazio, > 100 chars) | `parametro_invalido` | idem |

A escolha de **quando** chamar a tool é da regra de rota, não do modelo (D6).

---

## 8. Estratégia de contexto

1. **State compartilhado** carrega `analise`, `rota`, `contexto` e `tool_resultado` até `gerar_resposta` (memória da execução).
2. **Base de conhecimento** (`data/base_conhecimento/`): artigos Markdown com front-matter. Exemplos previstos: reset de senha AD; VPN não conecta; erro 500 no portal; lentidão no ERP; disco cheio em servidor; e-mail não sincroniza; impressora de rede offline; certificado TLS expirado; falha de deploy em homologação; acesso negado a pasta compartilhada.
3. **Recuperação BM25**: tokenização simples (minúsculas, remoção de pontuação e stopwords pt-BR), índice construído em memória no início da execução, consulta = título + descrição + `palavras_chave`. Top-3 com `score >= LIMIAR_BM25` (padrão 12.0, calibrado em 15/09 na issue #11; ver `docs/evidencias/execucoes/prompt-v1/README.md`).
4. **Uso efetivo**: o prompt de `gerar_resposta` recebe os artigos (id, título, procedimento) e exige que `acao_sugerida` se baseie neles quando existirem, citando os ids em `fontes_contexto`. Teste garante que os ids retornados aparecem no resultado.

Na rota `critico`, o contexto vem do catálogo (runbook, equipe, status), também injetado no prompt de `gerar_resposta`.

---

## 9. Observabilidade

Formato: uma linha JSON por evento, em stderr e em `logs/<run_id>.jsonl`.

| Evento | Campos além de `timestamp`, `run_id`, `nivel` |
|---|---|
| `execucao_iniciada` | `titulo` (truncado), `origem` (arquivo/argumentos) |
| `node_inicio` / `node_fim` | `node`, `duracao_ms` (no fim) |
| `roteamento` | `origem`, `decisao`, `motivo` |
| `llm_chamada` | `node`, `modelo`, `tentativa`, `duracao_ms`, `sucesso` |
| `tool_chamada` | `tool`, `parametros` |
| `tool_erro` | `tool`, `erro` |
| `alerta_seguranca` | `tipo`, `padroes` |
| `erro` | `node`, `tipo`, `mensagem` |
| `execucao_finalizada` | `rota`, `prioridade`, `requer_revisao_humana`, `duracao_total_ms` |

Um log completo de cada cenário demonstrado é copiado para `docs/evidencias/execucoes/<versão-do-prompt>/NN_nome.jsonl`, ao lado da saída `NN_nome.json` da mesma execução (mesmo `run_id`), com dados fictícios e PII mascarada. Índice e mapa para a rubrica em `docs/evidencias/README.md`. *Revisado em 16/09 (issue #19): o layout `logs/` + `saidas/` previsto originalmente foi trocado por pares por cenário e por versão de prompt, porque o refinamento da #16 precisa comparar antes/depois arquivo a arquivo.*

---

## 10. Segurança e tratamento de falhas

| Ameaça / falha | Controle |
|---|---|
| Vazamento de chave | `.gitignore` antes de qualquer `.env`; `.env.example`; revisão do histórico antes do push final |
| Entrada inválida | Pydantic em `validar_entrada`; mensagens de erro claras na saída de fallback |
| Entrada não confiável (injeção) | Detector determinístico + delimitadores no prompt + revisão humana forçada (E2) |
| LLM indisponível / quota | timeout, retry limitado, fallback estruturado |
| Saída do LLM fora do schema | `with_structured_output` + Pydantic; retry; fallback |
| Tool com erro | resultado tipado com `ok=false`; fluxo continua |
| Loop infinito | retry limitado + `recursion_limit` |
| Dados pessoais em logs | mascaramento de e-mail/CPF (P2) |

---

## 11. Estratégia de testes

Framework: pytest. LLM falso: classe `FakeLLM` com fila de respostas (objetos Pydantic ou exceções), injetada por execução via `executar_triagem(entrada, cfg=..., llm=..., registro=...)`, que passa `ContextoExecucao(cfg, llm, registro)` como `context` do LangGraph (`Runtime[ContextoExecucao]` nos nodes e nas funções de roteamento). *Revisado em 11/09 (issue #6): o grafo é compilado uma vez e as dependências chegam por invocação, em vez de `criar_grafo(llm=...)`.*

| # | Teste | Cobre | Rubrica |
|---|---|---|---|
| T1 | `test_fluxo_principal_simples` — chamado de reset de senha → rota `simples`, `consultar_base` no caminho, saída válida com `fontes_contexto` não vazio | caminho de sucesso | 10 |
| T2 | `test_fluxo_critico_aciona_tool` — portal fora do ar em produção → rota `critico`, `consultar_tool` no caminho, equipe responsável presente | grafo + tool | 10 |
| T3 | `test_entrada_invalida_nao_interrompe` — descrição vazia → `tratar_falha`, `requer_revisao_humana=True`, sem exceção propagada | falha / entrada inválida | 10 |
| T4 | `test_tool_servico_nao_encontrado` — serviço inexistente → `ok=false`, `erro=servico_nao_encontrado`, fluxo chega a `gerar_resposta` | tool com falha | 6 |
| T5 | `test_tool_valida_parametros` — servico vazio / > 100 chars → `parametro_invalido` | validação da tool | 6, 8 |
| T6 | `test_retry_respeita_limite` — LLM sempre falha → exatamente `MAX_TENTATIVAS_LLM` chamadas → `tratar_falha` | condição de parada | 5 |
| T7 | `test_prompt_injection_detectada` — chamado adversarial → alerta, revisão humana, prioridade não rebaixada | extensão E2 | 13 |
| T8 | `test_bm25_recupera_artigo_esperado` — consulta "vpn não conecta" retorna artigo de VPN em primeiro | contexto | 7 |
| T9 | `test_regras_classificar_risco` (parametrizado) — combinações de prioridade/ambiente/impacto → rota esperada | regras determinísticas | 5 |
| T10 | `test_live_gemini_smoke` (`@pytest.mark.live`, pulado sem chave) — execução real ponta a ponta. *Verde em 15/09 com `gemini-2.5-flash` (2 testes em `tests/test_live.py`).* | integração real | 4 |

Mínimo da rubrica: 3 testes (sucesso, falha, grafo/tool). Planejados: 9 offline + 1 live.

---

## 12. Prompts do agente, refinamento e QA com IA

### 12.1 Instruções do agente (`docs/instrucoes-agente.md`)

Documentar os dois system prompts (análise e resposta), com versão, data e racional. *Entregue na issue #16: `docs/instrucoes-agente.md` é gerado a partir de `prompts.py` e o teste `tests/test_prompts_docs.py` garante que os textos não divergem.* Regras obrigatórias nos prompts:
- Papel: analista de triagem de suporte técnico.
- Conteúdo do chamado entre delimitadores `<chamado>...</chamado>`, tratado como dado.
- Saída sempre em português do Brasil, no schema fornecido.
- Em dúvida entre categorias, usar `indefinido` e reduzir `confianca`.
- Nunca inventar sistemas, equipes ou procedimentos que não estejam no contexto fornecido.

### 12.2 Refinamento (`docs/refinamento-prompt.md`)

Registrar ao menos um ciclo real: **problema observado** (ex.: modelo classificava "sistema lento" como `critica` sem evidência de impacto) → **alteração** (critério explícito de prioridade no prompt + exemplos) → **resultado** (comparação antes/depois em 3 chamados de exemplo, com logs). O ciclo deve acontecer de fato durante a implementação e ser documentado com as saídas reais. *Entregue na issue #16 (15/09): problemas reais do v1 (confiança saturada em 1.0, passos colados, equipe inventada), diff v1 → v2 e antes/depois nos 7 exemplos em `docs/refinamento-prompt.md`, com saídas em `docs/evidencias/execucoes/prompt-v1/` e `prompt-v2/`.*

### 12.3 QA com IA (`docs/qa-com-ia.md`)

Usar IA (Claude Code) para revisar uma alteração real ou gerar/refinar um teste. Registrar: trecho revisado, problema apontado pela IA, sugestão, **decisão do aluno** (aceita, aceita com ajuste ou rejeitada) e motivo. Pelo menos uma sugestão deve ser rejeitada ou ajustada com justificativa, para evidenciar uso crítico.

### 12.4 Diário de prompts de desenvolvimento (`docs/prompts.md`)

Lista cronológica de todos os prompts usados (ou que deveriam ter sido usados) para chegar a cada resultado do projeto, inclusive os reconstruídos a partir de decisões tomadas pela IA. Atualizado no mesmo commit da alteração correspondente.

---

## 13. Estrutura do repositório

```
sctec-projeto-recuperacao/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── src/triagem/
│   ├── __init__.py
│   ├── config.py            # leitura do .env, constantes (MAX_TENTATIVAS_LLM, limiares)
│   ├── modelos.py           # Chamado, AnaliseChamado, ResultadoCatalogo, ResultadoTriagem, enums
│   ├── estado.py            # EstadoTriagem (TypedDict + reducers)
│   ├── llm.py               # fábrica do modelo (init_chat_model) e FakeLLM
│   ├── prompts.py           # system prompts do agente (fonte da verdade; docs espelham)
│   ├── regras.py            # classificar_risco, detectar_injecao, revisão humana
│   ├── retrieval.py         # carga da base e BM25
│   ├── tools/catalogo.py    # consultar_catalogo_servicos
│   ├── nodes.py             # funções dos nodes
│   ├── contexto.py          # ContextoExecucao (cfg, llm, registro) injetado via Runtime
│   ├── grafo.py             # StateGraph, edges, roteamento, criar_grafo(), executar_triagem(...)
│   ├── observabilidade.py   # logger JSON, run_id, helpers de evento
│   └── cli.py               # Typer: triar, exemplos, grafo
├── tests/
│   ├── conftest.py          # fixtures: fake_llm, grafo_teste, chamados de exemplo
│   ├── test_fluxo.py
│   ├── test_tool.py
│   ├── test_regras.py
│   ├── test_retrieval.py
│   ├── test_seguranca.py
│   └── test_live.py
├── data/
│   ├── base_conhecimento/*.md
│   ├── catalogo_servicos.json
│   └── exemplos/
│       ├── 01_reset_senha.json            # simples, suporte
│       ├── 02_portal_fora_do_ar.json      # critico, software, producao
│       ├── 03_vpn_intermitente.json       # simples, infraestrutura
│       ├── 04_entrada_invalida.json       # descricao vazia
│       ├── 05_servico_desconhecido.json   # critico, tool falha
│       ├── 06_prompt_injection.json       # adversarial
│       └── 07_fora_do_dominio.json        # categoria indefinido
├── docs/
│   ├── PRD.md
│   ├── prompts.md                # diário de prompts de desenvolvimento
│   ├── instrucoes-agente.md
│   ├── refinamento-prompt.md
│   ├── qa-com-ia.md
│   ├── extensoes.md
│   ├── roteiro-video.md
│   └── evidencias/           # README.md (índice), testes.txt, ci/, execucoes/prompt-v1/, execucoes/prompt-v2/
└── logs/ (gitignored)
```

---

## 14. Configuração (`.env.example`)

```env
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-2.5-flash        # confirmar modelo flash vigente no tier gratuito
GOOGLE_API_KEY=coloque-sua-chave-aqui
LLM_TIMEOUT_SEGUNDOS=30
MAX_TENTATIVAS_LLM=2
LLM_BACKOFF_BASE_SEGUNDOS=2       # espera em erro de quota (429), dobra por tentativa
LIMIAR_BM25=12.0                  # calibrado em 15/09 com o Gemini (issue #11)
LIMIAR_CONFIANCA=0.6              # confirmado com o prompt v2 (issue #16): técnicos 0.95, fora do domínio 0.5
LOG_NIVEL=INFO
LOG_FORMATO=json                  # json | texto
SIMULAR_FALHA_TOOL=0
```

---

## 15. Rastreabilidade com a rubrica

| Critério | Peso | Evidência principal | Requisitos |
|---|---|---|---|
| 1. Vídeo | 0,50 | link no README, ≤ 10 min, roteiro em `docs/roteiro-video.md` | seção 17 |
| 2. GitHub | 0,50 | commits incrementais, `main` final, `uv.lock`, `.env.example` | RNF-01, RNF-06 |
| 3. README | 0,50 | seções obrigatórias do item 5.2 da espec | seção 16 |
| 4. Aplicação funcional | 1,00 | CLI executa 7 exemplos; saída `ResultadoTriagem` | RF-01…05 |
| 5. LangGraph | 1,00 | `grafo.py`, diagrama, 3 edges condicionais, retry limitado | RF-10…16 |
| 6. Tool | 1,00 | `tools/catalogo.py`, T4, T5, exemplo 05 | RF-20…23 |
| 7. Contexto | 1,00 | `retrieval.py`, base em `data/`, T1, T8, `fontes_contexto` | RF-30…33 |
| 8. Segurança e falhas | 0,75 | `.env.example`, validação, exemplos 04/05, T3 | RF-02, RF-23, RNF-01…03 |
| 9. Observabilidade | 0,50 | logs JSONL em `docs/evidencias/execucoes/` (par `.json`/`.jsonl` por cenário) | seção 9 |
| 10. QA com IA e testes | 0,75 | 9 testes offline, `docs/qa-com-ia.md`, `docs/evidencias/testes.txt` | seção 11, 12.3 |
| 11. Prompts e refinamento | 0,50 | `docs/instrucoes-agente.md`, `docs/refinamento-prompt.md` | 12.1, 12.2 |
| 12. Extensão 1 (CI) | 1,00 | `ci.yml`, badge, registros em `docs/evidencias/ci/` | RF-50…52 |
| 13. Extensão 2 (injection) | 1,00 | `regras.py`, exemplo 06, T7, `docs/extensoes.md`, `docs/evidencias/execucoes/*/06_prompt_injection.*` | RF-60…63 |

O mapa completo de cada critério para o arquivo de evidência que o comprova está em [`docs/evidencias/README.md`](evidencias/README.md) (issue #19).

---

## 16. README (conteúdo obrigatório)

1. Descrição da solução e objetivo da triagem
2. Arquitetura e diagrama Mermaid do grafo
3. State, nodes e decisões condicionais
4. Tool e sua participação no fluxo
5. Estratégia de contexto (BM25 + state)
6. Instalação, configuração, execução e testes (comandos copiáveis)
7. Cenários demonstrados (principal e falha), com saídas reais
8. Evidências de QA com IA e refinamento de prompt (links para `docs/`)
9. Extensões E1 e E2 com evidências
10. Limitações conhecidas
11. Link do vídeo

---

## 17. Roteiro do vídeo (≤ 10 min)

| Tempo | Conteúdo |
|---|---|
| 0:00–1:00 | Problema, objetivo e arquitetura (diagrama) |
| 1:00–3:00 | Fluxo principal: exemplo 01 (simples) com logs mostrando roteamento e `consultar_base` |
| 3:00–4:30 | Rota crítica: exemplo 02 com `consultar_tool` e dados do catálogo na resposta |
| 4:30–5:30 | Cenário de falha: exemplo 04 (inválido) e 05 (tool falha) com saída de fallback |
| 5:30–6:30 | Testes: `uv run pytest` verde; abrir `docs/qa-com-ia.md` |
| 6:30–7:30 | Refinamento de prompt (antes/depois) |
| 7:30–9:00 | Extensões: CI verde no GitHub Actions; exemplo 06 (prompt injection) |
| 9:00–9:45 | Limitações e encerramento |

---

## 18. Cronograma

| Data | Entrega | Commits esperados |
|---|---|---|
| 11/09 (qui) | PRD aprovado; scaffold (`pyproject`, `.gitignore`, `.env.example`, estrutura de pastas); modelos Pydantic; `docs/prompts.md` iniciado | 3–4 |
| 12/09 (sex) | State, nodes e grafo com `FakeLLM`; regras; T1, T3, T6, T9 verdes | 4–5 |
| 13/09 (sáb) | Integração Gemini real; base de conhecimento + BM25; tool de catálogo; logs JSON; T2, T4, T5, T8 | 4–5 |
| 14/09 (dom) | Cenários de falha; prompt injection (E2) + T7; CI (E1) verde; exemplos completos em `data/` | 3–4 |
| 15/09 (seg) | Refinamento de prompt real e documentado; QA com IA documentado; README completo; `docs/extensoes.md`, evidências | 3–4 |
| 16/09 (ter) | Roteiro do vídeo; gravação; publicação não listada; link no README | 1–2 |
| 17/09 (qua) | Buffer: revisão do repositório do zero (clone limpo, `uv sync`, `pytest`), checklist final da espec | 1–2 |
| 18/09 (qui) | Submissão no AVA antes das 22h | — |

---

## 19. Riscos e mitigações

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Limite de requisições do tier gratuito do Gemini durante desenvolvimento/vídeo | alta | médio | 2 chamadas por chamado; backoff; desenvolver com `FakeLLM`; gravar vídeo com pausas entre execuções |
| Saída estruturada do Gemini instável para enums | média | alto | Pydantic + retry + fallback; prompts com enumeração explícita dos valores |
| Mudanças de API do LangGraph/LangChain | média | médio | pinar versões no `pyproject`; consultar docs da versão instalada antes de codar o grafo |
| Vídeo ultrapassar 10 min (nota zero no critério 1) | média | alto | roteiro cronometrado; ensaio; cortar em edição |
| Vazamento de chave em commit | baixa | crítico (nota zero) | `.gitignore` no primeiro commit; `.env` nunca criado antes dele; revisão de `git log -p` antes do push final |
| Código que o aluno não consiga explicar | média | crítico | PRD + `docs/prompts.md` + comentários nos pontos de decisão; ensaiar explicação de cada node |
| Python 3.10 local incompatível com alguma dependência | baixa | médio | `uv python install 3.12` e `requires-python` ajustado se necessário |
| Refinamento de prompt "artificial" | média | médio | executar os 7 exemplos com o prompt v1, registrar problemas reais, só então refinar |

---

## 20. Casos de borda e comportamento esperado

| Caso | Comportamento |
|---|---|
| Descrição vazia, só espaços ou < 20 chars | `tratar_falha`; saída com `erros=["descricao: ..."]`, revisão humana |
| Descrição > 8000 chars | rejeitada em `validar_entrada` (limite configurável) |
| Título ausente | rejeitado |
| Chamado fora do domínio técnico ("quero férias") | modelo retorna `indefinido` + confiança baixa → revisão humana; ação sugere encaminhar ao canal correto |
| Chamado em inglês | prompt exige saída em pt-BR; classificação normal |
| Vários problemas no mesmo chamado | prioridade pelo mais severo; `resumo` lista os problemas; se `confianca < 0.6` → revisão humana |
| Rota crítica sem serviço identificado | tool retorna `servico_nao_identificado`; revisão humana; ação pede confirmar sistema afetado |
| Serviço citado por apelido ("o portal") | resolução por `aliases` no catálogo |
| Serviço com `status_atual = degradado` | resposta menciona incidente conhecido e runbook |
| LLM retorna categoria fora do enum | Pydantic falha → retry → fallback |
| LLM indisponível (rede/quota) | retry com backoff → `tratar_falha` |
| Chave ausente no `.env` | erro claro antes do grafo, código de saída 2 |
| Catálogo corrompido | `catalogo_indisponivel`; fluxo segue |
| Base de conhecimento sem artigo relevante | `contexto=[]`; resposta genérica; `alertas=["sem_contexto_relevante"]` |
| Prompt injection | alerta + revisão humana; prioridade e categoria vêm das regras, não da instrução injetada |
| E-mail/CPF na descrição | mascarados nos logs (P2); nunca enviados a `docs/evidencias/` sem máscara |

---

## 21. Questões abertas

| # | Questão | Impacto | Prazo para decidir |
|---|---|---|---|
| Q1 | ~~Modelo flash exato do Gemini disponível~~ Resolvida em 15/09 (issue #11): `gemini-2.5-flash` responde com saída estruturada válida em 14 de 14 chamadas; a conta usada tem faturamento ativo (`serviceTier: standard`) | — | — |
| Q2 | Versões atuais de `langgraph` e `langchain-google-genai` e sintaxe vigente de `with_structured_output` / `init_chat_model` | `llm.py`, `grafo.py` | 12/09, no scaffold |
| Q3 | Se o Python 3.10 local atende às dependências ou se instalamos 3.12 via uv | `pyproject` | 11/09, no scaffold |
| Q4 | ~~Nível de detalhe dos artigos da base~~ Resolvida em 11/09 (issue #8): 10 artigos médios, com seções Sintomas, Causa provável, Procedimento e Escalonamento | — | — |

Nenhuma questão aberta bloqueia o início da implementação.
