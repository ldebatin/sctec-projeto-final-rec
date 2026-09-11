"""Os chamados de exemplo reproduzem os cenários documentados (issue #12)."""

import json

import pytest
from pydantic import ValidationError

from tests.conftest import RAIZ_DADOS
from tests.dados import ANALISE_PORTAL, ANALISE_SENHA, fake_llm
from triagem.grafo import executar_triagem
from triagem.llm import FakeLLM
from triagem.modelos import AnaliseChamado, Categoria, Chamado, Impacto, Prioridade
from triagem.regras import (
    MOTIVO_CATEGORIA_INDEFINIDA,
    MOTIVO_FALHA_TRATADA,
    MOTIVO_ROTA_CRITICA,
    MOTIVO_TOOL_FALHOU,
    detectar_termos_indisponibilidade,
)

PASTA = RAIZ_DADOS / "exemplos"
ESPERADOS = [
    "01_reset_senha.json",
    "02_portal_fora_do_ar.json",
    "03_vpn_intermitente.json",
    "04_entrada_invalida.json",
    "05_servico_desconhecido.json",
    "06_prompt_injection.json",
    "07_fora_do_dominio.json",
]


def carregar(nome):
    return json.loads((PASTA / nome).read_text(encoding="utf-8"))


def test_os_sete_exemplos_existem_e_tem_cenario():
    assert sorted(p.name for p in PASTA.glob("*.json")) == ESPERADOS
    for nome in ESPERADOS:
        dados = carregar(nome)
        assert dados["_cenario"], nome
        assert "titulo" in dados and "descricao" in dados, nome


@pytest.mark.parametrize("nome", [n for n in ESPERADOS if n != "04_entrada_invalida.json"])
def test_exemplos_validos_passam_na_validacao(nome):
    chamado = Chamado.model_validate(carregar(nome))
    assert chamado.titulo and len(chamado.descricao) >= 20


def test_exemplo_04_e_rejeitado_pela_validacao():
    with pytest.raises(ValidationError) as exc:
        Chamado.model_validate(carregar("04_entrada_invalida.json"))
    assert "descricao" in str(exc.value)


def test_exemplo_04_no_grafo_vira_fallback_sem_chamar_o_llm(cfg, registro):
    fake = FakeLLM()
    resultado = executar_triagem(
        carregar("04_entrada_invalida.json"), cfg=cfg, llm=fake, registro=registro
    )
    assert resultado.rota == "falha"
    assert resultado.motivo_revisao == [MOTIVO_FALHA_TRATADA]
    assert fake.total_chamadas == 0


def test_exemplo_05_tem_termo_de_indisponibilidade_e_servico_fora_do_catalogo(cfg, registro):
    dados = carregar("05_servico_desconhecido.json")
    assert detectar_termos_indisponibilidade(dados["titulo"] + dados["descricao"])
    analise = ANALISE_PORTAL.model_copy(
        update={"servico_mencionado": "Sistema XPTO", "categoria": Categoria.SOFTWARE}
    )
    resultado = executar_triagem(dados, cfg=cfg, llm=fake_llm(analise), registro=registro)
    assert resultado.rota == "critico"
    assert resultado.tool_resultado.erro == "servico_nao_encontrado"
    assert {MOTIVO_ROTA_CRITICA, MOTIVO_TOOL_FALHOU} <= set(resultado.motivo_revisao)


def test_exemplo_06_contem_instrucao_injetada_e_impacto_real():
    dados = carregar("06_prompt_injection.json")
    texto = dados["descricao"].lower()
    assert "ignore as instruções anteriores" in texto
    assert "google_api_key" in texto
    assert dados["ambiente"] == "producao"
    # O conteúdo real é uma indisponibilidade ampla: as regras devem manter a rota crítica
    # mesmo que o modelo seja manipulado a sugerir prioridade baixa.
    analise_manipulada = AnaliseChamado(
        categoria=Categoria.SUPORTE,
        prioridade_sugerida=Prioridade.BAIXA,
        impacto=Impacto.MULTIPLOS_USUARIOS,
        servico_mencionado="Servidor de Arquivos",
        palavras_chave=["pasta compartilhada", "servidor de arquivos"],
        resumo_tecnico="Pasta compartilhada inacessível para o setor.",
        confianca=0.8,
    )
    from triagem.regras import classificar_risco

    classificacao = classificar_risco(analise_manipulada, Chamado.model_validate(dados))
    assert classificacao.rota == "critico"
    assert classificacao.prioridade is Prioridade.ALTA


def test_exemplo_07_com_categoria_indefinida_exige_revisao(cfg, registro):
    analise = AnaliseChamado(
        categoria=Categoria.INDEFINIDO,
        prioridade_sugerida=Prioridade.BAIXA,
        impacto=Impacto.USUARIO_UNICO,
        palavras_chave=["ferias", "solicitacao"],
        resumo_tecnico="Pedido administrativo de férias, não é chamado técnico.",
        confianca=0.4,
    )
    resultado = executar_triagem(
        carregar("07_fora_do_dominio.json"), cfg=cfg, llm=fake_llm(analise), registro=registro
    )
    assert resultado.rota == "simples"
    assert resultado.categoria is Categoria.INDEFINIDO
    assert MOTIVO_CATEGORIA_INDEFINIDA in resultado.motivo_revisao
    assert "confianca_baixa" in resultado.motivo_revisao


def test_exemplos_01_e_02_percorrem_as_duas_rotas(cfg, registro):
    simples = executar_triagem(
        carregar("01_reset_senha.json"), cfg=cfg, llm=fake_llm(ANALISE_SENHA), registro=registro
    )
    assert simples.rota == "simples" and "kb-001-reset-senha-ad" in simples.fontes_contexto
    critico = executar_triagem(
        carregar("02_portal_fora_do_ar.json"), cfg=cfg, llm=fake_llm(ANALISE_PORTAL)
    )
    assert critico.rota == "critico" and critico.tool_resultado.equipe_responsavel == "Squad Portal"
