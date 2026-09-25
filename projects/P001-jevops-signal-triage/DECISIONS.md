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

## 기술 선택 상태

2026-09-25의 첫 미완료 milestone 구현 요청에 따라 M1에 필요한 로컬 실행 환경·샘플·전달 경로·대시보드를 아래 추천안으로 선택했다. 후속 milestone의 pending 결정과 비용 승인은 별도로 유지한다.

### P001-D006 — 로컬 실행 환경

- 날짜: 2026-09-25
- 상태: accepted (M1)
- 결정: 전용 `p001-m1` kind 클러스터와 프로젝트 내부 kubeconfig 사용. 기존 로컬 Docker만 사용하고 원격 context는 거부한다.
- 추천: `kind`
- 이유: Kubernetes API와 CRD 기반 chaos 도구를 로컬에서 재현하기 쉽고 cluster 전체를 삭제해 teardown할 수 있다.
- 대안:
  - `k3d`: 시작이 빠르고 로컬 registry 연계가 편리할 수 있다.
  - `minikube`: addon과 driver 선택지가 많지만 환경 차이가 늘 수 있다.
  - Docker Compose only: 가장 가볍지만 Kubernetes 고유 장애와 이벤트를 평가하기 어렵다.
- 결정에 필요한 정보: 사용자 환경에서 이미 사용하는 runtime, 사용 가능한 CPU·메모리, Kubernetes fidelity 우선순위.

### P001-D007 — Chaos engine

- 날짜: 2026-09-25
- 상태: accepted (M2; 사용자가 후속 milestone 적합성을 기준으로 선택 위임)
- 결정: `Chaos Mesh 2.8.4`와 checksum을 고정한 Helm chart를 전용 로컬 kind에 사용한다.
- 이유: 버전 관리한 CRD manifest·selector·주입/복구 상태를 M3의 관측 window, M4a의 AWS 재현, M5의 반복 평가에 연결하기 적합하다. AWS 호환성은 M4a에서 별도 검증한다.
- 대안: `LitmusChaos`
- 대안 장점: probe, ChaosHub, experiment 결과와 end-to-end 플랫폼 기능이 강하다.
- 선택하지 않은 이유: 이번 목적은 Jev 평가용 제한된 fault harness이며 별도 포털·workflow 플랫폼은 필수가 아니다.
- 영향: privileged daemon은 소유한 kind node에만 설치한다. namespace filter·대상 allowlist·duration·단일 실행 lock·복구 검증을 추가한다. dashboard는 설치하지 않으며 AWS 실행 및 비용은 승인하지 않는다.

### P001-D008 — Sample workload

- 날짜: 2026-09-25
- 상태: accepted (M1)
- 결정: `checkout → catalog → inventory` 3개 Python 서비스를 하나의 이미지로 실행한다. OTel SDK로 metrics·logs·traces를 계측한다.
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

- 날짜: 2026-09-25
- 상태: accepted (M1 전달 검증)
- 결정: Alertmanager webhook을 로컬 메모리 수신기에 전달한다. 실제 triage event 처리·deduplication은 M3 이후 범위다.
- 추천: Alertmanager webhook
- 이유: Prometheus alert 이후 triage라는 제품 경계를 명확히 하고 event-driven으로 실행할 수 있다.
- 대안: 주기적 Prometheus polling 또는 Grafana alert webhook.
- 영향: Alertmanager payload 정규화와 중복 이벤트 처리 전략이 필요하다.

### P001-D011 — 운영자 UI

- 날짜: 2026-09-25
- 상태: accepted (M1 baseline)
- 결정: Grafana provisioning으로 SLI·로그·trace 탐색 dashboard를 제공한다. Jev 판단과 ground truth 시각화는 M6 범위다.
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

## AWS 검증 순서

### P001-D015 — M4 뒤 첫 AWS 테스트, M5에서 환경 비교

- 날짜: 2026-09-25
- 상태: accepted (실행 순서와 문서 계획만)
- 결정: 로컬 M2~M4를 먼저 완료하고 M4a에서 대표 장애 2~3개의 AWS 통합 흐름을 검증한다. M5는 로컬·AWS 비교 평가로 확장하고 M6 이후 M7 최종 AWS 검증은 선택 사항으로 둔다.
- 이유: 안전한 장애 주입·마스킹·Jev 실패 처리를 갖춘 뒤 클라우드 차이를 확인하고, 운영 화면 완성 전에 환경별 평가 자료를 확보한다.
- 대안: M1 직후 AWS로 이전하거나 M6까지 기다린 뒤 첫 AWS 테스트. 전자는 triage 비교 기준이 부족하고 후자는 환경 차이 발견이 늦어진다.
- 영향: M4a pilot은 최종 test split에서 제외한다. AWS 구성·실습 계정·리전은 미정이며 실행별 AWS·Jev 비용 승인이 필요하다. 이번 결정은 리소스 생성이나 크레딧 소비 승인이 아니다.

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
