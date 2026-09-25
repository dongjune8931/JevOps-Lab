# JevOps-Lab 운영 계획

이 문서는 여러 Codex 세션과 여러 프로젝트·실험이 같은 저장소에서 충돌 없이 진행되도록 하는 저장소 운영 기준이다. 세부 구현보다 작업 경계, 문서화, Git/PR, 비용 통제를 우선 정의한다.

## 1. 목표

- Jev를 DevOps 업무에 적용하는 프로젝트와 실험을 독립적으로 축적한다.
- 각 작업의 가설, 구현, 결과, 한계, 비용을 나중에 재현할 수 있게 남긴다.
- 프로젝트마다 별도 Codex 세션을 사용해도 저장소의 공통 규칙과 현재 상태가 유지되게 한다.
- 모든 변경을 PR로 검토 가능한 형태로 남기고 일관된 Git 이력을 유지한다.

## 2. 저장소 구조

```text
JevOps-Lab/
├── AGENTS.md
├── README.md
├── CONTRIBUTING.md
├── docs/
│   └── WORKING_AGREEMENT.md
├── projects/
│   └── P###-project-slug/
│       ├── README.md
│       ├── PLAN.md
│       ├── DECISIONS.md
│       ├── COSTS.md
│       ├── src/
│       ├── tests/
│       ├── deploy/
│       ├── dashboards/
│       ├── fixtures/
│       └── docs/
├── experiments/
│   └── E###-experiment-slug/
│       ├── README.md
│       ├── PLAN.md
│       ├── DECISIONS.md
│       ├── COSTS.md
│       ├── src/
│       ├── fixtures/
│       └── results/
├── shared/
│   ├── libraries/
│   ├── tooling/
│   └── fixtures/
└── .github/
    └── PULL_REQUEST_TEMPLATE/
        ├── repository.md
        ├── project.md
        └── experiment.md
```

Git이 빈 폴더를 추적하지 않으므로 실제 작업에 필요한 폴더만 생성한다.

### 프로젝트와 실험의 구분

- `projects/`: 지속적으로 사용하거나 확장할 수 있는 애플리케이션, 서비스, CLI, 플랫폼.
- `experiments/`: 명확한 가설과 종료 조건을 가진 비교, 벤치마크, 기술 검증.
- 프로젝트 안에서 발생한 짧은 검증은 프로젝트 내부에 둘 수 있지만, 독립적인 결과나 별도 세션·PR 흐름이 필요하면 `experiments/`에 새 ID로 분리한다.
- 한 작업 단위의 구현 파일은 반드시 자신의 루트 폴더 아래에 둔다. 저장소 루트에 프로젝트 전용 소스나 설정을 두지 않는다.

### ID와 이름

- 프로젝트: `P001-jevops-signal-triage`
- 실험: `E001-signal-ablation`
- 번호는 루트 `README.md` 카탈로그에서 사용하지 않은 다음 번호를 선택한다.
- slug는 소문자 kebab-case 영어를 사용하며, 생성 후 의미가 바뀌어도 가급적 변경하지 않는다.

## 3. 세션과 작업 단위

- 프로젝트마다 별도 Codex 세션을 사용한다.
- 큰 프로젝트는 milestone별로 세션을 가지치기할 수 있지만 동일한 프로젝트 폴더와 문서를 source of truth로 사용한다.
- 새 세션은 프로젝트 전체를 무조건 읽지 않고, `AGENTS.md`와 자신의 작업 단위 문서부터 읽는다.
- 세션 종료 전 `PLAN.md`의 진행 상태와 `DECISIONS.md`의 중요한 결정을 갱신한다.
- 다음 세션이 추론해야만 알 수 있는 중요한 상태를 대화에만 남기지 않는다.

## 4. 작업 단위 필수 문서

### `README.md`

최소한 다음 내용을 포함한다.

1. 상태: proposed, active, paused, completed, archived 중 하나
2. 프로젝트 또는 실험 요약
3. 해결하려는 DevOps 문제
4. Jev의 역할과 사용한 primitive
5. 아키텍처 또는 실험 설계
6. 실행 및 재현 방법
7. 평가 지표와 검증 방법
8. 결과와 성과
9. 알려진 한계와 실패 사례
10. 비용 요약 및 `COSTS.md` 링크

결과가 아직 없다면 `아직 측정되지 않음`이라고 명시하고 예상 결과를 실제 결과처럼 쓰지 않는다.

### `PLAN.md`

- 목표와 비목표
- milestone과 각 acceptance criteria
- milestone별 검증 명령
- 현재 상태와 다음 작업
- 마지막으로 완료한 작업과 검증 결과
- 현재 브랜치, PR, 해결되지 않은 문제와 사용자 결정이 필요한 항목
- 완료 조건

### `DECISIONS.md`

날짜, 결정, 배경, 선택한 이유, 대안, 후속 영향을 짧게 기록한다.

### `COSTS.md`

- 무료로 실행 가능한 기본 경로
- 비용이 발생할 수 있는 서비스와 예상 단가
- 사용자 승인 일시와 승인 상한
- 가능하면 실제 사용량과 실제 비용

## 5. 루트 README 카탈로그

루트 `README.md`는 저장소 소개와 작업 단위의 인덱스다. 프로젝트·실험마다 다음 항목을 한 행으로 요약한다.

| 항목 | 설명 |
|---|---|
| ID | `P###` 또는 `E###` |
| 이름 | 작업 단위 이름과 README 링크 |
| 상태 | proposed, active, paused, completed, archived |
| 내용 | 무엇을 만드는지 또는 무엇을 검증하는지 |
| Jev 활용 | Jev가 담당하는 판단 |
| 결과 | 핵심 수치 또는 아직 측정되지 않았다는 표시 |

상세 내용은 중복 작성하지 않고 작업 단위의 README로 연결한다.

## 6. Git 규칙

### 브랜치

항상 최신 `origin/main`에서 분기한다.

```text
<type>/<unit-id>-<short-description>
```

예시:

```text
docs/repository-governance
feat/p001-alert-triage
experiment/e001-signal-ablation
fix/p001-context-timeout
```

허용 type:

- `feat`: 기능 추가
- `fix`: 버그 수정
- `experiment`: 실험 추가 또는 변경
- `docs`: 문서 변경
- `refactor`: 동작 변경 없는 구조 개선
- `test`: 테스트만 변경
- `chore`: 유지보수 및 도구 설정

### 커밋

Conventional Commits 형식을 사용한다.

```text
<type>(<scope>): <imperative summary>
```

예시:

```text
feat(p001): add alert context builder
experiment(e001): compare metrics and trace signals
docs(repo): define repository workflow
```

- type과 scope, 제목은 영어를 사용한다.
- scope는 작업 단위 ID를 소문자로 쓰고 저장소 공통 변경은 `repo`를 사용한다.
- 한 커밋에는 하나의 논리적 변경만 담는다.
- 생성된 대용량 결과물, 비밀정보, 로컬 환경 파일은 커밋하지 않는다.

## 7. PR 규칙

모든 변경은 다음 순서로 진행한다.

1. 최신 `origin/main` 확인
2. 작업 브랜치 생성
3. 구현과 관련 문서 갱신
4. 해당 범위의 테스트·lint·build 실행
5. 변경 파일과 diff 검토
6. 커밋 및 원격 push
7. 올바른 PR 템플릿으로 PR 생성
8. 필수 검사가 통과할 때까지 수정
9. squash merge
10. 원격 작업 브랜치 삭제 및 로컬 `main` 동기화

### PR 범위

- 한 PR은 하나의 프로젝트 또는 실험만 변경한다.
- 저장소 공통 규칙 변경은 별도의 repository PR로 분리한다.
- 공용 코드가 필요하면 먼저 작업 단위 안에서 검증한다. 두 번째 소비자가 생겼을 때 별도 PR로 `shared/`에 추출한다.
- 프로젝트 결과가 바뀌는 PR은 해당 README와 루트 README를 함께 갱신한다.

### PR 제목

커밋과 동일한 형식을 사용한다.

```text
feat(p001): classify alert ownership with Jev
```

### PR 템플릿

- 저장소 공통 작업: `.github/PULL_REQUEST_TEMPLATE/repository.md`
- 새 프로젝트를 만드는 첫 PR: `project.md`를 사용하고, 동시에 `<project-id>.md` 전용 템플릿을 생성한다.
- 새 실험을 만드는 첫 PR: `experiment.md`를 사용하고, 동시에 `<experiment-id>.md` 전용 템플릿을 생성한다.
- 이후 PR은 반드시 작업 단위 전용 템플릿을 사용한다.

GitHub CLI 예시:

```bash
gh pr create --template p001.md
```

GitHub는 `.github/PULL_REQUEST_TEMPLATE/` 아래에 여러 템플릿을 둘 수 있다. 전용 템플릿에는 그 작업 단위의 검증 명령, 결과 문서 체크, 비용 확인 항목을 포함한다.

### 머지 정책

- Codex는 사용자가 별도로 중단을 요청하지 않는 한 PR 작성부터 필수 검사 확인, 수정, squash merge까지 담당한다.
- 필수 검사가 없더라도 작업 단위 문서에 정의된 검증을 실행한다.
- 비용 승인, 운영 환경 변경, 비밀정보 입력, 권한 부족 등 사용자 판단이 필요한 상태에서는 머지하지 않는다.
- 미완료, 실패한 테스트, 알려진 치명적 결함을 숨긴 채 머지하지 않는다.

## 8. 비용 정책

기본 예산은 `0원`이다. 다음 작업은 실행 전에 반드시 사용자 승인을 받는다.

- Jev, LLM 등 사용량 기반 API의 유료 호출
- 클라우드 VM, Kubernetes, 스토리지, 네트워크, 관리형 데이터베이스 생성
- 유료 SaaS, 플러그인, 라이선스 또는 구독
- 비용 발생 가능성이 불명확한 외부 서비스 사용

승인 요청에는 다음을 포함한다.

1. 서비스와 목적
2. 예상 비용과 최대 상한
3. 과금 단위와 중단 방법
4. 무료 또는 로컬 대안
5. 비용을 추적할 위치

사용자의 승인은 특정 작업과 상한에만 유효하다. 다른 세션이나 후속 실험에서 자동으로 재사용하지 않는다.

## 9. Definition of Done

프로젝트 또는 실험은 다음 조건을 모두 만족해야 `completed`로 표시한다.

- 목표와 acceptance criteria를 충족했다.
- 해당 범위의 테스트, lint, build가 통과했다.
- 깨끗한 환경에서 문서의 실행 또는 재현 절차를 검증했다.
- 결과 수치가 원본 결과 파일 또는 재현 가능한 명령과 연결돼 있다.
- 성공뿐 아니라 알려진 실패, 한계, 제외한 데이터와 이유를 문서화했다.
- `README.md`, `PLAN.md`, `DECISIONS.md`, `COSTS.md`가 최신 상태다.
- 루트 `README.md` 카탈로그에 상태, Jev 활용, 핵심 결과를 반영했다.
- 생성한 리소스를 정리하고 과금이 종료됐는지 확인했다.
- 비밀정보와 민감한 운영 데이터가 커밋 또는 외부 전송되지 않았음을 확인했다.
- PR 검사가 통과했고 squash merge 및 원격 브랜치 삭제를 완료했다.

조건을 충족하지 못한 작업은 `active`, `paused` 또는 `archived`로 남기며 예상 결과를 완료된 성과처럼 표현하지 않는다.

## 10. 세션 인수인계

새 문서가 과도하게 늘어나는 것을 막기 위해 별도 `STATUS.md` 대신 `PLAN.md`의 현재 상태 섹션을 인수인계 기록으로 사용한다. 각 세션은 종료 전에 다음 내용을 갱신한다.

- 완료한 milestone과 변경 요약
- 현재 브랜치와 PR URL 또는 PR 생성이 막힌 이유
- 마지막으로 실행한 검증 명령과 결과
- 다음 세션이 시작할 구체적인 작업
- 해결되지 않은 문제와 기술 부채
- 사용자 승인 또는 외부 상태 변경이 필요한 블로커
- 재현에 필요한 주요 명령과 환경 차이

중요한 아키텍처 선택은 `PLAN.md`가 아니라 `DECISIONS.md`에도 남긴다.

## 11. 실행 환경과 재현성

- 런타임, 도구, 주요 라이브러리와 인프라 컴포넌트 버전을 고정한다.
- 재현 가능한 lockfile, 컨테이너 이미지 digest 또는 명시적 버전을 우선한다.
- 의미가 변할 수 있는 `latest` 이미지 태그를 재현성 기준으로 사용하지 않는다.
- 가능하면 설치, 실행, 테스트, teardown을 일관된 명령이나 task runner로 제공한다.
- `.env.example`에는 변수 이름과 설명만 두고 실제 비밀값을 포함하지 않는다.
- 실행 환경 차이가 결과에 영향을 줄 수 있으면 운영체제, 아키텍처, 클러스터와 주요 리소스 제한을 기록한다.

### 실험 run 메타데이터

각 측정 run은 가능한 범위에서 다음 정보를 보존한다.

- 실행 시각과 timezone
- Git commit SHA와 dirty worktree 여부
- 요청한 모델 alias와 응답이 반환한 실제 모델 버전
- Jev question 및 criteria 버전 또는 checksum
- 데이터셋과 fixture 버전 또는 checksum
- 비교 대상 모델, provider와 주요 설정
- 반복 횟수, random seed, timeout, concurrency
- 주요 의존성 및 실행 환경 버전
- 요청 수, 입력 토큰 등 사용량과 추정·실제 비용
- 원본 결과와 처리된 결과의 경로

`jev-latest` 같은 alias만 기록하지 않는다. provider가 실제 버전을 반환하지 않으면 그 사실과 실행 시각을 명시한다.

## 12. 결과 무결성

- 실험 실행 전에 가설, 비교군, 평가 지표, 성공 기준과 반증 조건을 `README.md` 또는 `PLAN.md`에 고정한다.
- baseline, Jev, 규칙 기반 방식, 다른 모델 등 비교 대상에는 가능한 한 동일한 입력과 평가 절차를 적용한다.
- 성공한 run만 선택하지 않고 실패, timeout, API 오류도 결과에 포함하거나 제외 이유를 기록한다.
- 원본 결과는 후처리 결과와 구분하고 가능하면 불변 파일로 보존한다.
- 수동으로 제외하거나 수정한 데이터는 대상, 이유, 영향을 기록한다.
- 예상, 공급자 주장, 실제 측정 결과를 명확히 구분한다.
- README의 성능, 비용, 정확도 주장은 원본 결과 또는 분석 파일로 연결한다.
- 동일 데이터가 질문 설계나 threshold 튜닝과 최종 평가에 중복 사용돼 결과가 누수되지 않도록 한다.

대용량 또는 민감한 원본 결과를 Git에 저장할 수 없다면 checksum, 생성 절차, 보관 위치와 접근 조건을 기록한다.

## 13. 보안과 데이터 처리

- 합성 데이터와 로컬 환경을 기본값으로 사용한다.
- 운영 로그, trace, metric label, Kubernetes 리소스에는 사용자 정보, 내부 주소, 토큰이나 식별자가 포함될 수 있다고 가정한다.
- 이메일, IP, 사용자 ID, 토큰, 세션 ID, 계정명과 내부 hostname은 저장 또는 외부 전송 전에 제거하거나 마스킹한다.
- 실제 운영 telemetry나 저장소 비공개 데이터를 Jev 또는 다른 외부 API에 전송하려면 범위와 위험을 설명하고 사용자의 명시적 승인을 받는다.
- API 키, 토큰, kubeconfig, 인증서, 개인키와 실제 `.env` 파일을 커밋하지 않는다.
- fixture와 예제에는 실제 비밀값처럼 보이는 문자열 대신 명백한 dummy 값을 사용한다.
- secret scanning 또는 저장소 기록에서 비밀 노출을 발견하면 추가 사용을 중단하고 사용자에게 폐기·교체 필요성을 알린다.

## 14. 리소스와 비용 종료

- Kubernetes namespace, Helm release, cloud resource, SaaS integration 등 생성되는 모든 리소스에는 생성과 teardown 절차를 함께 제공한다.
- 실험에는 timeout과 최대 반복 횟수를 두고 무제한 실행을 금지한다.
- 유료 리소스는 목적을 달성한 즉시 종료하는 것을 기본으로 한다.
- 작업 종료 전 남은 Pod, Job, namespace, load balancer, disk, IP, cluster와 외부 서비스 실행 상태를 확인한다.
- 자동 teardown이 실패하면 반복적인 파괴 명령을 실행하지 말고 남은 리소스, 예상 비용 영향, 수동 정리 방법을 사용자에게 알린다.
- 운영 환경에서의 장애 주입, 배포, 데이터 변경은 비용 승인과 별개로 사용자에게 별도 승인을 받는다.
- 정리 명령과 확인 결과를 `README.md` 또는 실행 결과에 남기고 비용 정보는 `COSTS.md`에 반영한다.

## 15. 작업 생명주기와 보관

작업 상태는 다음 중 하나를 사용한다.

- `proposed`: 아직 구현을 시작하지 않음
- `active`: 구현 또는 측정 진행 중
- `paused`: 재개할 의도가 있지만 사용자 요청이나 명시적 사유로 중단
- `completed`: Definition of Done 충족
- `archived`: 더 이상 진행하지 않음

`paused` 또는 `archived` 상태에는 중단 이유, 마지막으로 확인된 결과, 재개 조건을 README에 기록한다. 코드를 삭제하기보다 결과와 실패에서 얻은 교훈을 보존하며, 보안이나 라이선스 문제로 제거해야 한다면 별도 PR에서 처리한다.

## 16. 운영 규칙 개선

- 반복되는 실패, 여러 작업 단위에서 필요한 규칙, 새 비용 또는 보안 위험을 발견하면 공통 규칙 추가를 제안한다.
- 프로젝트·실험 구현 PR에 저장소 공통 규칙 변경을 섞지 않는다. 별도의 `docs(repo)` 브랜치와 repository PR로 분리한다.
- `AGENTS.md`에는 모든 세션에 필요한 짧은 규칙만 두고 상세 설명은 이 문서로 연결한다.
- 규칙 추가 시 해결하려는 실제 문제와 영향을 `DECISIONS.md` 또는 PR 설명에 기록한다.
- 더 이상 필요하지 않거나 중복되는 규칙은 제거해 세션 문맥이 불필요하게 커지지 않게 한다.

## 17. 언어 기준

- README, 계획, 결과, 의사결정 문서는 한국어를 기본으로 한다.
- 코드 식별자, 브랜치, 커밋, PR 제목은 영어를 사용한다.
- 로그, 메트릭, Jev question ID는 기계 처리와 비교가 쉽도록 영어를 사용한다.
- Jev의 한국어 성능 자체가 실험 대상이 아니라면 모델 입력은 영어 정규화본을 기본 후보로 검토한다.

## 18. 프로젝트·실험 생성 체크리스트

- [ ] 고유한 ID와 slug를 루트 카탈로그에서 확인했다.
- [ ] 작업 단위 전용 폴더를 만들었다.
- [ ] `README.md`, `PLAN.md`, `DECISIONS.md`, `COSTS.md`를 만들었다.
- [ ] 목표, 비목표, 완료 조건을 기록했다.
- [ ] 무료 기본 실행 경로를 정의했다.
- [ ] 버전 고정, 결과 메타데이터, teardown 방법을 정의했다.
- [ ] 데이터 출처와 민감정보 처리 방식을 확인했다.
- [ ] 작업 단위 전용 PR 템플릿을 만들었다.
- [ ] 루트 README에 항목과 링크를 추가했다.
- [ ] 별도 브랜치와 PR에서 변경했다.

## 19. 첫 번째 후보 작업

첫 프로젝트 후보는 `P001-jevops-signal-triage`다.

- 카오스 엔지니어링으로 알려진 장애를 주입해 ground truth를 만든다.
- OpenTelemetry, Prometheus, Tempo, Loki 등에서 장애 관련 신호를 수집한다.
- Jev가 장애 유형, 심각도, 담당 팀, 추천 runbook을 구조화된 값으로 판단한다.
- Grafana에서 시스템 상태와 Jev 판단 품질을 함께 시각화한다.
- 실제 구현은 이 저장소 운영 계획이 확정된 뒤 별도 프로젝트 세션과 PR에서 시작한다.
