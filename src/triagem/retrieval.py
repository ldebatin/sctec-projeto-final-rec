"""Base de conhecimento local e recuperação lexical BM25 (RF-30, RF-31; decisão D5 do PRD).

Os artigos ficam em ``data/base_conhecimento/*.md`` com front-matter YAML
(``id``, ``titulo``, ``categoria``, ``tags``, ``servicos``) e corpo em Markdown.
O índice é construído em memória uma vez por processo (``obter_base``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from rank_bm25 import BM25Okapi

from triagem.modelos import ArtigoRecuperado, Categoria, normalizar_texto


class ErroBaseConhecimento(RuntimeError):
    """Base ausente, vazia ou ilegível. O node trata e segue sem contexto."""


# Palavras muito frequentes em português que não ajudam a distinguir artigos.
# Normalizadas (sem acento) para casar com a saída de ``tokenizar``.
STOPWORDS_PT: frozenset[str] = frozenset(
    normalizar_texto(palavra)
    for palavra in """
    a o as os um uma uns umas de da do das dos e ou em no na nos nas por para com sem
    que se ao aos à às é ser esta está estão foi são não mais muito já também desde
    quando como onde qual quais seu sua seus suas meu minha ele ela eles elas isso isto
    este esta esse essa pelo pela até após sobre entre mas há ter tem têm hoje ontem
    favor gostaria preciso bom dia tarde boa obrigado olá oi aqui ali lá então
    """.split()
)

_TOKEN = re.compile(r"[a-z0-9]+")
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_TRECHO_MAX = 400


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sem acentos, só letras/dígitos, sem stopwords nem tokens de 1 caractere."""
    return [
        token
        for token in _TOKEN.findall(normalizar_texto(texto))
        if len(token) > 1 and token not in STOPWORDS_PT
    ]


@dataclass(frozen=True)
class Artigo:
    id: str
    titulo: str
    categoria: Categoria | None
    tags: tuple[str, ...]
    servicos: tuple[str, ...]
    corpo: str
    caminho: Path

    def texto_indexavel(self) -> str:
        # Título e tags repetidos para pesarem mais que o corpo na pontuação BM25.
        cabecalho = f"{self.titulo} {' '.join(self.tags)}"
        return f"{cabecalho}\n{cabecalho}\n{self.corpo}"

    def trecho(self) -> str:
        """Seção *Procedimento* (o que interessa à triagem) ou o início do corpo."""
        match = re.search(r"##\s*Procedimento\s*\n(.*?)(?:\n##|\Z)", self.corpo, re.DOTALL)
        texto = (match.group(1) if match else self.corpo).strip()
        texto = re.sub(r"\s+", " ", texto)
        return texto if len(texto) <= _TRECHO_MAX else texto[: _TRECHO_MAX - 1].rstrip() + "…"


def _parse_artigo(caminho: Path) -> Artigo:
    conteudo = caminho.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(conteudo)
    if not match:
        raise ValueError("front-matter YAML ausente (bloco entre '---')")
    meta = yaml.safe_load(match.group(1)) or {}
    if not isinstance(meta, dict) or not meta.get("id") or not meta.get("titulo"):
        raise ValueError("front-matter precisa de 'id' e 'titulo'")
    categoria_bruta = meta.get("categoria")
    try:
        categoria = Categoria(categoria_bruta) if categoria_bruta else None
    except ValueError as exc:
        raise ValueError(f"categoria inválida: {categoria_bruta!r}") from exc
    return Artigo(
        id=str(meta["id"]),
        titulo=str(meta["titulo"]),
        categoria=categoria,
        tags=tuple(str(t) for t in (meta.get("tags") or [])),
        servicos=tuple(str(s) for s in (meta.get("servicos") or [])),
        corpo=match.group(2).strip(),
        caminho=caminho,
    )


class BaseConhecimento:
    """Índice BM25 sobre os artigos. Imutável após a carga."""

    def __init__(self, artigos: list[Artigo], problemas: list[str] | None = None) -> None:
        if not artigos:
            raise ErroBaseConhecimento("nenhum artigo válido na base de conhecimento")
        self.artigos = list(artigos)
        self.problemas = list(problemas or [])
        self._bm25 = BM25Okapi([tokenizar(a.texto_indexavel()) for a in self.artigos])

    @classmethod
    def carregar(cls, pasta: Path) -> BaseConhecimento:
        if not pasta.is_dir():
            raise ErroBaseConhecimento(f"pasta da base de conhecimento não encontrada: {pasta}")
        artigos: list[Artigo] = []
        problemas: list[str] = []
        ids: set[str] = set()
        for caminho in sorted(pasta.glob("*.md")):
            try:
                artigo = _parse_artigo(caminho)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                problemas.append(f"{caminho.name}: {exc}")
                continue
            if artigo.id in ids:
                problemas.append(f"{caminho.name}: id duplicado '{artigo.id}'")
                continue
            ids.add(artigo.id)
            artigos.append(artigo)
        if not artigos:
            raise ErroBaseConhecimento(
                f"nenhum artigo válido em {pasta}"
                + (f" ({'; '.join(problemas)})" if problemas else "")
            )
        return cls(artigos, problemas)

    def __len__(self) -> int:
        return len(self.artigos)

    def buscar(self, consulta: str, k: int = 3, limiar: float = 1.0) -> list[ArtigoRecuperado]:
        """Top-``k`` artigos com score BM25 ≥ ``limiar``, em ordem decrescente.

        Observação: o IDF do BM25 só é positivo para termos presentes em menos da metade
        dos artigos; bases com um ou dois artigos produzem scores nulos ou negativos.
        """
        tokens = tokenizar(consulta)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ordenados = sorted(range(len(self.artigos)), key=lambda i: scores[i], reverse=True)
        recuperados: list[ArtigoRecuperado] = []
        for indice in ordenados[:k]:
            score = float(scores[indice])
            if score < limiar:
                break
            artigo = self.artigos[indice]
            recuperados.append(
                ArtigoRecuperado(
                    id=artigo.id,
                    titulo=artigo.titulo,
                    categoria=artigo.categoria,
                    score=round(score, 3),
                    trecho=artigo.trecho(),
                )
            )
        return recuperados


@lru_cache(maxsize=4)
def _carregar_cacheada(pasta: str) -> BaseConhecimento:
    return BaseConhecimento.carregar(Path(pasta))


def obter_base(pasta: Path) -> BaseConhecimento:
    """Base carregada uma única vez por pasta (por processo)."""
    return _carregar_cacheada(str(pasta.resolve()))


def montar_consulta(titulo: str, descricao: str, palavras_chave: list[str]) -> str:
    """Consulta do node ``consultar_base``: título + descrição + palavras-chave da análise."""
    return " ".join([titulo, descricao, *palavras_chave])
