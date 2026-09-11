"""Contratos de dados que atravessam o fluxo de triagem (seção 5 do PRD).

Todos os modelos usam Pydantic v2. Os enums herdam de ``str`` para serializar
como texto simples no JSON de saída e no schema enviado ao LLM.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Categoria(str, Enum):
    """Domínio do chamado. ``indefinido`` sinaliza dúvida e força revisão humana."""

    SOFTWARE = "software"
    INFRAESTRUTURA = "infraestrutura"
    SUPORTE = "suporte"
    INDEFINIDO = "indefinido"


class Prioridade(str, Enum):
    BAIXA = "baixa"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"


ORDEM_PRIORIDADE: dict[Prioridade, int] = {
    Prioridade.BAIXA: 0,
    Prioridade.MEDIA: 1,
    Prioridade.ALTA: 2,
    Prioridade.CRITICA: 3,
}


class Impacto(str, Enum):
    USUARIO_UNICO = "usuario_unico"
    EQUIPE = "equipe"
    MULTIPLOS_USUARIOS = "multiplos_usuarios"
    TODA_ORGANIZACAO = "toda_organizacao"


class Ambiente(str, Enum):
    PRODUCAO = "producao"
    HOMOLOGACAO = "homologacao"
    DESENVOLVIMENTO = "desenvolvimento"
    NAO_INFORMADO = "nao_informado"


Rota = Literal["simples", "critico", "falha"]

ErroCatalogo = Literal[
    "parametro_invalido",
    "servico_nao_encontrado",
    "servico_nao_identificado",
    "catalogo_indisponivel",
]

# Campos que a rubrica exige, no mínimo, na saída estruturada (item 4.1 da espec).
CAMPOS_MINIMOS_SAIDA: tuple[str, ...] = (
    "categoria",
    "prioridade",
    "resumo",
    "acao_sugerida",
    "requer_revisao_humana",
)

# ---------------------------------------------------------------------------
# Helpers de normalização
# ---------------------------------------------------------------------------


def _vazio_para_none(valor: object) -> object:
    """Converte strings vazias ou só com espaços em ``None``."""
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


def normalizar_texto(valor: str) -> str:
    """Minúsculas, sem acentos e sem espaços nas pontas. Usado em enums e nomes de serviço."""
    sem_acento = unicodedata.normalize("NFKD", valor)
    apenas_ascii = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(apenas_ascii.lower().split())


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


class Chamado(BaseModel):
    """Chamado técnico recebido pelo agente (RF-01, RF-02).

    Campos extras na entrada são ignorados para permitir metadados nos arquivos
    de exemplo (por exemplo ``_cenario``) sem quebrar a validação.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    titulo: str = Field(min_length=5, max_length=200, description="Título curto do problema.")
    descricao: str = Field(
        min_length=20, max_length=8000, description="Descrição detalhada do problema."
    )
    servico: str | None = Field(
        default=None, max_length=100, description="Sistema ou serviço afetado, se informado."
    )
    ambiente: Ambiente = Field(
        default=Ambiente.NAO_INFORMADO, description="Ambiente onde o problema ocorre."
    )
    solicitante: str | None = Field(
        default=None, max_length=100, description="Quem abriu o chamado."
    )

    @field_validator("servico", "solicitante", mode="before")
    @classmethod
    def _opcionais_vazios_viram_none(cls, valor: object) -> object:
        return _vazio_para_none(valor)

    @field_validator("ambiente", mode="before")
    @classmethod
    def _normalizar_ambiente(cls, valor: object) -> object:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return Ambiente.NAO_INFORMADO
        if isinstance(valor, str):
            return normalizar_texto(valor)
        return valor


# ---------------------------------------------------------------------------
# Saída do LLM no node analisar_chamado
# ---------------------------------------------------------------------------


class AnaliseChamado(BaseModel):
    """Interpretação do chamado feita pelo modelo. São sugestões: as regras decidem.

    Limites de ``palavras_chave`` são mais tolerantes (1–10) do que o pedido no
    prompt (3–8) para não descartar respostas quase corretas do modelo.
    """

    categoria: Categoria = Field(description="Categoria do chamado.")
    prioridade_sugerida: Prioridade = Field(description="Prioridade sugerida pelo modelo.")
    impacto: Impacto = Field(description="Abrangência do impacto observado.")
    servico_mencionado: str | None = Field(
        default=None,
        max_length=100,
        description="Nome do sistema ou serviço citado no chamado, se houver.",
    )
    palavras_chave: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Termos técnicos para busca na base de conhecimento.",
    )
    resumo_tecnico: str = Field(
        min_length=10, max_length=600, description="Resumo técnico em uma ou duas frases."
    )
    confianca: float = Field(ge=0.0, le=1.0, description="Confiança do modelo na análise.")

    @field_validator("servico_mencionado", mode="before")
    @classmethod
    def _servico_vazio_vira_none(cls, valor: object) -> object:
        return _vazio_para_none(valor)

    @field_validator("palavras_chave", mode="before")
    @classmethod
    def _limpar_palavras_chave(cls, valor: object) -> object:
        if not isinstance(valor, list):
            return valor
        vistas: set[str] = set()
        limpas: list[str] = []
        for item in valor:
            if not isinstance(item, str):
                continue
            termo = " ".join(item.split())
            chave = termo.lower()
            if termo and chave not in vistas:
                vistas.add(chave)
                limpas.append(termo)
        return limpas


# ---------------------------------------------------------------------------
# Saída do LLM no node gerar_resposta
# ---------------------------------------------------------------------------


class RespostaLLM(BaseModel):
    """Texto redigido pelo modelo a partir do contexto recuperado."""

    resumo: str = Field(min_length=10, max_length=600, description="Resumo do chamado.")
    acao_sugerida: str = Field(
        min_length=10, max_length=1200, description="Próximo passo recomendado para a triagem."
    )
    justificativa: str | None = Field(
        default=None, max_length=600, description="Por que essa ação, com base no contexto."
    )


# ---------------------------------------------------------------------------
# Contexto e tool
# ---------------------------------------------------------------------------


class ArtigoRecuperado(BaseModel):
    """Artigo da base de conhecimento devolvido pela busca BM25."""

    id: str
    titulo: str
    categoria: Categoria | None = None
    score: float = Field(ge=0.0)
    trecho: str


class ResultadoCatalogo(BaseModel):
    """Saída tipada da tool ``consultar_catalogo_servicos`` (RF-20, RF-23)."""

    ok: bool
    erro: ErroCatalogo | None = None
    mensagem: str | None = None
    servico_id: str | None = None
    nome: str | None = None
    equipe_responsavel: str | None = None
    criticidade: str | None = None
    status_atual: str | None = None
    runbook: str | None = None
    contato_escalonamento: str | None = None

    @classmethod
    def falha(cls, erro: ErroCatalogo, mensagem: str) -> ResultadoCatalogo:
        return cls(ok=False, erro=erro, mensagem=mensagem)


# ---------------------------------------------------------------------------
# Saída final
# ---------------------------------------------------------------------------


class ResultadoTriagem(BaseModel):
    """Saída estruturada da triagem (RF-03, RF-04)."""

    run_id: str
    categoria: Categoria
    prioridade: Prioridade
    resumo: str
    acao_sugerida: str
    requer_revisao_humana: bool
    motivo_revisao: list[str] = Field(default_factory=list)
    rota: Rota
    fontes_contexto: list[str] = Field(default_factory=list)
    tool_resultado: ResultadoCatalogo | None = None
    alertas: list[str] = Field(default_factory=list)
    erros: list[str] = Field(default_factory=list)
    caminho_percorrido: list[str] = Field(default_factory=list)
    modelo: str | None = None
