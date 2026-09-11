"""Regras determinísticas da aplicação (RF-16, RF-43 a RF-45; decisão D6 do PRD).

O modelo *sugere* (categoria, prioridade, impacto, confiança); estas funções
*decidem* rota, prioridade final e necessidade de revisão humana. São funções
puras, sem I/O e sem LLM, e devolvem sempre o motivo textual usado nos logs de
roteamento, para que a decisão seja explicável.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from triagem.modelos import (
    ORDEM_PRIORIDADE,
    Ambiente,
    AnaliseChamado,
    Categoria,
    Chamado,
    Impacto,
    Prioridade,
    normalizar_texto,
)

RotaDecidida = Literal["simples", "critico"]

# Termos que indicam indisponibilidade ampla. Comparados sem acento e em minúsculas.
# "não acessa" (citado no PRD) ficou de fora: é típico de problema de um único
# usuário (senha, permissão) e gerava rota crítica indevida.
TERMOS_INDISPONIBILIDADE: tuple[str, ...] = (
    "fora do ar",
    "indisponivel",
    "todos os usuarios",
    "ninguem consegue",
    "sistema parado",
    "queda geral",
    "perda de dados",
    "vazamento",
)

PRIORIDADES_CRITICAS: frozenset[Prioridade] = frozenset({Prioridade.ALTA, Prioridade.CRITICA})
IMPACTOS_AMPLOS: frozenset[Impacto] = frozenset(
    {Impacto.MULTIPLOS_USUARIOS, Impacto.TODA_ORGANIZACAO}
)

# Alertas emitidos pelas regras (aparecem em ResultadoTriagem.alertas).
ALERTA_ELEVADA_PRODUCAO = "prioridade_elevada_producao"
ALERTA_ELEVADA_INDISPONIBILIDADE = "prioridade_elevada_indisponibilidade"
ALERTA_ELEVADA_IMPACTO = "prioridade_elevada_impacto_producao"

# Motivos de revisão humana (aparecem em ResultadoTriagem.motivo_revisao).
MOTIVO_ROTA_CRITICA = "rota_critica"
MOTIVO_CATEGORIA_INDEFINIDA = "categoria_indefinida"
MOTIVO_CONFIANCA_BAIXA = "confianca_baixa"
MOTIVO_TOOL_FALHOU = "tool_falhou"
MOTIVO_INJECAO = "possivel_prompt_injection"
MOTIVO_FALHA_TRATADA = "falha_tratada"
MOTIVO_SEM_CONTEXTO = "sem_contexto_relevante"


@dataclass(frozen=True)
class Classificacao:
    """Resultado de ``classificar_risco``: decisão + explicação."""

    rota: RotaDecidida
    prioridade: Prioridade
    motivo: str
    alertas: tuple[str, ...] = ()
    termos_encontrados: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Blocos elementares
# ---------------------------------------------------------------------------


def detectar_termos_indisponibilidade(
    texto: str, termos: Iterable[str] = TERMOS_INDISPONIBILIDADE
) -> list[str]:
    """Devolve os termos de indisponibilidade presentes no texto (sem acento, minúsculas)."""
    normalizado = normalizar_texto(texto)
    return [termo for termo in termos if normalizar_texto(termo) in normalizado]


def _maior(a: Prioridade, b: Prioridade) -> Prioridade:
    return a if ORDEM_PRIORIDADE[a] >= ORDEM_PRIORIDADE[b] else b


def ajustar_prioridade(
    analise: AnaliseChamado,
    chamado: Chamado,
    termos_encontrados: Sequence[str] = (),
) -> tuple[Prioridade, list[str]]:
    """Prioridade final = sugerida pelo modelo, elevada por regras da aplicação (RF-44).

    Elevações (cada uma gera um alerta próprio):
    - produção + prioridade sugerida ``media`` → ``alta``;
    - termos de indisponibilidade no texto → pelo menos ``alta``;
    - produção + impacto amplo → pelo menos ``alta``.
    A prioridade nunca é rebaixada: o modelo pode estar certo em ser mais severo.
    """
    prioridade = analise.prioridade_sugerida
    alertas: list[str] = []
    em_producao = chamado.ambiente is Ambiente.PRODUCAO

    if em_producao and prioridade is Prioridade.MEDIA:
        prioridade = Prioridade.ALTA
        alertas.append(ALERTA_ELEVADA_PRODUCAO)

    if termos_encontrados and ORDEM_PRIORIDADE[prioridade] < ORDEM_PRIORIDADE[Prioridade.ALTA]:
        prioridade = _maior(prioridade, Prioridade.ALTA)
        alertas.append(ALERTA_ELEVADA_INDISPONIBILIDADE)

    if (
        em_producao
        and analise.impacto in IMPACTOS_AMPLOS
        and ORDEM_PRIORIDADE[prioridade] < ORDEM_PRIORIDADE[Prioridade.ALTA]
    ):
        prioridade = Prioridade.ALTA
        alertas.append(ALERTA_ELEVADA_IMPACTO)

    return prioridade, alertas


def definir_rota(
    analise: AnaliseChamado,
    chamado: Chamado,
    prioridade_final: Prioridade,
    termos_encontrados: Sequence[str] = (),
) -> tuple[RotaDecidida, str]:
    """Rota ``critico`` ou ``simples`` com o motivo (RF-43).

    É ``critico`` se qualquer condição valer: prioridade final alta/crítica;
    produção com impacto amplo; termos de indisponibilidade no texto.
    """
    if prioridade_final in PRIORIDADES_CRITICAS:
        origem = (
            "sugerida pelo modelo"
            if analise.prioridade_sugerida in PRIORIDADES_CRITICAS
            else "elevada por regra"
        )
        return "critico", f"prioridade {prioridade_final.value} ({origem})"
    if chamado.ambiente is Ambiente.PRODUCAO and analise.impacto in IMPACTOS_AMPLOS:
        return "critico", f"ambiente producao com impacto {analise.impacto.value}"
    if termos_encontrados:
        return "critico", "termos de indisponibilidade: " + ", ".join(termos_encontrados)
    return "simples", (
        f"prioridade {prioridade_final.value}, impacto {analise.impacto.value}, "
        f"ambiente {chamado.ambiente.value}"
    )


# ---------------------------------------------------------------------------
# Composição usada pelo node classificar_risco
# ---------------------------------------------------------------------------


def classificar_risco(
    analise: AnaliseChamado,
    chamado: Chamado,
    termos: Iterable[str] = TERMOS_INDISPONIBILIDADE,
) -> Classificacao:
    """Aplica, em ordem: detecção de termos → ajuste de prioridade → rota."""
    encontrados = detectar_termos_indisponibilidade(
        f"{chamado.titulo}\n{chamado.descricao}", termos
    )
    prioridade, alertas = ajustar_prioridade(analise, chamado, encontrados)
    rota, motivo = definir_rota(analise, chamado, prioridade, encontrados)
    return Classificacao(
        rota=rota,
        prioridade=prioridade,
        motivo=motivo,
        alertas=tuple(alertas),
        termos_encontrados=tuple(encontrados),
    )


# ---------------------------------------------------------------------------
# Revisão humana (RF-45)
# ---------------------------------------------------------------------------


def motivos_revisao_humana(
    *,
    rota: str,
    categoria: Categoria | None,
    confianca: float | None,
    limiar_confianca: float,
    tool_ok: bool | None = None,
    alertas: Iterable[str] = (),
    falha_tratada: bool = False,
) -> list[str]:
    """Lista de motivos; vazia significa que a triagem automática basta.

    ``tool_ok=None`` indica que a tool não foi acionada (rota simples).
    """
    motivos: list[str] = []
    if falha_tratada:
        motivos.append(MOTIVO_FALHA_TRATADA)
    if rota == "critico":
        motivos.append(MOTIVO_ROTA_CRITICA)
    if categoria is Categoria.INDEFINIDO:
        motivos.append(MOTIVO_CATEGORIA_INDEFINIDA)
    if confianca is not None and confianca < limiar_confianca:
        motivos.append(MOTIVO_CONFIANCA_BAIXA)
    if tool_ok is False:
        motivos.append(MOTIVO_TOOL_FALHOU)
    if MOTIVO_INJECAO in set(alertas):
        motivos.append(MOTIVO_INJECAO)
    return motivos
