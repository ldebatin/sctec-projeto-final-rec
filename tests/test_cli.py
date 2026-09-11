"""Testes da CLI (issue #7) com o FakeLLM injetado no lugar de criar_llm."""

import json

import pytest
from typer.testing import CliRunner

from tests.dados import ANALISE_PORTAL, ANALISE_SENHA, CHAMADO_PORTAL, CHAMADO_SENHA
from triagem import cli
from triagem.config import ErroConfiguracao
from triagem.llm import FakeLLM
from triagem.modelos import CAMPOS_MINIMOS_SAIDA

runner = CliRunner()


@pytest.fixture
def ambiente_cli(tmp_path, monkeypatch):
    """Logs em pasta temporária, sem .env real e com chave falsa."""
    monkeypatch.setenv("RAIZ_LOGS", str(tmp_path / "logs"))
    monkeypatch.setenv("GOOGLE_API_KEY", "chave-teste")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def llm_falso(monkeypatch):
    fake = FakeLLM([ANALISE_SENHA])
    monkeypatch.setattr(cli, "criar_llm", lambda cfg: fake)
    return fake


def _escrever(tmp_path, nome, conteudo):
    caminho = tmp_path / nome
    caminho.write_text(
        conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False),
        encoding="utf-8",
    )
    return caminho


# --------------------------------------------------------------------------- triar


def test_triar_arquivo_json_imprime_resultado_estruturado(ambiente_cli, llm_falso):
    arquivo = _escrever(ambiente_cli, "chamado.json", CHAMADO_SENHA)
    resultado = runner.invoke(cli.app, ["triar", "--arquivo", str(arquivo), "--sem-logs"])

    assert resultado.exit_code == 0, resultado.output
    saida = json.loads(resultado.stdout)
    for campo in CAMPOS_MINIMOS_SAIDA:
        assert campo in saida
    assert saida["rota"] == "simples"
    assert saida["categoria"] == "suporte"
    assert saida["caminho_percorrido"][0] == "validar_entrada"
    assert llm_falso.total_chamadas == 1


def test_triar_argumentos_formato_texto(ambiente_cli, monkeypatch):
    monkeypatch.setattr(cli, "criar_llm", lambda cfg: FakeLLM([ANALISE_PORTAL]))
    resultado = runner.invoke(
        cli.app,
        [
            "triar",
            "--titulo", CHAMADO_PORTAL["titulo"],
            "--descricao", CHAMADO_PORTAL["descricao"],
            "--servico", "Portal de Clientes",
            "--ambiente", "producao",
            "--formato", "texto",
            "--sem-logs",
        ],
    )  # fmt: skip

    assert resultado.exit_code == 0, resultado.output
    assert "Rota: critico" in resultado.stdout
    assert "Prioridade: alta" in resultado.stdout
    assert "Revisão humana: sim (rota_critica)" in resultado.stdout
    assert (
        "Caminho: validar_entrada -> analisar_chamado -> classificar_risco -> consultar_tool"
        in (resultado.stdout)
    )


def test_triar_entrada_invalida_devolve_fallback_com_exit_0(ambiente_cli, llm_falso):
    resultado = runner.invoke(
        cli.app, ["triar", "--titulo", "Título válido", "--descricao", "   ", "--sem-logs"]
    )
    assert resultado.exit_code == 0, resultado.output
    saida = json.loads(resultado.stdout)
    assert saida["rota"] == "falha"
    assert saida["requer_revisao_humana"] is True
    assert llm_falso.total_chamadas == 0


def test_triar_json_malformado_vira_fallback(ambiente_cli, llm_falso):
    arquivo = _escrever(ambiente_cli, "quebrado.json", '{"titulo": "x", ')
    resultado = runner.invoke(cli.app, ["triar", "-a", str(arquivo), "--sem-logs"])
    assert resultado.exit_code == 0, resultado.output
    saida = json.loads(resultado.stdout)
    assert saida["rota"] == "falha"
    assert any("esperado um objeto" in erro for erro in saida["erros"])


def test_triar_sem_chave_sai_com_codigo_2(ambiente_cli, monkeypatch):
    def sem_chave(cfg):
        raise ErroConfiguracao("Variável GOOGLE_API_KEY não definida.")

    monkeypatch.setattr(cli, "criar_llm", sem_chave)
    resultado = runner.invoke(cli.app, ["triar", "--titulo", "abcde", "--descricao", "x" * 30])
    assert resultado.exit_code == 2
    assert "GOOGLE_API_KEY" in resultado.output


def test_triar_sem_entrada_e_erro_de_uso(ambiente_cli, llm_falso):
    resultado = runner.invoke(cli.app, ["triar"])
    assert resultado.exit_code == 2
    assert "--arquivo ou --titulo" in resultado.output


def test_triar_arquivo_inexistente_e_erro_de_uso(ambiente_cli, llm_falso):
    resultado = runner.invoke(cli.app, ["triar", "-a", "nao-existe.json"])
    assert resultado.exit_code == 2


def test_triar_salvar_grava_json_e_logs_em_arquivo(ambiente_cli, llm_falso):
    arquivo = _escrever(ambiente_cli, "chamado.json", CHAMADO_SENHA)
    destino = ambiente_cli / "saidas" / "resultado.json"
    resultado = runner.invoke(
        cli.app, ["triar", "-a", str(arquivo), "--salvar", str(destino), "--sem-logs"]
    )
    assert resultado.exit_code == 0, resultado.output
    gravado = json.loads(destino.read_text(encoding="utf-8"))
    assert gravado["run_id"] == json.loads(resultado.stdout)["run_id"]
    logs = list((ambiente_cli / "logs").glob("*.jsonl"))
    assert len(logs) == 1 and logs[0].stem == gravado["run_id"]
    assert f"log: {logs[0]}" in resultado.stderr


def test_triar_imprime_logs_em_stderr_por_padrao(ambiente_cli, llm_falso, monkeypatch):
    monkeypatch.setenv("LOG_FORMATO", "texto")
    resultado = runner.invoke(
        cli.app, ["triar", "-t", CHAMADO_SENHA["titulo"], "-d", CHAMADO_SENHA["descricao"]]
    )
    assert resultado.exit_code == 0, resultado.output
    assert "roteamento" in resultado.stderr
    assert "execucao_finalizada" in resultado.stderr
    json.loads(resultado.stdout)  # stdout continua sendo só o JSON


# --------------------------------------------------------------------------- exemplos e grafo


def test_exemplos_lista_arquivos_com_cenario(tmp_path):
    pasta = tmp_path / "exemplos"
    pasta.mkdir()
    _escrever(pasta, "02_b.json", {**CHAMADO_PORTAL, "_cenario": "rota crítica"})
    _escrever(pasta, "01_a.json", CHAMADO_SENHA)
    _escrever(pasta, "03_c.json", "não é json")
    resultado = runner.invoke(cli.app, ["exemplos", "--pasta", str(pasta)])
    assert resultado.exit_code == 0
    linhas = resultado.stdout.strip().splitlines()
    assert linhas[0] == "01_a.json: Esqueci minha senha do AD"
    assert linhas[1] == "02_b.json: rota crítica"
    assert linhas[2].startswith("03_c.json: (inválido")


def test_exemplos_pasta_vazia(tmp_path):
    resultado = runner.invoke(cli.app, ["exemplos", "--pasta", str(tmp_path / "nada")])
    assert resultado.exit_code == 0
    assert "Nenhum exemplo" in resultado.stdout


def test_grafo_imprime_mermaid():
    resultado = runner.invoke(cli.app, ["grafo"])
    assert resultado.exit_code == 0
    for node in ("validar_entrada", "analisar_chamado", "classificar_risco", "gerar_resposta"):
        assert node in resultado.stdout


def test_versao():
    resultado = runner.invoke(cli.app, ["versao"])
    assert resultado.exit_code == 0
    assert resultado.stdout.startswith("triagem ")
