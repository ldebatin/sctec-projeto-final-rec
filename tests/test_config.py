"""Testes da configuração por variáveis de ambiente (issue #3)."""

from pathlib import Path

import pytest

from triagem.config import Configuracao, ErroConfiguracao, carregar_configuracao


def test_padroes_sem_variaveis():
    cfg = carregar_configuracao(ambiente={})
    assert cfg.llm_provider == "google_genai"
    assert cfg.llm_model == "gemini-2.5-flash"
    assert cfg.nome_modelo == "google_genai:gemini-2.5-flash"
    assert cfg.max_tentativas_llm == 2
    assert cfg.llm_timeout_segundos == 30.0
    assert cfg.limiar_bm25 == 12.0
    assert cfg.limiar_confianca == 0.6
    assert cfg.log_formato == "json"
    assert cfg.simular_falha_tool is False
    assert cfg.raiz_dados == Path("data")
    assert cfg.api_key is None


def test_le_variaveis_do_mapeamento():
    cfg = carregar_configuracao(
        ambiente={
            "LLM_PROVIDER": "OpenAI",
            "LLM_MODEL": "gpt-x",
            "OPENAI_API_KEY": " chave-teste ",
            "LLM_TIMEOUT_SEGUNDOS": "12.5",
            "MAX_TENTATIVAS_LLM": "3",
            "LIMIAR_BM25": "0,8",
            "LOG_NIVEL": "debug",
            "LOG_FORMATO": "TEXTO",
            "SIMULAR_FALHA_TOOL": "1",
        }
    )
    assert cfg.llm_provider == "openai"
    assert cfg.nome_modelo == "openai:gpt-x"
    assert cfg.api_key == "chave-teste"
    assert cfg.llm_timeout_segundos == 12.5
    assert cfg.max_tentativas_llm == 3
    assert cfg.limiar_bm25 == 0.8
    assert cfg.log_nivel == "DEBUG"
    assert cfg.log_formato == "texto"
    assert cfg.simular_falha_tool is True


def test_inteiro_invalido_menciona_variavel():
    with pytest.raises(ErroConfiguracao, match="MAX_TENTATIVAS_LLM"):
        carregar_configuracao(ambiente={"MAX_TENTATIVAS_LLM": "abc"})


def test_max_tentativas_abaixo_do_minimo():
    with pytest.raises(ErroConfiguracao, match=">= 1"):
        carregar_configuracao(ambiente={"MAX_TENTATIVAS_LLM": "0"})


def test_timeout_nao_numerico():
    with pytest.raises(ErroConfiguracao, match="LLM_TIMEOUT_SEGUNDOS"):
        carregar_configuracao(ambiente={"LLM_TIMEOUT_SEGUNDOS": "trinta"})


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [("1", True), ("true", True), ("Sim", True), ("0", False), ("false", False), ("não", False)],
)
def test_booleano_aceita_variantes(bruto, esperado):
    cfg = carregar_configuracao(ambiente={"SIMULAR_FALHA_TOOL": bruto})
    assert cfg.simular_falha_tool is esperado


def test_booleano_invalido():
    with pytest.raises(ErroConfiguracao, match="SIMULAR_FALHA_TOOL"):
        carregar_configuracao(ambiente={"SIMULAR_FALHA_TOOL": "talvez"})


def test_log_formato_invalido():
    with pytest.raises(ErroConfiguracao, match="LOG_FORMATO"):
        carregar_configuracao(ambiente={"LOG_FORMATO": "xml"})


def test_exigir_chave_ausente_indica_variavel_e_arquivo():
    cfg = Configuracao(api_key=None)
    with pytest.raises(ErroConfiguracao) as exc:
        cfg.exigir_chave_api()
    mensagem = str(exc.value)
    assert "GOOGLE_API_KEY" in mensagem
    assert ".env.example" in mensagem


def test_exigir_chave_presente_devolve_valor():
    assert Configuracao(api_key="abc").exigir_chave_api() == "abc"


def test_provedor_local_nao_exige_chave():
    cfg = Configuracao(llm_provider="ollama", llm_model="llama3", api_key=None)
    assert cfg.variavel_chave is None
    assert cfg.exigir_chave_api() is None


def test_provedor_desconhecido_usa_convencao_de_nome():
    cfg = carregar_configuracao(ambiente={"LLM_PROVIDER": "acme", "ACME_API_KEY": "k"})
    assert cfg.variavel_chave == "ACME_API_KEY"
    assert cfg.api_key == "k"


def test_chave_nao_aparece_no_repr():
    assert "segredo" not in repr(Configuracao(api_key="segredo"))


def test_carrega_arquivo_env(tmp_path, monkeypatch):
    for nome in ("LLM_MODEL", "MAX_TENTATIVAS_LLM", "GOOGLE_API_KEY"):
        monkeypatch.delenv(nome, raising=False)
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=modelo-do-arquivo\nMAX_TENTATIVAS_LLM=4\nGOOGLE_API_KEY=k-arquivo\n")
    cfg = carregar_configuracao(arquivo_env=env)
    assert cfg.llm_model == "modelo-do-arquivo"
    assert cfg.max_tentativas_llm == 4
    assert cfg.api_key == "k-arquivo"


def test_arquivo_env_inexistente_nao_falha(tmp_path, monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    cfg = carregar_configuracao(arquivo_env=tmp_path / "nao-existe.env")
    assert cfg.llm_model == "gemini-2.5-flash"
