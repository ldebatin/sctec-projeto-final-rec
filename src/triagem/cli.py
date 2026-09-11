"""Interface de linha de comando (esqueleto; comandos completos na issue #7)."""

import typer

from triagem import __version__

app = typer.Typer(help="Agente Inteligente de Triagem de Chamados Técnicos.", no_args_is_help=True)


@app.callback()
def _raiz() -> None:
    """Força o modo de subcomandos mesmo com um único comando registrado."""


@app.command()
def versao() -> None:
    """Exibe a versão instalada."""
    typer.echo(f"triagem {__version__}")
