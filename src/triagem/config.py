"""Configuração por variáveis de ambiente (seção 14 do PRD; RNF-02).

Todas as variáveis têm padrão seguro, exceto a chave do provedor de LLM, que só
é exigida quando o modelo real é instanciado (``Configuracao.exigir_chave_api``).
A leitura pode receber um ``Mapping`` no lugar de ``os.environ`` para testes.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


class ErroConfiguracao(ValueError):
    """Configuração ausente ou inválida. A CLI converte em código de saída 2."""


# Provedor aceito por init_chat_model -> variável de ambiente com a chave.
# ``None`` indica provedor local sem chave (ex.: ollama).
VARIAVEL_CHAVE_POR_PROVEDOR: dict[str, str | None] = {
    "google_genai": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": None,
}

_VERDADEIROS = {"1", "true", "sim", "yes", "on"}
_FALSOS = {"0", "false", "nao", "não", "no", "off", ""}


@dataclass(frozen=True)
class Configuracao:
    llm_provider: str = "google_genai"
    llm_model: str = "gemini-2.5-flash"
    llm_timeout_segundos: float = 30.0
    max_tentativas_llm: int = 2
    # Espera antes de nova tentativa quando o provedor devolve erro de quota (HTTP 429).
    llm_backoff_base_segundos: float = 2.0
    limiar_bm25: float = 12.0
    limiar_confianca: float = 0.6
    log_nivel: str = "INFO"
    log_formato: Literal["json", "texto"] = "json"
    simular_falha_tool: bool = False
    raiz_dados: Path = Path("data")
    raiz_logs: Path = Path("logs")
    # Nunca aparece em repr/log. Resolvida a partir da variável do provedor.
    api_key: str | None = field(default=None, repr=False)

    @property
    def nome_modelo(self) -> str:
        """Identificador ``provedor:modelo`` usado nos logs e na saída."""
        return f"{self.llm_provider}:{self.llm_model}"

    @property
    def variavel_chave(self) -> str | None:
        """Nome da variável de ambiente que guarda a chave do provedor configurado."""
        convencao = f"{self.llm_provider.upper()}_API_KEY"
        return VARIAVEL_CHAVE_POR_PROVEDOR.get(self.llm_provider, convencao)

    def exigir_chave_api(self) -> str | None:
        """Devolve a chave ou levanta ``ErroConfiguracao`` com instrução clara.

        Provedores locais (sem variável de chave) devolvem ``None`` sem erro.
        """
        variavel = self.variavel_chave
        if variavel is None:
            return None
        if not self.api_key:
            raise ErroConfiguracao(
                f"Variável {variavel} não definida. Copie .env.example para .env e preencha a "
                f"chave do provedor '{self.llm_provider}'."
            )
        return self.api_key


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _texto(ambiente: Mapping[str, str], nome: str, padrao: str) -> str:
    valor = ambiente.get(nome, "").strip()
    return valor or padrao


def _inteiro(ambiente: Mapping[str, str], nome: str, padrao: int, minimo: int) -> int:
    bruto = ambiente.get(nome, "").strip()
    if not bruto:
        return padrao
    try:
        valor = int(bruto)
    except ValueError as exc:
        raise ErroConfiguracao(f"{nome} deve ser um inteiro; recebido '{bruto}'.") from exc
    if valor < minimo:
        raise ErroConfiguracao(f"{nome} deve ser >= {minimo}; recebido {valor}.")
    return valor


def _decimal(ambiente: Mapping[str, str], nome: str, padrao: float, minimo: float) -> float:
    bruto = ambiente.get(nome, "").strip()
    if not bruto:
        return padrao
    try:
        valor = float(bruto.replace(",", "."))
    except ValueError as exc:
        raise ErroConfiguracao(f"{nome} deve ser numérico; recebido '{bruto}'.") from exc
    if valor < minimo:
        raise ErroConfiguracao(f"{nome} deve ser >= {minimo}; recebido {valor}.")
    return valor


def _booleano(ambiente: Mapping[str, str], nome: str, padrao: bool) -> bool:
    bruto = ambiente.get(nome)
    if bruto is None:
        return padrao
    normalizado = bruto.strip().lower()
    if normalizado in _VERDADEIROS:
        return True
    if normalizado in _FALSOS:
        return False
    raise ErroConfiguracao(f"{nome} deve ser 0/1, true/false ou sim/nao; recebido '{bruto}'.")


def carregar_configuracao(
    arquivo_env: str | os.PathLike[str] | None = ".env",
    *,
    ambiente: Mapping[str, str] | None = None,
) -> Configuracao:
    """Monta a configuração a partir de ``.env`` (se existir) e do ambiente do processo.

    Args:
        arquivo_env: caminho do ``.env``; ``None`` desativa a leitura do arquivo.
        ambiente: mapeamento alternativo a ``os.environ`` (para testes). Quando
            informado, o ``.env`` não é carregado.
    """
    if ambiente is None:
        if arquivo_env is not None and Path(arquivo_env).is_file():
            load_dotenv(arquivo_env, override=False)
        ambiente = os.environ

    provedor = _texto(ambiente, "LLM_PROVIDER", "google_genai").lower()
    modelo = _texto(ambiente, "LLM_MODEL", "gemini-2.5-flash")

    formato = _texto(ambiente, "LOG_FORMATO", "json").lower()
    if formato not in ("json", "texto"):
        raise ErroConfiguracao(f"LOG_FORMATO deve ser 'json' ou 'texto'; recebido '{formato}'.")

    variavel_chave = VARIAVEL_CHAVE_POR_PROVEDOR.get(provedor, f"{provedor.upper()}_API_KEY")
    chave = ambiente.get(variavel_chave, "").strip() or None if variavel_chave else None

    return Configuracao(
        llm_provider=provedor,
        llm_model=modelo,
        llm_timeout_segundos=_decimal(ambiente, "LLM_TIMEOUT_SEGUNDOS", 30.0, minimo=1.0),
        max_tentativas_llm=_inteiro(ambiente, "MAX_TENTATIVAS_LLM", 2, minimo=1),
        llm_backoff_base_segundos=_decimal(ambiente, "LLM_BACKOFF_BASE_SEGUNDOS", 2.0, minimo=0.0),
        limiar_bm25=_decimal(ambiente, "LIMIAR_BM25", 12.0, minimo=0.0),
        limiar_confianca=_decimal(ambiente, "LIMIAR_CONFIANCA", 0.6, minimo=0.0),
        log_nivel=_texto(ambiente, "LOG_NIVEL", "INFO").upper(),
        log_formato=formato,  # type: ignore[arg-type]
        simular_falha_tool=_booleano(ambiente, "SIMULAR_FALHA_TOOL", False),
        raiz_dados=Path(_texto(ambiente, "RAIZ_DADOS", "data")),
        raiz_logs=Path(_texto(ambiente, "RAIZ_LOGS", "logs")),
        api_key=chave,
    )
