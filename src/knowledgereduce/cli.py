"""Command-line interface entrypoint for KnowledgeReduce."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="kr",
    help="KnowledgeReduce: stackable, conflict-aware knowledge graph CLI.",
    no_args_is_help=True,
)


@app.callback()
def main_callback() -> None:
    """KnowledgeReduce CLI root."""


@app.command("version")
def version_command() -> None:
    """Print the installed KnowledgeReduce version."""
    from knowledgereduce import __version__

    typer.echo(f"knowledgereduce {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
