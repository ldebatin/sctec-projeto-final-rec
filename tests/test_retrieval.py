"""Testes da base de conhecimento e da recuperação BM25 (issue #8; teste T8 do PRD)."""

import pytest

from tests.conftest import RAIZ_DADOS
from tests.dados import ANALISE_SENHA, CHAMADO_SENHA, fake_llm
from triagem.grafo import executar_triagem
from triagem.modelos import Categoria
from triagem.regras import MOTIVO_SEM_CONTEXTO
from triagem.retrieval import BaseConhecimento, ErroBaseConhecimento, obter_base, tokenizar

PASTA_BASE = RAIZ_DADOS / "base_conhecimento"


@pytest.fixture(scope="module")
def base():
    return BaseConhecimento.carregar(PASTA_BASE)


# --------------------------------------------------------------------------- carga


def test_base_real_tem_pelo_menos_8_artigos_validos(base):
    assert len(base) >= 8
    assert base.problemas == []
    ids = [a.id for a in base.artigos]
    assert len(ids) == len(set(ids))
    assert {a.categoria for a in base.artigos} == {
        Categoria.SOFTWARE,
        Categoria.INFRAESTRUTURA,
        Categoria.SUPORTE,
    }
    for artigo in base.artigos:
        assert artigo.titulo and artigo.tags and artigo.corpo
        assert "## Procedimento" in artigo.corpo


def test_obter_base_e_cacheada_por_pasta():
    assert obter_base(PASTA_BASE) is obter_base(PASTA_BASE)


def test_pasta_inexistente_levanta_erro(tmp_path):
    with pytest.raises(ErroBaseConhecimento, match="não encontrada"):
        BaseConhecimento.carregar(tmp_path / "nao-existe")


def test_pasta_sem_artigos_validos_levanta_erro(tmp_path):
    (tmp_path / "ruim.md").write_text("sem front-matter", encoding="utf-8")
    with pytest.raises(ErroBaseConhecimento, match="nenhum artigo válido"):
        BaseConhecimento.carregar(tmp_path)


def test_artigos_invalidos_sao_ignorados_e_reportados(tmp_path):
    (tmp_path / "ok.md").write_text(
        "---\nid: a\ntitulo: Artigo bom\ncategoria: suporte\ntags: [x]\n---\ncorpo do artigo",
        encoding="utf-8",
    )
    (tmp_path / "sem-id.md").write_text("---\ntitulo: Falta id\n---\ncorpo", encoding="utf-8")
    (tmp_path / "dup.md").write_text("---\nid: a\ntitulo: Duplicado\n---\ncorpo", encoding="utf-8")
    (tmp_path / "cat.md").write_text(
        "---\nid: b\ntitulo: Categoria ruim\ncategoria: xpto\n---\ncorpo", encoding="utf-8"
    )
    base = BaseConhecimento.carregar(tmp_path)
    assert [a.id for a in base.artigos] == ["a"]
    assert len(base.problemas) == 3
    assert any("sem-id.md" in p for p in base.problemas)
    assert any("duplicado" in p for p in base.problemas)
    assert any("categoria inválida" in p for p in base.problemas)


# --------------------------------------------------------------------------- tokenização e busca


def test_tokenizar_remove_acentos_stopwords_e_tokens_curtos():
    tokens = tokenizar("A VPN não conecta desde ontem, é o roteador de casa?")
    assert tokens == ["vpn", "conecta", "roteador", "casa"]


def test_bm25_recupera_artigo_de_vpn_em_primeiro(base):
    """T8 do PRD."""
    resultados = base.buscar("vpn não conecta, cai toda hora no home office")
    assert resultados, "esperava pelo menos um artigo"
    assert resultados[0].id == "kb-002-vpn-nao-conecta"
    assert resultados[0].score >= 1.0
    assert resultados[0].categoria is Categoria.INFRAESTRUTURA
    assert "Procedimento" not in resultados[0].trecho  # trecho é o conteúdo, não o título
    assert resultados[0].trecho.startswith("1. Verificar")


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("portal de clientes com erro 500 para todos", "kb-003-portal-erro-500"),
        ("esqueci minha senha do active directory, conta bloqueada", "kb-001-reset-senha-ad"),
        ("acesso negado na pasta compartilhada da área", "kb-010-acesso-negado-pasta"),
        ("certificado ssl expirado no site, conexão não segura", "kb-008-certificado-tls-expirado"),
        ("impressora da rede está offline e a fila travou", "kb-007-impressora-rede-offline"),
    ],
)
def test_bm25_ranqueia_o_artigo_certo_em_primeiro(base, consulta, esperado):
    resultados = base.buscar(consulta, k=3)
    assert resultados and resultados[0].id == esperado


def test_scores_vem_em_ordem_decrescente_e_k_limita(base):
    resultados = base.buscar("erro no portal e no erp durante o fechamento", k=2, limiar=0.0)
    assert len(resultados) == 2
    assert resultados[0].score >= resultados[1].score


def test_limiar_filtra_consulta_irrelevante(base):
    assert base.buscar("receita de bolo de banana com canela", limiar=1.0) == []
    assert base.buscar("   ", limiar=0.0) == []


# --------------------------------------------------------------------------- integração no grafo


def test_node_consultar_base_preenche_contexto_e_fontes(cfg, registro):
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg, llm=fake_llm(ANALISE_SENHA), registro=registro
    )
    assert resultado.rota == "simples"
    assert "kb-001-reset-senha-ad" in resultado.fontes_contexto
    assert MOTIVO_SEM_CONTEXTO not in resultado.alertas

    fim = next(
        e
        for e in registro.ler_eventos()
        if e["evento"] == "node_fim" and e["node"] == "consultar_base"
    )
    assert fim["artigos"][0]["id"] == "kb-001-reset-senha-ad"
    assert fim["limiar"] == cfg.limiar_bm25


def test_base_indisponivel_nao_interrompe_o_fluxo(cfg, registro, tmp_path):
    cfg_sem_base = cfg.__class__(**{**cfg.__dict__, "raiz_dados": tmp_path / "vazio"})
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg_sem_base, llm=fake_llm(ANALISE_SENHA), registro=registro
    )
    assert resultado.rota == "simples"
    assert resultado.fontes_contexto == []
    assert MOTIVO_SEM_CONTEXTO in resultado.alertas
    assert any(e.startswith("base_indisponivel") for e in resultado.erros)
    assert any(
        e["evento"] == "erro" and e["node"] == "consultar_base" for e in registro.ler_eventos()
    )


def test_base_injetada_tem_precedencia(cfg, registro, tmp_path):
    (tmp_path / "senha.md").write_text(
        "---\nid: kb-teste\ntitulo: Senha expirada no AD\ncategoria: suporte\n"
        "tags: [senha, active directory]\n---\n## Procedimento\n1. Resetar.",
        encoding="utf-8",
    )
    # Mais dois artigos: o IDF do BM25 só fica positivo para termos presentes em menos
    # da metade dos documentos (com 2 artigos ele é exatamente zero).
    for nome, titulo, tag in (
        ("impressora", "Impressora offline", "impressora"),
        ("vpn", "VPN sem conexão", "vpn"),
    ):
        (tmp_path / f"{nome}.md").write_text(
            f"---\nid: kb-{nome}\ntitulo: {titulo}\ncategoria: infraestrutura\n"
            f"tags: [{tag}]\n---\n## Procedimento\n1. Verificar o serviço.",
            encoding="utf-8",
        )
    base_teste = BaseConhecimento.carregar(tmp_path)
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg, llm=fake_llm(ANALISE_SENHA), registro=registro, base=base_teste
    )
    assert resultado.fontes_contexto == ["kb-teste"]
