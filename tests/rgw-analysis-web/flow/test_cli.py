import pytest
from smurf_flow.cli import app
from typer.testing import CliRunner

from smurf_flow import __version__


def test_package_exports_version_when_imported() -> None:
    # Given: the feature-scoped installed package
    # When/Then: its public version matches project metadata
    assert __version__ == "0.1.0"


def test_cli_help_exposes_exact_pipeline_commands() -> None:
    # Given: the public RGW flow CLI
    runner = CliRunner()

    # When: base and command help are requested
    base = runner.invoke(app, ["--help"])
    commands = tuple(
        runner.invoke(app, [command, "--help"])
        for command in ("seed", "analyze", "fetch")
    )

    # Then: all three real surfaces are discoverable and successful
    assert base.exit_code == 0
    assert all(command in base.output for command in ("seed", "analyze", "fetch"))
    assert all(result.exit_code == 0 for result in commands)


def test_missing_config_is_redacted_when_command_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: no S3 configuration and credential sentinels in the environment
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "PLAN_TEST_ACCESS")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "PLAN_TEST_SECRET")
    runner = CliRunner()

    # When: a command crosses the configuration boundary
    result = runner.invoke(app, ["seed", "run-1"])

    # Then: it fails safely without exposing either credential
    assert result.exit_code == 2
    assert "configuration or run ID is invalid" in result.output
    assert "PLAN_TEST_ACCESS" not in result.output
    assert "PLAN_TEST_SECRET" not in result.output
