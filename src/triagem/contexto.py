"""Dependências injetadas em cada execução do grafo via ``Runtime[ContextoExecucao]``.

Passadas em ``grafo.invoke(..., context=ContextoExecucao(...))``. Assim o grafo é
compilado uma única vez e cada execução recebe seu próprio registro de logs e o
modelo de linguagem desejado (real ou ``FakeLLM`` nos testes).
"""

from __future__ import annotations

from dataclasses import dataclass

from triagem.config import Configuracao
from triagem.llm import ModeloLinguagem
from triagem.observabilidade import RegistroExecucao
from triagem.retrieval import BaseConhecimento


@dataclass
class ContextoExecucao:
    cfg: Configuracao
    llm: ModeloLinguagem
    registro: RegistroExecucao
    # Base de conhecimento já carregada; None = carregar de cfg.raiz_dados na primeira consulta.
    base: BaseConhecimento | None = None
