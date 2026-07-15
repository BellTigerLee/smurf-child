#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

uv run pytest tests/rgw-analysis-web/flow tests/rgw-analysis-web/web
tests/rgw-analysis-web/artifacts/test-contracts.sh
tests/rgw-analysis-web/artifacts/test-feature-registry.sh
tests/rgw-analysis-web/images/test-images.sh
tests/rgw-analysis-web/images/test-negative-contracts.sh
tests/rgw-analysis-web/scripts/test-boundaries.sh
tests/rgw-analysis-web/scripts/test-public-scan.sh
tests/rgw-analysis-web/scripts/test-validate-and-build.sh
./scripts/validate-chart.sh
tests/rgw-analysis-web/chart/test-negative-contracts.sh
tests/rgw-analysis-web/artifacts/test-package.sh
