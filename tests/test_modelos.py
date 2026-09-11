"""Testes dos contratos de dados e do state (issue #2)."""

import json
import operator
from typing import get_args, get_type_hints

import pytest
from pydantic import ValidationError

from triagem.estado import CAMPOS_ACUMULADOS, EstadoTriagem
from triagem.modelos import (
    CAMPOS_MINIMOS_SAIDA,
    Ambiente,
    AnaliseChamado,
    Categoria,
    Chamado,
    Impacto,
    Prioridade,
    ResultadoCatalogo,
    ResultadoTriagem,
)

DESCRICAO_OK = "Usuário não consegue acessar o portal desde as 9h; erro 500 em todas as páginas."


# --------------------------------------------------------------------------- Chamado


def test_chamado_valido_normaliza_espacos():
    chamado = Chamado(titulo="  Portal fora do ar  ", descricao=f"  {DESCRICAO_OK}  ")
    assert chamado.titulo == "Portal fora do ar"
    assert chamado.descricao == DESCRICAO_OK
    assert chamado.ambiente is Ambiente.NAO_INFORMADO
    assert chamado.servico is None


@pytest.mark.parametrize("descricao", ["", "   ", "\n\t"])
def test_chamado_descricao_vazia_ou_so_espacos_invalida(descricao):
    with pytest.raises(ValidationError) as exc:
        Chamado(titulo="Título válido", descricao=descricao)
    assert "descricao" in str(exc.value)


def test_chamado_descricao_curta_invalida():
    with pytest.raises(ValidationError):
        Chamado(titulo="Título válido", descricao="curta demais")


def test_chamado_descricao_longa_invalida():
    with pytest.raises(ValidationError):
        Chamado(titulo="Título válido", descricao="x" * 8001)


def test_chamado_titulo_ausente_invalido():
    with pytest.raises(ValidationError) as exc:
        Chamado(descricao=DESCRICAO_OK)  # type: ignore[call-arg]
    assert "titulo" in str(exc.value)


def test_chamado_ambiente_invalido():
    with pytest.raises(ValidationError) as exc:
        Chamado(titulo="Título válido", descricao=DESCRICAO_OK, ambiente="lua")
    assert "ambiente" in str(exc.value)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Produção", Ambiente.PRODUCAO),
        ("  HOMOLOGAÇÃO ", Ambiente.HOMOLOGACAO),
        ("desenvolvimento", Ambiente.DESENVOLVIMENTO),
        ("", Ambiente.NAO_INFORMADO),
        (None, Ambiente.NAO_INFORMADO),
    ],
)
def test_chamado_ambiente_normalizado(entrada, esperado):
    chamado = Chamado(titulo="Título válido", descricao=DESCRICAO_OK, ambiente=entrada)
    assert chamado.ambiente is esperado


def test_chamado_opcionais_vazios_viram_none():
    chamado = Chamado(titulo="Título válido", descricao=DESCRICAO_OK, servico="   ", solicitante="")
    assert chamado.servico is None
    assert chamado.solicitante is None


def test_chamado_ignora_campos_extras_dos_exemplos():
    chamado = Chamado.model_validate(
        {"titulo": "Título válido", "descricao": DESCRICAO_OK, "_cenario": "fluxo simples"}
    )
    assert chamado.titulo == "Título válido"


# --------------------------------------------------------------------------- AnaliseChamado


def _analise(**extras):
    base = dict(
        categoria=Categoria.SOFTWARE,
        prioridade_sugerida=Prioridade.ALTA,
        impacto=Impacto.MULTIPLOS_USUARIOS,
        palavras_chave=["portal", "erro 500"],
        resumo_tecnico="Portal retornando erro 500 para todos os usuários.",
        confianca=0.9,
    )
    base.update(extras)
    return AnaliseChamado(**base)


@pytest.mark.parametrize("confianca", [-0.1, 1.1])
def test_analise_confianca_fora_do_intervalo(confianca):
    with pytest.raises(ValidationError):
        _analise(confianca=confianca)


def test_analise_palavras_chave_normalizadas_e_sem_duplicatas():
    analise = _analise(palavras_chave=[" portal ", "Portal", "erro  500", "", 42])
    assert analise.palavras_chave == ["portal", "erro 500"]


def test_analise_palavras_chave_vazia_invalida():
    with pytest.raises(ValidationError):
        _analise(palavras_chave=["", "  "])


def test_analise_servico_mencionado_vazio_vira_none():
    assert _analise(servico_mencionado="  ").servico_mencionado is None


# --------------------------------------------------------------------------- ResultadoCatalogo


def test_resultado_catalogo_falha_helper():
    r = ResultadoCatalogo.falha("servico_nao_encontrado", "Serviço 'xpto' não consta no catálogo.")
    assert r.ok is False
    assert r.erro == "servico_nao_encontrado"
    assert r.equipe_responsavel is None


def test_resultado_catalogo_erro_desconhecido_invalido():
    with pytest.raises(ValidationError):
        ResultadoCatalogo(ok=False, erro="erro_inventado")


# --------------------------------------------------------------------------- ResultadoTriagem


def test_resultado_triagem_json_tem_campos_minimos_da_rubrica():
    resultado = ResultadoTriagem(
        run_id="abc",
        categoria=Categoria.SUPORTE,
        prioridade=Prioridade.BAIXA,
        resumo="Usuário esqueceu a senha.",
        acao_sugerida="Orientar reset pelo portal de autoatendimento.",
        requer_revisao_humana=False,
        rota="simples",
    )
    saida = json.loads(resultado.model_dump_json())
    for campo in CAMPOS_MINIMOS_SAIDA:
        assert campo in saida
    assert saida["categoria"] == "suporte"
    assert saida["caminho_percorrido"] == []
    assert saida["tool_resultado"] is None


def test_resultado_triagem_rota_invalida():
    with pytest.raises(ValidationError):
        ResultadoTriagem(
            run_id="abc",
            categoria=Categoria.SUPORTE,
            prioridade=Prioridade.BAIXA,
            resumo="Resumo qualquer.",
            acao_sugerida="Ação qualquer.",
            requer_revisao_humana=False,
            rota="atalho",
        )


# --------------------------------------------------------------------------- EstadoTriagem


def test_estado_acumuladores_usam_reducer_de_concatenacao():
    hints = get_type_hints(EstadoTriagem, include_extras=True)
    for campo in CAMPOS_ACUMULADOS:
        metadados = get_args(hints[campo])[1:]
        assert operator.add in metadados, f"{campo} deveria acumular com operator.add"


def test_estado_campos_simples_nao_tem_reducer():
    hints = get_type_hints(EstadoTriagem, include_extras=True)
    assert get_args(hints["tentativas_llm"]) == ()
    assert hints["run_id"] is str
