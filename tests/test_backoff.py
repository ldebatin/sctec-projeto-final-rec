"""Backoff em erro de quota antes de nova tentativa (issue #11, RNF-03)."""

import pytest

from tests.dados import ANALISE_SENHA, CHAMADO_SENHA, RESPOSTA_PADRAO
from triagem import nodes
from triagem.config import carregar_configuracao
from triagem.grafo import executar_triagem
from triagem.llm import FakeLLM
from triagem.nodes import calcular_backoff, e_erro_de_quota


@pytest.fixture
def esperas(monkeypatch):
    registradas: list[float] = []
    monkeypatch.setattr(nodes, "_dormir", registradas.append)
    return registradas


class ResourceExhausted(Exception):
    pass


@pytest.mark.parametrize(
    ("exc", "esperado"),
    [
        (RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"), True),
        (ResourceExhausted("limite atingido"), True),
        (RuntimeError("Rate limit reached"), True),
        (TimeoutError("sem resposta"), False),
        (ValueError("schema inválido"), False),
    ],
)
def test_reconhece_erro_de_quota(exc, esperado):
    assert e_erro_de_quota(exc) is esperado


def test_backoff_exponencial_limitado():
    assert calcular_backoff(2.0, 1) == 2.0
    assert calcular_backoff(2.0, 2) == 4.0
    assert calcular_backoff(2.0, 5) == 30.0
    assert calcular_backoff(0.0, 3) == 0.0


def test_quota_com_nova_tentativa_espera_e_recupera(cfg, registro, esperas):
    fake = FakeLLM([RuntimeError("429 RESOURCE_EXHAUSTED"), ANALISE_SENHA, RESPOSTA_PADRAO])
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)

    assert resultado.rota == "simples"
    assert esperas == [cfg.llm_backoff_base_segundos]
    fim = next(
        e
        for e in registro.ler_eventos()
        if e["evento"] == "node_fim" and e["node"] == "analisar_chamado" and e["tentativa"] == 1
    )
    assert fim["backoff_s"] == cfg.llm_backoff_base_segundos


def test_erro_que_nao_e_quota_nao_espera(cfg, registro, esperas):
    fake = FakeLLM([TimeoutError("sem resposta"), ANALISE_SENHA, RESPOSTA_PADRAO])
    executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)
    assert esperas == []


def test_ultima_tentativa_nao_espera(cfg, registro, esperas):
    fake = FakeLLM(padrao=RuntimeError("429 quota"))
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)
    assert resultado.rota == "falha"
    assert fake.total_chamadas == cfg.max_tentativas_llm
    assert len(esperas) == cfg.max_tentativas_llm - 1


def test_backoff_configuravel_por_ambiente():
    cfg = carregar_configuracao(ambiente={"LLM_BACKOFF_BASE_SEGUNDOS": "0,5"})
    assert cfg.llm_backoff_base_segundos == 0.5
    assert carregar_configuracao(ambiente={}).llm_backoff_base_segundos == 2.0
