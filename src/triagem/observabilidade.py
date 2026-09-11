"""Observabilidade: logs JSON Lines correlacionados por ``run_id`` (seção 9 do PRD; RNF-05).

Cada execução do grafo cria um ``RegistroExecucao`` com um ``run_id`` próprio.
Todos os eventos são escritos em ``logs/<run_id>.jsonl`` (sempre JSON, uma linha
por evento) e em stderr (JSON ou texto legível, conforme ``LOG_FORMATO``).
O módulo não depende do LangGraph: os nodes usam ``medir_node`` e os helpers.

Eventos padronizados (seção 9 do PRD):
``execucao_iniciada``, ``node_inicio``, ``node_fim``, ``roteamento``, ``llm_chamada``,
``tool_chamada``, ``tool_erro``, ``alerta_seguranca``, ``erro``, ``execucao_finalizada``.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from triagem.config import Configuracao

LOGGER_RAIZ = "triagem"

Evento = Literal[
    "execucao_iniciada",
    "node_inicio",
    "node_fim",
    "roteamento",
    "llm_chamada",
    "tool_chamada",
    "tool_erro",
    "alerta_seguranca",
    "erro",
    "execucao_finalizada",
]


def gerar_run_id() -> str:
    """Identificador único da execução (uuid4 em hexadecimal)."""
    return uuid.uuid4().hex


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Formatadores
# ---------------------------------------------------------------------------


class FormatadorJsonLines(logging.Formatter):
    """Uma linha JSON por evento, com campos fixos e os detalhes do evento."""

    def format(self, record: logging.LogRecord) -> str:
        linha: dict[str, Any] = {
            "timestamp": _agora_iso(),
            "run_id": getattr(record, "run_id", None),
            "nivel": record.levelname,
            "evento": getattr(record, "evento", record.getMessage()),
        }
        detalhes: Mapping[str, Any] = getattr(record, "detalhes", {}) or {}
        linha.update(detalhes)
        if record.exc_info:
            linha["excecao"] = self.formatException(record.exc_info)
        return json.dumps(linha, ensure_ascii=False, default=str)


class FormatadorTexto(logging.Formatter):
    """Formato legível para o terminal: hora, nível, run_id curto, evento e detalhes."""

    def format(self, record: logging.LogRecord) -> str:
        hora = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
        run_id = str(getattr(record, "run_id", "") or "")[:8]
        evento = getattr(record, "evento", record.getMessage())
        detalhes: Mapping[str, Any] = getattr(record, "detalhes", {}) or {}
        partes = [f"{chave}={_compacto(valor)}" for chave, valor in detalhes.items()]
        texto = f"{hora} {record.levelname:<7} [{run_id}] {evento} " + " ".join(partes)
        if record.exc_info:
            texto += "\n" + self.formatException(record.exc_info)
        return texto.rstrip()


def _compacto(valor: Any) -> str:
    if isinstance(valor, str):
        return json.dumps(valor, ensure_ascii=False) if " " in valor else valor
    return json.dumps(valor, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Registro de uma execução
# ---------------------------------------------------------------------------


@dataclass
class RegistroExecucao:
    """Logger vinculado a um ``run_id``; um por execução do grafo.

    Use ``criar_registro(cfg)`` em vez de instanciar diretamente.
    """

    run_id: str
    caminho_arquivo: Path | None
    _logger: logging.Logger = field(repr=False)
    _inicio: float = field(default_factory=time.perf_counter, repr=False)

    # ----- emissão genérica -------------------------------------------------

    def evento(
        self, nome: Evento | str, nivel: int = logging.INFO, exc_info: bool = False, **detalhes: Any
    ) -> None:
        self._logger.log(
            nivel,
            nome,
            exc_info=exc_info,
            extra={"run_id": self.run_id, "evento": nome, "detalhes": detalhes},
        )

    # ----- helpers dos eventos padronizados ---------------------------------

    def execucao_iniciada(self, titulo: str, origem: str) -> None:
        self.evento("execucao_iniciada", titulo=titulo[:80], origem=origem)

    def node_inicio(self, node: str) -> None:
        self.evento("node_inicio", node=node)

    def node_fim(self, node: str, duracao_ms: float, **detalhes: Any) -> None:
        self.evento("node_fim", node=node, duracao_ms=round(duracao_ms, 1), **detalhes)

    def roteamento(self, origem: str, decisao: str, motivo: str) -> None:
        self.evento("roteamento", origem=origem, decisao=decisao, motivo=motivo)

    def llm_chamada(
        self,
        node: str,
        modelo: str,
        tentativa: int,
        duracao_ms: float,
        sucesso: bool,
        erro: str | None = None,
    ) -> None:
        self.evento(
            "llm_chamada",
            nivel=logging.INFO if sucesso else logging.WARNING,
            node=node,
            modelo=modelo,
            tentativa=tentativa,
            duracao_ms=round(duracao_ms, 1),
            sucesso=sucesso,
            erro=erro,
        )

    def tool_chamada(self, tool: str, parametros: Mapping[str, Any]) -> None:
        self.evento("tool_chamada", tool=tool, parametros=dict(parametros))

    def tool_erro(self, tool: str, erro: str, mensagem: str) -> None:
        self.evento("tool_erro", nivel=logging.WARNING, tool=tool, erro=erro, mensagem=mensagem)

    def alerta_seguranca(self, tipo: str, padroes: list[str]) -> None:
        self.evento("alerta_seguranca", nivel=logging.WARNING, tipo=tipo, padroes=padroes)

    def erro(self, node: str, tipo: str, mensagem: str, exc_info: bool = False) -> None:
        self.evento(
            "erro", nivel=logging.ERROR, exc_info=exc_info, node=node, tipo=tipo, mensagem=mensagem
        )

    def execucao_finalizada(
        self, rota: str, prioridade: str | None, requer_revisao_humana: bool
    ) -> None:
        self.evento(
            "execucao_finalizada",
            rota=rota,
            prioridade=prioridade,
            requer_revisao_humana=requer_revisao_humana,
            duracao_total_ms=round((time.perf_counter() - self._inicio) * 1000, 1),
        )

    # ----- instrumentação de nodes ------------------------------------------

    @contextmanager
    def medir_node(self, node: str) -> Iterator[dict[str, Any]]:
        """Registra ``node_inicio``/``node_fim`` com duração; em exceção, registra ``erro``.

        O dicionário devolvido pode receber detalhes que serão anexados ao ``node_fim``.
        """
        self.node_inicio(node)
        inicio = time.perf_counter()
        detalhes: dict[str, Any] = {}
        try:
            yield detalhes
        except Exception as exc:
            self.erro(node, type(exc).__name__, str(exc), exc_info=True)
            raise
        finally:
            self.node_fim(node, (time.perf_counter() - inicio) * 1000, **detalhes)

    # ----- leitura e encerramento -------------------------------------------

    def ler_eventos(self) -> list[dict[str, Any]]:
        """Relê o arquivo JSONL desta execução (útil para testes e evidências)."""
        if self.caminho_arquivo is None or not self.caminho_arquivo.exists():
            return []
        with self.caminho_arquivo.open(encoding="utf-8") as arquivo:
            return [json.loads(linha) for linha in arquivo if linha.strip()]

    def fechar(self) -> None:
        """Descarrega e fecha os handlers. Chamar ao final da execução."""
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)


def criar_registro(
    cfg: Configuracao,
    run_id: str | None = None,
    *,
    stderr: bool = True,
    arquivo: bool = True,
) -> RegistroExecucao:
    """Cria o registro de uma execução com handlers de stderr e de arquivo JSONL."""
    run_id = run_id or gerar_run_id()
    logger = logging.getLogger(f"{LOGGER_RAIZ}.{run_id}")
    logger.setLevel(cfg.log_nivel)
    logger.propagate = False
    for handler in list(logger.handlers):  # idempotente em reexecuções no mesmo processo
        logger.removeHandler(handler)

    if stderr:
        saida = logging.StreamHandler(sys.stderr)
        saida.setFormatter(
            FormatadorJsonLines() if cfg.log_formato == "json" else FormatadorTexto()
        )
        logger.addHandler(saida)

    caminho: Path | None = None
    if arquivo:
        cfg.raiz_logs.mkdir(parents=True, exist_ok=True)
        caminho = cfg.raiz_logs / f"{run_id}.jsonl"
        em_arquivo = logging.FileHandler(caminho, encoding="utf-8")
        em_arquivo.setFormatter(FormatadorJsonLines())
        logger.addHandler(em_arquivo)

    return RegistroExecucao(run_id=run_id, caminho_arquivo=caminho, _logger=logger)


# ---------------------------------------------------------------------------
# Reconstrução do fluxo a partir do log
# ---------------------------------------------------------------------------


def resumir_eventos(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstrói o caminho da execução só com o log (critério 9 da rubrica)."""
    return {
        "run_id": next((e.get("run_id") for e in eventos if e.get("run_id")), None),
        "nodes": [e["node"] for e in eventos if e.get("evento") == "node_inicio"],
        "roteamentos": [
            {"origem": e.get("origem"), "decisao": e.get("decisao"), "motivo": e.get("motivo")}
            for e in eventos
            if e.get("evento") == "roteamento"
        ],
        "tools": [
            {"tool": e.get("tool"), "parametros": e.get("parametros")}
            for e in eventos
            if e.get("evento") == "tool_chamada"
        ],
        "chamadas_llm": sum(1 for e in eventos if e.get("evento") == "llm_chamada"),
        "erros": [
            {
                "node": e.get("node") or e.get("tool"),
                "tipo": e.get("tipo") or e.get("erro"),
                "mensagem": e.get("mensagem"),
            }
            for e in eventos
            if e.get("evento") in ("erro", "tool_erro")
        ],
        "alertas_seguranca": [
            e.get("tipo") for e in eventos if e.get("evento") == "alerta_seguranca"
        ],
        "duracao_total_ms": next(
            (
                e.get("duracao_total_ms")
                for e in eventos
                if e.get("evento") == "execucao_finalizada"
            ),
            None,
        ),
    }
