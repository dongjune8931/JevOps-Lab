# P001 — JevOps Signal Triage

## 상태

`active`

M1 무료 로컬 관측 baseline을 구현·검증했다. 3개 합성 서비스의 metrics·logs·traces, Grafana provisioning, Alertmanager 로컬 webhook이 동작한다. Jev 호출, chaos 주입과 triage 성능 평가는 아직 수행하지 않았다.

후속 순서는 로컬 M2~M4 → M4a 첫 AWS 통합 테스트 → M5 로컬·AWS 비교 평가 → M6 운영 화면 → M7 최종 AWS 검증(선택)이다. AWS 실행은 별도 비용 승인 후 진행하며 세부 조건은 [PLAN.md](PLAN.md)에 기록한다.

## 실행 및 검증

실행 환경, 고정 버전, 구성 상세와 문제 확인은 [M1 로컬 실행 안내](docs/M1-LOCAL.md)를 따른다.

```bash
cd projects/P001-jevops-signal-triage
python3 scripts/lab.py test
python3 scripts/lab.py start
python3 scripts/lab.py verify
python3 scripts/lab.py dashboard
# 대시보드 확인 후 Ctrl-C
python3 scripts/lab.py teardown
```

로컬 전용 `p001-m1` kind 클러스터와 `.local/kubeconfig`를 사용한다. 실험 후 teardown까지 수행한다. [M1 검증 기록](docs/M1-VALIDATION.md)에서 실제 결과와 실행 중 발견한 문제를 확인할 수 있다.

## 요약

JevOps Signal Triage는 모니터링 경보가 발생했을 때 관련 메트릭·로그·트레이스·Kubernetes 이벤트·변경 이력을 제한된 상태 객체로 구성하고, Jev가 장애 유형, 심각도, 담당 영역, 다음 조사 신호와 runbook 후보를 타입 있는 값으로 판단하도록 하는 DevOps 모니터링 보조 프로젝트다.

카오스 엔지니어링은 제품의 전면 기능이 아니라 정답이 알려진 장애를 반복해서 만드는 평가 장치로 사용한다. 이를 통해 Jev의 판단을 실제 주입 장애와 비교하고 정확도, calibration, latency, 비용과 실패 양상을 측정한다.

## 해결하려는 DevOps 문제

모니터링 시스템은 이상을 감지하고 많은 경보를 만들 수 있지만, 온콜 엔지니어는 여전히 다음 질문에 답해야 한다.

- 이 경보는 어떤 종류의 장애인가?
- 실제 사용자 영향과 긴급도는 어느 정도인가?
- 어떤 서비스나 의존성을 먼저 조사해야 하는가?
- 어느 팀이 소유해야 하는가?
- 어떤 runbook이 가장 적절한가?
- 증거가 부족해 사람의 검토가 필요한가?
- 여러 경보가 같은 incident의 증상인가?

이 프로젝트는 경보 감지 자체를 대체하지 않고, 감지 이후 triage에 걸리는 시간과 반복적인 판단 비용을 줄일 수 있는지 검증한다.

## 핵심 가설

1. 결정적으로 집계되고 마스킹된 다중 telemetry 상태를 Jev에 제공하면, 메트릭 임계치 규칙만 사용할 때보다 장애 유형과 조사 우선순위를 더 정확하게 분류할 수 있다.
2. Jev의 probability와 confidence를 이용하면 불확실한 판단을 사람에게 넘기면서 높은 신뢰 구간의 triage 일부를 자동화할 수 있다.
3. 카오스로 생성한 ground truth를 사용하면 공급자 주장과 별개로 실제 DevOps 시나리오에서 정확도, calibration, latency, 비용을 재현 가능하게 평가할 수 있다.

가설을 검증하기 전에는 성능 향상이나 운영 효과를 프로젝트 성과로 주장하지 않는다.

## 범위

### 포함

- Alertmanager 경보를 시작점으로 하는 triage 흐름
- 메트릭, 로그, 트레이스, Kubernetes 및 변경 이력의 제한된 context 구성
- Jev Choice, Score, Noul 질문 설계
- 카오스 기반 ground truth 장애 생성과 결과 레코딩
- 규칙 기반 baseline과 Jev 비교
- 선택적으로 일반 LLM baseline 비교
- confidence threshold별 자동화 가능 범위 평가
- Grafana에서 입력 신호, Jev 판단, ground truth와 결과 시각화

### 제외

- 새로운 time-series anomaly detection 모델 개발
- Jev가 직접 장애를 주입, 복구 또는 운영 명령을 실행하는 기능
- Jev가 자유 형식 runbook이나 Kubernetes manifest를 생성하는 기능
- 프로덕션 환경 장애 주입
- 사람 승인 없는 자동 복구와 경보 억제
- Grafana, Prometheus, Tempo, Loki 또는 OpenTelemetry 자체의 대체 구현

## 역할과 경계

| 구성요소 | 역할 | 담당하지 않는 것 |
|---|---|---|
| Jev | 제한된 상태에 대한 타입 있는 triage 판단과 probability 제공 | telemetry 수집·저장, 자유 형식 설명 생성, 장애 주입, 복구 실행, 최종 안전 정책 |
| Chaos Engineering | 정답이 알려진 장애를 제한된 범위와 시간 동안 주입하고 ground truth 생성 | 장애 진단, 모델 평가 결과 왜곡, 운영 자동복구 |
| OpenTelemetry | 애플리케이션 계측과 traces·metrics·logs의 표준 수집·전달·상관관계 | 장기 저장, incident 판정, Jev 호출 정책 |
| Prometheus | 수치형 time series 저장·PromQL 집계·결정적 alert와 abort 조건 | 로그·trace 원문 저장, 의미 기반 root cause 판단 |
| Tempo | trace 저장·조회와 dependency/latency 증거 제공 | alert의 최종 분류, 장기 로그 저장 |
| Loki | 구조화 로그 저장·조회와 오류 패턴 증거 제공 | time-series alert의 권위 있는 원천, 자유로운 원문 외부 전송 |
| Grafana | 데이터소스 탐색, dashboard, annotation과 비교 결과 시각화 | ground truth 원장, chaos 실행 권한, Jev 판단의 진실성 보장 |

프로젝트 자체의 결정적 구성요소도 분리한다.

| 내부 구성요소 | 책임 |
|---|---|
| Alert Trigger | Alertmanager 이벤트를 받아 평가 window를 시작 |
| Context Builder | 각 backend를 조회해 크기 제한·allowlist·마스킹된 state 구성 |
| Ground Truth Recorder | chaos scenario ID, 실제 fault, 대상, 시작·복구 시각 저장 |
| Jev Adapter | state와 typed questions 전송, 원본 응답과 실제 model version 기록 |
| Policy Gate | confidence·위험·데이터 품질에 따라 추천, 사람 검토, 보류 분기 |
| Evaluator | 예측과 ground truth를 비교해 accuracy, calibration, latency, cost 계산 |

## 논리 아키텍처

```text
Chaos Engine ───────────────> Ground Truth Recorder
      │                                │
      ▼                                │
Sample Workload                         │
      │                                │
      ▼                                │
OpenTelemetry Collector                 │
  ├── metrics ──> Prometheus ─> Alertmanager
  ├── traces  ──> Tempo                 │
  └── logs    ──> Loki                  │
                                           ▼
                             Alert Trigger / Context Builder
                                           │
                                sanitized bounded state
                                           │
                                           ▼
                                  Jev Decision Adapter
                                           │
                                typed answers + probabilities
                                           │
                         ┌─────────────────┴─────────────────┐
                         ▼                                   ▼
                    Policy Gate                           Evaluator
                         │                                   │
                         └─────────────> Grafana <───────────┘
```

Jev는 telemetry ingest hot path에 두지 않는다. Jev가 지연되거나 실패해도 관측 데이터 수집, Prometheus alert와 결정적 chaos abort는 계속 동작해야 한다.

## Jev에 전달할 state 후보

Context Builder는 raw telemetry를 그대로 보내지 않고 incident window를 요약한다. 다음은 논리 schema 후보이며 구현 전에 크기 제한과 필수·선택 필드를 확정한다.

```json
{
  "schema_version": "p001-state-v1",
  "incident_id": "synthetic-incident-id",
  "observed_at": "RFC3339 timestamp",
  "window": { "before_seconds": 300, "after_seconds": 120 },
  "environment": { "name": "local", "cluster": "lab", "namespace": "demo" },
  "alert": {
    "rule_id": "HighCheckoutLatency",
    "status": "firing",
    "starts_at": "RFC3339 timestamp",
    "labels": { "service.name": "checkout" }
  },
  "service": {
    "name": "checkout",
    "availability": 0.997,
    "request_rate_per_second": 24.3,
    "error_rate": 0.031,
    "latency_ms": { "p50": 82, "p95": 1480, "p99": 1910 }
  },
  "resources": {
    "cpu_utilization": 0.34,
    "memory_utilization": 0.48,
    "desired_replicas": 3,
    "healthy_replicas": 3,
    "restart_delta": 0
  },
  "dependencies": [
    {
      "service": "redis",
      "request_rate_per_second": 18.1,
      "error_rate": 0.02,
      "latency_ms_p95": 1210
    }
  ],
  "traces": {
    "sample_count": 100,
    "error_count": 3,
    "slowest_dependency": "redis",
    "representative_spans": [
      { "operation": "GET cart", "peer_service": "redis", "duration_ms": 1204, "status": "error" }
    ]
  },
  "logs": {
    "total_count": 420,
    "error_count": 31,
    "patterns": [
      { "fingerprint": "sha256-prefix", "severity": "error", "count": 27, "template": "redis command timeout" }
    ],
    "redaction_count": 12
  },
  "kubernetes": {
    "warning_event_types": [],
    "pending_pods": 0,
    "oom_killed_delta": 0
  },
  "changes": {
    "minutes_since_deployment": 380,
    "revision_changed": false,
    "config_changed": false
  },
  "chaos_context": {
    "scenario_id": "hidden-during-blind-evaluation",
    "phase": "evaluation"
  },
  "data_quality": {
    "missing_signals": [],
    "truncated_fields": [],
    "coverage": 0.96
  },
  "candidates": {
    "teams": ["application", "platform", "database", "network", "human_triage"],
    "runbooks": ["redis-latency", "pod-restart", "deployment-rollback", "manual-investigation"]
  }
}
```

### State 설계 원칙

- 서비스명, namespace 등 필요한 속성만 allowlist한다.
- user ID, email, IP, request body, token과 raw stack trace는 제외한다.
- 로그는 대표 원문보다 정규화된 template, fingerprint와 count를 우선한다.
- trace는 전체 payload 대신 dependency, duration, status와 제한된 대표 span만 포함한다.
- 입력 길이, 배열 원소 수와 문자열 길이에 상한을 둔다.
- blind evaluation에서는 정답을 누설하는 chaos 종류, scenario ID, 실험 label을 Jev 입력에서 제거한다.
- 데이터 부족 자체를 `data_quality`로 표현하고 억지 분류를 피할 `unknown` 후보를 제공한다.

## Jev typed question 후보

Jev 공식 문서상 Choice와 Score는 probability distribution과 confidence를, Noul은 0~1 값을 반환한다. 복합 결론 하나를 묻지 않고 atomic question을 병렬로 평가한 뒤 코드에서 조합한다.

### Choice

| ID | 질문 | 후보 값 |
|---|---|---|
| `incident_type` | 관측된 현상을 가장 잘 설명하는 장애 유형 | `no_incident`, `workload_unavailable`, `resource_exhaustion`, `network_latency`, `network_loss`, `dependency_failure`, `dns_failure`, `deployment_regression`, `configuration_error`, `unknown` |
| `primary_affected_service` | 사용자 영향의 중심 서비스 | state에서 만든 제한된 서비스 후보 + `unknown` |
| `probable_root_cause_service` | 원인 후보가 되는 서비스 또는 계층 | 제한된 dependency 후보 + `platform`, `network`, `unknown` |
| `primary_signal` | 사람이 다음에 확인할 가장 유용한 증거 | `metrics`, `logs`, `traces`, `kubernetes_events`, `change_history`, `insufficient_data` |
| `owning_team` | 최초 triage를 맡을 영역 | 구성 파일의 팀 후보 + `human_triage` |
| `recommended_runbook` | 적용할 검증된 runbook | 등록된 runbook ID + `manual_investigation` |
| `triage_action` | 다음 처리 방식 | `page_now`, `notify`, `create_ticket`, `observe`, `human_review` |

`owning_team`과 `recommended_runbook` 후보는 배포 환경의 설정에서 만들며 Jev가 존재하지 않는 팀이나 runbook 이름을 생성할 수 없게 한다.

### Score

| ID | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| `severity` | 영향 없음 | 경미한 저하 | 제한적 사용자 영향 | 광범위한 영향 | 핵심 기능 중단 또는 데이터 위험 |
| `urgency` | 추후 검토 | 업무 시간 내 | 수 시간 내 | 즉시 조사 | 즉시 호출·대응 |
| `user_impact` | 관측 없음 | 소수 요청 | 일부 사용자 | 다수 사용자 | 대부분 사용자 또는 핵심 흐름 |
| `evidence_quality` | 판단 불가 | 매우 부족 | 부분적 | 충분 | 서로 독립된 신호가 강하게 일치 |

Score의 최종 의미는 ordinal rubric으로 고정하고, 숫자 평균만으로 자동 실행하지 않는다.

### Noul

| ID | 판단할 명제 |
|---|---|
| `incident_active` | 현재 사용자 영향이 있는 incident가 진행 중이다 |
| `deployment_related` | 최근 배포 또는 설정 변경이 주요 원인일 가능성이 높다 |
| `dependency_related` | downstream dependency 문제가 주요 원인일 가능성이 높다 |
| `duplicate_of_active_incident` | 이 alert는 이미 열린 incident의 증상이다 |
| `sufficient_evidence` | 자동 triage 결과를 제시하기에 증거가 충분하다 |
| `recovered` | 장애 전 steady state로 복구됐다 |
| `requires_human_review` | 자동 라우팅보다 사람 검토가 필요하다 |

Noul은 별도 confidence 필드가 없으므로 반환된 0~1 값 자체를 확률적 신호로 평가한다. 초기 단계에서는 어떤 질문도 자동 경보 억제나 복구 실행 권한을 갖지 않는다.

## Ground truth 장애 시나리오

모든 시나리오는 로컬 격리 환경을 기본으로 하며, 승인된 AWS 실습 환경에서도 제한된 namespace, 고정된 최대 지속시간과 deterministic abort 조건을 유지한다.

| ID | 주입 상황 | Ground truth label | 기대되는 주요 증거 | 단계 |
|---|---|---|---|---|
| `S000` | 장애를 주입하지 않은 정상·배경 잡음 | `no_incident` | 정상 SLI, 일부 비관련 warning 허용 | MVP control |
| `S001` | replica가 있는 서비스 Pod 1개 종료 | `workload_unavailable` 또는 정상 복원 | replica 감소, restart/event, 짧은 오류 증가 | MVP |
| `S002` | 서비스에서 dependency 방향으로 고정 network latency | `network_latency` | dependency span 지연, p95 증가, timeout 로그 | MVP |
| `S003` | 제한된 비율의 packet loss | `network_loss` | 재시도, 산발적 timeout과 error 증가 | MVP |
| `S004` | 대상 Pod CPU stress | `resource_exhaustion` | CPU saturation, latency 증가, queueing | MVP |
| `S005` | dependency service 일시 중단 | `dependency_failure` | downstream error span과 관련 로그 | MVP |
| `S006` | 대상 서비스의 DNS resolution 실패 | `dns_failure` | lookup error, connection 실패, dependency 단절 | MVP 후보 |
| `S007` | feature flag 또는 잘못된 revision으로 5xx 증가 | `deployment_regression` | 배포 시각과 오류 증가의 일치 | MVP 후보 |
| `S008` | memory pressure 또는 제한된 OOMKill | `resource_exhaustion` | memory saturation, OOM event, restart | 확장 |
| `S009` | 두 장애를 시간차로 결합 | 복합 label 또는 `unknown` | 상충하거나 겹친 증거 | 확장 |

### Ground truth record

각 실행은 다음을 별도 레코드로 남긴다.

- scenario ID와 schema version
- Git commit SHA, chaos manifest checksum과 도구 실제 버전
- 대상 cluster, namespace, workload와 selector
- fault 종류, parameter, blast radius, 시작·종료·복구 시각
- 주입 성공과 복구 성공 여부
- deterministic precondition과 abort 결과
- 기대 label, 영향 서비스, 원인 계층
- 수집 window와 telemetry fixture checksum
- evaluator에서 사용할 split (`design`, `validation`, `test`)

질문과 threshold 설계에는 `design`만 사용하고 최종 수치는 보지 않은 `test` split에서 계산한다.

## 평가 계획

### Baseline

1. Prometheus·Kubernetes 조건을 조합한 결정적 규칙 기반 baseline은 무료로 필수 구현한다.
2. Jev는 동일한 state와 정답 split에서 평가한다. 실제 API 호출 전 비용 승인을 받는다.
3. 일반 LLM structured-output baseline은 선택 사항이며 별도 비용 승인 후에만 실행한다.

### 품질 지표

| 대상 | 지표 |
|---|---|
| Choice | top-1 accuracy, top-2 accuracy, macro/micro F1, class별 precision·recall, confusion matrix |
| Choice calibration | multiclass Brier score, negative log-likelihood, ECE, reliability diagram |
| Score | MAE, exact-match accuracy, one-step accuracy, quadratic weighted kappa, probability 기반 Brier score |
| Noul | Brier score, log loss, AUROC, AUPRC, threshold별 precision·recall |
| 선택적 자동화 | confidence threshold별 coverage, accepted accuracy, risk-coverage curve, human-review rate |
| 안전 중요 분류 | 심각 incident recall, 잘못된 `no_incident` 비율, 잘못된 자동 라우팅 비율 |
| 중복 경보 확장 | alert compression ratio, merge precision·recall |

### 성능과 비용 지표

- Context Builder latency p50/p95/p99
- Jev provider latency p50/p95/p99
- alert 수신부터 triage 결과까지 end-to-end latency p50/p95/p99
- timeout, transport error, invalid response와 fallback 비율
- 요청당 input token, 질문 수, API 호출 수와 비용
- incident당 비용, 1,000 alert당 예상 비용
- 규칙 baseline 대비 추가 비용과 정확도 차이
- telemetry query량과 state payload byte 크기

### 강건성 평가

- metrics only, metrics+logs, metrics+traces, 전체 신호의 ablation
- 일부 backend가 없거나 지연된 상태
- 같은 장애의 강도·지속시간·대상 replica 변화
- 비관련 warning과 로그 noise 추가
- 영어 중심 telemetry와 한국어 운영 메모가 섞인 입력
- 모델 alias 또는 실제 버전 변경 전후 회귀

초기 성공 threshold는 pilot 데이터 없이 확정하지 않는다. 추천안은 설계 split과 pilot에서 목표를 정한 뒤 test split을 보기 전에 `DECISIONS.md`에 고정하는 것이다.

## 운영 흐름 후보

```text
Alert fires
  -> build bounded context
  -> validate schema and redaction
  -> run deterministic baseline
  -> call Jev only when approved and enabled
  -> apply confidence/data-quality policy
  -> show recommendation or request human review
  -> compare with hidden chaos ground truth
  -> persist metrics without raw sensitive payload
```

Jev 장애, timeout 또는 낮은 confidence는 `human_review`로 fail closed한다. Prometheus alert와 Grafana 원본 탐색 경로는 Jev와 독립적으로 유지한다.

## 보안과 telemetry 마스킹

- 합성 workload와 synthetic traffic을 기본으로 사용한다.
- 외부 전송 필드는 allowlist 방식으로 구성한다.
- request/response body, authorization header, cookie, query string, user ID, email, IP, hostname, tenant ID, trace baggage 원문을 제외한다.
- 로그는 정규화 template와 fingerprint를 우선하고 raw line은 로컬 backend 밖으로 보내지 않는다.
- stack trace는 exception type과 허용된 frame category로 요약한다.
- trace와 metric의 고카디널리티 식별자는 제거한다.
- 마스킹 전·후 schema validation과 차단된 필드 count를 기록한다.
- 마스킹 테스트 fixture에 의도적으로 dummy secret과 PII를 넣어 누출 방지를 검증한다.
- Jev 요청·응답 저장 시 raw state가 아니라 필요 최소한의 평가 메타데이터를 보존한다.
- 실제 운영 telemetry나 비공개 데이터 사용은 별도 범위·보안 검토와 사용자 승인 없이는 금지한다.

## 안전과 teardown

- production cluster와 namespace를 대상에서 제외한다.
- chaos 대상은 namespace와 label allowlist를 모두 만족해야 한다.
- 실험 전 최소 replica, 현재 active incident, steady state와 최근 배포 여부를 결정적 코드로 확인한다.
- fault마다 duration, 최대 대상 수, 최대 병렬 수와 전체 실험 timeout을 지정한다.
- abort 조건은 Prometheus SLI 또는 직접 health check로 구현하고 Jev 판단에 의존하지 않는다.
- 각 실험 뒤 fault 복구 상태와 workload 정상화를 검증한다.
- 선택한 chaos 도구, observability stack과 sample workload에 start·verify·teardown 명령을 제공한다.
- teardown 뒤 namespace, chaos CR, Pod, Job, PVC, load balancer와 포트 포워딩 잔존 여부를 확인한다.
- 정리가 실패하면 반복적인 삭제를 자동 수행하지 않고 잔존 리소스와 수동 절차를 보고한다.

## 결과와 성과

- M1 검증: 격리·배포 경계·webhook 테스트 9개 통과, 두 번의 clean-cluster 통합 검증과 teardown 완료.
- 최종 통합 결과: 3개 서비스의 metric·log·trace 상관관계, 3개 recording-rule 시계열, 5개 Grafana 패널 및 3개 SLI 쿼리, Alertmanager webhook firing 수신 확인.
- 원본 근거: [최종 결과 JSON](results/m1-final.json), [정리 결과 JSON](results/m1-final-teardown.json), [전체 검증 기록](docs/M1-VALIDATION.md).
- Jev 정확도, calibration, latency 및 생산성 개선: 아직 측정되지 않음. M1은 관측 데이터 수집 경로 검증이며 장애 분류 결과가 아니다.
- 유료 API·클라우드 사용액: 0원. 검증에 사용한 전용 로컬 클러스터와 볼륨은 삭제했다.

## 알려진 한계와 위험

- M1은 합성 트래픽·단일 노드·임시 저장소를 사용한다. 운영 규모의 성능, HA, 장애 상황과 범용 telemetry 마스킹은 검증하지 않았다.
- 이미지와 패키지는 실습 재현을 위한 고정 버전이다. 운영 배포용 보안·업그레이드 검토를 대신하지 않는다.
- `dashboard`를 Ctrl-C로 종료하면 Python `KeyboardInterrupt`가 출력될 수 있다. 포워딩 종료와 포트 반환은 검증했다.
- Chaos ground truth는 주입한 fault를 알려주지만 실제 incident의 모든 복합성과 조직 맥락을 대표하지 않는다.
- 타입 안전한 출력은 선택지가 유효함을 보장하지만 선택 자체의 사실적 정답을 보장하지 않는다.
- confidence calibration은 프로젝트 데이터에서 별도로 검증해야 한다.
- 집계 과정이 중요한 단서를 제거하거나 잘못된 상관관계를 만들 수 있다.
- 로그와 trace를 많이 포함하면 비용, latency와 정보 노출 위험이 증가한다.
- 서울에서 provider까지의 네트워크 latency는 공급자의 발표 수치와 다를 수 있다.
- 모델 버전 변경으로 결과가 달라질 수 있으므로 실제 model version별 회귀가 필요하다.

## 결정이 필요한 기술 선택

확정 사항과 미결정 항목은 [`DECISIONS.md`](DECISIONS.md)에 기록한다. M1 구현 요청에 따라 kind·3개 소형 서비스·Alertmanager webhook·Grafana provisioning을 선택했다. 다음 표의 후속 기술 선택은 pending 상태다.

| 선택 | 추천안 | 주요 대안 |
|---|---|---|
| 로컬 Kubernetes | kind (M1 적용) | k3d, minikube, Docker Compose only |
| Chaos engine | Chaos Mesh | LitmusChaos |
| Sample workload | 작은 3개 서비스 (M1 적용) | OpenTelemetry Demo의 일부 또는 전체 |
| Context Builder 언어 | Python으로 검증 후 필요 시 Go 재평가 | 처음부터 Go |
| Trigger | Alertmanager webhook (M1 로컬 전달 적용) | 주기적 polling, Grafana alert webhook |
| 운영자 UI | Grafana dashboard (M1 적용), annotation은 후속 범위 | 별도 web UI |
| Jev provider | TypeSafe 공식 API 우선 검토 | OpenRouter 경유 |
| LLM baseline | 초기에는 제외 | 별도 승인 후 1개 모델 비교 |

## 비용

현재 승인 예산과 사용액은 모두 0원이다. 무료 기본 경로와 비용 발생 가능 항목은 [`COSTS.md`](COSTS.md)에 기록한다.

## 문서

- [실행 계획](PLAN.md)
- [결정 기록](DECISIONS.md)
- [비용 기록](COSTS.md)

## 공식 참고 자료

- [TypeSafe Jev 소개와 primitive](https://docs.typesafe.ai/introduction)
- [TypeSafe confidence](https://docs.typesafe.ai/confidence)
- [OpenTelemetry 문서](https://opentelemetry.io/docs/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [Prometheus 개요](https://prometheus.io/docs/introduction/overview/)
- [Grafana 소개](https://grafana.com/docs/grafana/latest/fundamentals/)
- [Tempo 소개](https://grafana.com/docs/tempo/latest/introduction/)
- [Loki 문서](https://grafana.com/docs/loki/latest/)
- [Chaos Mesh 실험 범위](https://chaos-mesh.org/docs/define-chaos-experiment-scope/)
- [LitmusChaos 문서](https://docs.litmuschaos.io/)
