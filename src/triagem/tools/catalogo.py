"""Tool ``consultar_catalogo_servicos`` (RF-20 a RF-23; decisões D4 e D6 do PRD).

Consulta o catálogo interno de serviços (``data/catalogo_servicos.json``) e devolve
equipe responsável, criticidade, status atual, runbook e contato de escalonamento.
A decisão de *quando* chamar a tool é das regras (rota ``critico``), não do modelo.

Falhas tratadas (todas viram ``ResultadoCatalogo.ok = False``, nunca exceção no fluxo):
``parametro_invalido``, ``servico_nao_encontrado``, ``servico_nao_identificado``
(decidida no node, antes de chamar a tool) e ``catalogo_indisponivel``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from triagem.modelos import Ambiente, ResultadoCatalogo, normalizar_texto

NOME_TOOL = "consultar_catalogo_servicos"
DESCRICAO_TOOL = (
    "Consulta o catálogo interno de serviços de TI pelo nome ou apelido do serviço e devolve "
    "equipe responsável, criticidade, status atual, runbook e contato de escalonamento. "
    "Use quando um chamado crítico citar um sistema ou serviço."
)


class ErroCatalogoIndisponivel(RuntimeError):
    """Arquivo do catálogo ausente, corrompido, inválido ou falha simulada."""


class ParametrosCatalogo(BaseModel):
    """Schema dos argumentos da tool (RF-21)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    servico: str = Field(
        min_length=1,
        max_length=100,
        description="Nome, id ou apelido do serviço afetado, como citado no chamado.",
    )
    ambiente: Ambiente | None = Field(
        default=None, description="Ambiente do chamado, se informado (producao, homologacao...)."
    )


class _EntradaCatalogo(BaseModel):
    """Validação de cada item do JSON do catálogo."""

    id: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    equipe_responsavel: str
    criticidade: Literal["baixa", "media", "alta"]
    status_atual: Literal["operacional", "degradado", "indisponivel", "manutencao"]
    ambientes: list[str] = Field(default_factory=list)
    runbook: str
    contato_escalonamento: str


@dataclass(frozen=True)
class ServicoCatalogo:
    id: str
    nome: str
    aliases: tuple[str, ...]
    equipe_responsavel: str
    criticidade: str
    status_atual: str
    ambientes: tuple[str, ...]
    runbook: str
    contato_escalonamento: str

    def chaves(self) -> tuple[str, ...]:
        """Todas as formas normalizadas pelas quais o serviço pode ser referenciado."""
        return tuple(normalizar_texto(c) for c in (self.id, self.nome, *self.aliases))


class Catalogo:
    def __init__(self, servicos: list[ServicoCatalogo]) -> None:
        if not servicos:
            raise ErroCatalogoIndisponivel("catálogo sem serviços")
        self.servicos = list(servicos)
        # Um apelido repetido entre serviços faria `resolver` escolher em silêncio o primeiro
        # da lista (QA com IA, issue #17): falha na carga, com mensagem que aponta o par.
        donos: dict[str, str] = {}
        for servico in self.servicos:
            for chave in servico.chaves():
                dono = donos.setdefault(chave, servico.id)
                if dono != servico.id:
                    raise ErroCatalogoIndisponivel(
                        f"apelido '{chave}' repetido entre os serviços '{dono}' e '{servico.id}'"
                    )

    @classmethod
    def carregar(cls, caminho: Path) -> Catalogo:
        if not caminho.is_file():
            raise ErroCatalogoIndisponivel(f"arquivo do catálogo não encontrado: {caminho}")
        try:
            bruto = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ErroCatalogoIndisponivel(f"catálogo ilegível ({caminho.name}): {exc}") from exc
        if not isinstance(bruto, list):
            raise ErroCatalogoIndisponivel("catálogo deve ser uma lista de serviços")
        servicos: list[ServicoCatalogo] = []
        ids: set[str] = set()
        for indice, item in enumerate(bruto):
            try:
                entrada = _EntradaCatalogo.model_validate(item)
            except ValidationError as exc:
                raise ErroCatalogoIndisponivel(
                    f"item {indice} do catálogo inválido: {exc}"
                ) from exc
            if entrada.id in ids:
                raise ErroCatalogoIndisponivel(f"id duplicado no catálogo: {entrada.id}")
            ids.add(entrada.id)
            servicos.append(
                ServicoCatalogo(
                    id=entrada.id,
                    nome=entrada.nome,
                    aliases=tuple(entrada.aliases),
                    equipe_responsavel=entrada.equipe_responsavel,
                    criticidade=entrada.criticidade,
                    status_atual=entrada.status_atual,
                    ambientes=tuple(entrada.ambientes),
                    runbook=entrada.runbook,
                    contato_escalonamento=entrada.contato_escalonamento,
                )
            )
        return cls(servicos)

    def __len__(self) -> int:
        return len(self.servicos)

    def resolver(self, referencia: str) -> ServicoCatalogo | None:
        """Casa por id, nome ou alias (sem acento, sem caixa); depois por alias contido na frase.

        Na busca por alias contido, vence o alias mais longo (mais específico), para que
        "portal web" prevaleça sobre "portal" quando ambos aparecerem. Apelidos de uso
        corrente fora de TI ("banco", "dominio", "autenticacao") saíram do catálogo em 15/09
        (QA com IA, issue #17) porque resolviam frases como "o banco recusou o boleto".
        """
        alvo = normalizar_texto(referencia)
        if not alvo:
            return None
        for servico in self.servicos:
            if alvo in servico.chaves():
                return servico
        melhor: tuple[int, ServicoCatalogo] | None = None
        for servico in self.servicos:
            for chave in servico.chaves():
                if re.search(rf"(?<![a-z0-9]){re.escape(chave)}(?![a-z0-9])", alvo):
                    if melhor is None or len(chave) > melhor[0]:
                        melhor = (len(chave), servico)
        return melhor[1] if melhor else None


@lru_cache(maxsize=4)
def _carregar_cacheado(caminho: str) -> Catalogo:
    return Catalogo.carregar(Path(caminho))


def obter_catalogo(caminho: Path) -> Catalogo:
    """Catálogo carregado uma única vez por arquivo (por processo)."""
    return _carregar_cacheado(str(caminho.resolve()))


def consultar_catalogo(
    catalogo: Catalogo, servico: str, ambiente: Ambiente | None = None
) -> ResultadoCatalogo:
    """Lógica pura da tool, separada do empacotamento LangChain para facilitar testes."""
    encontrado = catalogo.resolver(servico)
    if encontrado is None:
        return ResultadoCatalogo.falha(
            "servico_nao_encontrado",
            f"Serviço '{servico}' não consta no catálogo. Confirme o nome do sistema afetado.",
        )
    observacao: str | None = None
    if (
        ambiente is not None
        and ambiente is not Ambiente.NAO_INFORMADO
        and ambiente.value not in encontrado.ambientes
    ):
        observacao = (
            f"O serviço não está cadastrado para o ambiente '{ambiente.value}' "
            f"(ambientes: {', '.join(encontrado.ambientes)})."
        )
    return ResultadoCatalogo(
        ok=True,
        mensagem=observacao,
        servico_id=encontrado.id,
        nome=encontrado.nome,
        equipe_responsavel=encontrado.equipe_responsavel,
        criticidade=encontrado.criticidade,
        status_atual=encontrado.status_atual,
        runbook=encontrado.runbook,
        contato_escalonamento=encontrado.contato_escalonamento,
    )


def criar_tool_catalogo(caminho: Path, simular_falha: bool = False) -> StructuredTool:
    """Empacota a consulta como tool LangChain com schema de argumentos inspecionável.

    ``simular_falha`` (``SIMULAR_FALHA_TOOL=1``) reproduz indisponibilidade do catálogo
    para demonstrar o tratamento de falha de integração (RF-23).
    """

    def _executar(servico: str, ambiente: Ambiente | None = None) -> ResultadoCatalogo:
        if simular_falha:
            raise ErroCatalogoIndisponivel("falha simulada do catálogo (SIMULAR_FALHA_TOOL=1)")
        return consultar_catalogo(obter_catalogo(caminho), servico, ambiente)

    return StructuredTool.from_function(
        func=_executar,
        name=NOME_TOOL,
        description=DESCRICAO_TOOL,
        args_schema=ParametrosCatalogo,
    )
