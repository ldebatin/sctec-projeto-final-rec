"""Chamados e análises de exemplo compartilhados pelos testes."""

from triagem.llm import FakeLLM
from triagem.modelos import AnaliseChamado, Categoria, Impacto, Prioridade, RespostaLLM

CHAMADO_SENHA = {
    "titulo": "Esqueci minha senha do AD",
    "descricao": (
        "Não consigo entrar no computador desde ontem, a senha do Active Directory expirou."
    ),
    "ambiente": "producao",
}

CHAMADO_PORTAL = {
    "titulo": "Portal de clientes fora do ar",
    "descricao": (
        "O portal de clientes está retornando erro 500 para todos os usuários desde as 9h."
    ),
    "servico": "Portal de Clientes",
    "ambiente": "producao",
}

ANALISE_SENHA = AnaliseChamado(
    categoria=Categoria.SUPORTE,
    prioridade_sugerida=Prioridade.BAIXA,
    impacto=Impacto.USUARIO_UNICO,
    servico_mencionado="Active Directory",
    palavras_chave=["senha", "active directory", "expirada"],
    resumo_tecnico="Senha do AD expirou e o usuário não consegue autenticar.",
    confianca=0.95,
)

ANALISE_PORTAL = AnaliseChamado(
    categoria=Categoria.SOFTWARE,
    prioridade_sugerida=Prioridade.ALTA,
    impacto=Impacto.MULTIPLOS_USUARIOS,
    servico_mencionado="Portal de Clientes",
    palavras_chave=["portal", "erro 500", "indisponibilidade"],
    resumo_tecnico="Portal de clientes retorna erro 500 para todos os usuários.",
    confianca=0.9,
)

RESPOSTA_PADRAO = RespostaLLM(
    resumo="Resumo redigido pelo modelo a partir do contexto.",
    acao_sugerida="1. Seguir o procedimento indicado no contexto. 2. Responder ao solicitante.",
    justificativa="Baseado no artigo ou no catálogo fornecidos em <contexto>.",
)


def fake_llm(analise: AnaliseChamado, resposta: RespostaLLM = RESPOSTA_PADRAO) -> FakeLLM:
    """FakeLLM com as duas respostas do caminho feliz: análise e redação final."""
    return FakeLLM([analise, resposta])
