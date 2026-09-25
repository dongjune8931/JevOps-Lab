# P001 비용 계획 및 기록

## 현재 상태

- 기본 예산: 0원
- 사용자 승인 비용 상한: 0원
- 실제 사용액: 0원
- 승인된 유료 서비스: 없음
- 이번 M1 세션의 유료·외부 AI API 호출: 없음
- 이번 M1 세션의 리소스 생성: 로컬 전용 kind 클러스터 2회 생성·검증·삭제; 클라우드 리소스 없음

## 0원 기본 경로

다음 경로를 기본으로 하며 설치 또는 실행 전에 라이선스와 사용자 환경을 확인한다.

| 영역 | 무료 경로 |
|---|---|
| 실행 환경 | 사용자가 이미 보유한 로컬 머신과 설치된 container runtime |
| Kubernetes | kind, k3d 또는 minikube 중 승인된 로컬 도구 |
| Chaos | Chaos Mesh 또는 LitmusChaos 오픈소스 배포 |
| 계측·수집 | OpenTelemetry SDK와 Collector 오픈소스 배포 |
| Metrics | Prometheus 로컬 배포 |
| Traces | Tempo 로컬 단일 프로세스 또는 개발 구성 |
| Logs | Loki 로컬 단일 binary 또는 개발 구성 |
| 시각화 | Grafana OSS 로컬 배포 |
| Jev 개발 | mock adapter와 저장된 synthetic response fixture |
| Baseline | deterministic rules와 로컬 evaluator |
| 데이터 | synthetic traffic, chaos ground truth와 합성 fixture |

무료 경로에서는 클라우드 계정, Grafana Cloud, 유료 API, 외부 managed Kubernetes를 사용하지 않는다. 로컬 컴퓨팅·전기·기존 인터넷 비용은 금액 산정에서 제외하되 리소스 요구량은 문서화한다.

## 비용 발생 가능 항목

가격은 변경될 수 있으므로 실행 직전에 공식 가격과 계정 조건을 다시 확인한다. 아래 항목은 사용자 승인 전 실행하지 않는다.

| 항목 | 과금 가능 기준 | 비용 통제 방법 | 무료 대안 |
|---|---|---|---|
| TypeSafe Jev API | 입력 token, credit 또는 plan | 요청 수·입력 token 상한, 소규모 pilot, 즉시 중단 스위치 | mock adapter와 저장된 fixture |
| OpenRouter Jev | provider usage와 gateway 정책 | 모델 ID 고정, usage 응답 기록, 요청 상한 | 공식 API 검토 또는 mock |
| 일반 LLM baseline | input/output token | 작은 stratified sample, 단일 모델, 총예산 상한 | 규칙 baseline만 사용 |
| Managed Kubernetes | cluster·node 실행 시간 | 사용하지 않는 것을 기본으로 하고 종료 시각 설정 | 로컬 Kubernetes |
| Cloud storage·network | 저장량, request, egress | 원본 결과 로컬 보존, retention 제한 | 로컬 volume |
| Grafana Cloud 등 SaaS | plan과 ingest volume | 가입·전송 전 승인, 제한된 synthetic data만 사용 | Grafana OSS stack |
| CI hosted runner | 공개 저장소 quota 또는 초과 사용 | 짧은 문서·unit test, matrix 제한 | 로컬 검증 |

## 비용 승인 절차

유료 실행 전 다음 내용을 사용자에게 제시한다.

1. 사용할 서비스와 정확한 목적
2. 최신 공식 단가와 과금 단위
3. 예상 요청 수, token 또는 실행 시간
4. 계산된 예상 비용과 절대 최대 상한
5. 상한 도달 전 중단 방법
6. 무료 대안과 유료 호출이 필요한 이유
7. telemetry 또는 데이터가 외부로 전송되는 범위

승인은 해당 milestone과 상한에만 유효하며 다른 세션에서 재사용하지 않는다.

## 비용 계산식 후보

```text
Jev run cost = sum(request input tokens × applicable input-token rate)
LLM baseline cost = sum(input tokens × input rate + output tokens × output rate)
Cost per incident = total approved API cost / evaluated incidents
Projected cost per 1,000 alerts = mean cost per decision × 1,000
```

provider가 credit 기반이면 token 추정과 별도로 실제 차감 credit을 기록한다. 무료 credit도 사용량과 소진량을 기록하며 0원이라고 해서 무제한 호출하지 않는다.

## 비용 ledger

| 날짜 | 세션/PR | 서비스 | 승인 상한 | 실제 사용량 | 실제 비용 | 비고 |
|---|---|---|---:|---:|---:|---|
| 2026-09-25 | P001 기획 | 없음 | 0원 | 0 | 0원 | 문서 작성만 수행 |
| 2026-09-25 | P001 M1 | 기존 로컬 Docker, kind, OSS 관측 스택 | 0원 | 신규 로컬 클러스터 검증 2회 | 0원 | 공개 이미지·패키지 다운로드, 합성 데이터만 사용; 유료 API·SaaS 없음 |

M1 종료 확인: [최종 teardown 결과](results/m1-final-teardown.json)에서 P001 node container와 volume 잔존 0개를 확인했다. Grafana 포워딩도 종료했다. 재실행용 이미지·빌드 캐시와 다른 랩이 사용하는 공유 network는 보존했다. 클라우드·유료 SaaS 구독이나 리소스를 생성하지 않았다.

## 종료와 정리

- 유료 API 실행 뒤 usage 응답과 dashboard 사용량을 가능한 범위에서 교차 확인한다.
- 로컬 실험도 container, cluster, volume과 port-forward를 teardown한다.
- cloud 또는 SaaS를 승인받은 경우 resource ID, 생성·종료 시각과 최종 과금 상태를 기록한다.
- 자동 정리가 실패하면 추가 비용 가능성과 수동 종료 방법을 즉시 보고한다.
