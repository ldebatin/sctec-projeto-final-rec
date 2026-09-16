"""Regras determinísticas da aplicação (RF-16, RF-43 a RF-45; decisão D6 do PRD).

O modelo *sugere* (categoria, prioridade, impacto, confiança); estas funções
*decidem* rota, prioridade final e necessidade de revisão humana. São funções
puras, sem I/O e sem LLM, e devolvem sempre o motivo textual usado nos logs de
roteamento, para que a decisão seja explicável.
"""

from __future__ import annotations

import re
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
# Limitação conhecida e aceita (QA com IA, issue #17): a comparação é por substring e sem
# semântica, então "estarei indisponível na sexta" ou "vazamento de água" também disparam.
# O erro é na direção segura (só gera revisão humana a mais), e a regra continua simples de
# explicar; um incidente real nunca deixa de ser elevado por causa disso.
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
    - produção + prioridade sugerida ``media`` + impacto além de um usuário → ``alta``;
    - termos de indisponibilidade no texto → pelo menos ``alta``;
    - produção + impacto amplo → pelo menos ``alta``.
    A prioridade nunca é rebaixada: o modelo pode estar certo em ser mais severo.

    Revisado em 15/09 (QA com IA, issue #17): a elevação (a) passou a exigir impacto além de
    ``usuario_unico``. Antes, um reset de senha de um usuário em produção virava rota crítica
    (evidência real: ``docs/evidencias/execucoes/prompt-v1/01_reset_senha.json``).
    """
    prioridade = analise.prioridade_sugerida
    alertas: list[str] = []
    em_producao = chamado.ambiente is Ambiente.PRODUCAO

    if (
        em_producao
        and prioridade is Prioridade.MEDIA
        and analise.impacto is not Impacto.USUARIO_UNICO
    ):
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
    alertas: Sequence[str] = (),
) -> tuple[RotaDecidida, str]:
    """Rota ``critico`` ou ``simples`` com o motivo (RF-43).

    Depois de ``ajustar_prioridade``, a rota é função apenas da prioridade final: as
    condições "produção com impacto amplo" e "termos de indisponibilidade" já elevaram a
    prioridade para pelo menos ``alta`` (RF-44 b e c). Revisado em 15/09 (QA com IA, issue
    #17): os dois ramos que repetiam essas condições aqui eram inalcançáveis via
    ``classificar_risco`` (128 combinações verificadas) e foram removidos; em troca, o
    motivo passa a citar a regra que elevou, para o log de roteamento ser explicável.
    """
    if prioridade_final in PRIORIDADES_CRITICAS:
        if analise.prioridade_sugerida in PRIORIDADES_CRITICAS:
            return "critico", f"prioridade {prioridade_final.value} (sugerida pelo modelo)"
        regras = ", ".join(alertas) if alertas else "regra da aplicação"
        return "critico", f"prioridade {prioridade_final.value} (elevada por regra: {regras})"
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
    rota, motivo = definir_rota(analise, chamado, prioridade, alertas)
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


# ---------------------------------------------------------------------------
# Entrada não confiável: prompt injection (RF-60, RF-61; extensão E2)
# ---------------------------------------------------------------------------

# Padrões comparados sobre o texto normalizado (minúsculas, sem acento). Cada entrada é
# (rótulo, regex). Os rótulos aparecem no log `alerta_seguranca` e nos testes.
PADROES_INJECAO: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (rotulo, re.compile(regex))
    for rotulo, regex in (
        (
            "ignorar_instrucoes",
            r"\b(ignore|ignorar|desconsidere|esqueca)\b.{0,40}\binstru(coes|cao)\b",
        ),
        (
            "ignore_previous_instructions",
            r"\bignore\b.{0,30}\b(previous|prior|above|all)\b.{0,20}\binstructions?\b",
        ),
        (
            "system_prompt",
            r"\b(system prompt|prompt do sistema|suas instrucoes|your instructions)\b",
        ),
        (
            "mudanca_de_papel",
            r"\b(voce agora e|a partir de agora voce|you are now|act as|aja como|finja ser)\b",
        ),
        (
            "exfiltracao_de_segredo",
            r"\b(revele|mostre|exiba|imprima|inclua|liste|print|reveal|show)\b.{0,60}"
            r"\b(chave|senha|token|api[_ ]?key|variavel|segredo|credencia(l|is)|secret)\b",
        ),
        (
            "instrucao_ao_triador",
            r"\b(para o sistema de triagem|ao sistema de triagem|para o modelo|para a ia"
            r"|para o agente)\b",
        ),
        ("forcar_classificacao", r"\bclassifique\b.{0,40}\bcomo\b"),
        ("forcar_formato", r"\bresponda (apenas|somente|so) com\b"),
        ("sem_revisao", r"\bsem revisao humana\b"),
        ("jailbreak", r"\b(jailbreak|developer mode|modo desenvolvedor|dan mode)\b"),
    )
)

ALERTA_INJECAO = MOTIVO_INJECAO  # mesmo rótulo em `alertas` e em `motivo_revisao`
ALERTA_SEGREDO_REDIGIDO = "segredo_redigido"


def detectar_injecao(texto: str) -> list[str]:
    """Rótulos dos padrões de instrução injetada encontrados no texto (RF-60).

    Detector determinístico e conservador: serve para sinalizar e forçar revisão humana,
    não para bloquear o chamado. O conteúdo continua sendo triado como dado.
    """
    normalizado = normalizar_texto(texto)
    return [rotulo for rotulo, padrao in PADROES_INJECAO if padrao.search(normalizado)]


_FRAGMENTO_MINIMO_SEGREDO = 12


def redigir_segredos(texto: str, segredos: Iterable[str | None]) -> tuple[str, bool]:
    """Substitui por ``[REDIGIDO]`` ocorrências literais de segredos (ex.: a chave de API) ou de
    fragmentos deles com pelo menos 12 caracteres.

    Revisado em 15/09 (QA com IA, issue #17): antes só a chave inteira era redigida, e um
    modelo manipulado que citasse "os 20 primeiros caracteres" vazava parte do segredo.
    Fragmentos são varridos do maior para o menor; marcadores adjacentes são fundidos.
    """
    redigido = False
    for segredo in segredos:
        if not segredo or len(segredo) < 8:
            continue
        if segredo in texto:
            texto = texto.replace(segredo, "[REDIGIDO]")
            redigido = True
            continue
        for tamanho in range(len(segredo) - 1, _FRAGMENTO_MINIMO_SEGREDO - 1, -1):
            for inicio in range(len(segredo) - tamanho + 1):
                fragmento = segredo[inicio : inicio + tamanho]
                if fragmento in texto:
                    texto = texto.replace(fragmento, "[REDIGIDO]")
                    redigido = True
    while "[REDIGIDO][REDIGIDO]" in texto:
        texto = texto.replace("[REDIGIDO][REDIGIDO]", "[REDIGIDO]")
    return texto, redigido
