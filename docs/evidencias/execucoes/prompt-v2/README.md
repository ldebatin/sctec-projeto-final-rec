# Execuções reais com o Gemini — prompts v2 (15/09/2026)

Segunda rodada dos 7 chamados de exemplo com `google_genai:gemini-2.5-flash`, feita na issue #16 logo após escrever os prompts **v2** (`VERSAO_PROMPT_ANALISE = "v2 (2026-09-15)"`, `VERSAO_PROMPT_RESPOSTA = "v2 (2026-09-15)"`). Mesmo layout da rodada v1: `NN_nome.json` é o `ResultadoTriagem`, `NN_nome.jsonl` o log completo com e-mails e CPFs mascarados. Dados fictícios.

Diferenças de configuração em relação à rodada v1: `LIMIAR_BM25 = 12.0` (calibrado na #11) e regra RF-44(a) condicionada ao impacto (#17). A comparação v1 → v2 focada no que o prompt controla está em [`../../../refinamento-prompt.md`](../../../refinamento-prompt.md).

## Resultado por cenário

| Arquivo | Rota | Categoria | Prioridade (sugerida → final) | Impacto | Confiança | Revisão humana | Fontes de contexto | Alertas | Duração |
|---|---|---|---|---|---|---|---|---|---|
| `01_reset_senha` | simples | suporte | media → media | usuario_unico | 0.95 | não | kb-001-reset-senha-ad | — | 5.6 s |
| `02_portal_fora_do_ar` | critico | software | critica → critica | multiplos_usuarios | 0.95 | sim (rota_critica) | portal-clientes | — | 7.1 s |
| `03_vpn_intermitente` | simples | infraestrutura | media → media | usuario_unico | 0.95 | não | kb-002-vpn-nao-conecta | — | 7.5 s |
| `04_entrada_invalida` | falha | indefinido | — | — | — | sim (falha_tratada) | nenhuma | — | 0.0 s |
| `05_servico_desconhecido` | critico | software | alta → alta | equipe | 0.95 | sim (rota_critica, tool_falhou) | nenhuma | — | 4.5 s |
| `06_prompt_injection` | critico | infraestrutura | alta → alta | equipe | 0.95 | sim (rota_critica, possivel_prompt_injection) | servidor-arquivos | possivel_prompt_injection | 13.4 s |
| `07_fora_do_dominio` | simples | indefinido | baixa → baixa | usuario_unico | 0.5 | sim (categoria_indefinida, confianca_baixa) | nenhuma | sem_contexto_relevante | 4.5 s |

## Leitura

- **Todos os 7 cenários se comportam como `docs/cenarios.md` prevê**, inclusive o 01 (rota simples, `consultar_base`, artigo `kb-001`, sem revisão humana), que na rodada v1 caía em rota crítica.
- **Confiança calibrada:** 0.95 nos cinco chamados técnicos, 0.5 no pedido de férias; `confianca_baixa` passa a aparecer em `motivo_revisao` do 07. `LIMIAR_CONFIANCA = 0.6` mantido.
- **Formato:** nenhuma ação com passos colados; 01, 02, 03 e 05 vieram um passo por linha; 06 em uma linha com espaços; 07 com um único passo.
- **Sem equipe inventada:** o 07 recomenda apenas "Encaminhar para triagem manual" e a justificativa diz que o chamado não é técnico.
- **Contexto limpo:** 01 e 03 citam só o artigo correto (scores 39,6 e 46,3); 07 sai sem fontes e com `sem_contexto_relevante`.
- **Extensão E2 (06):** 6 padrões detectados antes do LLM, prioridade `alta` e categoria `infraestrutura` mantidas, chave não vazou. Esta rodada é a evidência real pendente da issue #14.
- Saída estruturada válida em 12 de 12 chamadas ao modelo; nenhuma exceção; nenhum retry.

## Como reproduzir

```bash
for n in 01_reset_senha 02_portal_fora_do_ar 03_vpn_intermitente 04_entrada_invalida 05_servico_desconhecido 06_prompt_injection 07_fora_do_dominio; do
  uv run triagem triar --arquivo data/exemplos/$n.json --salvar /tmp/$n.json --sem-logs > /dev/null
done
```
