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

## Fase 2 — Grafo LangGraph e CLI (pendente)
