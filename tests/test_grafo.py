"""Testes do grafo LangGraph (issue #6): T3, T6 e comportamento estrutural."""

from tests.dados import ANALISE_PORTAL, ANALISE_SENHA, CHAMADO_PORTAL, CHAMADO_SENHA
from triagem.grafo import ORDEM_NODES, criar_grafo, diagrama_mermaid, executar_triagem
from triagem.llm import FakeLLM
from triagem.observabilidade import resumir_eventos
from triagem.regras import MOTIVO_FALHA_TRATADA, MOTIVO_ROTA_CRITICA

# --------------------------------------------------------------------------- T3


def test_entrada_invalida_nao_interrompe_e_produz_fallback(cfg, registro):
    fake = FakeLLM([ANALISE_SENHA])
    resultado = executar_triagem(
        {"titulo": "Título válido", "descricao": "   "}, cfg=cfg, llm=fake, registro=registro
    )

    assert resultado.rota == "falha"
    assert resultado.requer_revisao_humana is True
    assert resultado.motivo_revisao == [MOTIVO_FALHA_TRATADA]
    assert resultado.categoria.value == "indefinido"
    assert resultado.caminho_percorrido == ["validar_entrada", "tratar_falha"]
    assert any("descricao" in erro for erro in resultado.erros)
    assert fake.total_chamadas == 0, "LLM não deve ser chamado com entrada inválida"

    resumo = resumir_eventos(registro.ler_eventos())
    assert resumo["nodes"] == ["validar_entrada", "tratar_falha"]
    assert resumo["roteamentos"][0]["decisao"] == "tratar_falha"


def test_entrada_que_nao_e_objeto_tambem_e_tratada(cfg, registro):
    resultado = executar_triagem("texto solto", cfg=cfg, llm=FakeLLM(), registro=registro)
    assert resultado.rota == "falha"
    assert "esperado um objeto" in resultado.erros[0]


# --------------------------------------------------------------------------- T6


def test_retry_respeita_limite_e_termina_em_tratar_falha(cfg, registro):
    fake = FakeLLM(padrao=TimeoutError("sem resposta do provedor"))
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)

    assert fake.total_chamadas == cfg.max_tentativas_llm == 2
    assert resultado.rota == "falha"
    assert resultado.caminho_percorrido == [
        "validar_entrada",
        "analisar_chamado",
        "analisar_chamado",
        "tratar_falha",
    ]
    assert len([e for e in resultado.erros if e.startswith("analise_falhou")]) == 2

    eventos = registro.ler_eventos()
    chamadas = [e for e in eventos if e["evento"] == "llm_chamada"]
    assert [c["tentativa"] for c in chamadas] == [1, 2]
    assert all(c["sucesso"] is False for c in chamadas)
    decisoes = [r["decisao"] for r in resumir_eventos(eventos)["roteamentos"]]
    assert decisoes == ["analisar_chamado", "analisar_chamado", "tratar_falha"]
    assert "condição de parada" in resumir_eventos(eventos)["roteamentos"][-1]["motivo"]


def test_retry_recupera_na_segunda_tentativa(cfg, registro):
    fake = FakeLLM([RuntimeError("429 quota"), ANALISE_SENHA])
    resultado = executar_triagem(CHAMADO_SENHA, cfg=cfg, llm=fake, registro=registro)

    assert fake.total_chamadas == 2
    assert resultado.rota == "simples"
    assert resultado.caminho_percorrido[:3] == [
        "validar_entrada",
        "analisar_chamado",
        "analisar_chamado",
    ]
    assert "classificar_risco" in resultado.caminho_percorrido
    assert len(resultado.erros) == 1  # a falha da primeira tentativa fica registrada


# --------------------------------------------------------------------------- fluxos


def test_fluxo_simples_percorre_consultar_base(cfg, registro):
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg, llm=FakeLLM([ANALISE_SENHA]), registro=registro
    )

    assert resultado.rota == "simples"
    assert resultado.caminho_percorrido == [
        "validar_entrada",
        "analisar_chamado",
        "classificar_risco",
        "consultar_base",
        "gerar_resposta",
    ]
    assert resultado.categoria.value == "suporte"
    assert resultado.prioridade.value == "baixa"
    assert resultado.requer_revisao_humana is False
    assert resultado.motivo_revisao == []
    assert resultado.run_id == registro.run_id
    assert resultado.modelo == cfg.nome_modelo


def test_fluxo_critico_percorre_consultar_tool_e_exige_revisao(cfg, registro):
    resultado = executar_triagem(
        CHAMADO_PORTAL, cfg=cfg, llm=FakeLLM([ANALISE_PORTAL]), registro=registro
    )

    assert resultado.rota == "critico"
    assert "consultar_tool" in resultado.caminho_percorrido
    assert "consultar_base" not in resultado.caminho_percorrido
    assert resultado.prioridade.value == "alta"
    assert resultado.requer_revisao_humana is True
    assert MOTIVO_ROTA_CRITICA in resultado.motivo_revisao

    roteamentos = resumir_eventos(registro.ler_eventos())["roteamentos"]
    ultimo = roteamentos[-1]
    assert ultimo["origem"] == "classificar_risco" and ultimo["decisao"] == "consultar_tool"
    assert "prioridade alta" in ultimo["motivo"]


def test_logs_reconstroem_o_caminho_percorrido(cfg, registro):
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg, llm=FakeLLM([ANALISE_SENHA]), registro=registro
    )
    eventos = registro.ler_eventos()
    resumo = resumir_eventos(eventos)
    assert resumo["nodes"] == resultado.caminho_percorrido
    assert resumo["chamadas_llm"] == 1
    assert len(resumo["roteamentos"]) == 3
    assert eventos[0]["evento"] == "execucao_iniciada"
    assert eventos[-1]["evento"] == "execucao_finalizada"
    assert eventos[-1]["rota"] == "simples"


# --------------------------------------------------------------------------- condição de parada


def test_recursion_limit_e_rede_de_seguranca(cfg, registro):
    """Com limite artificialmente baixo, o GraphRecursionError vira fallback controlado."""
    resultado = executar_triagem(
        CHAMADO_SENHA, cfg=cfg, llm=FakeLLM([ANALISE_SENHA]), registro=registro, limite_recursao=2
    )
    assert resultado.rota == "falha"
    assert any("GraphRecursionError" in erro for erro in resultado.erros)
    assert any(e["evento"] == "erro" and e["node"] == "grafo" for e in registro.ler_eventos())


def test_unico_ciclo_e_o_retry_de_analisar_chamado():
    grafo = criar_grafo().get_graph()
    posicao = {nome: i for i, nome in enumerate(ORDEM_NODES)}
    retrocessos = {
        (aresta.source, aresta.target)
        for aresta in grafo.edges
        if aresta.source in posicao
        and aresta.target in posicao
        and posicao[aresta.target] <= posicao[aresta.source]
    }
    assert retrocessos == {("analisar_chamado", "analisar_chamado")}


def test_diagrama_mermaid_lista_todos_os_nodes():
    mermaid = diagrama_mermaid()
    assert mermaid.startswith("---") or "graph" in mermaid or "flowchart" in mermaid
    for nome in ORDEM_NODES:
        assert nome in mermaid
    assert "__end__" in mermaid
