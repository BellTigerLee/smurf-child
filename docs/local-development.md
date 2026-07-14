# 로컬 개발과 검증

Python 3.13과 `uv`, Helm 3가 필요하다. Dependency와 lockfile을 임의로 갱신하지 않고
다음 frozen gate를 실행한다.

```bash
uv lock --check
uv sync --frozen
uv run --frozen ruff format --check .
uv run --frozen ruff check .
uv run --frozen basedpyright
./scripts/test.sh
```

`scripts/test.sh`는 fake S3 flow, web output contract, image context, Helm lint/render와
package contract를 검증한다. 실제 image가 필요하면 full source SHA를 지정해
`SOURCE_REVISION=<40-hex> scripts/rgw-analysis-web/build-images.sh`를 실행한다.
Compose는 local-only MinIO credential과 digest-pinned MinIO image를 환경 변수로 받아
render/build하며 그 값은 commit하지 않는다.

`scripts/package-chart.sh`는 이미 registry가 반환한 두 component digest를 받을 때만
chart와 `scalex.io/promotion/v1` metadata를 `dist/rgw-analysis-web/`에 만든다. Script는
cluster나 Karmada API에 연결하지 않는다.
