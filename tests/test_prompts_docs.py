"""A documentação das instruções do agente espelha o código (seção 12.1 do PRD, issue #16)."""

from pathlib import Path

from triagem import prompts

DOC = Path(__file__).resolve().parents[1] / "docs" / "instrucoes-agente.md"


def test_docs_espelham_os_prompts_do_codigo():
    texto = DOC.read_text(encoding="utf-8")
    for nome in (
        "PROMPT_ANALISE_SISTEMA",
        "PROMPT_ANALISE_HUMANO",
        "AVISO_INJECAO",
        "PROMPT_RESPOSTA_SISTEMA",
        "PROMPT_RESPOSTA_HUMANO",
    ):
        assert getattr(prompts, nome).rstrip("\n") in texto, f"{nome} divergente em {DOC.name}"


def test_docs_citam_as_versoes_vigentes():
    texto = DOC.read_text(encoding="utf-8")
    assert prompts.VERSAO_PROMPT_ANALISE in texto
    assert prompts.VERSAO_PROMPT_RESPOSTA in texto
