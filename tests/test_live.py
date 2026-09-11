"""Teste ponta a ponta com o Gemini real (T10 do PRD).

Marcado ``live``: excluído no CI (``pytest -m "not live"``) e pulado automaticamente
quando não há chave. Rodar com ``uv run pytest -m live -v``.
"""

import json

import pytest

from tests.conftest import RAIZ_DADOS
from triagem.config import carregar_configuracao
from triagem.grafo import executar_triagem
from triagem.llm import criar_llm
from triagem.modelos import CAMPOS_MINIMOS_SAIDA
from triagem.observabilidade import criar_registro

pytestmark = pytest.mark.live

CFG = carregar_configuracao(RAIZ_DADOS.parent / ".env")
SEM_CHAVE = not CFG.api_key


@pytest.fixture(scope="module")
def llm():
    if SEM_CHAVE:
        pytest.skip("GOOGLE_API_KEY não definida; teste live pulado")
    return criar_llm(CFG)


def _exemplo(nome):
    return json.loads((RAIZ_DADOS / "exemplos" / nome).read_text(encoding="utf-8"))


def test_live_fluxo_simples_ponta_a_ponta(llm, tmp_path):
    cfg = CFG.__class__(**{**CFG.__dict__, "raiz_logs": tmp_path, "raiz_dados": RAIZ_DADOS})
    registro = criar_registro(cfg, stderr=False)
    resultado = executar_triagem(
        _exemplo("01_reset_senha.json"), cfg=cfg, llm=llm, registro=registro
    )

    saida = json.loads(resultado.model_dump_json())
    assert all(campo in saida for campo in CAMPOS_MINIMOS_SAIDA)
    assert resultado.rota in ("simples", "critico")
    assert resultado.rota != "falha", resultado.erros
    assert "resposta_fallback" not in resultado.alertas, resultado.erros
    eventos = registro.ler_eventos()
    assert sum(1 for e in eventos if e["evento"] == "llm_chamada" and e["sucesso"]) == 2


def test_live_fluxo_critico_aciona_tool(llm, tmp_path):
    cfg = CFG.__class__(**{**CFG.__dict__, "raiz_logs": tmp_path, "raiz_dados": RAIZ_DADOS})
    resultado = executar_triagem(_exemplo("02_portal_fora_do_ar.json"), cfg=cfg, llm=llm)

    assert resultado.rota == "critico", (resultado.prioridade, resultado.alertas)
    assert resultado.tool_resultado is not None and resultado.tool_resultado.ok
    assert resultado.requer_revisao_humana is True
