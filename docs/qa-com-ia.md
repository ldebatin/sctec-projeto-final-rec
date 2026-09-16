# QA com IA — revisão crítica de `regras.py` e `tools/catalogo.py`

Evidência do critério 10 da rubrica (uso de IA para QA, com decisão crítica do aluno). Sessão de 15/09/2026, issue #17, feita com o Claude Code sobre o código já integrado ao Gemini real (issue #11).

**Como foi feito.** O aluno pediu à IA uma revisão crítica de `src/triagem/regras.py` e `src/triagem/tools/catalogo.py` à luz das execuções reais de `docs/evidencias/execucoes/prompt-v1/`, com proposta de testes adicionais. A IA levantou hipóteses lendo o código e **confirmou cada uma empiricamente** antes de apresentá-la (script de verificação: 128 combinações de prioridade × ambiente × impacto × termos; frases de teste no catálogo; fragmentos de chave). O aluno decidiu cada sugestão entre *aceita*, *aceita com ajuste* e *rejeitada*. As decisões foram aplicadas no commit [`d004bc8`](https://github.com/ldebatin/sctec-projeto-recuperacao/commit/d004bc8) da branch `issue-17-qa-com-ia`, integrado à `main` pelo PR #37.

Convenção das seções: **Trecho** (o que foi revisado), **Problema** (o que a IA apontou e como confirmou), **Sugestão** (o que a IA propôs), **Decisão do aluno** e **Motivo**, **Efeito** (código, teste, evidência).

---

## 1. RF-44(a): produção elevava a prioridade sem olhar o impacto

**Trecho revisado** (`regras.py`, `ajustar_prioridade`, antes):

```python
if em_producao and prioridade is Prioridade.MEDIA:
    prioridade = Prioridade.ALTA
    alertas.append(ALERTA_ELEVADA_PRODUCAO)
```

**Problema.** Na execução real do exemplo 01 (reset de senha de um usuário, `ambiente = producao`), o Gemini seguiu a regra 3 do prompt v1 e sugeriu `media` com `impacto = usuario_unico`. A regra elevou para `alta`, a rota virou `critico` e a resposta acionou a equipe de Identidade e Acessos por um reset de senha. Evidência: `docs/evidencias/execucoes/prompt-v1/01_reset_senha.json` e `.jsonl` (motivo no log: `prioridade alta (elevada por regra)`). A regra tratava qualquer problema de um único usuário em produção como crítico.

**Sugestão da IA.** Condicionar a elevação ao impacto: só elevar `media → alta` quando `impacto ≠ usuario_unico`. Alternativas apresentadas: remover a regra (a) e deixar (c) cuidar de produção; ou manter e mudar a rota esperada do cenário 01 para `critico`.

**Decisão do aluno: aceita** (opção "condicionar ao impacto").
**Motivo.** Um problema de uma pessoa, mesmo em produção, não é incidente; já um problema de uma equipe em produção sem contorno continua merecendo rota crítica. Remover (a) por completo deixaria o caso `equipe` em `media`, e manter a regra faria o fluxo principal da demonstração (cenário 01, `consultar_base`) nunca acontecer com o modelo real.

**Efeito.** `ajustar_prioridade` exige `analise.impacto is not Impacto.USUARIO_UNICO`; RF-44 no PRD 1.5; T9 caso 5 passa a esperar `simples`/`media` e ganha o caso 5b (`equipe` em produção → `critico`/`alta`); teste `test_reset_de_senha_de_um_usuario_em_producao_e_rota_simples` reproduz a análise real do Gemini. Nova execução com o modelo real em `docs/evidencias/execucoes/prompt-v1/pos-qa-regras/01_reset_senha.json`: rota `simples`, `consultar_base` com `kb-001-reset-senha-ad` (score 39,6), sem revisão humana.

## 2. `definir_rota` tinha dois ramos inalcançáveis

**Trecho revisado** (`regras.py`, `definir_rota`, antes):

```python
if prioridade_final in PRIORIDADES_CRITICAS:
    ...
    return "critico", ...
if chamado.ambiente is Ambiente.PRODUCAO and analise.impacto in IMPACTOS_AMPLOS:
    return "critico", f"ambiente producao com impacto {analise.impacto.value}"
if termos_encontrados:
    return "critico", "termos de indisponibilidade: " + ", ".join(termos_encontrados)
return "simples", ...
```

**Problema.** `classificar_risco` chama `ajustar_prioridade` antes de `definir_rota`, e as elevações (b) e (c) já levam a prioridade a pelo menos `alta` exatamente nas condições dos ramos 2 e 3. A IA verificou as 128 combinações de prioridade × ambiente × impacto × presença de termo: os ramos 2 e 3 nunca foram alcançados. Além de código morto, o motivo registrado no log era pobre: "prioridade alta (elevada por regra)" sem dizer qual regra.

**Sugestão da IA.** Simplificar: rota `critico` se e somente se a prioridade final é alta ou crítica; o motivo passa a citar os alertas das regras que elevaram (`prioridade_elevada_producao`, `prioridade_elevada_indisponibilidade`, `prioridade_elevada_impacto_producao`). Alternativa: manter os ramos como redundância documentada, com teste unitário direto.

**Decisão do aluno: aceita** (simplificar e explicar).
**Motivo.** Menos código para explicar no vídeo e um log de roteamento que diz exatamente por que o chamado virou crítico. A redundância "de segurança" não protegia nada, porque `definir_rota` só é chamada depois das elevações.

**Efeito.** `definir_rota(analise, chamado, prioridade_final, alertas)`; RF-43 reescrita no PRD 1.5; teste de propriedade `test_rota_critica_e_funcao_apenas_da_prioridade_final` (128 casos parametrizados) garante `rota == critico ⇔ prioridade ∈ {alta, critica}` e que o motivo cita todos os alertas; `test_motivo_da_rota_explica_a_origem` passa a exigir o nome da regra no motivo.

## 3. Termos de indisponibilidade disparam em frases legítimas

**Trecho revisado** (`regras.py`, `detectar_termos_indisponibilidade`):

```python
return [termo for termo in termos if normalizar_texto(termo) in normalizado]
```

**Problema.** Comparação por substring, sem semântica. A IA confirmou três falsos positivos: "Estarei indisponível na sexta para o treinamento do ERP" → `indisponivel`; "Vazamento de água no banheiro do 3º andar" → `vazamento`; "O ar-condicionado da sala de servidores está fora do ar" → `fora do ar`. Cada um eleva a prioridade para `alta` e manda o chamado para a rota crítica.

**Sugestão da IA.** Duas opções de correção: restringir "vazamento" a "vazamento de dados"/"vazamento de informações"; ou trocar a lista por expressões regulares com fronteira de palavra e tratamento de negação.

**Decisão do aluno: rejeitada.**
**Motivo.** O erro é na direção segura: um falso positivo só gera revisão humana a mais, enquanto um falso negativo (incidente real não elevado) é o que a regra existe para impedir. Regex com negação traria complexidade e risco de deixar passar "não está mais fora do ar… voltou a cair"; restringir "vazamento" resolveria um caso e deixaria os outros dois. A regra fica simples de explicar e a limitação fica documentada.

**Efeito.** Comentário em `TERMOS_INDISPONIBILIDADE` registrando a limitação; teste `test_termos_disparam_em_frases_legitimas_por_desenho` fixa o comportamento atual para que uma mudança futura seja consciente; RF-43 no PRD menciona a limitação.

## 4. Apelidos genéricos do catálogo resolviam frases fora do domínio

**Trecho revisado** (`data/catalogo_servicos.json` + `Catalogo.resolver`, busca por apelido contido na frase):

```json
"aliases": ["banco de dados", "banco", "database", "sql", "cluster de banco"]
"aliases": ["ad", "active directory", "dominio", "contas de usuario", "autenticacao", "login de rede"]
```

**Problema.** A IA confirmou: "O banco recusou o boleto do cliente" → `banco-dados`; "O domínio empresa.com.br expirou no registro.br" → `active-directory`; "Sem autenticação no wifi da recepção" → `active-directory`. Na rota crítica isso faria a resposta acionar a equipe errada com um runbook que não se aplica.

**Sugestão da IA.** Remover "banco", "dominio" e "autenticacao"; manter "ad" (abreviação usual de Active Directory) e a busca por frase para os apelidos específicos. Alternativas: manter e documentar o risco; desativar a busca por frase.

**Decisão do aluno: aceita** (remover os três apelidos).
**Motivo.** A busca por frase é útil ("o portal dos clientes está lento" → `portal-clientes`) e não deve ser desativada; o problema são apelidos que têm uso corrente fora de TI. "ad" fica porque "ad hoc" é raro em chamado de suporte e "AD" é como os usuários se referem ao serviço.

**Efeito.** Três apelidos removidos do JSON; teste parametrizado `test_apelidos_genericos_nao_resolvem_frases_fora_do_dominio` com as três frases; RF-22 no PRD 1.5.

## 5. Sugestões aditivas aceitas sem discussão

Aceitas pelo aluno por serem seguras e pequenas; registradas para completar o quadro.

| # | Achado | Efeito |
|---|---|---|
| 5a | `Catalogo.resolver` escolhia em silêncio o primeiro serviço quando um apelido se repetia entre dois serviços (não havia validação na carga; o catálogo atual não tem colisão). | `Catalogo.__init__` levanta `ErroCatalogoIndisponivel` apontando o par; teste `test_apelido_repetido_entre_servicos_falha_na_carga`. |
| 5b | `redigir_segredos` só redigia a chave inteira: um modelo manipulado que citasse "os 20 primeiros caracteres" vazava parte do segredo (confirmado com fragmento de 20 caracteres). | Redação de fragmentos com 12 ou mais caracteres, marcadores adjacentes fundidos; teste `test_redigir_segredos_cobre_fragmentos_da_chave`; RF-61 no PRD. |
| 5c | Testes propostos pela IA para lacunas de T5 e do catálogo. | Fronteira de 100 caracteres aceita pela tool (`test_tool_aceita_servico_no_limite_de_100_caracteres`); unicode de largura total resolvido pela normalização NFKD (`test_resolver_normaliza_unicode_de_largura_total`). |

## Resumo

| # | Sugestão | Decisão | Onde |
|---|---|---|---|
| 1 | RF-44(a) condicionada ao impacto | aceita | `regras.py`, T9, PRD RF-44, evidência `pos-qa-regras/` |
| 2 | `definir_rota` simplificada, motivo cita a regra | aceita | `regras.py`, teste de 128 combinações, PRD RF-43 |
| 3 | Termos por regex/contexto | **rejeitada** | comentário + teste que fixa a limitação |
| 4 | Remover apelidos genéricos | aceita | `catalogo_servicos.json`, `test_tool.py` |
| 5a–c | Colisão de apelidos, fragmentos de chave, testes de fronteira | aceitas | `catalogo.py`, `regras.py`, `test_tool.py`, `test_seguranca.py` |

Suíte antes da QA: 228 testes. Depois: 368 (140 novos, 128 deles do teste de propriedade). Commit das alterações: `d004bc8`. O prompt de revisão está registrado como P-037 em [`prompts.md`](prompts.md).
