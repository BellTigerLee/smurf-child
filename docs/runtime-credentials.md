# Runtime credential 경계

Public source, image, chart, promotion metadata에는 access key, secret key, kubeconfig 또는
cluster-specific 설정을 넣지 않는다. Helm values는 Secret의 이름과 key contract만
받는다.

배포 시스템은 workload를 reconcile하기 전에 release namespace에 native Kubernetes
`Secret`을 준비한다. Secret의 생성 원본은 Rook-Ceph ObjectBucketClaim, 외부 secret
backend 또는 운영 bootstrap일 수 있지만, 선택과 동기화 방식은 Infra/Federation 경계가
소유한다. Child chart는 `.Values.credentials.existingSecret`과 key 이름으로 이미 존재하는
Secret을 참조할 뿐 `Secret`, `ExternalSecret`, `ObjectBucketClaim`을 렌더링하지 않는다.

여러 member cluster에 배포할 때 credential 복제도 배포 시스템의 책임이다. Child는
특정 cluster 이름, OBC 이름, SecretStore 또는 credential 전달 구현을 가정하지 않는다.

로컬 검증의 `scripts/rgw-analysis-web/scan-public-artifacts.sh`는 Git이 공개 대상으로
인식하는 전체 tree를 검사한다. `.env*`, kubeconfig, private key/certificate, SSH 및
cloud credential 경로는 Git과 모든 image build context에서 제외되며, 강제로 tracked된
경우 filename 또는 고신뢰 signature 검사에서 실패한다. Scanner는 검출된 경로만
보고하고 credential로 의심되는 파일 내용은 출력하지 않는다.
