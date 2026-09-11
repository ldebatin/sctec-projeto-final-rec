"""Grafo LangGraph da triagem (seção 6 do PRD): state, nodes, edges e condição de parada.

Fluxo (o diagrama Mermaid oficial é gerado por ``diagrama_mermaid()``):

- START → validar_entrada → [válida] analisar_chamado | [inválida] tratar_falha
- analisar_chamado → [ok] classificar_risco | [erro, tentativas < MAX] analisar_chamado
  | [erro, tentativas ≥ MAX] tratar_falha
- classificar_risco → [simples] consultar_base | [critico] consultar_tool
- consultar_base / consultar_tool → gerar_resposta → END; tratar_falha → END

O único ciclo é o retry limitado de ``analisar_chamado`` (``MAX_TENTATIVAS_LLM``);
``recursion_limit`` é a rede de segurança (decisão D7).
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from triagem.config import Configuracao
from triagem.contexto import ContextoExecucao
from triagem.estado import EstadoTriagem
from triagem.llm import ModeloLinguagem
from triagem.modelos import Categoria, Prioridade, ResultadoTriagem
from triagem.nodes import (
    ANALISAR_CHAMADO,
    CLASSIFICAR_RISCO,
    CONSULTAR_BASE,
    CONSULTAR_TOOL,
    GERAR_RESPOSTA,
    TRATAR_FALHA,
    VALIDAR_ENTRADA,
    analisar_chamado,
    classificar_risco_node,
    consultar_base,
    consultar_tool,
    gerar_resposta,
    tratar_falha,
    validar_entrada,
)
from triagem.observabilidade import RegistroExecucao, criar_registro
from triagem.regras import MOTIVO_FALHA_TRATADA
from triagem.retrieval import BaseConhecimento

# Caminho mais longo possível: validar + MAX tentativas + classificar + consulta + resposta.
# 10 cobre MAX_TENTATIVAS_LLM até 6 com folga.
LIMITE_RECURSAO = 10

ORDEM_NODES: tuple[str, ...] = (
    VALIDAR_ENTRADA,
    ANALISAR_CHAMADO,
    CLASSIFICAR_RISCO,
    CONSULTAR_BASE,
    CONSULTAR_TOOL,
    GERAR_RESPOSTA,
    TRATAR_FALHA,
)

# ---------------------------------------------------------------------------
# Funções de roteamento (edges condicionais). Cada uma registra o evento `roteamento`.
# ---------------------------------------------------------------------------


def rotear_apos_validacao(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao]
) -> Literal["analisar_chamado", "tratar_falha"]:
    registro = runtime.context.registro
    if state.get("chamado") is None:
        erros = state.get("erros", [])
        registro.roteamento(
            VALIDAR_ENTRADA, TRATAR_FALHA, erros[-1] if erros else "entrada inválida"
        )
        return TRATAR_FALHA
    registro.roteamento(VALIDAR_ENTRADA, ANALISAR_CHAMADO, "entrada válida")
    return ANALISAR_CHAMADO


def rotear_apos_analise(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao]
) -> Literal["classificar_risco", "analisar_chamado", "tratar_falha"]:
    registro, cfg = runtime.context.registro, runtime.context.cfg
    tentativas = state.get("tentativas_llm", 0)
    if state.get("analise") is not None:
        registro.roteamento(
            ANALISAR_CHAMADO, CLASSIFICAR_RISCO, f"análise ok na tentativa {tentativas}"
        )
        return CLASSIFICAR_RISCO
    if tentativas < cfg.max_tentativas_llm:
        registro.roteamento(
            ANALISAR_CHAMADO,
            ANALISAR_CHAMADO,
            f"tentativa {tentativas} falhou; nova tentativa "
            f"({tentativas + 1}/{cfg.max_tentativas_llm})",
        )
        return ANALISAR_CHAMADO
    registro.roteamento(
        ANALISAR_CHAMADO,
        TRATAR_FALHA,
        f"limite de {cfg.max_tentativas_llm} tentativas atingido (condição de parada)",
    )
    return TRATAR_FALHA


def rotear_apos_classificacao(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao]
) -> Literal["consultar_base", "consultar_tool"]:
    rota = state.get("rota")
    destino = CONSULTAR_TOOL if rota == "critico" else CONSULTAR_BASE
    runtime.context.registro.roteamento(
        CLASSIFICAR_RISCO, destino, state.get("motivo_rota") or f"rota {rota}"
    )
    return destino


# ---------------------------------------------------------------------------
# Construção e execução
# ---------------------------------------------------------------------------


def criar_grafo() -> CompiledStateGraph:
    """Monta e compila o grafo. As dependências chegam por ``context`` em cada invocação."""
    grafo = StateGraph(EstadoTriagem, context_schema=ContextoExecucao)

    grafo.add_node(VALIDAR_ENTRADA, validar_entrada)
    grafo.add_node(ANALISAR_CHAMADO, analisar_chamado)
    grafo.add_node(CLASSIFICAR_RISCO, classificar_risco_node)
    grafo.add_node(CONSULTAR_BASE, consultar_base)
    grafo.add_node(CONSULTAR_TOOL, consultar_tool)
    grafo.add_node(GERAR_RESPOSTA, gerar_resposta)
    grafo.add_node(TRATAR_FALHA, tratar_falha)

    grafo.add_edge(START, VALIDAR_ENTRADA)
    grafo.add_conditional_edges(
        VALIDAR_ENTRADA,
        rotear_apos_validacao,
        {ANALISAR_CHAMADO: ANALISAR_CHAMADO, TRATAR_FALHA: TRATAR_FALHA},
    )
    grafo.add_conditional_edges(
        ANALISAR_CHAMADO,
        rotear_apos_analise,
        {
            CLASSIFICAR_RISCO: CLASSIFICAR_RISCO,
            ANALISAR_CHAMADO: ANALISAR_CHAMADO,
            TRATAR_FALHA: TRATAR_FALHA,
        },
    )
    grafo.add_conditional_edges(
        CLASSIFICAR_RISCO,
        rotear_apos_classificacao,
        {CONSULTAR_BASE: CONSULTAR_BASE, CONSULTAR_TOOL: CONSULTAR_TOOL},
    )
    grafo.add_edge(CONSULTAR_BASE, GERAR_RESPOSTA)
    grafo.add_edge(CONSULTAR_TOOL, GERAR_RESPOSTA)
    grafo.add_edge(GERAR_RESPOSTA, END)
    grafo.add_edge(TRATAR_FALHA, END)

    return grafo.compile()


_GRAFO: CompiledStateGraph | None = None


def obter_grafo() -> CompiledStateGraph:
    """Instância compilada única do processo (a compilação é determinística)."""
    global _GRAFO
    if _GRAFO is None:
        _GRAFO = criar_grafo()
    return _GRAFO


def estado_inicial(run_id: str, entrada_bruta: Any) -> EstadoTriagem:
    return {
        "run_id": run_id,
        "entrada_bruta": entrada_bruta,
        "chamado": None,
        "analise": None,
        "tentativas_llm": 0,
        "rota": None,
        "motivo_rota": None,
        "prioridade_final": None,
        "contexto": [],
        "tool_resultado": None,
        "alertas": [],
        "erros": [],
        "caminho_percorrido": [],
        "resultado": None,
    }


def executar_triagem(
    entrada_bruta: Any,
    *,
    cfg: Configuracao,
    llm: ModeloLinguagem,
    registro: RegistroExecucao | None = None,
    base: BaseConhecimento | None = None,
    origem: str = "api",
    limite_recursao: int = LIMITE_RECURSAO,
) -> ResultadoTriagem:
    """Executa o fluxo completo para um chamado e devolve a saída estruturada.

    Nunca propaga exceções do fluxo: qualquer falha não prevista vira resultado de
    fallback com ``rota="falha"`` (encerramento controlado, RF-15).
    """
    registro = registro or criar_registro(cfg)
    titulo = entrada_bruta.get("titulo", "") if isinstance(entrada_bruta, dict) else ""
    registro.execucao_iniciada(str(titulo), origem)
    contexto = ContextoExecucao(cfg=cfg, llm=llm, registro=registro, base=base)

    try:
        final = obter_grafo().invoke(
            estado_inicial(registro.run_id, entrada_bruta),
            context=contexto,
            config={"recursion_limit": limite_recursao},
        )
        resultado = final["resultado"]
        assert resultado is not None
    except GraphRecursionError as exc:
        registro.erro("grafo", "GraphRecursionError", str(exc))
        resultado = _fallback(registro.run_id, cfg, f"GraphRecursionError: {exc}")
    except Exception as exc:  # última linha de defesa: nunca derrubar a aplicação
        registro.erro("grafo", type(exc).__name__, str(exc), exc_info=True)
        resultado = _fallback(registro.run_id, cfg, f"{type(exc).__name__}: {exc}")

    registro.execucao_finalizada(
        resultado.rota, resultado.prioridade.value, resultado.requer_revisao_humana
    )
    registro.fechar()
    return resultado


def _fallback(run_id: str, cfg: Configuracao, erro: str) -> ResultadoTriagem:
    return ResultadoTriagem(
        run_id=run_id,
        categoria=Categoria.INDEFINIDO,
        prioridade=Prioridade.MEDIA,
        resumo="Não foi possível concluir a triagem automática.",
        acao_sugerida=f"Encaminhar para triagem manual. Erro: {erro}",
        requer_revisao_humana=True,
        motivo_revisao=[MOTIVO_FALHA_TRATADA],
        rota="falha",
        erros=[erro],
        modelo=cfg.nome_modelo,
    )


def diagrama_mermaid() -> str:
    """Diagrama do grafo gerado pelo LangGraph (para README e comando ``triagem grafo``)."""
    return obter_grafo().get_graph().draw_mermaid()
