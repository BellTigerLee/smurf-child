"""Safe CLI boundary for the RGW analysis flow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from pydantic import ValidationError

from smurf_flow.errors import FlowError
from smurf_flow.flow import FlowRuntime, analyze_run, fetch_run, seed_run
from smurf_flow.models import (
    RunPaths,
    StorageSettings,
    WebAssetSettings,
    parse_run_id,
)
from smurf_flow.polling import MarkerWait, SystemPoller
from smurf_flow.render import WebAssets
from smurf_flow.storage import BotoObjectStore

if TYPE_CHECKING:
    from collections.abc import Callable

app = typer.Typer(
    name="smurf-flow",
    help="Seed, analyze, and fetch an immutable RGW analysis run.",
    no_args_is_help=True,
)


def _runtime(run_id: str, marker_kind: str) -> FlowRuntime:
    parsed_run_id = parse_run_id(run_id)
    settings = StorageSettings.model_validate({})
    web_asset_settings = WebAssetSettings.model_validate({})
    paths = RunPaths(run_id=parsed_run_id)
    marker_key = paths.input_marker if marker_kind == "input" else paths.output_marker
    return FlowRuntime(
        store=BotoObjectStore.from_settings(settings),
        paths=paths,
        wait=MarkerWait(
            key=marker_key,
            timeout_seconds=settings.wait_seconds,
            interval_seconds=settings.poll_interval_seconds,
        ),
        poller=SystemPoller(),
        web_assets=WebAssets(directory=web_asset_settings.directory),
    )


def _execute(action: Callable[[], str]) -> None:
    try:
        message = action()
    except ValidationError:
        typer.echo("configuration or run ID is invalid", err=True)
        raise typer.Exit(code=2) from None
    except FlowError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None
    typer.echo(message)


@app.command()
def seed(
    run_id: Annotated[str, typer.Argument(help="Immutable lowercase run ID.")],
) -> None:
    """Create the deterministic dataset and input marker."""

    def action() -> str:
        runtime = _runtime(run_id, "input")
        marker = seed_run(runtime)
        return f"seeded {marker.run_id}"

    _execute(action)


@app.command()
def analyze(
    run_id: Annotated[str, typer.Argument(help="Immutable lowercase run ID.")],
) -> None:
    """Wait for verified CSV inputs and publish analysis outputs."""

    def action() -> str:
        runtime = _runtime(run_id, "input")
        marker = analyze_run(runtime)
        return f"analyzed {marker.run_id}"

    _execute(action)


@app.command()
def fetch(
    run_id: Annotated[str, typer.Argument(help="Immutable lowercase run ID.")],
    output_directory: Annotated[
        Path | None,
        typer.Option("--output-directory", file_okay=False),
    ] = None,
) -> None:
    """Wait for verified outputs and atomically sync the static result."""

    def action() -> str:
        runtime = _runtime(run_id, "output")
        target = output_directory or Path("/usr/share/nginx/html")
        result_path, index_path = fetch_run(runtime, target)
        return f"fetched {result_path.name} and {index_path.name}"

    _execute(action)
