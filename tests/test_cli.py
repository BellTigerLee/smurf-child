from pathlib import Path

from typer.testing import CliRunner

from smurf_child.cli import app

runner = CliRunner()


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
