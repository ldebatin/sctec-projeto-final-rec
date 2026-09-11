"""Testes do node gerar_resposta com LLM e fallback (issue #10; T1 e T2 do PRD)."""

from tests.dados import (
    ANALISE_PORTAL,
    ANALISE_SENHA,
    CHAMADO_PORTAL,
    CHAMADO_SENHA,
    RESPOSTA_PADRAO,
)
from triagem.grafo import executar_triagem
from triagem.llm import FakeLLM
from triagem.modelos import (
    Ambiente,
    ArtigoRecuperado,
    Categoria,
    Chamado,
    Prioridade,
    RespostaLLM,
    ResultadoCatalogo,
)
from triagem.nodes import ALERTA_RESPOSTA_FALLBACK, _acao_fallback
from triagem.prompts import PROMPT_RESPOSTA_SISTEMA, formatar_contexto, montar_mensagens_resposta
from triagem.regras import MOTIVO_ROTA_CRITICA


def _conteudo(mensagens):
    return "\n".join(conteudo for _, conteudo in mensagens)


# --------------------------------------------------------------------------- T1


def test_fluxo_simples_usa_artigos_da_base_na_resposta(cfg, registro):
    """T1 do PRD: o contexto recuperado chega ao modelo e os ids aparecem em fontes_contexto."""
    fake = FakeLLM([ANALISE_SENHA, RESPOSTA_PADRAO])
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)

    assert fake.total_chamadas == 2
    chamada_resposta = fake.chamadas[1]
    assert chamada_resposta.schema == "RespostaLLM"
    prompt = _conteudo(chamada_resposta.entrada)
    assert "<contexto>" in prompt and "kb-001-reset-senha-ad" in prompt
    assert "Artigo kb-001-reset-senha-ad" in prompt
    assert "prioridade_final: baixa" in prompt and "rota: simples" in prompt

    assert resultado.resumo == RESPOSTA_PADRAO.resumo
    assert resultado.acao_sugerida == RESPOSTA_PADRAO.acao_sugerida
    assert resultado.justificativa == RESPOSTA_PADRAO.justificativa
    assert "kb-001-reset-senha-ad" in resultado.fontes_contexto
    assert ALERTA_RESPOSTA_FALLBACK not in resultado.alertas
    assert resultado.requer_revisao_humana is False

    chamadas_llm = [e for e in registro.ler_eventos() if e["evento"] == "llm_chamada"]
    assert [c["node"] for c in chamadas_llm] == ["analisar_chamado", "gerar_resposta"]
    assert all(c["sucesso"] for c in chamadas_llm)


# --------------------------------------------------------------------------- T2


def test_fluxo_critico_passa_dados_do_catalogo_ao_modelo(cfg, registro):
    """T2 do PRD: tool acionada e seus dados chegam ao prompt da resposta."""
    fake = FakeLLM([ANALISE_PORTAL, RESPOSTA_PADRAO])
    resultado = executar_triagem(CHAMADO_PORTAL, cfg=cfg, llm=fake, registro=registro)

    prompt = _conteudo(fake.chamadas[1].entrada)
    assert "Catálogo de serviços:" in prompt
    assert "Squad Portal" in prompt and "rollback" in prompt
    assert "rota: critico" in prompt and "prioridade_final: alta" in prompt
    assert "Artigo " not in prompt  # rota crítica não consulta a base

    assert resultado.tool_resultado.equipe_responsavel == "Squad Portal"
    assert resultado.fontes_contexto == ["portal-clientes"]
    assert MOTIVO_ROTA_CRITICA in resultado.motivo_revisao
    assert resultado.resumo == RESPOSTA_PADRAO.resumo


# --------------------------------------------------------------------------- fallback


def test_falha_do_llm_na_resposta_cai_no_fallback_com_contexto(cfg, registro):
    fake = FakeLLM([ANALISE_SENHA, RuntimeError("429 quota excedida")])
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)

    assert resultado.rota == "simples"
    assert resultado.resumo == ANALISE_SENHA.resumo_tecnico
    assert "kb-001-reset-senha-ad" in resultado.acao_sugerida
    assert resultado.justificativa.startswith("Artigo kb-001-reset-senha-ad")
    assert ALERTA_RESPOSTA_FALLBACK in resultado.alertas
    assert any(e.startswith("resposta_falhou: RuntimeError") for e in resultado.erros)
    assert resultado.requer_revisao_humana is False  # fallback não força revisão por si só

    chamada = [e for e in registro.ler_eventos() if e["evento"] == "llm_chamada"][-1]
    assert chamada["node"] == "gerar_resposta" and chamada["sucesso"] is False
    fim = next(
        e
        for e in registro.ler_eventos()
        if e["evento"] == "node_fim" and e["node"] == "gerar_resposta"
    )
    assert fim["fallback"] is True


def test_resposta_fora_do_schema_cai_no_fallback(cfg, registro):
    fake = FakeLLM([ANALISE_SENHA, {"resumo": "só o resumo, sem ação"}])
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)
    assert ALERTA_RESPOSTA_FALLBACK in resultado.alertas
    assert any("ValidationError" in e for e in resultado.erros)


def test_fallback_critico_com_tool_ok_cita_equipe_e_runbook(cfg, registro):
    fake = FakeLLM([ANALISE_PORTAL, TimeoutError("sem resposta")])
    resultado = executar_triagem(CHAMADO_PORTAL, cfg=cfg, llm=fake, registro=registro)
    assert resultado.acao_sugerida.startswith("1. Acionar Squad Portal")
    assert "runbook" in resultado.acao_sugerida.lower()
    assert "portal-clientes" in resultado.justificativa


def test_fallback_critico_sem_tool_orienta_triagem_manual():
    tool = ResultadoCatalogo.falha(
        "servico_nao_encontrado", "Serviço 'XPTO' não consta no catálogo."
    )
    acao, justificativa = _acao_fallback("critico", [], tool)
    assert "triagem manual" in acao
    assert "XPTO" in acao
    assert "escalonamento manual" in justificativa


def test_fallback_simples_sem_contexto_e_generico():
    acao, justificativa = _acao_fallback("simples", [], None)
    assert "Nenhum artigo relevante" in acao
    assert "genérica" in justificativa


def test_fallback_simples_lista_artigos_relacionados():
    artigos = [
        ArtigoRecuperado(id="kb-a", titulo="A", score=3.0, trecho="1. Fazer A."),
        ArtigoRecuperado(id="kb-b", titulo="B", score=2.0, trecho="1. Fazer B."),
    ]
    acao, _ = _acao_fallback("simples", artigos, None)
    assert acao.startswith("1. Seguir o procedimento do artigo kb-a")
    assert "kb-b" in acao


# --------------------------------------------------------------------------- prompt


def test_prompt_de_resposta_tem_delimitadores_e_regras_de_seguranca():
    chamado = Chamado(**CHAMADO_SENHA)
    mensagens = montar_mensagens_resposta(
        chamado, ANALISE_SENHA, "simples", Prioridade.BAIXA, [], None
    )
    assert mensagens[0][0] == "system" and mensagens[1][0] == "human"
    assert "DADO escrito por um usuário" in PROMPT_RESPOSTA_SISTEMA
    assert "APENAS" in PROMPT_RESPOSTA_SISTEMA
    humano = mensagens[1][1]
    assert "<chamado>" in humano and "</chamado>" in humano
    assert "<analise>" in humano and "<contexto>" in humano
    assert "nenhum contexto relevante encontrado" in humano


def test_formatar_contexto_com_tool_falha_e_artigos():
    tool = ResultadoCatalogo.falha("catalogo_indisponivel", "falha simulada")
    artigos = [
        ArtigoRecuperado(
            id="kb-x", titulo="X", categoria=Categoria.SUPORTE, score=1.5, trecho="1. X."
        )
    ]
    texto = formatar_contexto(artigos, tool)
    assert "consulta falhou (catalogo_indisponivel)" in texto
    assert "Artigo kb-x — X (score 1.5)" in texto


def test_formatar_contexto_inclui_observacao_de_ambiente():
    tool = ResultadoCatalogo(
        ok=True,
        servico_id="vpn",
        nome="VPN",
        equipe_responsavel="Redes",
        criticidade="media",
        status_atual="operacional",
        runbook="1. Ver.",
        contato_escalonamento="x@y",
        mensagem="O serviço não está cadastrado para o ambiente 'desenvolvimento'.",
    )
    assert "observacao: O serviço não está cadastrado" in formatar_contexto([], tool)
    assert Ambiente.DESENVOLVIMENTO.value in formatar_contexto([], tool)


def test_resposta_llm_valida_tamanhos():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RespostaLLM(resumo="curto", acao_sugerida="1. Fazer algo suficientemente longo.")
