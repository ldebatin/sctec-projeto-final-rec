"""Mascaramento de dados pessoais nos logs, sem tocar na saída (issue #15, RF-70)."""

import pytest

from tests.dados import ANALISE_SENHA
from triagem.grafo import executar_triagem
from triagem.llm import FakeLLM
from triagem.modelos import RespostaLLM
from triagem.observabilidade import criar_registro, mascarar_pii


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("contato: maria.souza@empresa.exemplo", "contato: m***@empresa.exemplo"),
        ("CPF 123.456.789-09 do solicitante", "CPF ***.***.***-09 do solicitante"),
        ("cpf 12345678909 informado", "cpf ***.***.***-09 informado"),
        ("dois: a@x.com e b.c@y.org", "dois: a***@x.com e b***@y.org"),
        ("sem dados pessoais aqui", "sem dados pessoais aqui"),
        ("ramal 4100 e pedido 2026091100123", "ramal 4100 e pedido 2026091100123"),
    ],
)
def test_mascarar_pii(texto, esperado):
    assert mascarar_pii(texto) == esperado


def test_logs_mascaram_pii_em_campos_simples_e_aninhados(cfg):
    registro = criar_registro(cfg, stderr=False)
    registro.execucao_iniciada("Acesso de joao.lima@empresa.exemplo bloqueado", origem="teste")
    registro.tool_chamada(
        "tool", {"servico": "AD", "obs": "CPF 123.456.789-09", "lista": ["x@y.com"]}
    )
    registro.fechar()

    inicio, tool = registro.ler_eventos()
    assert inicio["titulo"] == "Acesso de j***@empresa.exemplo bloqueado"
    assert tool["parametros"]["obs"] == "CPF ***.***.***-09"
    assert tool["parametros"]["lista"] == ["x***@y.com"]
    assert tool["parametros"]["servico"] == "AD"


def test_saida_da_triagem_nao_e_mascarada_mas_o_log_e(cfg, registro):
    chamado = {
        "titulo": "Acesso de maria.souza@empresa.exemplo bloqueado",
        "descricao": (
            "A conta de maria.souza@empresa.exemplo (CPF 123.456.789-09) bloqueou hoje cedo."
        ),
    }
    resposta = RespostaLLM(
        resumo="Conta de maria.souza@empresa.exemplo bloqueada após senha expirar.",
        acao_sugerida="1. Confirmar identidade. 2. Resetar a senha e desbloquear a conta.",
    )
    resultado = executar_triagem(
        chamado, cfg=cfg, llm=FakeLLM([ANALISE_SENHA, resposta]), registro=registro
    )

    # saída íntegra: o atendente precisa do e-mail real
    assert "maria.souza@empresa.exemplo" in resultado.resumo
    # log mascarado: evidências podem ser publicadas
    conteudo = registro.caminho_arquivo.read_text(encoding="utf-8")
    assert "maria.souza@empresa.exemplo" not in conteudo
    assert "123.456.789-09" not in conteudo
    assert "m***@empresa.exemplo" in conteudo
