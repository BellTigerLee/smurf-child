# CI, version, promotion

Pull Request workflow는 frozen Python gate, `scripts/test.sh`, workflow/action pin,
promotion dry-run, Compose render, chart/package, public credential scan을 수행한다.
Workflow의 존재는 hosted run이 수행됐다는 뜻이 아니다.

`main` push만 검증 후 다음 image를 서로 독립적으로 build한다. Pull Request와
`workflow_dispatch`, `release/**` branch는 registry publication이나 promotion을 실행하지
않는다. 수동 검증은 read-only validation workflow를 사용한다.

- `ghcr.io/belltigerlee/smurf-child-flow:sha-<full-commit>@sha256:<digest>`
- `ghcr.io/belltigerlee/smurf-child-web:sha-<full-commit>@sha256:<digest>`

`main`에 한해 `latest` alias도 publication 편의를 위해 붙인다. `latest`는 promotion
metadata, Federation values, rollback coordinate에 절대 사용하지 않는다. BuildKit의
SBOM/provenance도 image와 함께 생성하지만 별도의 signing key가 없으므로 서명됐다고
주장하지 않는다.

두 immutable image publication과 검증이 모두 성공하면 GitHub App의 단기 token을
사용한다. 필요한 repository secret 이름은 `SCALEX_PROMOTION_APP_ID`와
`SCALEX_PROMOTION_APP_PRIVATE_KEY`다. Tower가 bootstrap source로 소비하고 local
origin과 일치하는 authority는 정확히
`https://github.com/SJoon99/scalex-federation.git`이다. GitHub target은
`SJoon99/scalex-federation`, chart path는 `charts/rgw-analysis-web`, 같은 repository의
bot branch는 `automation/cuty-rgw-analysis-web`이다. 별도 fork flow를 만들지 않는다.
Promotion은 `releases/cuty/rgw-analysis-web/release.yaml`과 `values.yaml`만 갱신한다.
기존 `releases/poc/rgw-analysis-web` release는 읽거나 변환하거나 stage하지 않는다.

`features.yaml`의 `renderer`가 `helm/v1`일 때만 renderer-specific helper가 source full
SHA와 `flow`/`web` tag+digest를 하나의 PR에 반영한다. 알 수 없는 renderer는 변환하지
않고 실패한다. Federation release가 `pinned`면 아무 파일도 바꾸지 않고, `tracked`면
열려 있는 bot PR을 재사용한다. CI는 merge하지 않는다. Protected branch의 수동 review와
merge가 반드시 필요하며 child workflow는 apply, Argo sync, Karmada/member cluster 호출을
하지 않는다.

Rollback은 Federation Git history에서 이전의 full child SHA와 두 image digest를 함께
복원하는 review PR로 수행한다. Tag만 되돌리거나 `latest`를 선택하는 것은 rollback이
아니다.
