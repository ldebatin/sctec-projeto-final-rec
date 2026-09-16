# Evidência E1 — execução do CI na `main` com o código final

Registro gerado a partir da API do GitHub Actions em 16/09/2026. Complementa a [primeira execução verde](primeira-execucao-verde.md) (11/09) mostrando o pipeline rodando sobre o código final do projeto: prompts v2, regra RF-44(a) revisada na QA com IA e 370 testes offline. As duas actions de terceiros já estão pinadas por hash de commit (issue #23).

| Campo | Valor |
|---|---|
| Workflow | CI (`.github/workflows/ci.yml`) |
| Execução | [#36](https://github.com/ldebatin/sctec-projeto-recuperacao/actions/runs/35040249724) (id 35040249724) |
| Evento | `push` na `main` (merge do PR #38, branch `issue-16-refinamento-prompt`) |
| Commit | `d377839` — feat: prompts v2 com ciclo real de refinamento e instruções do agente documentadas (#38) |
| Início | 2026-09-16T00:29:59Z (UTC) |
| Conclusão | **success** em 22 s (os dois jobs rodam em paralelo) |

## Jobs

### Lint, testes e build (Python 3.10) — **success** (16 s)

Interpretador instalado pelo uv: CPython 3.10.21.

| Etapa | Resultado | Duração | Saída relevante |
|---|---|---|---|
| Checkout | success | <1 s | |
| Instalar uv e Python 3.10 | success | 3 s | |
| Instalar dependências (lock travado) | success | 1 s | `uv sync --locked` sem alteração do `uv.lock` |
| Lint (ruff check) | success | 1 s | `All checks passed!` |
| Formatação (ruff format --check) | success | <1 s | |
| Testes automatizados (exclui marcador live) | success | 7 s | `collected 372 items / 2 deselected / 370 selected` → `370 passed, 2 deselected in 5.06s` |
| Build do pacote (sdist + wheel) | success | <1 s | `triagem_chamados-0.1.0.tar.gz`, `triagem_chamados-0.1.0-py3-none-any.whl` |
| Conferir artefatos do build | success | <1 s | |

### Lint, testes e build (Python 3.12) — **success** (18 s)

Interpretador do runner: CPython 3.12.3.

| Etapa | Resultado | Duração | Saída relevante |
|---|---|---|---|
| Checkout | success | 1 s | |
| Instalar uv e Python 3.12 | success | 3 s | |
| Instalar dependências (lock travado) | success | 1 s | |
| Lint (ruff check) | success | 1 s | `All checks passed!` |
| Formatação (ruff format --check) | success | <1 s | |
| Testes automatizados (exclui marcador live) | success | 6 s | `collected 372 items / 2 deselected / 370 selected` → `370 passed, 2 deselected in 4.12s` |
| Build do pacote (sdist + wheel) | success | <1 s | mesmos artefatos |
| Conferir artefatos do build | success | <1 s | |

Os 2 testes desmarcados são os marcados com `live` (`tests/test_live.py`), que chamam o Gemini real e ficam fora do CI por não haver chave no runner. A saída local da suíte completa, com esses 2 testes passando, está em [`../testes.txt`](../testes.txt).

## Histórico do workflow até esta execução

36 execuções entre 11/09 e 16/09/2026: **34 verdes e 2 falhas**, ambas em `pull_request` e corrigidas na própria branch antes do merge. Nenhuma execução disparada por `push` na `main` falhou.

| Execução | Branch | O que falhou | Correção |
|---|---|---|---|
| [#1](https://github.com/ldebatin/sctec-projeto-recuperacao/actions/runs/34638475229) | `issue-13-ci` | *Set up job*: `astral-sh/setup-uv@v10` não resolve (a action não publica tag de major) | execução #2 verde no commit `41fe588` (pin em tag exata; depois trocado por hash na issue #23) |
| #16 | `issue-8-base-conhecimento` | etapa *Testes automatizados* nas duas versões de Python, commit `3718d69` | execução #17 verde no commit seguinte, `4a05bed`, ainda no PR |

Isso é o comportamento esperado da extensão E1: a falha aparece no PR, antes de chegar à `main`.

## Como reproduzir

Abrir um pull request para a `main` ou fazer push na `main`. A aba *Actions* lista todas as execuções: https://github.com/ldebatin/sctec-projeto-recuperacao/actions/workflows/ci.yml. Os dados desta página vieram de `GET /repos/ldebatin/sctec-projeto-recuperacao/actions/runs/35040249724` e `/jobs`, mais os logs dos jobs.
