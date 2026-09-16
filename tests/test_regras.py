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
    PRIORIDADES_CRITICAS,
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
        # 5. média em produção para UM usuário → simples, sem elevação
        #    (revisado na QA com IA, issue #17: caso real do exemplo 01, reset de senha)
        (
            Prioridade.MEDIA,
            Ambiente.PRODUCAO,
            Impacto.USUARIO_UNICO,
            DESCRICAO_NEUTRA,
            "simples",
            Prioridade.MEDIA,
        ),
        # 5b. média em produção para uma equipe → elevada para alta → crítico
        (
            Prioridade.MEDIA,
            Ambiente.PRODUCAO,
            Impacto.EQUIPE,
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

    elevada = classificar_risco(
        analise(Prioridade.MEDIA, Impacto.EQUIPE), chamado(ambiente=Ambiente.PRODUCAO)
    )
    # O motivo cita a regra que elevou (revisão da QA com IA, issue #17).
    assert elevada.motivo == f"prioridade alta (elevada por regra: {ALERTA_ELEVADA_PRODUCAO})"
    assert elevada.alertas == (ALERTA_ELEVADA_PRODUCAO,)

    termo = classificar_risco(
        analise(Prioridade.BAIXA), chamado("Houve vazamento de dados de clientes.")
    )
    assert termo.termos_encontrados == ("vazamento",)
    assert ALERTA_ELEVADA_INDISPONIBILIDADE in termo.alertas
    assert termo.prioridade is Prioridade.ALTA
    assert ALERTA_ELEVADA_INDISPONIBILIDADE in termo.motivo

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


# --------------------------------------------------------------------------- QA com IA (issue #17)


def test_reset_de_senha_de_um_usuario_em_producao_e_rota_simples():
    """Caso real da execução com o Gemini (docs/evidencias/execucoes/prompt-v1/01_reset_senha):
    o modelo sugeriu `media` para um usuário sem contorno e a regra antiga elevava para
    `alta`, mandando um reset de senha para a rota crítica."""
    analise_gemini = analise(
        Prioridade.MEDIA,
        Impacto.USUARIO_UNICO,
        categoria=Categoria.SUPORTE,
        servico_mencionado="Active Directory",
    )
    resultado = classificar_risco(
        analise_gemini,
        chamado(
            "Tentei entrar no computador hoje cedo e a senha não funcionou. Depois de "
            "algumas tentativas apareceu a mensagem de conta bloqueada.",
            Ambiente.PRODUCAO,
            titulo="Esqueci minha senha e a conta bloqueou",
        ),
    )
    assert resultado.rota == "simples"
    assert resultado.prioridade is Prioridade.MEDIA
    assert resultado.alertas == ()


@pytest.mark.parametrize(
    ("prioridade", "ambiente", "impacto", "com_termo"),
    [(p, a, i, t) for p in Prioridade for a in Ambiente for i in Impacto for t in (False, True)],
)
def test_rota_critica_e_funcao_apenas_da_prioridade_final(prioridade, ambiente, impacto, com_termo):
    """Propriedade verificada na QA: depois das elevações de RF-44, `rota == critico` se e
    somente se a prioridade final é alta ou crítica (os ramos redundantes saíram de
    `definir_rota`)."""
    descricao = "Sistema fora do ar para a área toda." if com_termo else DESCRICAO_NEUTRA
    resultado = classificar_risco(analise(prioridade, impacto), chamado(descricao, ambiente))
    assert (resultado.rota == "critico") == (resultado.prioridade in PRIORIDADES_CRITICAS)
    if resultado.rota == "critico" and prioridade not in PRIORIDADES_CRITICAS:
        assert "elevada por regra: " in resultado.motivo
        assert all(alerta in resultado.motivo for alerta in resultado.alertas)


@pytest.mark.parametrize(
    ("frase", "termo"),
    [
        ("Estarei indisponível na sexta para o treinamento do ERP.", "indisponivel"),
        ("Vazamento de água no banheiro do 3º andar, perto do rack.", "vazamento"),
        ("O ar-condicionado da sala de servidores está fora do ar.", "fora do ar"),
    ],
)
def test_termos_disparam_em_frases_legitimas_por_desenho(frase, termo):
    """Limitação conhecida, mantida de propósito (decisão registrada em docs/qa-com-ia.md):
    a comparação é por substring, sem semântica. O erro é na direção segura (revisão
    humana a mais), e um incidente real nunca deixa de ser elevado."""
    assert detectar_termos_indisponibilidade(frase) == [termo]
    resultado = classificar_risco(analise(Prioridade.BAIXA), chamado(frase))
    assert resultado.rota == "critico" and resultado.prioridade is Prioridade.ALTA


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
