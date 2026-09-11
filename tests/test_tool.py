"""Testes da tool consultar_catalogo_servicos (issue #9; T4 e T5 do PRD)."""

import json

import pytest
from pydantic import ValidationError

from tests.conftest import RAIZ_DADOS
from tests.dados import ANALISE_PORTAL, ANALISE_SENHA, CHAMADO_PORTAL, CHAMADO_SENHA, fake_llm
from triagem.grafo import executar_triagem
from triagem.modelos import Ambiente
from triagem.regras import MOTIVO_ROTA_CRITICA, MOTIVO_TOOL_FALHOU
from triagem.tools.catalogo import (
    NOME_TOOL,
    Catalogo,
    ErroCatalogoIndisponivel,
    consultar_catalogo,
    criar_tool_catalogo,
    obter_catalogo,
)

CAMINHO_CATALOGO = RAIZ_DADOS / "catalogo_servicos.json"


@pytest.fixture(scope="module")
def catalogo():
    return Catalogo.carregar(CAMINHO_CATALOGO)


# --------------------------------------------------------------------------- catálogo


def test_catalogo_real_tem_pelo_menos_6_servicos_e_um_degradado(catalogo):
    assert len(catalogo) >= 6
    assert any(s.status_atual == "degradado" for s in catalogo.servicos)
    ids = {s.id for s in catalogo.servicos}
    assert {"portal-clientes", "erp", "vpn", "active-directory"} <= ids
    for servico in catalogo.servicos:
        assert servico.runbook and servico.contato_escalonamento and servico.equipe_responsavel


@pytest.mark.parametrize(
    ("referencia", "esperado"),
    [
        ("portal-clientes", "portal-clientes"),
        ("Portal de Clientes", "portal-clientes"),
        ("  PORTAL WEB ", "portal-clientes"),
        ("Área do Cliente", "portal-clientes"),
        ("o portal dos clientes está lento", "portal-clientes"),
        ("VPN", "vpn"),
        ("Active Directory", "active-directory"),
        ("AD", "active-directory"),
        ("e-mail", "email-corporativo"),
    ],
)
def test_resolver_por_id_nome_alias_e_frase(catalogo, referencia, esperado):
    servico = catalogo.resolver(referencia)
    assert servico is not None and servico.id == esperado


def test_resolver_prefere_alias_mais_longo(catalogo):
    # "cliente vpn" (alias da VPN) contém "vpn"; ambos são da VPN, mas o teste garante
    # que uma frase com dois apelidos de serviços diferentes escolhe o mais específico.
    servico = catalogo.resolver("erro no gateway de pagamento do portal")
    assert servico is not None and servico.id == "api-pagamentos"


def test_resolver_desconhecido_e_vazio(catalogo):
    assert catalogo.resolver("Sistema XPTO") is None
    assert catalogo.resolver("   ") is None


def test_obter_catalogo_e_cacheado():
    assert obter_catalogo(CAMINHO_CATALOGO) is obter_catalogo(CAMINHO_CATALOGO)


@pytest.mark.parametrize(
    ("conteudo", "trecho"),
    [
        ("{nao é json", "ilegível"),
        ('{"id": "x"}', "lista"),
        ('[{"id": "x"}]', "inválido"),
        ("[]", "sem serviços"),
    ],
)
def test_catalogo_corrompido_levanta_erro_tipado(tmp_path, conteudo, trecho):
    caminho = tmp_path / "catalogo.json"
    caminho.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ErroCatalogoIndisponivel, match=trecho):
        Catalogo.carregar(caminho)


def test_catalogo_ausente_levanta_erro_tipado(tmp_path):
    with pytest.raises(ErroCatalogoIndisponivel, match="não encontrado"):
        Catalogo.carregar(tmp_path / "nao-existe.json")


# --------------------------------------------------------------------------- lógica da consulta


def test_consulta_sucesso_devolve_dados_do_servico(catalogo):
    resultado = consultar_catalogo(catalogo, "portal", Ambiente.PRODUCAO)
    assert resultado.ok is True
    assert resultado.erro is None and resultado.mensagem is None
    assert resultado.servico_id == "portal-clientes"
    assert resultado.equipe_responsavel == "Squad Portal"
    assert resultado.status_atual == "operacional"
    assert "rollback" in resultado.runbook


def test_consulta_servico_inexistente(catalogo):
    """T4 do PRD."""
    resultado = consultar_catalogo(catalogo, "Sistema XPTO")
    assert resultado.ok is False
    assert resultado.erro == "servico_nao_encontrado"
    assert "Sistema XPTO" in resultado.mensagem
    assert resultado.equipe_responsavel is None


def test_ambiente_nao_cadastrado_gera_observacao_sem_falhar(catalogo):
    resultado = consultar_catalogo(catalogo, "vpn", Ambiente.DESENVOLVIMENTO)
    assert resultado.ok is True
    assert "desenvolvimento" in resultado.mensagem


# --------------------------------------------------------------------------- tool LangChain


def test_tool_tem_schema_inspecionavel():
    tool = criar_tool_catalogo(CAMINHO_CATALOGO)
    assert tool.name == NOME_TOOL
    assert set(tool.args) == {"servico", "ambiente"}
    assert "catálogo" in tool.description


def test_tool_invoke_devolve_resultado_tipado():
    tool = criar_tool_catalogo(CAMINHO_CATALOGO)
    resultado = tool.invoke({"servico": "ERP Corporativo", "ambiente": "producao"})
    assert resultado.ok is True and resultado.servico_id == "erp"


@pytest.mark.parametrize("servico", ["", "   ", "x" * 101])
def test_tool_valida_parametros(servico):
    """T5 do PRD: parâmetros fora do contrato são rejeitados antes de consultar."""
    tool = criar_tool_catalogo(CAMINHO_CATALOGO)
    with pytest.raises(ValidationError):
        tool.invoke({"servico": servico})


def test_tool_ambiente_invalido_rejeitado():
    tool = criar_tool_catalogo(CAMINHO_CATALOGO)
    with pytest.raises(ValidationError):
        tool.invoke({"servico": "vpn", "ambiente": "lua"})


def test_tool_com_falha_simulada_levanta_erro_tipado():
    tool = criar_tool_catalogo(CAMINHO_CATALOGO, simular_falha=True)
    with pytest.raises(ErroCatalogoIndisponivel, match="simulada"):
        tool.invoke({"servico": "vpn"})


# --------------------------------------------------------------------------- integração no grafo


def _executar(cfg, registro, chamado, analise):
    return executar_triagem(chamado, cfg=cfg, llm=fake_llm(analise), registro=registro)


def test_fluxo_critico_aciona_tool_com_sucesso(cfg, registro):
    resultado = _executar(cfg, registro, CHAMADO_PORTAL, ANALISE_PORTAL)

    assert resultado.rota == "critico"
    assert "consultar_tool" in resultado.caminho_percorrido
    tool = resultado.tool_resultado
    assert tool is not None and tool.ok is True
    assert tool.equipe_responsavel == "Squad Portal"
    assert "portal-clientes" in resultado.fontes_contexto
    assert MOTIVO_ROTA_CRITICA in resultado.motivo_revisao
    assert MOTIVO_TOOL_FALHOU not in resultado.motivo_revisao

    eventos = registro.ler_eventos()
    chamada = next(e for e in eventos if e["evento"] == "tool_chamada")
    assert chamada["tool"] == NOME_TOOL
    assert chamada["parametros"] == {"servico": "Portal de Clientes", "ambiente": "producao"}
    assert not any(e["evento"] == "tool_erro" for e in eventos)


def test_servico_nao_encontrado_no_fluxo_exige_revisao(cfg, registro):
    analise = ANALISE_PORTAL.model_copy(update={"servico_mencionado": "Sistema XPTO"})
    chamado = {**CHAMADO_PORTAL, "servico": None}
    resultado = _executar(cfg, registro, chamado, analise)

    assert resultado.tool_resultado.ok is False
    assert resultado.tool_resultado.erro == "servico_nao_encontrado"
    assert MOTIVO_TOOL_FALHOU in resultado.motivo_revisao
    assert "gerar_resposta" in resultado.caminho_percorrido
    assert any(e.startswith("tool_servico_nao_encontrado") for e in resultado.erros)
    erro = next(e for e in registro.ler_eventos() if e["evento"] == "tool_erro")
    assert erro["erro"] == "servico_nao_encontrado"


def test_servico_nao_identificado_nao_chama_a_tool(cfg, registro):
    analise = ANALISE_PORTAL.model_copy(update={"servico_mencionado": None})
    chamado = {**CHAMADO_PORTAL, "servico": None}
    resultado = _executar(cfg, registro, chamado, analise)

    assert resultado.tool_resultado.erro == "servico_nao_identificado"
    assert MOTIVO_TOOL_FALHOU in resultado.motivo_revisao
    eventos = registro.ler_eventos()
    assert not any(e["evento"] == "tool_chamada" for e in eventos)
    assert any(e["evento"] == "tool_erro" for e in eventos)


def test_catalogo_indisponivel_nao_interrompe_o_fluxo(cfg, registro, tmp_path):
    cfg_sem_catalogo = cfg.__class__(**{**cfg.__dict__, "raiz_dados": tmp_path})
    resultado = _executar(cfg_sem_catalogo, registro, CHAMADO_PORTAL, ANALISE_PORTAL)

    assert resultado.rota == "critico"
    assert resultado.tool_resultado.erro == "catalogo_indisponivel"
    assert MOTIVO_TOOL_FALHOU in resultado.motivo_revisao
    assert resultado.caminho_percorrido[-1] == "gerar_resposta"


def test_falha_simulada_por_configuracao(cfg, registro):
    cfg_falha = cfg.__class__(**{**cfg.__dict__, "simular_falha_tool": True})
    resultado = _executar(cfg_falha, registro, CHAMADO_PORTAL, ANALISE_PORTAL)

    assert resultado.tool_resultado.erro == "catalogo_indisponivel"
    assert "simulada" in resultado.tool_resultado.mensagem
    assert MOTIVO_TOOL_FALHOU in resultado.motivo_revisao


def test_rota_simples_nao_aciona_a_tool(cfg, registro):
    resultado = _executar(cfg, registro, CHAMADO_SENHA, ANALISE_SENHA)
    assert resultado.tool_resultado is None
    assert not any(e["evento"] == "tool_chamada" for e in registro.ler_eventos())


def test_catalogo_json_referenciado_pela_base_de_conhecimento(catalogo):
    """Os ids em `servicos` dos artigos existem no catálogo (coerência entre #8 e #9)."""
    from triagem.retrieval import BaseConhecimento

    ids = {s.id for s in catalogo.servicos}
    base = BaseConhecimento.carregar(RAIZ_DADOS / "base_conhecimento")
    referenciados = {sid for artigo in base.artigos for sid in artigo.servicos}
    assert referenciados <= ids, referenciados - ids
    json.loads(CAMINHO_CATALOGO.read_text(encoding="utf-8"))  # continua sendo JSON válido
