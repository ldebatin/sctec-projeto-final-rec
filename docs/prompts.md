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

---

## Fase 1 — Scaffold e modelos (pendente)

_(entradas serão adicionadas conforme a implementação avançar)_
