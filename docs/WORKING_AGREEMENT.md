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

1. 상태: proposed, active, paused, completed 중 하나
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
| 상태 | proposed, active, paused, completed |
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

## 9. 언어 기준

- README, 계획, 결과, 의사결정 문서는 한국어를 기본으로 한다.
- 코드 식별자, 브랜치, 커밋, PR 제목은 영어를 사용한다.
- 로그, 메트릭, Jev question ID는 기계 처리와 비교가 쉽도록 영어를 사용한다.
- Jev의 한국어 성능 자체가 실험 대상이 아니라면 모델 입력은 영어 정규화본을 기본 후보로 검토한다.

## 10. 프로젝트·실험 생성 체크리스트

- [ ] 고유한 ID와 slug를 루트 카탈로그에서 확인했다.
- [ ] 작업 단위 전용 폴더를 만들었다.
- [ ] `README.md`, `PLAN.md`, `DECISIONS.md`, `COSTS.md`를 만들었다.
- [ ] 목표, 비목표, 완료 조건을 기록했다.
- [ ] 무료 기본 실행 경로를 정의했다.
- [ ] 작업 단위 전용 PR 템플릿을 만들었다.
- [ ] 루트 README에 항목과 링크를 추가했다.
- [ ] 별도 브랜치와 PR에서 변경했다.

## 11. 첫 번째 후보 작업

첫 프로젝트 후보는 `P001-jevops-signal-triage`다.

- 카오스 엔지니어링으로 알려진 장애를 주입해 ground truth를 만든다.
- OpenTelemetry, Prometheus, Tempo, Loki 등에서 장애 관련 신호를 수집한다.
- Jev가 장애 유형, 심각도, 담당 팀, 추천 runbook을 구조화된 값으로 판단한다.
- Grafana에서 시스템 상태와 Jev 판단 품질을 함께 시각화한다.
- 실제 구현은 이 저장소 운영 계획이 확정된 뒤 별도 프로젝트 세션과 PR에서 시작한다.

