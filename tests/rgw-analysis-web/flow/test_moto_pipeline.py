from pathlib import Path

import pytest
from boto3.session import Session
from moto import mock_aws
from smurf_flow.cli import app
from smurf_flow.flow import FlowRuntime, analyze_run, fetch_run, seed_run
from smurf_flow.models import RunPaths, parse_run_id
from smurf_flow.polling import MarkerWait
from smurf_flow.render import WebAssets
from smurf_flow.storage import BotoObjectStore
from typer.testing import CliRunner

WEB_ASSETS = Path(__file__).parents[3] / "src" / "rgw-analysis-web" / "web"


class ImmediatePoller:
    """Deterministic poller for markers that already exist."""

    def monotonic(self) -> float:
        return 0.0

    def sleep(self, seconds: float) -> None:
        raise AssertionError(seconds)


def test_boto_adapter_pipeline_round_trips_against_moto(tmp_path: Path) -> None:
    # Given: an isolated S3-compatible SDK sandbox and typed adapter
    with mock_aws():
        client = Session().client("s3", region_name="us-east-1")
        _ = client.create_bucket(Bucket="flow-bucket")
        store = BotoObjectStore(client=client, bucket="flow-bucket")
        paths = RunPaths(run_id=parse_run_id("integration-1"))
        input_runtime = FlowRuntime(
            store=store,
            paths=paths,
            wait=MarkerWait(
                key=paths.input_marker,
                timeout_seconds=1,
                interval_seconds=0.1,
            ),
            poller=ImmediatePoller(),
            web_assets=WebAssets(directory=WEB_ASSETS),
        )

        # When: seed, analyze, idempotent replay, and fetch run end to end
        first_seed = seed_run(input_runtime)
        second_seed = seed_run(input_runtime)
        first_analysis = analyze_run(input_runtime)
        second_analysis = analyze_run(input_runtime)
        output_runtime = FlowRuntime(
            store=store,
            paths=paths,
            wait=MarkerWait(
                key=paths.output_marker,
                timeout_seconds=1,
                interval_seconds=0.1,
            ),
            poller=ImmediatePoller(),
            web_assets=WebAssets(directory=WEB_ASSETS),
        )
        result_path, index_path = fetch_run(output_runtime, tmp_path)

        # Then: immutable replay and exact viewer outputs are observable
        assert first_seed == second_seed
        assert first_analysis == second_analysis
        assert result_path.read_bytes() == (
            b'{"amountAverage":"30.00","amountSum":"150.00","rowCount":5}\n'
        )
        assert b"RGW Analysis Result" in index_path.read_bytes()
        assert tuple(tmp_path.glob(".*.tmp")) == ()


def test_cli_pipeline_runs_through_public_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the real CLI configured for an isolated SDK sandbox
    with mock_aws():
        endpoint = "https://s3.amazonaws.com"
        bucket = "cli-flow-bucket"
        monkeypatch.setenv("S3_ENDPOINT_URL", endpoint)
        monkeypatch.setenv("S3_BUCKET", bucket)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "fake")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake")
        monkeypatch.setenv("SMURF_WEB_ASSETS_PATH", str(WEB_ASSETS))
        client = Session().client("s3", region_name="us-east-1")
        _ = client.create_bucket(Bucket=bucket)
        runner = CliRunner()

        # When: a user invokes each public command in order
        seed = runner.invoke(app, ["seed", "cli-1"])
        analyze = runner.invoke(app, ["analyze", "cli-1"])
        fetch = runner.invoke(
            app,
            ["fetch", "cli-1", "--output-directory", str(tmp_path)],
        )

        # Then: commands succeed and publish the observable static result
        assert seed.exit_code == 0
        assert analyze.exit_code == 0
        assert fetch.exit_code == 0
        assert "seeded cli-1" in seed.output
        assert "analyzed cli-1" in analyze.output
        assert "fetched result.json and index.html" in fetch.output
        assert (tmp_path / "current").is_symlink()
        assert (tmp_path / "current" / "result.json").is_file()
        assert (tmp_path / "current" / "index.html").is_file()
