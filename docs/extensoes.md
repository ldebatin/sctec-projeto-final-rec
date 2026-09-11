# Extensões técnicas

Duas extensões distintas do item 4.9 da especificação, escolhidas em 11/09/2026 (decisão D3 do [PRD](PRD.md)). Nenhuma delas é usada para cumprir um requisito obrigatório, portanto ambas contam integralmente como extensão.

## E1 — Pipeline de CI (GitHub Actions)

**O que é.** Workflow em [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) que valida cada alteração antes de ela chegar à `main`.

**Quando roda.** A cada `push` na `main` e a cada `pull_request` com destino à `main`. Execuções repetidas no mesmo branch cancelam a anterior (`concurrency`).

**O que executa**, em matriz com Python 3.10 e 3.12:

| Etapa | Comando | O que garante |
|---|---|---|
| Instalação | `uv sync --locked` | o `uv.lock` está em dia com o `pyproject.toml`; instalação reproduzível |
| Lint | `uv run ruff check .` | sem erros de estilo, imports ou bugs comuns (regras E, F, I, B, UP, N, W) |
| Formatação | `uv run ruff format --check .` | código formatado de forma uniforme |
| Testes | `uv run pytest -m "not live"` | suíte completa sem rede e sem chave; testes `live` ficam de fora |
| Build | `uv build` | o pacote gera sdist e wheel válidos |

**Actions pinadas por hash de commit.** As duas actions de terceiros (`actions/checkout`, `astral-sh/setup-uv`) são referenciadas pelo hash completo do commit, com a versão em comentário. Isso evita que uma tag remanejada execute código diferente do revisado (vetor conhecido de ataque de supply chain) e resolve a causa da falha da execução #1: `astral-sh/setup-uv` deixou de publicar tags de major flutuantes a partir da v8 e recomenda o pin por hash no próprio README. O [`.github/dependabot.yml`](../.github/dependabot.yml) mantém os hashes atualizados com PRs semanais.

**Por que os testes não precisam de chave.** Os nodes recebem o modelo por injeção (`executar_triagem(..., llm=...)`, via `Runtime[ContextoExecucao]` do LangGraph) e os testes usam o `FakeLLM` de `src/triagem/llm.py`. Só os testes marcados com `live` chamam o Gemini, e eles são excluídos no CI.

**Como ver a evidência.**
- Badge no topo do [README](../README.md) (visível para quem tem acesso ao repositório).
- Aba *Actions* do repositório: https://github.com/ldebatin/sctec-projeto-recuperacao/actions/workflows/ci.yml
- Registro da primeira execução verde em [`evidencias/ci/`](evidencias/ci/).

**Relação com o fluxo de trabalho.** Cada issue é desenvolvida em uma branch própria e integrada por pull request; o PR só é mergeado com o CI verde. Isso deixa no histórico uma verificação automática por alteração (critério 2 da rubrica) além da pontuação da extensão (critério 12).

## E2 — Cenário adversarial de prompt injection

_A implementar na issue #14 (Fase 4)._
