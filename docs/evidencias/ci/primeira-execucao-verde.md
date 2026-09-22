# Evidência E1 — primeira execução verde do CI

Registro gerado a partir da API do GitHub Actions logo após a execução.

| Campo | Valor |
|---|---|
| Workflow | CI (`.github/workflows/ci.yml`) |
| Execução | [#2](https://github.com/ldebatin/sctec-projeto-final-rec/actions/runs/34638572561) (id 34638572561) |
| Evento | `pull_request` — PR #22 (`issue-13-ci` → `main`) |
| Commit | `41fe588` — ci: pina versões exatas das actions (setup-uv não tem tag de major) |
| Início | 2026-09-11T19:23:29Z (UTC) |
| Conclusão | **success** |

## Jobs

### Lint, testes e build (Python 3.10) — **success** (17s)

| Etapa | Resultado | Duração |
|---|---|---|
| Checkout | success | 1s |
| Instalar uv e Python 3.10 | success | 2s |
| Instalar dependências (lock travado) | success | 2s |
| Lint (ruff check) | success | 0s |
| Formatação (ruff format --check) | success | 0s |
| Testes automatizados (exclui marcador live) | success | 4s |
| Build do pacote (sdist + wheel) | success | 0s |
| Conferir artefatos do build | success | 0s |

### Lint, testes e build (Python 3.12) — **success** (17s)

| Etapa | Resultado | Duração |
|---|---|---|
| Checkout | success | 1s |
| Instalar uv e Python 3.12 | success | 2s |
| Instalar dependências (lock travado) | success | 1s |
| Lint (ruff check) | success | 1s |
| Formatação (ruff format --check) | success | 0s |
| Testes automatizados (exclui marcador live) | success | 4s |
| Build do pacote (sdist + wheel) | success | 0s |
| Conferir artefatos do build | success | 0s |

## Histórico

- Execução anterior [#1](https://github.com/ldebatin/sctec-projeto-final-rec/actions/runs/34638475229) (commit `e9030d4`) falhou em *Set up job*: `astral-sh/setup-uv@v10` não resolve, pois a action publica apenas tags de release. Corrigido pinando `setup-uv@v10.1.0` e `checkout@v7.0.1`.

## Como reproduzir

Abrir um pull request para a `main` ou fazer push na `main`. A aba *Actions* do repositório lista todas as execuções: https://github.com/ldebatin/sctec-projeto-final-rec/actions/workflows/ci.yml
