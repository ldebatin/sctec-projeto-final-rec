"""Fixtures compartilhadas: configuração isolada e registro sem stderr."""

import pytest

from triagem.config import Configuracao
from triagem.observabilidade import criar_registro


@pytest.fixture
def cfg(tmp_path):
    return Configuracao(raiz_logs=tmp_path / "logs", max_tentativas_llm=2, api_key="chave-teste")


@pytest.fixture
def registro(cfg):
    reg = criar_registro(cfg, stderr=False)
    yield reg
    reg.fechar()
