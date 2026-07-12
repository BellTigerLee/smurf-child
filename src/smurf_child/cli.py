"""Command-line boundary for child contract validation."""

from pathlib import Path
from typing import Annotated

import typer

from smurf_child.contract import validate_repository
from smurf_child.models import PlannedBehaviorError

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def root() -> None:
    """Inspect the representative child repository contract."""


@app.command()
def validate(
    root: Annotated[
        Path, typer.Option(exists=True, file_okay=False, resolve_path=True)
    ],
) -> None:
    """Validate the child repository contract when Task 4 implements it."""
    try:
        _ = validate_repository(root)
    except PlannedBehaviorError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from None


def main() -> None:
    """Run the child contract command-line application."""
    app()
