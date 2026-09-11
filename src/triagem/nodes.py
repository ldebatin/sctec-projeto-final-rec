"""Nodes do grafo (seção 6.1 do PRD). Cada função tem uma responsabilidade única.

Assinatura padrão: ``node(state, runtime, detalhes)``, onde ``detalhes`` é o dicionário
anexado ao evento ``node_fim`` pelo decorator ``instrumentar``. O decorator também
acrescenta o nome do node a ``caminho_percorrido``.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from langgraph.runtime import Runtime
from pydantic import ValidationError

from triagem.contexto import ContextoExecucao
from triagem.estado import EstadoTriagem
from triagem.modelos import (
    Ambiente,
    AnaliseChamado,
    Categoria,
    Chamado,
    Prioridade,
    ResultadoCatalogo,
    ResultadoTriagem,
)
from triagem.prompts import montar_mensagens_analise
from triagem.regras import (
    MOTIVO_FALHA_TRATADA,
    MOTIVO_SEM_CONTEXTO,
    classificar_risco,
    motivos_revisao_humana,
)
from triagem.retrieval import ErroBaseConhecimento, montar_consulta, obter_base
from triagem.tools.catalogo import NOME_TOOL, ErroCatalogoIndisponivel, criar_tool_catalogo

# Nomes dos nodes (também usados nas edges e nos logs).
VALIDAR_ENTRADA = "validar_entrada"
ANALISAR_CHAMADO = "analisar_chamado"
CLASSIFICAR_RISCO = "classificar_risco"
CONSULTAR_BASE = "consultar_base"
CONSULTAR_TOOL = "consultar_tool"
GERAR_RESPOSTA = "gerar_resposta"
TRATAR_FALHA = "tratar_falha"

Node = Callable[[EstadoTriagem, Runtime[ContextoExecucao]], dict[str, Any]]
NodeInterno = Callable[[EstadoTriagem, Runtime[ContextoExecucao], dict[str, Any]], dict[str, Any]]


def instrumentar(nome: str) -> Callable[[NodeInterno], Node]:
    """Registra ``node_inicio``/``node_fim`` (com duração) e acumula ``caminho_percorrido``."""

    def decorador(fn: NodeInterno) -> Node:
        def node(state: EstadoTriagem, runtime: Runtime[ContextoExecucao]) -> dict[str, Any]:
            with runtime.context.registro.medir_node(nome) as detalhes:
                saida = fn(state, runtime, detalhes)
            return {"caminho_percorrido": [nome], **saida}

        node.__name__ = nome
        node.__doc__ = fn.__doc__
        return node

    return decorador


# ---------------------------------------------------------------------------


@instrumentar(VALIDAR_ENTRADA)
def validar_entrada(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Valida ``entrada_bruta`` com Pydantic (RF-02). Falha vira ``erros``; a edge decide."""
    bruto = state.get("entrada_bruta")
    if not isinstance(bruto, dict):
        detalhes["valida"] = False
        return {
            "chamado": None,
            "erros": ["entrada_invalida: esperado um objeto com titulo e descricao"],
        }
    try:
        chamado = Chamado.model_validate(bruto)
    except ValidationError as exc:
        erros = [
            "entrada_invalida: " + ".".join(str(p) for p in e["loc"]) + ": " + e["msg"]
            for e in exc.errors()
        ]
        detalhes["valida"] = False
        detalhes["erros"] = len(erros)
        return {"chamado": None, "erros": erros}
    detalhes["valida"] = True
    return {"chamado": chamado}


@instrumentar(ANALISAR_CHAMADO)
def analisar_chamado(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Chama o LLM com saída estruturada.

    Falha registra o erro e deixa ``analise`` vazia para a edge decidir o retry.
    """
    ctx = runtime.context
    chamado = state["chamado"]
    assert chamado is not None  # garantido pela edge anterior
    tentativa = state.get("tentativas_llm", 0) + 1
    detalhes["tentativa"] = tentativa

    inicio = time.perf_counter()
    try:
        analise = ctx.llm.with_structured_output(AnaliseChamado).invoke(
            montar_mensagens_analise(chamado)
        )
        if not isinstance(analise, AnaliseChamado):
            analise = AnaliseChamado.model_validate(analise)
    except Exception as exc:  # timeout, quota, schema inválido: tudo vira retry controlado
        duracao = (time.perf_counter() - inicio) * 1000
        erro = f"{type(exc).__name__}: {exc}"
        ctx.registro.llm_chamada(
            ANALISAR_CHAMADO, ctx.cfg.nome_modelo, tentativa, duracao, sucesso=False, erro=erro
        )
        detalhes["sucesso"] = False
        return {
            "analise": None,
            "tentativas_llm": tentativa,
            "erros": [f"analise_falhou (tentativa {tentativa}): {erro}"],
        }

    duracao = (time.perf_counter() - inicio) * 1000
    ctx.registro.llm_chamada(
        ANALISAR_CHAMADO, ctx.cfg.nome_modelo, tentativa, duracao, sucesso=True
    )
    detalhes["sucesso"] = True
    detalhes["categoria"] = analise.categoria.value
    detalhes["prioridade_sugerida"] = analise.prioridade_sugerida.value
    detalhes["confianca"] = analise.confianca
    return {"analise": analise, "tentativas_llm": tentativa}


@instrumentar(CLASSIFICAR_RISCO)
def classificar_risco_node(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Aplica as regras determinísticas (RF-43 a RF-45). Nenhuma chamada de LLM."""
    analise, chamado = state["analise"], state["chamado"]
    assert analise is not None and chamado is not None
    classificacao = classificar_risco(analise, chamado)
    detalhes.update(
        rota=classificacao.rota,
        prioridade=classificacao.prioridade.value,
        termos=list(classificacao.termos_encontrados),
    )
    return {
        "rota": classificacao.rota,
        "motivo_rota": classificacao.motivo,
        "prioridade_final": classificacao.prioridade,
        "alertas": list(classificacao.alertas),
    }


@instrumentar(CONSULTAR_BASE)
def consultar_base(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Recupera até 3 artigos da base de conhecimento por BM25 (RF-31).

    Base ausente ou ilegível não interrompe o fluxo: registra erro, segue sem contexto
    e sinaliza ``sem_contexto_relevante`` para a resposta ser genérica.
    """
    ctx = runtime.context
    chamado, analise = state["chamado"], state["analise"]
    assert chamado is not None and analise is not None
    try:
        base = ctx.base or obter_base(ctx.cfg.raiz_dados / "base_conhecimento")
    except ErroBaseConhecimento as exc:
        ctx.registro.erro(CONSULTAR_BASE, "ErroBaseConhecimento", str(exc))
        detalhes["artigos"] = []
        return {
            "contexto": [],
            "erros": [f"base_indisponivel: {exc}"],
            "alertas": [MOTIVO_SEM_CONTEXTO],
        }

    consulta = montar_consulta(chamado.titulo, chamado.descricao, analise.palavras_chave)
    artigos = base.buscar(consulta, k=3, limiar=ctx.cfg.limiar_bm25)
    detalhes["artigos"] = [{"id": a.id, "score": a.score} for a in artigos]
    detalhes["limiar"] = ctx.cfg.limiar_bm25
    saida: dict[str, Any] = {"contexto": artigos}
    if not artigos:
        saida["alertas"] = [MOTIVO_SEM_CONTEXTO]
    return saida


@instrumentar(CONSULTAR_TOOL)
def consultar_tool(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Aciona ``consultar_catalogo_servicos`` na rota crítica (RF-20 a RF-23).

    Toda falha vira ``ResultadoCatalogo.ok = False`` e um item em ``erros``; o fluxo
    segue para ``gerar_resposta``, que exigirá revisão humana (``tool_falhou``).
    """
    ctx = runtime.context
    chamado, analise = state["chamado"], state["analise"]
    assert chamado is not None and analise is not None

    servico = analise.servico_mencionado or chamado.servico
    if not servico:
        resultado = ResultadoCatalogo.falha(
            "servico_nao_identificado",
            "Nem a análise nem o chamado identificam o serviço afetado; "
            "confirme com o solicitante.",
        )
    else:
        ambiente = None if chamado.ambiente is Ambiente.NAO_INFORMADO else chamado.ambiente
        parametros = {"servico": servico, "ambiente": ambiente}
        ctx.registro.tool_chamada(
            NOME_TOOL, {"servico": servico, "ambiente": ambiente.value if ambiente else None}
        )
        tool = criar_tool_catalogo(
            ctx.cfg.raiz_dados / "catalogo_servicos.json", ctx.cfg.simular_falha_tool
        )
        try:
            resultado = tool.invoke(parametros)
        except ValidationError as exc:
            resultado = ResultadoCatalogo.falha("parametro_invalido", str(exc).splitlines()[0])
        except ErroCatalogoIndisponivel as exc:
            resultado = ResultadoCatalogo.falha("catalogo_indisponivel", str(exc))
        except Exception as exc:  # integração nunca derruba o fluxo (RF-23)
            resultado = ResultadoCatalogo.falha(
                "catalogo_indisponivel", f"{type(exc).__name__}: {exc}"
            )

    detalhes["ok"] = resultado.ok
    detalhes["servico_id"] = resultado.servico_id
    detalhes["status_atual"] = resultado.status_atual
    if not resultado.ok:
        detalhes["erro"] = resultado.erro
        ctx.registro.tool_erro(
            NOME_TOOL, resultado.erro or "desconhecido", resultado.mensagem or ""
        )
        return {
            "tool_resultado": resultado,
            "erros": [f"tool_{resultado.erro}: {resultado.mensagem}"],
        }
    return {"tool_resultado": resultado}


_ACAO_PADRAO = {
    "simples": "Seguir o procedimento padrão da categoria e responder ao solicitante.",
    "critico": (
        "Escalar imediatamente para a equipe responsável pelo serviço "
        "e acompanhar até a normalização."
    ),
}


@instrumentar(GERAR_RESPOSTA)
def gerar_resposta(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Monta ``ResultadoTriagem``. Redação com LLM e uso do contexto chegam na issue #10.

    A montagem dos campos de controle é determinística: categoria e prioridade vêm das
    regras; ``requer_revisao_humana`` vem de ``motivos_revisao_humana``.
    """
    ctx = runtime.context
    analise = state["analise"]
    assert analise is not None
    rota = state.get("rota") or "simples"
    contexto = state.get("contexto") or []
    tool = state.get("tool_resultado")

    fontes = [artigo.id for artigo in contexto]
    if tool is not None and tool.ok and tool.servico_id:
        fontes.append(tool.servico_id)

    motivos = motivos_revisao_humana(
        rota=rota,
        categoria=analise.categoria,
        confianca=analise.confianca,
        limiar_confianca=ctx.cfg.limiar_confianca,
        tool_ok=None if tool is None else tool.ok,
        alertas=state.get("alertas", []),
    )
    resultado = ResultadoTriagem(
        run_id=state["run_id"],
        categoria=analise.categoria,
        prioridade=state.get("prioridade_final") or analise.prioridade_sugerida,
        resumo=analise.resumo_tecnico,
        acao_sugerida=_ACAO_PADRAO[rota],
        requer_revisao_humana=bool(motivos),
        motivo_revisao=motivos,
        rota=rota,  # type: ignore[arg-type]
        fontes_contexto=fontes,
        tool_resultado=tool,
        alertas=list(state.get("alertas", [])),
        erros=list(state.get("erros", [])),
        caminho_percorrido=[*state.get("caminho_percorrido", []), GERAR_RESPOSTA],
        modelo=ctx.cfg.nome_modelo,
    )
    detalhes["requer_revisao_humana"] = resultado.requer_revisao_humana
    return {"resultado": resultado}


@instrumentar(TRATAR_FALHA)
def tratar_falha(
    state: EstadoTriagem, runtime: Runtime[ContextoExecucao], detalhes: dict[str, Any]
) -> dict[str, Any]:
    """Encerramento controlado: saída estruturada de fallback com revisão humana obrigatória."""
    erros = list(state.get("erros", []))
    ultimo = erros[-1] if erros else "motivo não registrado"
    detalhes["erros"] = len(erros)
    chamado = state.get("chamado")
    resumo = (
        f"Não foi possível triar automaticamente o chamado '{chamado.titulo}'."
        if chamado is not None
        else "Não foi possível triar automaticamente: entrada inválida."
    )
    resultado = ResultadoTriagem(
        run_id=state["run_id"],
        categoria=Categoria.INDEFINIDO,
        prioridade=Prioridade.MEDIA,
        resumo=resumo,
        acao_sugerida=f"Encaminhar para triagem manual. Último erro: {ultimo}",
        requer_revisao_humana=True,
        motivo_revisao=[MOTIVO_FALHA_TRATADA],
        rota="falha",
        alertas=list(state.get("alertas", [])),
        erros=erros,
        caminho_percorrido=[*state.get("caminho_percorrido", []), TRATAR_FALHA],
        modelo=runtime.context.cfg.nome_modelo,
    )
    return {"resultado": resultado}
