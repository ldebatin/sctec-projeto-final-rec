# Agente Inteligente de Triagem de Chamados Técnicos

Agente construído com **LangGraph** que recebe um chamado técnico (título e descrição), analisa o conteúdo com um LLM, classifica o risco com regras determinísticas, consulta uma base de conhecimento ou uma tool de catálogo de serviços e devolve uma triagem estruturada com categoria, prioridade, resumo, ação sugerida e indicação de revisão humana.

Projeto avaliativo de recuperação do módulo 2 de *IA para Desenvolvedores [T1]*. O guia de implementação está em [`docs/PRD.md`](docs/PRD.md).

## Início rápido

```bash
uv sync                      # instala dependências (Python 3.12 via .python-version)
cp .env.example .env         # preencha GOOGLE_API_KEY
uv run pytest                # testes (não exigem chave)
uv run ruff check .          # lint
```

> README completo (arquitetura, cenários, evidências, extensões e limitações) será entregue na issue #18.
