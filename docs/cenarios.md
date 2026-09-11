# Cenários de demonstração

Todos os chamados de exemplo ficam em [`data/exemplos/`](../data/exemplos/) e são listados por `uv run triagem exemplos`. Os dados são fictícios. O campo `_cenario` de cada arquivo descreve o que ele demonstra e é ignorado pela validação.

| Arquivo | O que demonstra | Rota esperada | Revisão humana |
|---|---|---|---|
| `01_reset_senha.json` | **Fluxo principal**: suporte, um usuário, `consultar_base` recupera o artigo de senha do AD | `simples` | não |
| `02_portal_fora_do_ar.json` | **Rota crítica**: software em produção para todos os usuários; `consultar_tool` traz equipe, status e runbook do Portal de Clientes | `critico` | sim (`rota_critica`) |
| `03_vpn_intermitente.json` | Infraestrutura, um usuário remoto, ambiente não informado; artigo de VPN | `simples` | não |
| `04_entrada_invalida.json` | **Cenário de falha**: descrição vazia rejeitada pela validação; saída de fallback sem exceção | `falha` | sim (`falha_tratada`) |
| `05_servico_desconhecido.json` | **Falha da tool**: serviço fora do catálogo (`servico_nao_encontrado`); fluxo segue e exige revisão | `critico` | sim (`rota_critica`, `tool_falhou`) |
| `06_prompt_injection.json` | **Extensão E2**: instrução injetada tenta rebaixar a prioridade e exfiltrar configuração; regras e detector (issue #14) neutralizam | `critico` | sim (`rota_critica`, `possivel_prompt_injection`) |
| `07_fora_do_dominio.json` | Pedido não técnico: `categoria = indefinido`, confiança baixa | `simples` | sim (`categoria_indefinida`) |

A rota efetiva depende da análise do modelo e das regras determinísticas de `regras.py`; a coluna "esperada" é o comportamento observado com o Gemini nos testes de referência (issue #11) e o garantido pelos testes automatizados com o `FakeLLM`.

## Como executar

```bash
uv run triagem exemplos                                        # lista os arquivos
uv run triagem triar --arquivo data/exemplos/01_reset_senha.json
uv run triagem triar --arquivo data/exemplos/02_portal_fora_do_ar.json --formato texto
```

Cada execução grava `logs/<run_id>.jsonl` e imprime o caminho em stderr. Com `LOG_FORMATO=texto` no `.env`, os eventos aparecem legíveis no terminal: nodes percorridos, decisões de roteamento com motivo, chamada da tool e erros.

## Cenários de falha

| Cenário | Como reproduzir | Comportamento |
|---|---|---|
| Entrada inválida | `uv run triagem triar --arquivo data/exemplos/04_entrada_invalida.json` | `validar_entrada` → `tratar_falha`; saída estruturada com `rota = "falha"`, `erros` preenchidos, código de saída 0; o LLM não é chamado |
| JSON malformado | `echo '{"titulo": ' > /tmp/quebrado.json && uv run triagem triar --arquivo /tmp/quebrado.json` | mesmo tratamento: fallback estruturado, código 0 |
| Serviço fora do catálogo | `uv run triagem triar --arquivo data/exemplos/05_servico_desconhecido.json` | `consultar_tool` devolve `ok = false`, `erro = servico_nao_encontrado`; `gerar_resposta` pede confirmação do sistema e revisão humana |
| Catálogo indisponível (falha de integração) | `SIMULAR_FALHA_TOOL=1 uv run triagem triar --arquivo data/exemplos/02_portal_fora_do_ar.json` | a tool levanta indisponibilidade simulada; `tool_erro` no log, `erro = catalogo_indisponivel`, fluxo segue com revisão humana |
| Chave do provedor ausente | `uv run triagem triar --env /dev/null --arquivo data/exemplos/01_reset_senha.json` | falha rápida antes do grafo, mensagem cita `GOOGLE_API_KEY`, código de saída 2 |
| LLM indisponível ou fora do schema | reproduzido nos testes com `FakeLLM` (`tests/test_grafo.py::test_retry_respeita_limite_e_termina_em_tratar_falha`) | retry limitado por `MAX_TENTATIVAS_LLM`, depois `tratar_falha` |
