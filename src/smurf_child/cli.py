"""Command-line boundary for child contract validation and evidence."""

import os
import tempfile
from pathlib import Path
from typing import Annotated, ClassVar, Literal, NoReturn

import typer
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from smurf_child.bundle import build_bundle
from smurf_child.checkout import CheckoutExpectation, read_head, verify_checkout
from smurf_child.contract import validate_repository
from smurf_child.evidence import EvidenceInput, build_evidence
from smurf_child.models import ContractErrorCategory, ContractValidationError
from smurf_child.yaml_boundary import load_yaml

_CANONICAL_ORIGIN = "git@github.com:BellTigerLee/smurf-child.git"


class CiMetadata(BaseModel):
    """Deterministic workflow metadata supplied by CI."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True, strict=True
    )

    workflow_issuer: str = Field(alias="workflowIssuer")
    workflow_subject: str = Field(alias="workflowSubject")
    workflow_name: str = Field(alias="workflowName")
    run_id: str = Field(alias="runId")
    build_result: Literal["success", "failure"] = Field(alias="buildResult")
    test_result: Literal["success", "failure"] = Field(alias="testResult")
    started_at: str = Field(alias="startedAt")
    completed_at: str = Field(alias="completedAt")


app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def root() -> None:
    """Inspect the representative child repository contract."""


def _fail(error: ContractValidationError) -> NoReturn:
    typer.echo(str(error), err=True)
    raise typer.Exit(code=2)


@app.command()
def validate(
    root: Annotated[
        Path, typer.Option(exists=True, file_okay=False, resolve_path=True)
    ],
) -> None:
    """Validate the child request and namespace-neutral manifest bundle."""
    try:
        result = validate_repository(root)
    except ContractValidationError as error:
        _fail(error)
    typer.echo(
        f"child repository contract valid bundleDigest={result.manifests.bundle_digest}"
    )


@app.command("evidence-payload")
def evidence_payload(
    root: Annotated[
        Path, typer.Option(exists=True, file_okay=False, resolve_path=True)
    ],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    """Write canonical unsigned evidence payload bytes atomically."""
    try:
        metadata_value = load_yaml(
            root / "smurfx" / "ci-metadata.yaml", ContractErrorCategory.EVIDENCE_INPUT
        )
        try:
            metadata = CiMetadata.model_validate(metadata_value)
        except ValidationError as error:
            raise ContractValidationError(
                ContractErrorCategory.EVIDENCE_INPUT,
                root / "smurfx" / "ci-metadata.yaml",
            ) from error
        head = read_head(root)
        checkout = verify_checkout(
            root, CheckoutExpectation(_CANONICAL_ORIGIN, head, "deploy/dev")
        )
        bundle = build_bundle(root, checkout.manifest_paths)
        evidence = build_evidence(
            EvidenceInput(
                workflow_issuer=metadata.workflow_issuer,
                workflow_subject=metadata.workflow_subject,
                workflow_name=metadata.workflow_name,
                run_id=metadata.run_id,
                repository=checkout.repository,
                path="deploy/dev",
                sha=checkout.head_sha,
                build_result=metadata.build_result,
                test_result=metadata.test_result,
                bundle_digest=bundle.digest,
                image_digests=tuple(
                    image.rsplit("@", maxsplit=1)[1] for image in bundle.images
                ),
                started_at=metadata.started_at,
                completed_at=metadata.completed_at,
            )
        )
    except ContractValidationError as error:
        _fail(error)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.name}."
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            _ = stream.write(evidence.payload)
            stream.flush()
            os.fsync(stream.fileno())
        _ = temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    typer.echo(f"evidence payload written evidenceDigest={evidence.digest}")


def main() -> None:
    """Run the child contract command-line application."""
    app()
