"""Interface de linha de comando (RF-05, RF-71, RF-72; decisão D2 do PRD).

Códigos de saída: 0 para triagem concluída (inclusive fallback controlado);
2 para erro de configuração ou de uso.
"""

from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from triagem import __version__
from triagem.config import ErroConfiguracao, carregar_configuracao
from triagem.grafo import diagrama_mermaid, executar_triagem
from triagem.llm import criar_llm
from triagem.modelos import ResultadoTriagem
from triagem.observabilidade import criar_registro

app = typer.Typer(
    help="Agente Inteligente de Triagem de Chamados Técnicos.",
    no_args_is_help=True,
    rich_markup_mode=None,
)

PASTA_EXEMPLOS_PADRAO = Path("data/exemplos")


class Formato(str, Enum):
    json = "json"
    texto = "texto"


@app.callback()
def _raiz() -> None:
    """Força o modo de subcomandos mesmo com um único comando registrado."""


@app.command()
def versao() -> None:
    """Exibe a versão instalada."""
    typer.echo(f"triagem {__version__}")


# ---------------------------------------------------------------------------
# triar
# ---------------------------------------------------------------------------


def _ler_entrada(
    arquivo: Path | None,
    titulo: str | None,
    descricao: str | None,
    servico: str | None,
    ambiente: str | None,
    solicitante: str | None,
) -> tuple[object, str]:
    """Monta a entrada bruta (dict ou texto inválido) e a origem para o log."""
    if arquivo is not None:
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except OSError as exc:
            raise typer.BadParameter(f"não foi possível ler {arquivo}: {exc}") from exc
        try:
            return json.loads(texto), f"arquivo:{arquivo.name}"
        except json.JSONDecodeError as exc:
            # Entrada inválida é cenário tratado pelo grafo, não erro de uso.
            return f"json inválido em {arquivo.name}: {exc.msg} (linha {exc.lineno})", (
                f"arquivo:{arquivo.name}"
            )
    if titulo is None and descricao is None:
        raise typer.BadParameter("informe --arquivo ou --titulo e --descricao")
    entrada: dict[str, object] = {"titulo": titulo, "descricao": descricao}
    if servico is not None:
        entrada["servico"] = servico
    if ambiente is not None:
        entrada["ambiente"] = ambiente
    if solicitante is not None:
        entrada["solicitante"] = solicitante
    return entrada, "argumentos"


def _formatar_texto(resultado: ResultadoTriagem) -> str:
    linhas = [
        f"Triagem {resultado.run_id}",
        f"Rota: {resultado.rota} | Categoria: {resultado.categoria.value} | "
        f"Prioridade: {resultado.prioridade.value}",
        "Revisão humana: "
        + (
            "sim (" + ", ".join(resultado.motivo_revisao) + ")"
            if resultado.requer_revisao_humana
            else "não"
        ),
        f"Resumo: {resultado.resumo}",
        f"Ação sugerida: {resultado.acao_sugerida}",
    ]
    if resultado.justificativa:
        linhas.append(f"Justificativa: {resultado.justificativa}")
    if resultado.fontes_contexto:
        linhas.append("Fontes de contexto: " + ", ".join(resultado.fontes_contexto))
    if resultado.tool_resultado is not None:
        tool = resultado.tool_resultado
        estado = "ok" if tool.ok else f"falha ({tool.erro})"
        linhas.append(
            f"Tool catálogo: {estado}"
            + (f" | equipe: {tool.equipe_responsavel}" if tool.equipe_responsavel else "")
        )
    if resultado.alertas:
        linhas.append("Alertas: " + ", ".join(resultado.alertas))
    if resultado.erros:
        linhas.append("Erros: " + " | ".join(resultado.erros))
    linhas.append("Caminho: " + " -> ".join(resultado.caminho_percorrido))
    if resultado.modelo:
        linhas.append(f"Modelo: {resultado.modelo}")
    return "\n".join(linhas)


@app.command()
def triar(
    arquivo: Annotated[
        Path | None, typer.Option("--arquivo", "-a", help="Arquivo JSON com o chamado.")
    ] = None,
    titulo: Annotated[str | None, typer.Option("--titulo", "-t")] = None,
    descricao: Annotated[str | None, typer.Option("--descricao", "-d")] = None,
    servico: Annotated[str | None, typer.Option("--servico")] = None,
    ambiente: Annotated[
        str | None, typer.Option("--ambiente", help="producao | homologacao | desenvolvimento")
    ] = None,
    solicitante: Annotated[str | None, typer.Option("--solicitante")] = None,
    formato: Annotated[Formato, typer.Option("--formato", "-f")] = Formato.json,
    salvar: Annotated[
        Path | None, typer.Option("--salvar", help="Grava o resultado em JSON neste caminho.")
    ] = None,
    env: Annotated[Path, typer.Option("--env", help="Arquivo .env a carregar.")] = Path(".env"),
    sem_logs: Annotated[
        bool, typer.Option("--sem-logs", help="Não imprime os logs de execução em stderr.")
    ] = False,
) -> None:
    """Executa a triagem de um chamado (arquivo JSON ou argumentos) e imprime a saída."""
    entrada, origem = _ler_entrada(arquivo, titulo, descricao, servico, ambiente, solicitante)

    try:
        cfg = carregar_configuracao(env)
        llm = criar_llm(cfg)
    except ErroConfiguracao as exc:
        typer.echo(f"Erro de configuração: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    registro = criar_registro(cfg, stderr=not sem_logs)
    resultado = executar_triagem(entrada, cfg=cfg, llm=llm, registro=registro, origem=origem)

    saida_json = resultado.model_dump_json(indent=2)
    if salvar is not None:
        salvar.parent.mkdir(parents=True, exist_ok=True)
        salvar.write_text(saida_json + "\n", encoding="utf-8")

    typer.echo(saida_json if formato is Formato.json else _formatar_texto(resultado))
    if registro.caminho_arquivo is not None:
        typer.echo(f"log: {registro.caminho_arquivo}", err=True)


# ---------------------------------------------------------------------------
# exemplos e grafo
# ---------------------------------------------------------------------------


@app.command()
def exemplos(
    pasta: Annotated[Path, typer.Option("--pasta", help="Pasta com os chamados de exemplo.")] = (
        PASTA_EXEMPLOS_PADRAO
    ),
) -> None:
    """Lista os chamados de exemplo disponíveis (um por linha, com o cenário que ilustram)."""
    arquivos = sorted(pasta.glob("*.json")) if pasta.is_dir() else []
    if not arquivos:
        typer.echo(f"Nenhum exemplo encontrado em {pasta}.")
        return
    for caminho in arquivos:
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            typer.echo(f"{caminho.name}: (inválido: {exc})")
            continue
        if isinstance(dados, dict):
            cenario = dados.get("_cenario") or dados.get("titulo") or ""
        else:
            cenario = "(conteúdo não é um objeto)"
        typer.echo(f"{caminho.name}: {cenario}")


@app.command()
def grafo() -> None:
    """Imprime o diagrama Mermaid do grafo LangGraph (para o README)."""
    typer.echo(diagrama_mermaid())


def main() -> None:  # pragma: no cover
    app(prog_name="triagem")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
