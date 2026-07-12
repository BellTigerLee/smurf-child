"""Read-only CLI for the child handoff guard."""

from pathlib import Path

import typer
from pydantic import ValidationError

from smurf_child.handoff import HandoffState, evaluate_handoff

app = typer.Typer(add_completion=False)


@app.command("check")
def guard(state: Path) -> None:
    """Evaluate a measured state document without performing a network write."""
    try:
        measured = HandoffState.model_validate_json(state.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        typer.echo("HANDOFF_REJECTED[INPUT]", err=True)
        raise typer.Exit(code=2) from error
    rejection = evaluate_handoff(measured)
    if rejection is not None:
        typer.echo(f"HANDOFF_REJECTED[{rejection.category.value}]")
        raise typer.Exit(code=1)
    typer.echo("HANDOFF_GUARD_PASS")


def main() -> None:
    """Run the guard command."""
    app()
