# Runtime credential 경계

Public source, image, chart, promotion metadata에는 access key, secret key, kubeconfig 또는
cluster-specific 설정을 넣지 않는다. Helm values는 Secret의 이름과 key contract만
받는다.

ScaleX Federation은 External Secrets Operator를 통해 `SecretStore`
`scalex-cuty-rgw-analysis-web`의 external key
`scalex/cuty/rgw-analysis-web/rgw`를 target Secret `scalex-cuty-rgw`로 materialize한다.
실제 값과 store backend 구성은 Infra Layer가 소유한다. Child CI가 사용하는 GitHub App
credential은 PR 생성만 허용하고 runtime이나 cluster credential로 재사용하지 않는다.

CI는 Git이 공개 대상으로 인식하는 전체 tree를 검사한다. `.env*`, kubeconfig, private
key/certificate, SSH 및 cloud credential 경로는 Git과 모든 image build context에서
제외되며, 강제로 tracked된 경우 filename 또는 고신뢰 signature 검사에서 실패한다.
Scanner는 검출된 경로만 보고하고 credential로 의심되는 파일 내용은 출력하지 않는다.
