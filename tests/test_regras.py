"""Testes das regras determinísticas (issue #5; teste T9 do PRD)."""

import pytest

from triagem.modelos import Ambiente, AnaliseChamado, Categoria, Chamado, Impacto, Prioridade
from triagem.regras import (
    ALERTA_ELEVADA_IMPACTO,
    ALERTA_ELEVADA_INDISPONIBILIDADE,
    ALERTA_ELEVADA_PRODUCAO,
    MOTIVO_CATEGORIA_INDEFINIDA,
    MOTIVO_CONFIANCA_BAIXA,
    MOTIVO_FALHA_TRATADA,
    MOTIVO_INJECAO,
    MOTIVO_ROTA_CRITICA,
    MOTIVO_TOOL_FALHOU,
    ajustar_prioridade,
    classificar_risco,
    detectar_termos_indisponibilidade,
    motivos_revisao_humana,
)

DESCRICAO_NEUTRA = "Usuário relata comportamento inesperado ao abrir o relatório mensal."


def chamado(
    descricao=DESCRICAO_NEUTRA, ambiente=Ambiente.NAO_INFORMADO, titulo="Problema no sistema"
):
    return Chamado(titulo=titulo, descricao=descricao, ambiente=ambiente)


def analise(prioridade=Prioridade.MEDIA, impacto=Impacto.USUARIO_UNICO, **extras):
    base = dict(
        categoria=Categoria.SOFTWARE,
        prioridade_sugerida=prioridade,
        impacto=impacto,
        palavras_chave=["relatorio"],
        resumo_tecnico="Relatório mensal não abre para um usuário.",
        confianca=0.9,
    )
    base.update(extras)
    return AnaliseChamado(**base)


# --------------------------------------------------------------------------- T9 (parametrizado)


@pytest.mark.parametrize(
    ("prioridade", "ambiente", "impacto", "descricao", "rota", "prioridade_final"),
    [
        # 1. baixa, sem produção, usuário único → simples
        (
            Prioridade.BAIXA,
            Ambiente.NAO_INFORMADO,
            Impacto.USUARIO_UNICO,
            DESCRICAO_NEUTRA,
            "simples",
            Prioridade.BAIXA,
        ),
        # 2. média em homologação → simples, sem elevação
        (
            Prioridade.MEDIA,
            Ambiente.HOMOLOGACAO,
            Impacto.EQUIPE,
            DESCRICAO_NEUTRA,
            "simples",
            Prioridade.MEDIA,
        ),
        # 3. alta sugerida → crítico
        (
            Prioridade.ALTA,
            Ambiente.NAO_INFORMADO,
            Impacto.USUARIO_UNICO,
            DESCRICAO_NEUTRA,
            "critico",
            Prioridade.ALTA,
        ),
        # 4. crítica sugerida → crítico
        (
            Prioridade.CRITICA,
            Ambiente.DESENVOLVIMENTO,
            Impacto.EQUIPE,
            DESCRICAO_NEUTRA,
            "critico",
            Prioridade.CRITICA,
        ),
        # 5. média em produção → elevada para alta → crítico
        (
            Prioridade.MEDIA,
            Ambiente.PRODUCAO,
            Impacto.USUARIO_UNICO,
            DESCRICAO_NEUTRA,
            "critico",
            Prioridade.ALTA,
        ),
        # 6. baixa em produção com impacto amplo → alta → crítico
        (
            Prioridade.BAIXA,
            Ambiente.PRODUCAO,
            Impacto.MULTIPLOS_USUARIOS,
            DESCRICAO_NEUTRA,
            "critico",
            Prioridade.ALTA,
        ),
        # 7. baixa em produção, usuário único → simples (sem gatilho)
        (
            Prioridade.BAIXA,
            Ambiente.PRODUCAO,
            Impacto.USUARIO_UNICO,
            DESCRICAO_NEUTRA,
            "simples",
            Prioridade.BAIXA,
        ),
        # 8. termo de indisponibilidade eleva baixa para alta → crítico
        (
            Prioridade.BAIXA,
            Ambiente.NAO_INFORMADO,
            Impacto.USUARIO_UNICO,
            "O portal está FORA DO AR desde cedo.",
            "critico",
            Prioridade.ALTA,
        ),
        # 9. termo com acento é reconhecido
        (
            Prioridade.MEDIA,
            Ambiente.HOMOLOGACAO,
            Impacto.EQUIPE,
            "Serviço indisponível para a equipe.",
            "critico",
            Prioridade.ALTA,
        ),
        # 10. impacto amplo fora de produção, sem termo → simples
        (
            Prioridade.MEDIA,
            Ambiente.DESENVOLVIMENTO,
            Impacto.TODA_ORGANIZACAO,
            DESCRICAO_NEUTRA,
            "simples",
            Prioridade.MEDIA,
        ),
        # 11. "não acessa" de um usuário não é gatilho (falso positivo evitado)
        (
            Prioridade.BAIXA,
            Ambiente.PRODUCAO,
            Impacto.USUARIO_UNICO,
            "Usuário não acessa a pasta compartilhada da área.",
            "simples",
            Prioridade.BAIXA,
        ),
    ],
)
def test_classificar_risco_combinacoes(
    prioridade, ambiente, impacto, descricao, rota, prioridade_final
):
    resultado = classificar_risco(analise(prioridade, impacto), chamado(descricao, ambiente))
    assert resultado.rota == rota
    assert resultado.prioridade is prioridade_final
    assert resultado.motivo


# --------------------------------------------------------------------------- motivos e alertas


def test_motivo_da_rota_explica_a_origem():
    sugerida = classificar_risco(analise(Prioridade.ALTA), chamado())
    assert "sugerida pelo modelo" in sugerida.motivo

    elevada = classificar_risco(analise(Prioridade.MEDIA), chamado(ambiente=Ambiente.PRODUCAO))
    assert "elevada por regra" in elevada.motivo
    assert elevada.alertas == (ALERTA_ELEVADA_PRODUCAO,)

    termo = classificar_risco(
        analise(Prioridade.BAIXA), chamado("Houve vazamento de dados de clientes.")
    )
    assert termo.termos_encontrados == ("vazamento",)
    assert ALERTA_ELEVADA_INDISPONIBILIDADE in termo.alertas
    assert termo.prioridade is Prioridade.ALTA

    simples = classificar_risco(analise(Prioridade.BAIXA), chamado())
    assert simples.motivo.startswith("prioridade baixa")
    assert simples.alertas == ()


def test_impacto_amplo_em_producao_eleva_e_alerta():
    prioridade, alertas = ajustar_prioridade(
        analise(Prioridade.BAIXA, Impacto.TODA_ORGANIZACAO), chamado(ambiente=Ambiente.PRODUCAO)
    )
    assert prioridade is Prioridade.ALTA
    assert alertas == [ALERTA_ELEVADA_IMPACTO]


def test_prioridade_nunca_e_rebaixada():
    prioridade, alertas = ajustar_prioridade(
        analise(Prioridade.CRITICA),
        chamado("Portal fora do ar para todos.", ambiente=Ambiente.PRODUCAO),
    )
    assert prioridade is Prioridade.CRITICA
    assert alertas == []


def test_detectar_termos_ignora_acentos_e_caixa():
    encontrados = detectar_termos_indisponibilidade(
        "SISTEMA PARADO: ninguém consegue entrar, serviço INDISPONÍVEL."
    )
    assert encontrados == ["indisponivel", "ninguem consegue", "sistema parado"]
    assert detectar_termos_indisponibilidade("tudo normal") == []


def test_termos_configuraveis():
    resultado = classificar_risco(
        analise(Prioridade.BAIXA),
        chamado("Cluster de banco degradado hoje."),
        termos=("degradado",),
    )
    assert resultado.rota == "critico"
    assert resultado.termos_encontrados == ("degradado",)


# --------------------------------------------------------------------------- revisão humana (RF-45)


def test_sem_motivos_quando_tudo_normal():
    assert (
        motivos_revisao_humana(
            rota="simples", categoria=Categoria.SUPORTE, confianca=0.9, limiar_confianca=0.6
        )
        == []
    )


def test_motivos_acumulam_em_ordem_estavel():
    motivos = motivos_revisao_humana(
        rota="critico",
        categoria=Categoria.INDEFINIDO,
        confianca=0.3,
        limiar_confianca=0.6,
        tool_ok=False,
        alertas=["prioridade_elevada_producao", MOTIVO_INJECAO],
        falha_tratada=True,
    )
    assert motivos == [
        MOTIVO_FALHA_TRATADA,
        MOTIVO_ROTA_CRITICA,
        MOTIVO_CATEGORIA_INDEFINIDA,
        MOTIVO_CONFIANCA_BAIXA,
        MOTIVO_TOOL_FALHOU,
        MOTIVO_INJECAO,
    ]


def test_tool_nao_acionada_nao_gera_motivo():
    motivos = motivos_revisao_humana(
        rota="simples",
        categoria=Categoria.SOFTWARE,
        confianca=0.8,
        limiar_confianca=0.6,
        tool_ok=None,
    )
    assert MOTIVO_TOOL_FALHOU not in motivos


def test_confianca_no_limiar_nao_gera_motivo():
    motivos = motivos_revisao_humana(
        rota="simples", categoria=Categoria.SOFTWARE, confianca=0.6, limiar_confianca=0.6
    )
    assert motivos == []
