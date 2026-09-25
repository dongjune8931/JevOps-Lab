# M1 로컬 관측 baseline 실행

M1의 범위는 합성 트래픽의 metrics·logs·traces 수집과 로컬 alert 전달이다. Jev adapter, Context Builder, 규칙 기반 triage 분류기, chaos fault와 평가 데이터셋은 후속 milestone 범위다.

현재 코드는 M2에서 checkout replica 2개·headless dependency·합성 앱 종료 유예 2초를 추가했다. M1 당시 결과는 그대로 보존하며, 추가 실행 요구량과 Chaos Mesh 경계는 [M2 안내](M2-CHAOS.md)를 따른다.

## 실행 환경

- 기존 로컬 Docker daemon이 필요하다. Unix socket만 허용하며 원격 Docker endpoint는 거부한다.
- `kind v0.31.0`, `kubectl v1.36.0`과 Python 3.10 이상을 사용한다. 컨테이너 안의 Python은 3.12.10이다.
- 이미지 버전은 [`versions.json`](../deploy/versions.json), Python의 직접·전이 의존성은 [`requirements.txt`](../src/requirements.txt)에 고정했다. Helm chart는 사용하지 않는다.
- 최초 실행에는 공개 이미지와 PyPI 패키지 다운로드가 필요하다. 클라우드 계정, SaaS 계정, Jev key는 필요 없다.
- 컨테이너 메모리 limit 합계는 3 GiB다. Kubernetes/Docker VM 여유를 포함해 로컬 Docker에 최소 6 GiB를 확보하는 것을 권장한다. 검증 Job은 추가 128 MiB를 사용한다.
- 검증된 환경과 실제 이미지 ID는 검증 결과에 기록한다. 호스트 Docker·Python 버전 차이는 결과와 함께 남긴다.

셸의 alias나 버전 선택 shim과 Python subprocess가 사용하는 `kubectl`이 다를 수 있다. 실제 선택 경로는 다음으로 확인한다.

```bash
python3 -c 'import shutil, subprocess; print(shutil.which("kubectl")); subprocess.run(["kubectl", "version", "--client"])'
```

## 실행 순서

저장소 루트에서 프로젝트 폴더로 이동한다.

```bash
cd projects/P001-jevops-signal-triage
python3 scripts/lab.py test
python3 scripts/lab.py start
python3 scripts/lab.py verify
python3 scripts/lab.py dashboard
```

`dashboard` 실행 중 http://127.0.0.1:13000/d/p001-baseline 에 접속한다. 익명 Viewer만 제공하며 admin 계정·비밀번호를 생성하지 않는다. 종료는 Ctrl-C다. 확인 후 반드시 정리한다.

```bash
python3 scripts/lab.py teardown
```

- 클러스터는 `p001-m1`, namespace는 `p001`로 고정한다.
- `.local/kubeconfig`와 명시적 `kind-p001-m1` context만 사용한다. 사용자의 기본 kubeconfig와 current-context는 수정하지 않는다.
- Docker context를 지정하려면 `P001_DOCKER_CONTEXT`를 사용한다. `DOCKER_HOST`가 설정되어 있으면 실행을 거부한다.
- 기존 동명 클러스터가 있으면 start가 중단된다. 저장소별 소유 기록과 Docker context가 맞아야 verify·teardown을 실행할 수 있다.
- `render`는 클러스터 접근 없이 Kubernetes JSON을 출력한다.

## 구성과 데이터 경로

```text
traffic (2초에 1회) → checkout → catalog → inventory
                         └──────── OTLP/HTTP ────────┐
                                             Collector
                          ┌───────────────────────┼────────────────┐
                          ▼                       ▼                ▼
                     Prometheus                 Tempo            Loki
                          │                       └──── Grafana ───┘
                     Alertmanager → webhook (최근 100개만 메모리 보관)
```

3개 서비스는 동일한 이미지와 서로 다른 서비스명·dependency 설정을 사용한다. `/work`만 계측하고 `/healthz`는 계측에서 제외한다. W3C trace context를 다음 서비스에 전달한다. 응답에는 생성된 trace ID가 포함되며 로그에는 고정 메시지와 서비스명·status·trace ID만 기록한다.

Collector는 OTLP metrics를 Prometheus exporter에 노출하고 Prometheus가 5초마다 scrape한다. 로그는 Loki의 native OTLP endpoint, trace는 Tempo의 OTLP endpoint로 보낸다. Dashboard는 request rate·error ratio·p95 duration·logs·traces의 5개 패널이다. latency histogram은 초 단위 bucket 경계를 사용하며 성공 요청만 있는 동안 error ratio는 0을 표시한다.

`P001SyntheticTraffic`은 트래픽이 수집되면 발생하는 **전달 경로 확인용 alert**다. 정상 트래픽을 장애로 분류하는 규칙이나 M3의 triage baseline이 아니다. 외부 paging·메일·Slack 연동 없이 `webhook:8080/alerts`에만 전달한다.

## 검증이 확인하는 것

`test`는 네트워크가 차단된 일회성 컨테이너에서 배포 경계, remote endpoint 거부, 소유 기록, webhook payload 제한·allowlist·잘못된 batch의 원자성을 검사한다. 빌드 중 `pip check`도 실행한다.

`verify`는 다음을 실제 로컬 클러스터에서 확인한다.

1. 모든 Deployment readiness와 Kubernetes server-side manifest dry-run.
2. 3개 서비스의 요청 counter 및 recording rule, 정상 Prometheus scrape target.
3. `/work`가 반환한 동일 trace ID의 Tempo trace에 3개 서비스가 모두 포함됨.
4. 같은 trace ID로 조회한 Loki 로그에 3개 서비스가 모두 포함됨.
5. Grafana에 3개 datasource·5개 dashboard panel·Loki → Tempo 링크가 provisioning됨.
6. Prometheus → Alertmanager → 로컬 webhook에 `P001SyntheticTraffic` firing 이벤트가 도달함.

검증 Job에는 240초 deadline과 재시도 0회를 지정한다. 실패한 Job은 로그 확인을 위해 teardown까지 남긴다. `.local/verify-*.json`에는 실행 시각·commit·dirty 상태·소스 checksum·버전·실제 이미지 ID와 결과를 보존한다. `.local/`는 kubeconfig 등 로컬 데이터를 포함하므로 통째로 커밋하지 않는다. 공유할 결과는 비밀정보 없이 검토한 JSON만 `results/`에 복사한다.

## 보안과 리소스 정리

- 모든 Service는 ClusterIP이며 대시보드 포워딩은 127.0.0.1에만 바인딩한다.
- Pod는 non-root, read-only root filesystem, capability drop, service-account token 미마운트를 적용한다.
- telemetry는 합성 데이터만 사용한다. 요청 header·본문·IP·원문 예외는 수집하지 않는다. M3의 범용 telemetry 마스킹 기능은 아직 구현하지 않았다.
- Grafana·Tempo·Loki의 usage reporting과 Grafana update check를 끈다. Kubernetes 네트워크 정책으로 egress를 강제 차단하는 구성은 아니다.
- backend 데이터는 크기가 제한된 `emptyDir`에 저장되며 재시작·teardown 시 사라진다. 영구 저장·고가용성을 제공하지 않는다.
- `teardown`은 소유 기록이 일치하는 `p001-m1` kind 클러스터만 삭제하고 해당 node container·volume이 남지 않았는지 확인한다.
- 이미지·빌드 캐시와 공유 `kind` Docker network는 다른 프로젝트가 재사용할 수 있으므로 보존한다. API 과금·상시 실행 프로세스는 남기지 않는다.
- start가 중간에 실패해도 소유 기록이 남아 있어 같은 teardown 명령을 사용할 수 있다. 정리 실패 시 추가 삭제 대신 남은 정확한 리소스를 보고한다.

## 문제 확인

아래 명령은 모두 프로젝트 전용 kubeconfig와 context를 명시한다.

```bash
kubectl --kubeconfig .local/kubeconfig --context kind-p001-m1 -n p001 get pods
kubectl --kubeconfig .local/kubeconfig --context kind-p001-m1 -n p001 logs deployment/collector
kubectl --kubeconfig .local/kubeconfig --context kind-p001-m1 -n p001 get jobs
```

포트 충돌 시 기존 프로세스를 종료하지 말고 포워딩 명령의 로컬 포트를 변경한다. 이 랩은 별도 Kubernetes cluster이므로 이미 실행 중인 실습 환경의 namespace나 컨테이너를 수정할 필요가 없다.

## 참고

- [OTel Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [Loki native OTLP 수집](https://grafana.com/docs/loki/latest/send-data/otel/)
- [kind quick start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
