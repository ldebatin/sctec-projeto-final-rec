"""Fábrica do modelo de linguagem e dublê determinístico para testes (D1, D11).

Os nodes dependem apenas de ``with_structured_output(schema).invoke(entrada)``.
Qualquer objeto que ofereça essa interface serve, o que permite injetar o
``FakeLLM`` nos testes e no CI sem chave nem rede.

APIs confirmadas na versão instalada (langchain 1.4, langchain-google-genai 4.4):
- ``init_chat_model(model, *, model_provider=None, **kwargs)`` aceita
  ``"provedor:modelo"`` e repassa kwargs ao construtor do provedor.
- ``ChatGoogleGenerativeAI`` tem ``temperature=0.7``, ``timeout=None`` e
  ``max_retries=6`` por padrão; aqui usamos ``temperature=0`` (RNF-04) e
  ``max_retries=0`` para que o retry limitado do grafo (D7) seja o único.
- ``with_structured_output(schema, method="json_schema", *, include_raw=False)``.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import BaseModel

from triagem.config import Configuracao

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


@runtime_checkable
class SaidaEstruturada(Protocol):
    """Objeto devolvido por ``with_structured_output``; devolve instâncias do schema."""

    def invoke(self, entrada: Any, config: Any | None = None) -> Any: ...


@runtime_checkable
class ModeloLinguagem(Protocol):
    """Subconjunto da interface de ``BaseChatModel`` usado pelos nodes."""

    def with_structured_output(
        self, schema: type[BaseModel], **kwargs: Any
    ) -> SaidaEstruturada: ...


def criar_llm(cfg: Configuracao) -> BaseChatModel:
    """Instancia o modelo real configurado por ``.env``.

    Levanta ``ErroConfiguracao`` antes de qualquer chamada de rede se a chave do
    provedor estiver ausente (falha rápida, RNF-02).
    """
    chave = cfg.exigir_chave_api()

    # Import tardio: testes e CI que usam apenas o FakeLLM não pagam o custo.
    from langchain.chat_models import init_chat_model

    parametros: dict[str, Any] = {
        "temperature": 0,
        "timeout": cfg.llm_timeout_segundos,
        "max_retries": 0,
    }
    if chave is not None:
        parametros["api_key"] = chave
    return init_chat_model(cfg.nome_modelo, **parametros)


# ---------------------------------------------------------------------------
# Dublê para testes
# ---------------------------------------------------------------------------


@dataclass
class ChamadaRegistrada:
    schema: str
    entrada: Any


class FakeLLM:
    """Modelo falso que devolve respostas enfileiradas, em ordem.

    Cada item pode ser uma instância do schema pedido, um ``dict`` validado
    contra o schema ou uma ``Exception`` a ser levantada. ``padrao`` é usado
    quando a fila esvazia (útil para simular falha permanente).
    """

    def __init__(
        self,
        respostas: Iterable[BaseModel | dict[str, Any] | Exception] = (),
        *,
        padrao: BaseModel | dict[str, Any] | Exception | None = None,
        nome: str = "fake:determinista",
    ) -> None:
        self._fila: deque[BaseModel | dict[str, Any] | Exception] = deque(respostas)
        self.padrao = padrao
        self.nome = nome
        self.chamadas: list[ChamadaRegistrada] = []

    @property
    def total_chamadas(self) -> int:
        return len(self.chamadas)

    @property
    def respostas_restantes(self) -> int:
        return len(self._fila)

    def with_structured_output(self, schema: type[BaseModel], **_: Any) -> _SaidaEstruturadaFake:
        return _SaidaEstruturadaFake(self, schema)

    def _responder(self, schema: type[BaseModel], entrada: Any) -> BaseModel:
        self.chamadas.append(ChamadaRegistrada(schema=schema.__name__, entrada=entrada))
        if self._fila:
            item = self._fila.popleft()
        elif self.padrao is not None:
            item = self.padrao
        else:
            raise RuntimeError(f"FakeLLM sem respostas enfileiradas para {schema.__name__}.")

        if isinstance(item, Exception):
            raise item
        if isinstance(item, dict):
            return schema.model_validate(item)
        if isinstance(item, schema):
            return item
        raise TypeError(
            f"FakeLLM: resposta do tipo {type(item).__name__} incompatível com {schema.__name__}."
        )


class _SaidaEstruturadaFake:
    def __init__(self, fake: FakeLLM, schema: type[BaseModel]) -> None:
        self._fake = fake
        self._schema = schema

    def invoke(self, entrada: Any, config: Any | None = None) -> BaseModel:
        return self._fake._responder(self._schema, entrada)
