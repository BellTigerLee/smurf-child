import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from smurf_child.cli import app

runner = CliRunner()
_ORIGIN = "git@github.com:BellTigerLee/smurf-child.git"
_PINNED_IMAGE = f"example.invalid/sample@sha256:{'a' * 64}"


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed Git executable in test fixture
        ["/usr/bin/git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _evidence_repository(tmp_path: Path, metadata: str) -> Path:
    root = tmp_path / "child"
    (root / "deploy" / "dev").mkdir(parents=True)
    (root / "smurfx").mkdir()
    _ = (root / "deploy" / "dev" / "deployment.yaml").write_text(
        f"""apiVersion: apps/v1
kind: Deployment
metadata: {{name: sample}}
spec:
  template:
    spec:
      containers:
        - name: sample
          image: {_PINNED_IMAGE}
""",
        encoding="utf-8",
    )
    _ = (root / "smurfx" / "request.yaml").write_text(
        """apiVersion: smurfx.dev/v1alpha1
kind: ChildRequest
developerId: developer-one
childId: child-one
workloadId: workload-one
environment: dev
target: both
""",
        encoding="utf-8",
    )
    _ = (root / "smurfx" / "ci-metadata.yaml").write_text(metadata, encoding="utf-8")
    _ = _git(root, "init", "-q")
    _ = _git(root, "config", "user.email", "test@example.com")
    _ = _git(root, "config", "user.name", "Contract Test")
    _ = _git(root, "remote", "add", "origin", _ORIGIN)
    _ = _git(root, "add", ".")
    _ = _git(root, "commit", "-qm", "fixture")
    return root


_VALID_METADATA = """workflowIssuer: https://token.actions.githubusercontent.com
workflowSubject: repo:BellTigerLee/smurf-child:ref:refs/heads/poc
workflowName: validate
runId: "1001"
buildResult: success
testResult: success
startedAt: "2026-07-12T06:00:00.000000Z"
completedAt: "2026-07-12T06:01:00.000000Z"
"""


def test_validate_reports_success_for_repository_contract() -> None:
    # Given: the representative child repository root.
    repository_root = Path.cwd()

    # When: a developer validates the repository through the installed CLI.
    result = runner.invoke(app, ["validate", "--root", str(repository_root)])

    # Then: the future CLI success narrative is observable.
    assert result.exit_code == 0
    assert "child repository contract valid" in result.stdout


def test_validate_reports_named_error_without_traceback(tmp_path: Path) -> None:
    # Given: a repository root containing a forbidden Namespace object.
    deploy_root = tmp_path / "deploy" / "dev"
    deploy_root.mkdir(parents=True)
    _ = (deploy_root / "namespace.yaml").write_text(
        "apiVersion: v1\nkind: Namespace\nmetadata:\n  name: forbidden\n",
        encoding="utf-8",
    )

    # When: a developer validates the malformed repository.
    result = runner.invoke(app, ["validate", "--root", str(tmp_path)])

    # Then: the future CLI emits a categorized error rather than a traceback.
    assert result.exit_code == 2
    assert "FORBIDDEN_KIND" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "metadata",
    [
        _VALID_METADATA.replace(
            "2026-07-12T06:00:00.000000Z", "2026-99-99T99:99:99.000000Z"
        ),
        _VALID_METADATA.replace("workflowName: validate", 'workflowName: ""'),
        f"{_VALID_METADATA}unknownField: forbidden\n",
    ],
)
def test_evidence_payload_translates_invalid_metadata_without_output(
    metadata: str, tmp_path: Path
) -> None:
    # Given: a clean committed child repository with invalid CI evidence metadata.
    root = _evidence_repository(tmp_path, metadata)
    output = tmp_path / "output" / "evidence.json"

    # When: evidence generation reaches strict boundary validation.
    result = runner.invoke(
        app, ["evidence-payload", "--root", str(root), "--output", str(output)]
    )

    # Then: the typed CLI category is the only observable and no output exists.
    expected = f"EVIDENCE_INPUT:{root / 'smurfx' / 'ci-metadata.yaml'}\n"
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == expected
    assert "Traceback" not in result.stderr
    assert not output.parent.exists()
