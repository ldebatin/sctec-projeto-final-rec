"""State compartilhado do grafo LangGraph (seção 5.5 do PRD).

Campos anotados com ``operator.add`` são acumulados entre nodes (reducer de
concatenação); os demais são sobrescritos pelo último node que os devolver.
``total=False`` permite que cada node retorne apenas os campos que alterou.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from triagem.modelos import (
    AnaliseChamado,
    ArtigoRecuperado,
    Chamado,
    Prioridade,
    ResultadoCatalogo,
    ResultadoTriagem,
)


class EstadoTriagem(TypedDict, total=False):
    # Identificação e entrada
    run_id: str
    entrada_bruta: dict[str, Any]
    chamado: Chamado | None

    # Análise pelo modelo e controle do retry limitado
    analise: AnaliseChamado | None
    tentativas_llm: int

    # Decisões determinísticas
    rota: str | None
    motivo_rota: str | None
    prioridade_final: Prioridade | None

    # Contexto recuperado
    contexto: list[ArtigoRecuperado]
    tool_resultado: ResultadoCatalogo | None

    # Acumuladores (reducer de concatenação)
    alertas: Annotated[list[str], operator.add]
    erros: Annotated[list[str], operator.add]
    caminho_percorrido: Annotated[list[str], operator.add]

    # Saída
    resultado: ResultadoTriagem | None


CAMPOS_ACUMULADOS: tuple[str, ...] = ("alertas", "erros", "caminho_percorrido")
