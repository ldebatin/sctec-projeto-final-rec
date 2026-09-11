# Diário de prompts de desenvolvimento

Registro cronológico de todos os prompts utilizados (ou que deveriam ter sido utilizados) para chegar a cada resultado deste projeto, com assistência do Claude Code.

Convenções:
- **Origem "usuário"**: prompt escrito de fato pelo aluno, transcrito como enviado.
- **Origem "reconstruído"**: a IA tomou uma decisão ou produziu um artefato por iniciativa própria; o prompt equivalente que teria gerado aquele resultado foi redigido depois, para que o processo seja reproduzível.
- Este arquivo é atualizado no mesmo commit da alteração correspondente.
- As instruções internas do agente (system prompts do LangGraph) **não** ficam aqui; ver `docs/instrucoes-agente.md`.

---

## Fase 0 — Preparação (11/09/2026)

### P-001 · Vincular a pasta ao repositório remoto
- **Origem:** usuário
- **Objetivo:** iniciar o versionamento do projeto no GitHub.
- **Prompt:**
  > sincronize a pasta com o repositório https://github.com/ldebatin/sctec-projeto-recuperacao.git
- **Resultado:** `git init -b main` na pasta vazia e `git remote add origin`. Repositório remoto estava vazio; nenhum commit ainda.

### P-002 · Extrair e analisar a especificação do projeto
- **Origem:** usuário
- **Objetivo:** compreender requisitos, rubrica, extensões e prazo.
- **Prompt:**
  > analise o documento ~/Downloads/IA PARA DESENVOLVEDORES [T1] - RECUPERAÇÃO DE PROJETO.docx que contem a descrição do projeto que iremos implementar
- **Resultado:** texto extraído com LibreOffice, Figura 1 (fluxo de referência) lida; análise dos 13 critérios, 8 extensões possíveis e prazo 18/09/2026 22h.

### P-003 · Detalhar a extração do documento
- **Origem:** reconstruído
- **Objetivo:** garantir que a análise cubra texto e imagens do .docx.
- **Prompt:**
  > Converta o .docx para texto preservando a estrutura de seções e tabelas, extraia as imagens embutidas e descreva o diagrama da Figura 1 (nodes e arestas). Em seguida resuma: desafio, entregáveis, requisitos obrigatórios por seção, extensões técnicas e regras de pontuação, critérios de avaliação com pesos, checklist final e prazo.
- **Resultado:** fluxo de referência identificado: `Entrada → analisar_chamado → classificar_risco → [simples → consultar_base | critico → consultar_tool] → gerar_resposta → END`.

### P-004 · Elaborar o PRD
- **Origem:** usuário
- **Objetivo:** condensar a especificação em um documento norteador da implementação.
- **Prompt:**
  > certo o primeiro ponto é condensar toda essa informações em um PRD para ser nosso norte na implementação, análise bem os requisitos e estresse as possibilidades, sempre sugir dúvidas ou bifurcações me consulte.
- **Resultado:** `docs/PRD.md` v1.0 com decisões, requisitos funcionais e não funcionais, modelo de domínio, arquitetura do grafo, tool, contexto, observabilidade, testes, rastreabilidade com a rubrica, cronograma, riscos e casos de borda.

### P-005 · Verificar o ambiente antes de recomendar a stack
- **Origem:** reconstruído
- **Objetivo:** basear as recomendações técnicas no que existe na máquina.
- **Prompt:**
  > Antes de sugerir a stack, verifique a versão do Python, quais gerenciadores de pacotes estão instalados (uv, pip, poetry) e se há chaves de API de LLM nas variáveis de ambiente. Não exponha valores de chaves, só os nomes.
- **Resultado:** Python 3.10.12, uv 0.12.7 disponível, nenhuma chave de LLM no ambiente. Decisões D1 e D9 do PRD.

### P-006 · Levantar bifurcações e consultar o aluno
- **Origem:** reconstruído
- **Objetivo:** decidir com o aluno o que muda materialmente a arquitetura.
- **Prompt:**
  > Identifique as decisões da especificação que alteram materialmente a arquitetura ou o esforço e que não têm um padrão óbvio. Para cada uma, apresente 3 a 4 opções com prós e contras, marque a recomendada e me pergunte antes de escrever o PRD. Decisões com padrão claro (gerenciador de pacotes, framework de testes, idioma dos identificadores, formato de log) assuma e registre como premissas revisáveis.
- **Resultado:** quatro perguntas respondidas: provedor **Google Gemini**; formato **CLI**; extensões **CI + prompt injection**; tool **catálogo de serviços local**. Registradas na seção 2 do PRD.

### P-007 · Instituir o diário de prompts
- **Origem:** usuário
- **Objetivo:** manter registro reproduzível do processo assistido por IA.
- **Prompt:**
  > Um ponto importe que vc deve guardar na memório, dentro da pasta docs deve ter uma arquivo chamado pronpts.md onde como deve ir criando uma lista com todos os pronpts que eu deveria utlizar para chegar nos resultados que estamos chegando nesse projeto, mesmo que eu não tenho escrito o pronpt.
- **Resultado:** este arquivo (`docs/prompts.md`) e a instrução gravada na memória persistente do assistente. Decisão D13 do PRD separa este diário das instruções do agente.

### P-008 · Estressar requisitos com casos de borda e riscos
- **Origem:** reconstruído
- **Objetivo:** antecipar comportamentos em situações limite antes de codar.
- **Prompt:**
  > No PRD, inclua uma tabela de casos de borda (entrada vazia ou enorme, chamado fora do domínio, chamado em inglês, vários problemas no mesmo chamado, serviço não identificado, apelidos de serviço, LLM indisponível ou fora do schema, chave ausente, catálogo corrompido, base sem artigo relevante, prompt injection, dados pessoais) com o comportamento esperado em cada um. Inclua também riscos com probabilidade, impacto e mitigação, e uma tabela de rastreabilidade critério da rubrica → evidência → requisitos.
- **Resultado:** seções 15, 19 e 20 do PRD.

### P-009 · Commit inicial, GitHub Project e issues por entregável
- **Origem:** usuário
- **Objetivo:** iniciar o histórico incremental e transformar o PRD em um plano de trabalho rastreável.
- **Prompt:**
  > 1 - Faça o commit inicial com o prd, 2 - crie um project no gitgub para esse repositório, 3 - Com base no prd divida em entregáveis e abra as issues desses entregáveis no project
- **Resultado:** commit `d95bda2` (PRD, diário de prompts e `.gitignore`); Project "Triagem de Chamados — Recuperação SENAI" (https://github.com/users/ldebatin/projects/6) vinculado ao repositório; 21 issues abertas, todas no Project com status Todo.

### P-010 · Decompor o PRD em entregáveis
- **Origem:** reconstruído
- **Objetivo:** definir a granularidade e a estrutura das issues.
- **Prompt:**
  > Divida o PRD em entregáveis de meio dia a um dia de trabalho, agrupados em milestones que sigam o cronograma da seção 18 (uma milestone por fase, com data). Cada issue deve ter objetivo, escopo em checkboxes, critérios de aceite verificáveis, referências aos requisitos e critérios da rubrica no PRD, dependências entre issues e um prompt sugerido para o assistente de IA executar a tarefa. Use labels de prioridade (P0 núcleo, P1 extensão, P2 desejável) e de área. Adicione todas ao Project com status Todo.
- **Resultado:** 6 milestones (Fase 1 a Fase 6, 11/09 a 17/09), 14 labels, 21 issues: #1–#3 scaffold e modelos; #4–#7 grafo e CLI; #8–#11 contexto, tool e Gemini; #12–#15 cenários e extensões; #16–#19 documentação e evidências; #20–#21 vídeo e entrega.

### P-011 · Corrigir referências cruzadas entre issues
- **Origem:** reconstruído
- **Objetivo:** garantir que as dependências apontem para as issues corretas após inserção de uma issue P2 no meio da sequência.
- **Prompt:**
  > Liste todas as referências `#N` na seção Dependências de cada issue aberta e confira se o título da issue referenciada corresponde à dependência pretendida. Corrija as divergentes via API e imprima a tabela final de dependências.
- **Resultado:** issues #18, #20 e #21 corrigidas; tabela de dependências verificada.

---

## Fase 1 — Scaffold e modelos (11/09/2026)

### P-012 · Iniciar a Fase 1
- **Origem:** usuário
- **Objetivo:** executar as issues #1, #2 e #3 do Project.
- **Prompt:**
  > pode iniciar a fase 1
- **Resultado:** issues executadas em sequência, cada uma em um commit próprio com `Closes #N`, e status atualizado no Project.

### P-013 · Scaffold do projeto (issue #1)
- **Origem:** reconstruído (prompt sugerido na issue #1, ajustado ao que foi feito)
- **Objetivo:** base reproduzível com segredos protegidos.
- **Prompt:**
  > Crie o scaffold conforme a seção 13 do docs/PRD.md usando uv: pyproject.toml com as dependências listadas e build backend uv_build, ruff configurado (excluindo Markdown do formatador), marcador pytest `live`, .env.example com as variáveis da seção 14, estrutura de pastas com .gitkeep, README mínimo e um esqueleto de CLI Typer com o comando `versao` para validar o entry point. Verifique se o uv já tem um Python mais novo que o 3.10 local; se tiver, fixe-o em .python-version mantendo requires-python >= 3.10. Rode uv sync, ruff check, ruff format --check e pytest, e liste as versões resolvidas das dependências principais.
- **Resultado:** Python 3.12.14 (já baixado pelo uv) fixado em `.python-version`; `requires-python >= 3.10` mantido para o CI. Versões resolvidas: langgraph 1.2.11, langchain 1.4.0, langchain-core 1.6.3, langchain-google-genai 4.4.0, pydantic 2.13.5, typer 0.27.2, pytest 9.1.1, ruff 0.16.7. Dois ajustes necessários: `extend-exclude = ["*.md"]` no ruff (o 0.16 formata blocos de código em Markdown) e `@app.callback()` no Typer (um único comando vira comando raiz sem isso). Questão Q3 do PRD resolvida.

### P-014 · Confirmar APIs vigentes das bibliotecas (questão Q2)
- **Origem:** reconstruído
- **Objetivo:** não codar contra assinaturas desatualizadas.
- **Prompt:**
  > Na versão instalada, imprima a assinatura de langchain.chat_models.init_chat_model, os defaults de model, temperature, timeout e max_retries de ChatGoogleGenerativeAI, a assinatura de with_structured_output e confirme os imports de StateGraph/START/END do langgraph e de tool do langchain_core.
- **Resultado:** `init_chat_model(model, *, model_provider=None, ..., **kwargs)`; `ChatGoogleGenerativeAI` tem `temperature=0.7`, `timeout=None`, `max_retries=6` por padrão (o retry interno será zerado para o loop limitado do grafo ficar visível); `with_structured_output(schema, method='json_schema', *, include_raw=False)`; imports confirmados.

### P-015 · Modelos de domínio e state do grafo (issue #2)
- **Origem:** reconstruído (prompt sugerido na issue #2, ajustado ao que foi feito)
- **Objetivo:** contratos de dados validados e state com reducers.
- **Prompt:**
  > Implemente em src/triagem/modelos.py os enums e modelos Pydantic v2 da seção 5 do docs/PRD.md (Chamado, AnaliseChamado, RespostaLLM, ArtigoRecuperado, ResultadoCatalogo, ResultadoTriagem), com strip de espaços antes da validação de tamanho, campos opcionais vazios convertidos para None, ambiente normalizado (minúsculas, sem acento) e campos extras ignorados para permitir metadados nos exemplos. Exponha uma constante com os cinco campos mínimos de saída exigidos pela rubrica. Em src/triagem/estado.py crie o TypedDict EstadoTriagem (total=False) com reducer operator.add em alertas, erros e caminho_percorrido. Escreva testes cobrindo entrada válida, vazia, curta, longa, título ausente, ambiente inválido e normalizado, palavras-chave deduplicadas, confiança fora do intervalo, campos mínimos no JSON de saída e presença dos reducers no state.
- **Resultado:** 26 testes verdes. Desvio consciente do PRD: `palavras_chave` aceita 1–10 itens (o prompt pedirá 3–8) para não descartar respostas quase corretas do modelo; registrado no docstring do modelo.

### P-016 · Configuração por .env e fábrica de LLM com FakeLLM (issue #3)
- **Origem:** reconstruído (prompt sugerido na issue #3, ajustado ao que foi feito)
- **Objetivo:** trocar o provedor por variável de ambiente e testar sem rede.
- **Prompt:**
  > Implemente src/triagem/config.py com um dataclass congelado Configuracao lendo as variáveis da seção 14 do docs/PRD.md via python-dotenv, aceitando um Mapping alternativo a os.environ para testes, com parsing validado de inteiros, decimais (aceitar vírgula) e booleanos (0/1, true/false, sim/não) e erros ErroConfiguracao que citam a variável. A chave do provedor não deve aparecer no repr e só é exigida por exigir_chave_api(), que cita a variável e o .env.example; provedores locais como ollama não exigem chave. Em src/triagem/llm.py crie criar_llm() usando init_chat_model("provedor:modelo") com temperature=0, timeout da configuração e max_retries=0 (o retry fica no grafo), com import tardio do langchain, e um FakeLLM com fila de respostas (instância do schema, dict validado ou exceção), resposta padrão quando a fila esvazia e registro de chamadas, compatível com with_structured_output(...).invoke(...). Defina um Protocol ModeloLinguagem com essa interface. Teste tudo, incluindo que criar_llm com chave falsa constrói o ChatGoogleGenerativeAI sem acessar a rede.
- **Resultado:** 30 testes novos (56 no total), todos verdes. `criar_llm(Configuracao(api_key="chave-falsa"))` instancia `ChatGoogleGenerativeAI` com `temperature=0`, `max_retries=0` e `timeout` da configuração sem chamada de rede. Regra N818 do ruff desativada para manter nomes de exceção em português. Questão Q2 do PRD encerrada (APIs registradas no docstring de `llm.py`).

---

## Fase 2 — Grafo LangGraph e CLI (iniciada em 11/09/2026)

### P-017 · Fluxo de trabalho por issue
- **Origem:** usuário
- **Objetivo:** rastreabilidade de processo: branch, PR, registro na issue e kanban.
- **Prompt:**
  > uma observação sempre criar uma branch para cada issue e ao fazer o push abrir um pr para a main, sempre regitre nas issues do project o que foi feito, sempre navegue a issue por todos as raias do kanban do projeto. guarde isso na memoria
- **Resultado:** regra gravada na memória do assistente. Decidido em seguida (consulta ao aluno): o assistente faz o merge após lint e testes verdes, com merge commit; raia "Em revisão" adicionada ao kanban (Todo → In Progress → Em revisão → Done). Comentários retroativos nas issues #1 a #3.

### P-018 · Exigir CI a cada push e PR
- **Origem:** usuário
- **Objetivo:** validação automática antes de qualquer merge.
- **Prompt:**
  > Outro ponto que notei agora, não está executando o CI com build e testes a cada push/pr
- **Resultado:** issue #13 (extensão E1) antecipada da Fase 4 para a Fase 2, com etapa de build acrescentada ao escopo.

### P-019 · Pipeline de CI (issue #13)
- **Origem:** reconstruído (prompt sugerido na issue #13, ajustado ao que foi feito)
- **Objetivo:** lint, formatação, testes e build a cada push na main e a cada PR.
- **Prompt:**
  > Crie .github/workflows/ci.yml disparado em push na main e pull_request para a main, com concurrency cancelando execuções antigas do mesmo ref e permissões mínimas. Use as versões mais recentes de actions/checkout e astral-sh/setup-uv (confira pela API de releases), matriz Python 3.10 e 3.12, uv sync --locked, ruff check, ruff format --check, pytest excluindo o marcador live e uv build. Adicione o badge ao README, documente a extensão E1 em docs/extensoes.md (o que roda, quando, por que os testes não precisam de chave, onde ver a evidência) e reserve docs/evidencias/ci/ para o registro da primeira execução verde.
- **Resultado:** workflow com 7 etapas em 2 versões de Python. A primeira execução falhou em "Set up job": `astral-sh/setup-uv` não publica tag de major flutuante (`v10` não existe, só `v10.1.0`). Correção: pinar versões exatas, `actions/checkout@v7.0.1` e `astral-sh/setup-uv@v10.1.0`, o que também torna o pipeline reproduzível. Evidência da primeira execução verde registrada em `docs/evidencias/ci/` no mesmo PR.

### P-020 · Analisar a falha do CI
- **Origem:** usuário
- **Objetivo:** entender a causa da execução #1 antes de seguir.
- **Prompt:**
  > antes, analise pq o CI quebrou
- **Resultado:** falha em *Set up job*, antes de qualquer etapa rodar: `astral-sh/setup-uv@v10` não resolve porque a action publica majors flutuantes só até `v7` (a partir da v8, apenas tags exatas) e o README oficial recomenda pin por hash. Erro de processo do assistente: inferiu a tag `v10` da release `v10.1.0` por analogia com `actions/checkout`, sem verificar a referência.

### P-021 · Aprovar o endurecimento do CI
- **Origem:** usuário
- **Objetivo:** aplicar as prevenções propostas na análise.
- **Prompt:**
  > pode fazer
- **Resultado:** issue #23 aberta e executada no fluxo padrão (branch, PR, CI, merge, comentário, raias).

### P-022 · Pin por hash e Dependabot (issue #23)
- **Origem:** reconstruído (prompt sugerido na issue #23)
- **Objetivo:** proteger o pipeline contra remanejamento de tags e automatizar atualizações.
- **Prompt:**
  > Resolva via API do GitHub o hash de commit das tags actions/checkout@v7.0.1 e astral-sh/setup-uv@v10.1.0, dereferenciando tags anotadas se necessário, e troque os `uses:` do ci.yml para `owner/action@<sha40> # vX.Y.Z`. Crie .github/dependabot.yml para github-actions com verificação semanal, label `ci` e prefixo de commit `ci`. Atualize a seção E1 de docs/extensoes.md explicando o pin por hash e registre tudo em docs/prompts.md.
- **Resultado:** `checkout@3d3c42e…` (v7.0.1) e `setup-uv@bec219d…` (v10.1.0); o hash da `setup-uv` coincide com o recomendado no README da action. Dependabot semanal às segundas, 9h de Brasília.

### P-023 · Continuar para a Fase 2
- **Origem:** usuário
- **Objetivo:** iniciar a issue #4 no fluxo padrão.
- **Prompt:**
  > pode seguir
- **Resultado:** issue #4 executada em branch própria com PR.

### P-024 · Observabilidade com JSON Lines e run_id (issue #4)
- **Origem:** reconstruído (prompt sugerido na issue #4, ajustado ao que foi feito)
- **Objetivo:** permitir reconstruir o caminho de qualquer execução só com o log.
- **Prompt:**
  > Implemente src/triagem/observabilidade.py com logging da stdlib: um RegistroExecucao por execução, com run_id (uuid4), handler de arquivo logs/<run_id>.jsonl sempre em JSON Lines (campos fixos timestamp, run_id, nivel, evento mais os detalhes) e handler de stderr em JSON ou texto legível conforme LOG_FORMATO. Crie helpers para os eventos da seção 9 do PRD, um context manager medir_node que registra node_inicio/node_fim com duração e, em exceção, um evento erro com traceback antes de propagar, e uma função resumir_eventos que reconstrói nodes percorridos, roteamentos, tools, chamadas de LLM, erros e alertas a partir do JSONL. Sem dependência do LangGraph. Garanta idempotência dos handlers e um método fechar(). Teste tudo, inclusive o formato texto via capsys e o filtro de nível. Mantenha compatibilidade com Python 3.10.
- **Resultado:** 10 testes novos (66 no total). Correção antes do PR: `datetime.UTC` só existe no 3.11; trocado por `timezone.utc` para a matriz 3.10 do CI passar. `resumir_eventos` normaliza `tool_erro` (tool → node, erro → tipo) para o resumo de erros ficar uniforme.

### P-025 · Regras determinísticas de risco e revisão humana (issue #5)
- **Origem:** reconstruído (prompt sugerido na issue #5, ajustado ao que foi feito)
- **Objetivo:** separar o que o modelo sugere do que a aplicação decide, em código puro e testável.
- **Prompt:**
  > Implemente src/triagem/regras.py como funções puras: detectar_termos_indisponibilidade (comparação sem acento e em minúsculas, lista configurável), ajustar_prioridade (elevações da RF-44, nunca rebaixando, cada uma com um alerta próprio), definir_rota (RF-43, devolvendo o motivo textual que explica a decisão, inclusive se a prioridade foi sugerida pelo modelo ou elevada por regra) e classificar_risco compondo as três. Implemente motivos_revisao_humana (RF-45) com tool_ok=None significando tool não acionada. Escreva um teste parametrizado com pelo menos 8 combinações de prioridade × ambiente × impacto × termos e testes dos motivos e alertas. Se alguma regra do PRD gerar falso positivo evidente, ajuste e registre a revisão no PRD.
- **Resultado:** 20 testes novos (86 no total); parametrizado com 11 combinações. Duas revisões registradas no PRD v1.1: "não acessa" removido dos termos (falso positivo para problema de um único usuário) e elevação de prioridade também por termo de indisponibilidade e por impacto amplo em produção, para a rota crítica nunca sair com prioridade baixa.

### P-026 · Grafo LangGraph com edges condicionais, retry limitado e tratar_falha (issue #6)
- **Origem:** reconstruído (prompt sugerido na issue #6, ajustado ao que foi feito)
- **Objetivo:** fluxo principal funcional de ponta a ponta com FakeLLM, antes de contexto e tool.
- **Prompt:**
  > Verifique na versão instalada do LangGraph se StateGraph aceita context_schema e se nodes e funções de roteamento recebem Runtime[Contexto]. Então implemente: src/triagem/contexto.py (ContextoExecucao com cfg, llm e registro), src/triagem/prompts.py (prompt v1 de análise com delimitadores <chamado> e enumeração explícita dos valores), src/triagem/nodes.py (decorator instrumentar que usa medir_node e acumula caminho_percorrido; nodes validar_entrada, analisar_chamado com contagem de tentativas, classificar_risco usando regras.py, stubs honestos de consultar_base e consultar_tool, gerar_resposta determinístico e tratar_falha com fallback) e src/triagem/grafo.py (três funções de roteamento que registram o evento roteamento com motivo, criar_grafo(), executar_triagem(entrada, cfg=, llm=, registro=) que nunca propaga exceção e trata GraphRecursionError, diagrama_mermaid()). Testes: T3 entrada inválida sem LLM, T6 retry exatamente MAX vezes com condição de parada no log, recuperação na segunda tentativa, fluxo simples e crítico, reconstrução do caminho pelo log, recursion_limit como rede de segurança, prova estrutural de que o único retrocesso é analisar_chamado→analisar_chamado e diagrama com todos os nodes.
- **Resultado:** 10 testes novos (96 no total). Decisão registrada no PRD v1.2: dependências por invocação (`Runtime[ContextoExecucao]`) em vez de `criar_grafo(llm=...)`, permitindo compilar o grafo uma vez. `tests/` virou pacote com `tests/dados.py` compartilhando chamados e análises de exemplo. `prompts.py` isento da regra de comprimento de linha, pois quebrar linhas alteraria o texto enviado ao modelo.

### P-027 · CLI com Typer: triar, exemplos e grafo (issue #7)
- **Origem:** reconstruído (prompt sugerido na issue #7, ajustado ao que foi feito)
- **Objetivo:** formato executável escolhido (D2) para rodar o fluxo completo.
- **Prompt:**
  > Implemente src/triagem/cli.py com Typer: comando triar aceitando --arquivo JSON ou --titulo/--descricao/--servico/--ambiente/--solicitante, --formato json|texto, --salvar, --env e --sem-logs; JSON malformado e entrada inválida devem virar a saída de fallback do grafo com código 0, enquanto erro de configuração (chave ausente) e erro de uso saem com código 2; imprima em stderr o caminho do log JSONL. Comandos exemplos (lista data/exemplos/*.json com o campo _cenario) e grafo (Mermaid do LangGraph). Teste com CliRunner injetando o FakeLLM no lugar de criar_llm, cobrindo saída JSON com os campos mínimos da rubrica, formato texto, fallback com exit 0, código 2 sem chave e sem entrada, --salvar, logs em stderr, exemplos e grafo.
- **Resultado:** 13 testes novos (109 no total). Entry point validado sem chave: mensagem "Erro de configuração: Variável GOOGLE_API_KEY não definida..." e código 2. `uv run triagem grafo` imprime o Mermaid gerado pelo LangGraph.

---

## Fase 3 — Contexto, tool e Gemini (iniciada em 11/09/2026)

### P-028 · Seguir para a Fase 3
- **Origem:** usuário
- **Prompt:**
  > pode seguir
- **Resultado:** Fase 3 iniciada pela issue #8, no fluxo padrão.

### P-029 · Base de conhecimento e recuperação BM25 (issue #8)
- **Origem:** reconstruído (prompt sugerido na issue #8, ajustado ao que foi feito)
- **Objetivo:** contexto obrigatório (RF-30, RF-31) usado de fato pelo fluxo.
- **Prompt:**
  > Escreva 10 artigos em data/base_conhecimento/*.md com front-matter YAML (id, titulo, categoria, tags, servicos) e seções Sintomas, Causa provável, Procedimento e Escalonamento, cobrindo suporte, infraestrutura e software (senha do AD, VPN, portal com erro 500, ERP lento, disco cheio, e-mail, impressora, certificado TLS, deploy em homologação, acesso negado a pasta). Implemente src/triagem/retrieval.py com tokenização sem acento e sem stopwords (normalizadas), índice BM25Okapi com título e tags pesando mais que o corpo, buscar(consulta, k, limiar) devolvendo ArtigoRecuperado com trecho da seção Procedimento, carga tolerante que ignora e reporta artigos inválidos ou com id duplicado, cache por pasta e erro tipado para base ausente. Ligue ao grafo: campo base em ContextoExecucao, node consultar_base real (consulta = título + descrição + palavras-chave; base indisponível vira erro no log + alerta sem_contexto_relevante sem interromper) e parâmetro base em executar_triagem. Testes: T8 (VPN em primeiro), ranking de 5 consultas, limiar, k, carga tolerante, integração no grafo e base injetada.
- **Resultado:** 15 testes novos (126 no total). Dois ajustes durante os testes: stopwords normalizadas sem acento (senão "nao" sobrevivia à tokenização) e documentação de que o BM25 precisa de pelo menos dois artigos para scores positivos (IDF). Questão Q4 do PRD resolvida.

### P-030 · Tool de catálogo de serviços (issue #9)
- **Origem:** reconstruído (prompt sugerido na issue #9, ajustado ao que foi feito)
- **Objetivo:** tool funcional com contrato tipado, validação e falhas controladas (RF-20 a RF-23).
- **Prompt:**
  > Crie data/catalogo_servicos.json com 8 serviços (portal, ERP, API de pagamentos, VPN, servidor de arquivos, banco de dados, Active Directory, e-mail) com aliases, equipe, criticidade, status (um degradado), ambientes, runbook e contato. Em src/triagem/tools/catalogo.py: ParametrosCatalogo (Pydantic, servico 1–100 chars, ambiente opcional), carga validada do JSON com erro tipado ErroCatalogoIndisponivel, resolução por id/nome/alias normalizados e por alias contido na frase (preferindo o mais longo), função pura consultar_catalogo e uma fábrica criar_tool_catalogo(caminho, simular_falha) que devolve um StructuredTool do LangChain com o schema. No node consultar_tool: servico = analise.servico_mencionado ou chamado.servico (ausente → servico_nao_identificado sem chamar a tool), registre tool_chamada, capture ValidationError → parametro_invalido e ErroCatalogoIndisponivel → catalogo_indisponivel, registre tool_erro e adicione a falha a erros sem interromper. Testes: T4 (serviço inexistente), T5 (validação de parâmetros pela tool), resolução por alias, catálogo corrompido/ausente, falha simulada, fluxo crítico com sucesso, serviço não identificado, rota simples não aciona a tool e coerência entre os ids dos artigos da base e do catálogo.
- **Resultado:** 35 testes novos (161 no total). A tool é construída por fábrica em vez de decorada no módulo para receber o caminho do catálogo e o flag de falha simulada da configuração, mantendo a lógica de consulta pura e testável sem LangChain.

### P-031 · gerar_resposta com LLM, contexto e fallback (issue #10)
- **Origem:** reconstruído (prompt sugerido na issue #10, ajustado ao que foi feito)
- **Objetivo:** fechar o caminho feliz provando que o contexto influencia a resposta (RF-32).
- **Prompt:**
  > Em src/triagem/prompts.py crie o prompt de resposta v1: papel de redator da triagem, categoria/prioridade/rota já decididas em <analise> e não questionáveis, chamado em <chamado> tratado como dado, ação baseada APENAS em <contexto> (artigos ou dados do catálogo) citando id do artigo ou equipe, recomendação de triagem manual quando o contexto estiver vazio, resumo de 1–2 frases, ação em até 5 passos numerados e justificativa de uma frase. Implemente formatar_contexto (catálogo ou artigos, com observação de ambiente e registro de tool falha) e montar_mensagens_resposta. No node gerar_resposta: chame with_structured_output(RespostaLLM), registre llm_chamada, mantenha categoria/prioridade/revisão determinísticas e, se o modelo falhar ou sair do schema, monte ação e justificativa sem LLM a partir do contexto com alerta resposta_fallback e erro resposta_falhou. Adicione justificativa opcional ao ResultadoTriagem e à saída texto da CLI. Atualize os testes existentes para enfileirar também a resposta no FakeLLM e escreva T1 (ids dos artigos chegam ao prompt e às fontes) e T2 (dados do catálogo chegam ao prompt), além de fallbacks e prompt.
- **Resultado:** 12 testes novos (173 no total). `tests/dados.py` ganhou `RESPOSTA_PADRAO` e `fake_llm(analise)`; os testes anteriores passaram a esperar 2 chamadas de LLM no caminho feliz. PRD v1.3 registra o campo `justificativa`.

### P-032 · Dados de exemplo e cenários de falha (issue #12, antecipada)
- **Origem:** reconstruído (prompt sugerido na issue #12, ajustado ao que foi feito)
- **Objetivo:** reprodutibilidade dos cenários obrigatórios só com o que está no repositório.
- **Prompt:**
  > Crie os 7 chamados de exemplo em data/exemplos/ com dados fictícios e um campo _cenario descrevendo o que cada um demonstra: 01 reset de senha (simples, suporte), 02 portal fora do ar (crítico, produção), 03 VPN intermitente (simples, sem ambiente informado, para não ser elevado pela regra de produção), 04 entrada inválida (descrição vazia), 05 serviço fora do catálogo (crítico com termo de indisponibilidade), 06 prompt injection (instrução injetada tentando rebaixar prioridade e exfiltrar GOOGLE_API_KEY, sobre uma indisponibilidade real), 07 fora do domínio (férias). Escreva docs/cenarios.md com a tabela de exemplos, rota e revisão esperadas, comandos e a tabela de cenários de falha, incluindo SIMULAR_FALHA_TOOL=1 e chave ausente. Teste que os 7 existem, que os válidos passam na validação, que o 04 falha sem chamar o LLM, que o 05 cai em servico_nao_encontrado, que as regras mantêm o 06 crítico mesmo com análise manipulada e que o 07 exige revisão por categoria indefinida.
- **Resultado:** 13 testes novos (186 no total). Issue #12 executada antes da #11 porque esta depende dos exemplos e a chave do Gemini ainda não está disponível.

### P-033 · Backoff para quota e teste live (issue #11, parte independente da chave)
- **Origem:** reconstruído (parte do prompt sugerido na issue #11 que não exige a chave do Gemini)
- **Objetivo:** preparar a integração real enquanto a chave não está disponível.
- **Prompt:**
  > Sem a GOOGLE_API_KEY, implemente só o que não depende dela: em analisar_chamado, quando a falha for de quota (429, RESOURCE_EXHAUSTED, rate limit) e ainda houver tentativa, espere um backoff exponencial limitado (LLM_BACKOFF_BASE_SEGUNDOS, padrão 2 s, máximo 30 s) antes de devolver ao grafo, registrando a espera no node_fim; sem espera na última tentativa nem em erros que não são de quota. Torne a espera substituível nos testes. Crie tests/test_live.py marcado live com dois testes ponta a ponta (exemplos 01 e 02) que são pulados automaticamente sem chave. Atualize .env.example e o PRD. Abra o PR sem fechar a issue e registre a pendência.
- **Resultado:** 10 testes novos (196 no total, mais 2 live pulados). Pendente na #11, dependente da chave: confirmar o modelo flash do tier gratuito, rodar os 7 exemplos com o Gemini, salvar saídas e logs em docs/evidencias/ e calibrar LIMIAR_BM25 e LIMIAR_CONFIANCA.

---

## Fase 4 — Cenários e extensões (iniciada em 11/09/2026)

### P-034 · Extensão E2: prompt injection com comportamento seguro (issue #14)
- **Origem:** reconstruído (prompt sugerido na issue #14, ajustado ao que foi feito)
- **Objetivo:** entrada não confiável sinalizada e neutralizada em camadas (RF-60 a RF-63).
- **Prompt:**
  > Em regras.py, implemente detectar_injecao(texto) com padrões rotulados (pt-BR e inglês) sobre o texto normalizado: ignorar instruções, system prompt, mudança de papel, exfiltração de segredo, instrução dirigida ao triador, forçar classificação ou formato, "sem revisão humana", jailbreak; e redigir_segredos(texto, segredos). Em validar_entrada, se houver padrões, registre alerta_seguranca com os rótulos e adicione o alerta possivel_prompt_injection sem bloquear o chamado. Anexe um aviso extra ao system prompt das duas chamadas quando houver suspeita. Em gerar_resposta, substitua qualquer ocorrência literal da chave de API por [REDIGIDO] com alerta segredo_redigido. Testes: 12 positivos e 5 chamados legítimos sem disparo, T7 com o exemplo 06 e uma análise manipulada para baixa (alerta, revisão humana, rota crítica e prioridade alta mantidas, aviso nos prompts, alerta antes do LLM no log), redação da chave vazada pelo modelo e prompts com delimitadores. Documente a E2 em docs/extensoes.md com ameaça, controles em camadas, evidências e limitação.
- **Resultado:** 24 testes novos (220 no total). A evidência com o Gemini real do exemplo 06 fica pendente da chave (issue #11).
