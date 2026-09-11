"""Fixtures compartilhadas: configuração isolada e registro sem stderr."""

from pathlib import Path

import pytest

from triagem.config import Configuracao
from triagem.observabilidade import criar_registro

RAIZ_DADOS = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def cfg(tmp_path):
    return Configuracao(
        raiz_logs=tmp_path / "logs",
        raiz_dados=RAIZ_DADOS,
        max_tentativas_llm=2,
        api_key="chave-teste",
    )


@pytest.fixture
def registro(cfg):
    reg = criar_registro(cfg, stderr=False)
    yield reg
    reg.fechar()
