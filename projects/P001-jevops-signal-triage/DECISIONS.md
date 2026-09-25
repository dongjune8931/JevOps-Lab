# P001 결정 기록

## 확정된 결정

### D001 — 프로젝트는 모니터링 triage를 중심으로 한다

- 날짜: 2026-09-25
- 상태: accepted
- 결정: 프로젝트의 주 기능은 alert 이후 장애 유형, 심각도, 담당 영역, 다음 조사 신호와 runbook 후보를 판단하는 것이다.
- 이유: DevOps 엔지니어의 반복적인 모니터링 판단을 직접 지원하면서 Jev의 typed decision 특성을 평가할 수 있다.
- 제외한 방향: Jev 기반 범용 모니터링 backend, 완전 자동 remediation.
- 영향: 관측 backend와 기존 alert는 계속 source of evidence이며 Jev가 이를 대체하지 않는다.

### D002 — Chaos Engineering은 ground truth 생성기로 제한한다

- 날짜: 2026-09-25
- 상태: accepted
- 결정: chaos 도구는 정답이 알려진 장애를 재현하고 평가 fixture를 만드는 용도로 사용한다.
- 이유: Jev의 판단을 객관적인 fault label과 비교할 수 있다.
- 대안: 실제 incident 데이터만 사용.
- 대안을 선택하지 않은 이유: 초기 단계에서 개인정보와 운영 위험이 크고 정답 품질을 통제하기 어렵다.
- 영향: chaos 종류와 parameter가 blind evaluation state에 누출되지 않게 별도로 저장한다.

### D003 — Jev는 telemetry hot path와 안전 제어 경로에서 분리한다

- 날짜: 2026-09-25
- 상태: accepted
- 결정: Jev 실패가 telemetry ingest, Prometheus alert, chaos abort와 복구에 영향을 주지 않게 한다.
- 이유: 외부 모델 장애나 낮은 confidence가 관측과 안전 기능을 중단해서는 안 된다.
- 대안: Collector processor 또는 alert pipeline 내부에서 동기 Jev 호출.
- 대안을 선택하지 않은 이유: backpressure와 단일 장애점 위험이 있다.
- 영향: Alert Trigger 이후 비동기 또는 bounded 동기 호출과 human-review fallback이 필요하다.

### D004 — 외부 전송 state는 allowlist와 최소화 원칙을 사용한다

- 날짜: 2026-09-25
- 상태: accepted
- 결정: raw logs, complete traces, request payload 대신 집계값, template와 제한된 대표 span만 Jev state에 포함한다.
- 이유: 비용, latency와 개인정보·비밀정보 노출 위험을 동시에 낮춘다.
- 대안: backend query 결과를 원문 그대로 전달.
- 대안을 선택하지 않은 이유: 불필요한 데이터 전송과 정답 누수 가능성이 높다.
- 영향: Context Builder에 schema validation, redaction test와 payload limit이 필요하다.

### D005 — 규칙 기반 baseline은 필수, 유료 LLM baseline은 선택 사항이다

- 날짜: 2026-09-25
- 상태: accepted
- 결정: 무료 deterministic rules를 기본 비교군으로 구현한다. 일반 LLM 비교는 별도 비용 승인 후에만 추가한다.
- 이유: Jev가 실제로 추가하는 정확도와 비용을 가장 단순한 대안과 먼저 비교할 수 있다.
- 영향: rules baseline도 동일한 state와 test split을 사용한다.

## 결정 대기

아래 항목은 구현 전에 사용자 결정을 받는다. 추천은 초기 실험을 위한 제안이며 아직 확정이 아니다.

### P001-D006 — 로컬 실행 환경

- 상태: pending
- 추천: `kind`
- 이유: Kubernetes API와 CRD 기반 chaos 도구를 로컬에서 재현하기 쉽고 cluster 전체를 삭제해 teardown할 수 있다.
- 대안:
  - `k3d`: 시작이 빠르고 로컬 registry 연계가 편리할 수 있다.
  - `minikube`: addon과 driver 선택지가 많지만 환경 차이가 늘 수 있다.
  - Docker Compose only: 가장 가볍지만 Kubernetes 고유 장애와 이벤트를 평가하기 어렵다.
- 결정에 필요한 정보: 사용자 환경에서 이미 사용하는 runtime, 사용 가능한 CPU·메모리, Kubernetes fidelity 우선순위.

### P001-D007 — Chaos engine

- 상태: pending
- 추천: `Chaos Mesh`
- 이유: Kubernetes CRD, selector 기반 blast radius와 workflow/status-check 흐름이 이 프로젝트의 제한된 fault harness에 잘 맞는다.
- 대안: `LitmusChaos`
- 대안 장점: probe, ChaosHub, experiment 결과와 end-to-end 플랫폼 기능이 강하다.
- 결정에 필요한 정보: 경량 로컬 실행 우선인지, 완성된 chaos workflow·포털 경험 우선인지.

### P001-D008 — Sample workload

- 상태: pending
- 추천: 3~4개의 작은 다중 서비스 workload를 프로젝트 내부에서 구성
- 이유: 리소스 사용량과 ground truth를 통제하고 필요한 signal을 의도적으로 설계할 수 있다.
- 대안: OpenTelemetry Demo 전체 또는 일부
- 대안 장점: 표준화된 다양한 언어와 풍부한 telemetry 시나리오를 즉시 활용할 수 있다.
- 위험: 직접 구성은 구현 시간이 늘고, OTel Demo는 로컬 리소스와 분석 복잡도가 커질 수 있다.

### P001-D009 — Context Builder 구현 언어

- 상태: pending
- 추천: Python으로 실험 인터페이스를 먼저 검증한 뒤 성능 병목이 확인되면 Go를 재평가
- 이유: schema, evaluator와 데이터 분석을 빠르게 반복하기 쉽다.
- 대안: 처음부터 Go
- 대안 장점: 단일 binary, concurrency, 배포와 운영 특성이 좋다.
- 결정에 필요한 정보: 사용자의 학습 목표, 장기 도구화 의도와 선호 언어.

### P001-D010 — Alert trigger

- 상태: pending
- 추천: Alertmanager webhook
- 이유: Prometheus alert 이후 triage라는 제품 경계를 명확히 하고 event-driven으로 실행할 수 있다.
- 대안: 주기적 Prometheus polling 또는 Grafana alert webhook.
- 영향: Alertmanager payload 정규화와 중복 이벤트 처리 전략이 필요하다.

### P001-D011 — 운영자 UI

- 상태: pending
- 추천: MVP에서는 Grafana dashboard와 annotation만 사용
- 이유: 별도 frontend 없이 원본 signals와 평가 결과를 같은 화면에서 비교할 수 있다.
- 대안: 전용 web UI.
- 대안이 유리한 시점: 승인 workflow나 incident queue가 핵심 기능으로 확장될 때.

### P001-D012 — Jev provider와 모델 접근

- 상태: pending, 비용 승인 필요
- 추천: TypeSafe 공식 API를 우선 검토
- 이유: 원본 Jev 응답 schema와 model version을 직접 확인하기 쉽다.
- 대안: OpenRouter 경유.
- 결정 전에 확인할 것: 계정 접근 가능 여부, 최신 가격, data retention 정책, 요청 지역, rate limit과 실제 model version 반환 여부.
- 제한: 결정과 비용 승인 전에는 실제 API를 호출하지 않는다.

### P001-D013 — Confidence policy와 성공 threshold

- 상태: pending
- 추천: pilot의 calibration과 risk-coverage curve를 본 뒤 test split을 열기 전에 threshold를 고정
- 대안: 공급자 예제의 threshold를 그대로 사용.
- 대안을 권하지 않는 이유: 업무 위험과 프로젝트 데이터 분포에 맞지 않을 수 있다.
- 영향: 초기 구현은 recommendation-only이며 자동 suppression과 remediation을 허용하지 않는다.

### P001-D014 — 모델 입력 언어

- 상태: pending
- 추천: 기계 telemetry와 question은 영어를 기본으로 하고 한국어 운영 메모는 별도 강건성 실험으로 분리
- 대안: 모든 입력을 한국어로 유지하거나 번역 계층 추가.
- 고려사항: 번역 계층은 비용, latency와 새로운 오류 원인을 만든다.

## 결정 추가 형식

```text
### D### — 제목

- 날짜:
- 상태: proposed | accepted | superseded
- 결정:
- 이유:
- 대안:
- 영향:
```

