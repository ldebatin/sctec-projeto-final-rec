"""Testes da fábrica de LLM e do FakeLLM (issue #3)."""

import pytest

from triagem.config import Configuracao, ErroConfiguracao
from triagem.llm import FakeLLM, ModeloLinguagem, criar_llm
from triagem.modelos import AnaliseChamado, Categoria, Impacto, Prioridade, RespostaLLM

ANALISE = AnaliseChamado(
    categoria=Categoria.SUPORTE,
    prioridade_sugerida=Prioridade.BAIXA,
    impacto=Impacto.USUARIO_UNICO,
    palavras_chave=["senha", "reset"],
    resumo_tecnico="Usuário esqueceu a senha do AD.",
    confianca=0.95,
)


def test_fake_devolve_respostas_na_ordem():
    segunda = ANALISE.model_copy(update={"confianca": 0.5})
    fake = FakeLLM([ANALISE, segunda])
    saida = fake.with_structured_output(AnaliseChamado)
    assert saida.invoke("primeira") is ANALISE
    assert saida.invoke("segunda") is segunda
    assert fake.total_chamadas == 2
    assert fake.respostas_restantes == 0


def test_fake_valida_dict_contra_o_schema():
    fake = FakeLLM([{"resumo": "Resumo do chamado.", "acao_sugerida": "Resetar a senha."}])
    resposta = fake.with_structured_output(RespostaLLM).invoke("x")
    assert isinstance(resposta, RespostaLLM)
    assert resposta.justificativa is None


def test_fake_levanta_excecao_enfileirada():
    fake = FakeLLM([TimeoutError("demorou")])
    with pytest.raises(TimeoutError, match="demorou"):
        fake.with_structured_output(AnaliseChamado).invoke("x")
    assert fake.total_chamadas == 1


def test_fake_sem_respostas_erro_explicito():
    fake = FakeLLM()
    with pytest.raises(RuntimeError, match="AnaliseChamado"):
        fake.with_structured_output(AnaliseChamado).invoke("x")


def test_fake_tipo_incompativel_erro():
    fake = FakeLLM([ANALISE])
    with pytest.raises(TypeError, match="RespostaLLM"):
        fake.with_structured_output(RespostaLLM).invoke("x")


def test_fake_padrao_repete_apos_esvaziar_fila():
    fake = FakeLLM(padrao=RuntimeError("quota"))
    saida = fake.with_structured_output(AnaliseChamado)
    for _ in range(3):
        with pytest.raises(RuntimeError, match="quota"):
            saida.invoke("x")
    assert fake.total_chamadas == 3


def test_fake_registra_schema_e_entrada():
    fake = FakeLLM([ANALISE])
    fake.with_structured_output(AnaliseChamado).invoke(["mensagem"])
    registro = fake.chamadas[0]
    assert registro.schema == "AnaliseChamado"
    assert registro.entrada == ["mensagem"]


def test_fake_satisfaz_protocolo_dos_nodes():
    assert isinstance(FakeLLM(), ModeloLinguagem)


def test_criar_llm_sem_chave_falha_rapido():
    with pytest.raises(ErroConfiguracao, match="GOOGLE_API_KEY"):
        criar_llm(Configuracao(api_key=None))


def test_criar_llm_com_chave_constroi_modelo_gemini_sem_rede():
    modelo = criar_llm(Configuracao(api_key="chave-falsa", llm_timeout_segundos=7))
    assert "GoogleGenerativeAI" in type(modelo).__name__
    assert modelo.temperature == 0
    assert modelo.max_retries == 0
    assert modelo.timeout == 7
    assert isinstance(modelo, ModeloLinguagem)
