# P001 실행 계획

## 목표

- 정답이 알려진 장애 시나리오에서 Jev 기반 signal triage의 품질과 비용을 측정한다.
- Prometheus 경보 이후 필요한 조사·라우팅 판단을 타입 있는 결과로 제공한다.
- confidence와 데이터 품질을 이용해 자동 추천과 human review의 안전한 경계를 찾는다.
- 모든 실험을 로컬·격리·재현 가능한 방식으로 실행한다.

## 비목표

- 이번 기획 세션에서 구현하거나 리소스를 생성하지 않는다.
- anomaly detector나 observability backend를 새로 만들지 않는다.
- Jev에 장애 주입, 복구, 배포 또는 경보 억제 권한을 주지 않는다.
- 실제 운영 telemetry와 production cluster를 사용하지 않는다.
- pilot 전에 성능 threshold와 미결정 기술 스택을 최종 확정하지 않는다.

## 현재 상태

- 상태: `proposed`
- 현재 단계: Milestone 0 — 기획 및 프로젝트 bootstrap
- 현재 브랜치: `docs/p001-project-planning`
- PR: https://github.com/dongjune8931/JevOps-Lab/pull/2
- 사용자 승인이 필요한 항목: chaos engine, 로컬 실행 환경, sample workload, 구현 언어, Jev provider, 유료 평가 예산
- 블로커: 없음. 구현 시작 전 미결정 기술 선택 확인 필요

## Milestone 0 — 기획 및 프로젝트 bootstrap

### 산출물

- 프로젝트 `README.md`, `PLAN.md`, `DECISIONS.md`, `COSTS.md`
- P001 전용 PR 템플릿
- 루트 README 카탈로그 링크

### Acceptance criteria

- [x] 프로젝트 목표, 비목표, 역할과 경계를 문서화했다.
- [x] Jev state와 Choice, Score, Noul 후보를 정의했다.
- [x] ground truth 장애 시나리오와 평가 지표를 정의했다.
- [x] 보안, telemetry 마스킹과 teardown 원칙을 정의했다.
- [x] 기술 선택은 추천안과 대안으로 남기고 임의 확정하지 않았다.
- [x] 현재 세션에서 외부 API 호출과 리소스 생성을 하지 않았다.

### 검증 방법

```bash
git diff --check
test -f projects/P001-jevops-signal-triage/README.md
test -f projects/P001-jevops-signal-triage/PLAN.md
test -f projects/P001-jevops-signal-triage/DECISIONS.md
test -f projects/P001-jevops-signal-triage/COSTS.md
test -f .github/PULL_REQUEST_TEMPLATE/p001.md
rg -n "P001-jevops-signal-triage" README.md
rg -n "Choice|Score|Noul|ground truth|teardown" projects/P001-jevops-signal-triage
```

## Milestone 1 — 무료 로컬 관측 baseline

### 목표

선택된 local runtime에서 sample workload와 metrics·logs·traces 수집 경로를 비용 없이 재현한다.

### Acceptance criteria

- [ ] 선택한 runtime과 모든 이미지·chart·dependency 버전을 고정했다.
- [ ] OpenTelemetry에서 Prometheus, Tempo, Loki까지 신호가 도달한다.
- [ ] trace ID를 이용해 trace와 허용된 로그를 상관 분석할 수 있다.
- [ ] Grafana에 SLI와 신호 탐색 dashboard가 provisioning된다.
- [ ] Alertmanager가 합성 alert를 로컬 endpoint에 전달한다.
- [ ] start, verify, teardown 명령이 문서화되고 깨끗한 환경에서 통과한다.
- [ ] 외부 SaaS와 유료 API 호출이 없다.

### 검증 방법 후보

- 컨테이너·Pod readiness 검사
- Prometheus API에서 대상과 기록 규칙 확인
- Tempo에서 synthetic trace ID 조회
- Loki에서 synthetic fingerprint 조회
- Grafana provisioning API 또는 파일 검증
- teardown 전후 리소스 목록 비교

## Milestone 2 — Chaos ground truth harness

### 목표

고정된 시나리오를 안전하게 실행하고 주입 사실, telemetry window와 복구 결과를 ground truth로 기록한다.

### Acceptance criteria

- [ ] 사용자 결정으로 chaos engine을 확정하고 `DECISIONS.md`에 기록했다.
- [ ] `S000`과 최소 5개 fault 시나리오가 버전 관리된다.
- [ ] namespace·label allowlist, 최대 duration, target 수와 timeout이 강제된다.
- [ ] precondition 실패 시 fault를 주입하지 않는다.
- [ ] deterministic abort와 fault 복구를 검증한다.
- [ ] ground truth record에 checksum, 시각, 대상, parameter와 결과가 포함된다.
- [ ] 반복 실행 후 잔존 chaos resource와 workload 이상이 없다.

### 검증 방법 후보

- chaos manifest schema·dry-run 검증
- 허용되지 않은 namespace와 selector에 대한 음성 테스트
- 시나리오별 주입·복구 상태 확인
- Prometheus steady-state와 abort rule 테스트
- fixture checksum과 ground truth schema 테스트

## Milestone 3 — Context Builder와 규칙 baseline

### 목표

동일한 ground truth window에서 제한되고 마스킹된 state를 만들고, 무료 규칙 기반 baseline을 계산한다.

### Acceptance criteria

- [ ] state schema version과 필수·선택 필드를 고정했다.
- [ ] backend별 query timeout과 partial failure를 처리한다.
- [ ] allowlist, 문자열·배열·payload 크기 제한을 적용한다.
- [ ] dummy secret과 PII fixture가 state에서 제거된다.
- [ ] blind test state에 chaos 정답 누수가 없다.
- [ ] 동일 fixture에서 deterministic한 state와 baseline 결과가 생성된다.
- [ ] rules baseline의 분류와 latency가 저장된다.

### 검증 방법 후보

- schema unit test와 golden fixture 비교
- redaction leakage test
- backend missing/timeout integration test
- state byte limit과 truncation test
- ground truth leakage 검사

## Milestone 4 — Jev adapter와 typed decisions

### 목표

승인된 비용 범위 안에서 Jev API를 연결하고 versioned state와 atomic questions의 원본 결과를 안전하게 기록한다.

### 선행 조건

- 사용자가 provider와 최대 비용을 명시적으로 승인해야 한다.
- `COSTS.md`에 승인 일시, 상한과 중단 기준을 기록해야 한다.

### Acceptance criteria

- [ ] provider와 모델 alias 선택을 `DECISIONS.md`에 기록했다.
- [ ] Choice, Score, Noul request와 response schema를 검증한다.
- [ ] API key가 로그, fixture, Git과 결과 파일에 남지 않는다.
- [ ] 요청 model alias와 실제 반환 model version을 기록한다.
- [ ] timeout, rate limit, provider error는 human review로 fail closed한다.
- [ ] 승인 비용 상한을 넘기 전에 실행이 중단된다.
- [ ] 동일 test input에 대한 retry와 중복 과금을 제한한다.

### 검증 방법 후보

- 무료 mock adapter contract test
- 승인 후 최소 paid smoke test
- timeout·429·5xx·invalid response fixture test
- request redaction snapshot test
- usage와 cost ledger 정합성 검사

## Milestone 5 — 평가와 calibration

### 목표

보지 않은 test split에서 규칙 baseline과 Jev를 비교하고 품질·latency·비용·강건성을 보고한다.

### Acceptance criteria

- [ ] test split 확인 전에 성공 threshold와 분석 계획을 고정했다.
- [ ] 모든 run에 commit, model, question, data, environment와 cost 메타데이터가 있다.
- [ ] Choice, Score, Noul별 정확도와 calibration 지표를 계산한다.
- [ ] confidence threshold별 coverage와 accepted accuracy를 보고한다.
- [ ] context build, model, end-to-end latency를 분리한다.
- [ ] 실패, timeout, 제외 데이터와 제외 이유를 포함한다.
- [ ] signal ablation과 missing-backend 강건성을 평가한다.
- [ ] README의 모든 성과 수치를 원본 결과와 연결한다.

### 검증 방법 후보

- 데이터 split과 checksum 검증
- metric calculation unit test
- raw result 불변성과 analysis reproducibility 검사
- 같은 commit·seed에서 report 재생성
- 결과 표와 원본 record 표본 대조

## Milestone 6 — 운영자 경험과 안전 경계

### 목표

Jev의 판단을 원본 observability 증거와 함께 표시하고, 신뢰도에 따라 안전하게 사람 검토로 넘기는 운영 흐름을 완성한다.

### Acceptance criteria

- [ ] Grafana에서 ground truth, alert, signals, prediction, confidence와 실제 결과를 함께 확인한다.
- [ ] 낮은 confidence, 낮은 data quality와 provider failure는 human review로 표시한다.
- [ ] 잘못된 판단이 원본 alert나 telemetry 접근을 막지 않는다.
- [ ] 자동 alert suppression과 remediation은 비활성 상태다.
- [ ] start, demo, verify, teardown 문서가 깨끗한 환경에서 검증된다.
- [ ] 최종 결과, 비용, 한계와 후속 실험을 README에 반영한다.

### 검증 방법 후보

- end-to-end synthetic incident walkthrough
- confidence boundary와 fallback test
- dashboard provisioning 검증
- provider unavailable 상태에서 observability 경로 유지 확인
- 전체 teardown 및 잔존 리소스 검사

## 프로젝트 Definition of Done

- [ ] Milestone 0~6의 acceptance criteria를 충족하거나 제외 이유를 결정 기록에 남겼다.
- [ ] 테스트, lint, build와 문서 검증이 통과한다.
- [ ] 깨끗한 로컬 환경에서 start, demo, evaluation, report, teardown을 재현했다.
- [ ] 최소 control 1개와 독립 fault 5개의 ground truth dataset을 보존한다.
- [ ] 규칙 baseline과 Jev를 동일한 test split에서 비교했다.
- [ ] 정확도, calibration, latency, 비용, coverage와 안전 중요 오류를 보고했다.
- [ ] model·question·dataset·environment·commit 버전을 모든 run에 기록했다.
- [ ] 성공뿐 아니라 실패, timeout, 제외 데이터와 한계를 문서화했다.
- [ ] 민감정보 누출 테스트와 secret scan을 통과했다.
- [ ] 생성한 모든 리소스를 제거하고 남은 비용이 없음을 확인했다.
- [ ] 프로젝트와 루트 README, PLAN, DECISIONS, COSTS가 최신 상태다.
- [ ] 관련 PR 검사가 통과하고 squash merge됐다.

## 이번 세션 인수인계

- 완료: Milestone 0 기획 문서 초안
- 마지막 검증: 2026-09-25에 Milestone 0의 파일 존재, 필수 키워드, 루트 README 링크와 `git diff --check` 검증 통과
- 다음 작업: 미결정 기술 선택을 사용자와 확정하고 Milestone 1 구현 계획을 세분화
- 구현 상태: 구현 없음
- 비용: 외부 호출·리소스 생성 없음, 0원
- 알려진 블로커: 구현 시작 전 `DECISIONS.md`의 pending 항목 결정 필요
