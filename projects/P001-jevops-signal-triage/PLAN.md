# P001 실행 계획

## 목표

- 정답이 알려진 장애 시나리오에서 Jev 기반 signal triage의 품질과 비용을 측정한다.
- Prometheus 경보 이후 필요한 조사·라우팅 판단을 타입 있는 결과로 제공한다.
- confidence와 데이터 품질을 이용해 자동 추천과 human review의 안전한 경계를 찾는다.
- 로컬·격리 환경을 기본으로 하고, 별도 승인된 AWS 실습 환경에서 같은 흐름을 재현·비교한다.

## 비목표

- AWS에서의 상시 서비스 운영이나 production 배포를 목표로 하지 않는다.
- anomaly detector나 observability backend를 새로 만들지 않는다.
- Jev에 장애 주입, 복구, 배포 또는 경보 억제 권한을 주지 않는다.
- 실제 운영 telemetry와 production cluster를 사용하지 않는다.
- pilot 전에 성능 threshold와 미결정 기술 스택을 최종 확정하지 않는다.

## 현재 상태

- 상태: `active`
- 현재 단계: Milestone 1 — 무료 로컬 관측 baseline 완료
- 현재 브랜치: `docs/p001-aws-validation-plan`
- AWS 검증 계획 PR: https://github.com/dongjune8931/JevOps-Lab/pull/5
- M1 PR: https://github.com/dongjune8931/JevOps-Lab/pull/4
- 기획 브랜치: `docs/p001-project-planning` (원격 브랜치 삭제 완료)
- 기획 PR: https://github.com/dongjune8931/JevOps-Lab/pull/2 (squash merge 완료)
- 검증 보완 브랜치: `docs/p001-planning-validation`
- 검증 보완 PR: https://github.com/dongjune8931/JevOps-Lab/pull/3
- 다음 미완료 단계: Milestone 2 — Chaos ground truth harness
- 후속 결정 항목: chaos engine(M2), Context Builder 언어(M3), Jev provider·유료 평가 예산(M4), AWS 실습 계정·리전·구성·비용 상한(M4a)
- 블로커: M1 없음. M2 시작 전 chaos engine 선택 필요

## 진행 순서와 클라우드 진입 시점

`로컬 M2 → 로컬 M3 → 로컬 M4 → M4a AWS 통합 테스트 → M5 로컬·AWS 비교 평가 → M6 운영 화면 → M7 최종 AWS 검증(선택)`

- 첫 실제 클라우드 통합 테스트는 M4 완료 직후 진행한다. M2의 안전한 장애 주입·복구, M3의 마스킹·state·규칙 비교군, M4의 Jev 연결·실패 처리를 먼저 확보한다.
- 기존 M1~M6 번호를 유지하고 중간 단계에 `M4a`를 추가한다. 다음 구현 세션의 첫 미완료 milestone은 계속 M2다.
- Jev 비용 승인이 늦어지면 M3 이후 mock으로 AWS 배포·수집 경로만 먼저 확인할 수 있다. 이 경우에도 AWS 비용 승인은 필요하며, M4 또는 M4a의 실제 Jev 통합 완료로 간주하지 않는다.
- 이 계획의 승인은 AWS 리소스 생성·크레딧 소비·유료 Jev 호출 승인이 아니다. 실행 직전에 구체적인 구성·예상 비용·상한·중단 및 정리 방법을 제시하고 승인을 받는다.

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

- [x] 선택한 runtime과 모든 이미지·dependency 버전을 고정했다. Helm chart는 사용하지 않는다.
- [x] OpenTelemetry에서 Prometheus, Tempo, Loki까지 신호가 도달한다.
- [x] trace ID를 이용해 trace와 허용된 로그를 상관 분석할 수 있다.
- [x] Grafana에 SLI와 신호 탐색 dashboard가 provisioning된다.
- [x] Alertmanager가 합성 alert를 로컬 endpoint에 전달한다.
- [x] start, verify, teardown 명령이 문서화되고 깨끗한 환경에서 통과한다.
- [x] 외부 SaaS와 유료 API 호출이 없다.

### 검증 방법과 결과

```bash
cd projects/P001-jevops-signal-triage
python3 scripts/lab.py test
python3 scripts/lab.py start
python3 scripts/lab.py verify
python3 scripts/lab.py dashboard
# Ctrl-C로 포워딩 종료 후
python3 scripts/lab.py teardown
```

2026-09-25: 단위·경계 테스트 9개, 두 번의 신규 클러스터 통합 검증과 teardown 통과. 최종 검증은 SLI PromQL의 유효한 수치까지 확인했다. [검증 기록](docs/M1-VALIDATION.md)과 [원본 결과](results/m1-final.json)를 참조한다.

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

로컬에서 승인된 비용 범위 안에서 Jev API를 연결하고 versioned state와 atomic questions의 원본 결과를 안전하게 기록한다. 이 흐름의 통과를 첫 AWS 통합 테스트의 진입 조건으로 삼는다.

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

## Milestone 4a — 첫 AWS 통합 테스트

### 목표

격리된 AWS 실습 환경에서 대표 장애 2~3개의 주입 → 신호 수집 → state 구성 → Jev 추천 → 복구 흐름을 짧게 검증한다. 정확도·calibration의 정식 성과 판정은 M5에서 수행한다.

### 선행 조건과 범위

- 로컬 M2~M4 검증이 통과하고 abort·복구·마스킹·timeout·호출 제한이 동작해야 한다.
- 실습 계정의 운영 환경 분리 여부, 대상 계정·리전, 크레딧 잔액·만료일·적용 서비스와 예상 청구액을 확인한다.
- EC2 + kind 또는 소규모 EKS 중 목적·예산에 맞게 선택하고 `DECISIONS.md`에 기록한다. 현재 구성은 미정이다.
- AWS 생성·실행 시간·정리 예산과 이번 Jev 호출 예산을 각각 승인받고 `COSTS.md`에 기록한다. 기존 M4 승인을 자동 재사용하지 않는다.
- 계정·리전·리소스 allowlist, 실행 시간과 반복 횟수 제한, 자원 생성 목록, 재현 가능한 배포·teardown 절차를 준비한다. 기존 로컬 실행기의 원격 접근 차단을 해제하지 않고 AWS 실행 경로를 구분한다.
- M2에서 복구까지 검증한 대표 장애 2~3개와 정상 control을 사용한다. 새 AWS 고유 장애나 광범위한 node·네트워크 장애는 이 단계에 추가하지 않는다.

### Acceptance criteria

- [ ] 합성 workload와 observability 구성을 승인된 AWS 실습 환경에 재현했다.
- [ ] 대표 장애마다 metrics·logs·traces가 수집되고 마스킹된 state로 Jev 추천까지 도달한다.
- [ ] Jev 실패·timeout 시 원본 alert와 telemetry 접근을 유지하고 human review로 전환한다.
- [ ] fault별 abort·복구와 steady state 회복을 확인했다.
- [ ] 환경·모델·question·scenario 버전과 수집량, end-to-end latency, AWS 사용량·비용, Jev 호출량·비용을 기록했다.
- [ ] 이번 smoke/pilot 데이터는 design 또는 validation으로 표시해 M5의 최종 test split에서 제외했다.
- [ ] 실험 뒤 생성 목록과 대조해 cluster·instance·disk·load balancer·IP 등 해당 자원을 정리하고 잔존 자원과 추가 과금 가능성을 확인했다.

### 검증 방법 후보

- IaC 정적 검증과 생성 예정 자원·대상 계정·리전 대조; 실제 생성은 승인 후 수행
- 로컬과 같은 scenario ID·parameter·workload version으로 end-to-end smoke test
- trace ID·incident ID를 이용한 원본 신호 → state → Jev 응답 추적 및 누출 검사
- provider 실패 시 fallback, fault abort·복구·steady state 검사
- run 메타데이터·비용 ledger·배포 전후 자원 목록과 teardown 결과 대조

실행 명령은 AWS 구성을 선택하는 구현 PR에서 확정한다. 현재는 계획만 정의했으며 AWS에 접근하거나 리소스를 생성하지 않았다.

## Milestone 5 — 로컬·AWS 비교 평가와 calibration

### 목표

보지 않은 test split에서 규칙 baseline과 Jev를 비교하고, 로컬과 AWS 환경별 품질·calibration·latency·비용·강건성 차이를 보고한다.

AWS 비교 실행은 M4a 통과와 해당 평가 범위의 별도 비용 승인을 전제로 한다. 승인이 대기 중이면 로컬 평가를 먼저 진행할 수 있으나 AWS 비교를 완료로 표시하지 않는다.

### Acceptance criteria

- [ ] test split 확인 전에 성공 threshold와 분석 계획을 고정했다.
- [ ] 모든 run에 commit, model, question, data, environment와 cost 메타데이터가 있다.
- [ ] Choice, Score, Noul별 정확도와 calibration 지표를 계산한다.
- [ ] confidence threshold별 coverage와 accepted accuracy를 보고한다.
- [ ] context build, model, end-to-end latency를 분리한다.
- [ ] 실패, timeout, 제외 데이터와 제외 이유를 포함한다.
- [ ] signal ablation과 missing-backend 강건성을 평가한다.
- [ ] 로컬·AWS에 같은 scenario·parameter·workload·question·모델 버전과 평가 절차를 적용하고 자원·부하·환경 차이를 기록했다.
- [ ] 같은 환경 안의 baseline·Jev 비교에는 동일 state를 사용하고, 환경 간 비교는 각 환경에서 수집한 state를 사용함을 명시했다.
- [ ] 환경별 정확도·calibration·coverage·latency와 AWS 인프라·Jev 비용을 분리해 보고했다.
- [ ] M4a pilot을 최종 test split에 재사용하지 않고 AWS 평가 자원도 정리했다.
- [ ] README의 모든 성과 수치를 원본 결과와 연결한다.

### 검증 방법 후보

- 데이터 split과 checksum 검증
- metric calculation unit test
- raw result 불변성과 analysis reproducibility 검사
- 같은 commit·seed에서 report 재생성
- 결과 표와 원본 record 표본 대조
- 환경별 scenario manifest·split checksum·부하·반복 횟수 대조 및 비교 보고서 재생성

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

## Milestone 7 — 최종 AWS 검증과 데모 (선택)

### 목표와 선행 조건

M5 평가와 M6 운영 화면을 완성한 뒤 최종 사용 흐름을 AWS에서 재현한다. M4a의 첫 클라우드 테스트와 구분하며, 실행 여부·범위·비용은 사용자와 별도로 확정한다. 선택하지 않으면 사유를 기록하고 이 단계만으로 프로젝트 완료를 막지 않는다.

### Acceptance criteria

- [ ] 최종 버전의 배포 → 장애 재현 → Grafana 신호·Jev 추천·human review 확인 → 복구 흐름을 재현했다.
- [ ] M5에서 정한 품질·안전 기준의 회귀를 확인하고 최종 결과·한계·데모 절차를 README에 반영했다.
- [ ] 실행 비용과 크레딧 차감을 기록하고 생성 자원을 정리했다.

### 검증 방법 후보

- 버전을 고정한 end-to-end 데모와 M5 기준의 회귀 검증
- clean deployment·fallback·teardown 및 잔존 자원 확인

## 프로젝트 Definition of Done

- [ ] Milestone 0~6 및 M4a의 acceptance criteria를 충족하거나 합의된 범위 조정과 제외 이유를 결정 기록에 남겼다. 비용 승인 대기를 임의 제외로 처리하지 않는다.
- [ ] M7의 실행 여부를 기록하고, 실행했다면 해당 acceptance criteria도 충족했다.
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

- 완료: M4 뒤 M4a AWS 통합 테스트 추가, M5 로컬·AWS 비교 평가와 선택형 M7 최종 검증 계획 반영
- 마지막 검증: 2026-09-25, 문서 diff·링크·milestone 순서·승인 조건·미완료 상태 검증. 실행 코드가 바뀌지 않아 M1 테스트는 재실행하지 않음
- 마지막 구현 검증: M1 테스트 9개와 clean-cluster 통합 검증 2회 통과; 원본 결과 유지
- 실행 안내: `docs/M1-LOCAL.md`, 원본 결과: `results/m1-final.json`, 정리 확인: `results/m1-final-teardown.json`
- 다음 작업: M2의 chaos engine을 확정하고 S000 + 최소 5개 fault의 precondition·abort·복구·ground truth harness 구현
- 구현 상태: M1 완료. M2~M7 및 M4a 미구현·미실행. Jev 호출 및 실제 성능 평가 없음
- 비용: 이번 변경은 문서만 수정, 0원. AWS 계정 접근·리소스 생성·크레딧 사용 없음. 이전 M1 자원 정리 상태 유지
- 환경 차이: Python subprocess가 셸과 다른 kubectl을 선택해 첫 preflight 실패. 실제 실행 버전 v1.36.0으로 고정 후 통과
- 알려진 블로커: M1 없음. 후속 milestone의 pending 결정과 유료 실행 승인은 그대로 유지
