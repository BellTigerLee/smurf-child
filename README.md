# smurf-child

`smurf-child`는 공개 feature source repository다. 현재 `rgw-analysis-web` feature는
결정론적 RGW 분석 flow, 정적 결과 viewer, 독립적인 `flow`/`web` image, Helm chart를
제공한다. Runtime credential, cluster placement, Karmada resource는 이 repository가
소유하지 않는다.

## 구조

- `src/rgw-analysis-web/`: 공개 flow source와 network dependency가 없는 web asset
- `images/rgw-analysis-web/{flow,web}/`: component별 독립 build context
- `charts/rgw-analysis-web/`: cluster-neutral Helm renderer artifact
- `tests/rgw-analysis-web/`: flow, web, image, chart의 로컬 contract test
- `scripts/`: 로컬 test/validate/package helper
- `features.yaml`: feature, renderer, source, image, chart 경로의 machine-readable registry

로컬 검증과 packaging은 [로컬 개발](docs/local-development.md), credential 경계는
[runtime credential](docs/runtime-credentials.md)을 따른다. Repository 선언은 실제
image publication 또는 cluster 배포 성공의 증거가 아니다.

## Image build와 push

`rgw-analysis-web`는 역할과 runtime이 다른 image 두 개를 사용한다.

- `belltigerlee/test-image-flow:0.1.0`: Python 기반 `seed`, `analyze`, `fetch` 실행
- `belltigerlee/test-image-web:0.1.0`: nginx 기반 결과 HTML 제공

이 `0.1.0` image는 수동 개발·검증용이다.

Repository root에서 Docker Compose로 두 image를 한 번에 빌드한다.

```bash
docker compose -f images/docker-compose.build.yaml build
```

빌드된 image 이름을 확인한다.

```bash
docker compose -f images/docker-compose.build.yaml config --images
docker image inspect \
  belltigerlee/test-image-flow:0.1.0 \
  belltigerlee/test-image-web:0.1.0 >/dev/null
```

Docker Hub에 로그인한 다음 두 image를 한 번에 push한다. Password 대신 Docker Hub
access token을 사용하고 token을 파일이나 Git에 저장하지 않는다.

```bash
docker compose -f images/docker-compose.build.yaml config --images
docker login --username belltigerlee
docker compose -f images/docker-compose.build.yaml push
docker logout
```

`config --images` 출력이 의도한 Docker Hub repository와 tag인지 확인한 다음 push한다.
환경 변수나 repository root의 `.env`도 Compose image 좌표를 덮어쓸 수 있으므로 이
확인 단계를 생략하지 않는다.

다른 repository나 version을 사용할 때는 Compose 파일을 수정하지 않고 환경 변수로
덮어쓴다.

```bash
FLOW_IMAGE_REPOSITORY=belltigerlee/test-image-flow \
FLOW_IMAGE_TAG=0.2.0 \
WEB_IMAGE_REPOSITORY=belltigerlee/test-image-web \
WEB_IMAGE_TAG=0.2.0 \
  docker compose -f images/docker-compose.build.yaml build

FLOW_IMAGE_REPOSITORY=belltigerlee/test-image-flow \
FLOW_IMAGE_TAG=0.2.0 \
WEB_IMAGE_REPOSITORY=belltigerlee/test-image-web \
WEB_IMAGE_TAG=0.2.0 \
  docker compose -f images/docker-compose.build.yaml push
```

`images/docker-compose.yaml`은 image build 전용 파일이 아니라 MinIO를 포함한 로컬
동작 확인용 stack이다.
