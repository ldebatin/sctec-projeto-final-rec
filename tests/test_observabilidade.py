"""Testes do registro de execução em JSON Lines (issue #4)."""

import json
import logging

import pytest

from triagem.config import Configuracao
from triagem.observabilidade import criar_registro, gerar_run_id, resumir_eventos


@pytest.fixture
def cfg(tmp_path):
    return Configuracao(raiz_logs=tmp_path / "logs")


def test_gera_arquivo_jsonl_com_uma_linha_por_evento(cfg):
    registro = criar_registro(cfg, stderr=False)
    registro.execucao_iniciada("Portal fora do ar", origem="arquivo")
    registro.roteamento("classificar_risco", "critico", "prioridade alta")
    registro.execucao_finalizada("critico", "alta", True)
    registro.fechar()

    assert registro.caminho_arquivo is not None
    assert registro.caminho_arquivo.name == f"{registro.run_id}.jsonl"
    linhas = registro.caminho_arquivo.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 3
    eventos = [json.loads(linha) for linha in linhas]
    assert [e["evento"] for e in eventos] == [
        "execucao_iniciada",
        "roteamento",
        "execucao_finalizada",
    ]
    assert {e["run_id"] for e in eventos} == {registro.run_id}
    assert all({"timestamp", "nivel", "evento", "run_id"} <= e.keys() for e in eventos)
    assert eventos[1] == {
        **eventos[1],
        "origem": "classificar_risco",
        "decisao": "critico",
        "motivo": "prioridade alta",
    }
    assert eventos[2]["duracao_total_ms"] >= 0


def test_medir_node_registra_inicio_fim_e_duracao(cfg):
    registro = criar_registro(cfg, stderr=False)
    with registro.medir_node("analisar_chamado") as detalhes:
        detalhes["tentativa"] = 1
    registro.fechar()

    inicio, fim = registro.ler_eventos()
    assert inicio["evento"] == "node_inicio" and inicio["node"] == "analisar_chamado"
    assert fim["evento"] == "node_fim" and fim["node"] == "analisar_chamado"
    assert fim["duracao_ms"] >= 0
    assert fim["tentativa"] == 1


def test_medir_node_registra_erro_e_propaga(cfg):
    registro = criar_registro(cfg, stderr=False)
    with pytest.raises(ValueError, match="boom"):
        with registro.medir_node("consultar_tool"):
            raise ValueError("boom")
    registro.fechar()

    eventos = registro.ler_eventos()
    assert [e["evento"] for e in eventos] == ["node_inicio", "erro", "node_fim"]
    erro = eventos[1]
    assert erro["nivel"] == "ERROR"
    assert erro["node"] == "consultar_tool"
    assert erro["tipo"] == "ValueError"
    assert erro["mensagem"] == "boom"
    assert "Traceback" in erro["excecao"]


def test_helpers_de_llm_tool_e_seguranca(cfg):
    registro = criar_registro(cfg, stderr=False)
    registro.llm_chamada("analisar_chamado", "google_genai:x", 1, 12.34, False, erro="timeout")
    registro.tool_chamada("consultar_catalogo_servicos", {"servico": "portal", "ambiente": None})
    registro.tool_erro("consultar_catalogo_servicos", "servico_nao_encontrado", "xpto não existe")
    registro.alerta_seguranca("possivel_prompt_injection", ["ignore as instruções"])
    registro.fechar()

    llm, tool, tool_erro, alerta = registro.ler_eventos()
    assert llm["nivel"] == "WARNING" and llm["sucesso"] is False and llm["erro"] == "timeout"
    assert llm["duracao_ms"] == 12.3
    assert tool["parametros"] == {"servico": "portal", "ambiente": None}
    assert tool_erro["nivel"] == "WARNING" and tool_erro["erro"] == "servico_nao_encontrado"
    assert alerta["nivel"] == "WARNING" and alerta["padroes"] == ["ignore as instruções"]


def test_formato_json_no_stderr(cfg, capsys):
    registro = criar_registro(cfg, arquivo=False)
    registro.node_inicio("validar_entrada")
    registro.fechar()

    linha = capsys.readouterr().err.strip()
    evento = json.loads(linha)
    assert evento["evento"] == "node_inicio"
    assert evento["run_id"] == registro.run_id
    assert registro.caminho_arquivo is None


def test_formato_texto_no_stderr(tmp_path, capsys):
    cfg = Configuracao(raiz_logs=tmp_path, log_formato="texto")
    registro = criar_registro(cfg, arquivo=False)
    registro.roteamento("classificar_risco", "simples", "prioridade baixa")
    registro.fechar()

    linha = capsys.readouterr().err.strip()
    assert f"[{registro.run_id[:8]}]" in linha
    assert "roteamento" in linha
    assert "decisao=simples" in linha
    assert 'motivo="prioridade baixa"' in linha


def test_nivel_filtra_eventos_abaixo(cfg):
    registro = criar_registro(cfg, stderr=False)
    registro.evento("detalhe_interno", nivel=logging.DEBUG, x=1)
    registro.node_inicio("validar_entrada")
    registro.fechar()

    assert [e["evento"] for e in registro.ler_eventos()] == ["node_inicio"]


def test_run_id_explicito_e_gerado_sao_unicos(cfg):
    assert gerar_run_id() != gerar_run_id()
    registro = criar_registro(cfg, run_id="abc123", stderr=False)
    assert registro.run_id == "abc123"
    assert registro.caminho_arquivo.name == "abc123.jsonl"
    registro.fechar()


def test_fechar_libera_handlers_e_recriar_nao_duplica(cfg):
    registro = criar_registro(cfg, run_id="mesmo", stderr=False)
    registro.node_inicio("a")
    registro.fechar()
    assert registro._logger.handlers == []

    outro = criar_registro(cfg, run_id="mesmo", stderr=False)
    outro.node_inicio("b")
    outro.fechar()
    assert len(outro._logger.handlers) == 0
    # o arquivo é reaberto em modo append pelo FileHandler: 2 eventos, sem duplicatas
    assert [e["node"] for e in outro.ler_eventos()] == ["a", "b"]


def test_resumir_eventos_reconstroi_o_fluxo(cfg):
    registro = criar_registro(cfg, stderr=False)
    registro.execucao_iniciada("VPN cai", "argumentos")
    for node in ("validar_entrada", "analisar_chamado", "classificar_risco"):
        with registro.medir_node(node):
            pass
    registro.llm_chamada("analisar_chamado", "fake", 1, 1.0, True)
    registro.roteamento("classificar_risco", "critico", "ambiente producao")
    with registro.medir_node("consultar_tool"):
        registro.tool_chamada("consultar_catalogo_servicos", {"servico": "vpn"})
        registro.tool_erro("consultar_catalogo_servicos", "catalogo_indisponivel", "simulado")
    registro.alerta_seguranca("possivel_prompt_injection", ["x"])
    registro.execucao_finalizada("critico", "alta", True)
    registro.fechar()

    resumo = resumir_eventos(registro.ler_eventos())
    assert resumo["run_id"] == registro.run_id
    assert resumo["nodes"] == [
        "validar_entrada",
        "analisar_chamado",
        "classificar_risco",
        "consultar_tool",
    ]
    assert resumo["roteamentos"] == [
        {"origem": "classificar_risco", "decisao": "critico", "motivo": "ambiente producao"}
    ]
    assert resumo["tools"] == [
        {"tool": "consultar_catalogo_servicos", "parametros": {"servico": "vpn"}}
    ]
    assert resumo["chamadas_llm"] == 1
    assert resumo["erros"] == [
        {
            "node": "consultar_catalogo_servicos",
            "tipo": "catalogo_indisponivel",
            "mensagem": "simulado",
        }
    ]
    assert resumo["alertas_seguranca"] == ["possivel_prompt_injection"]
    assert resumo["duracao_total_ms"] >= 0
