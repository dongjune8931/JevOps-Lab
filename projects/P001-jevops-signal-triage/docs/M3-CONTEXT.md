# M3 — Context Builder와 무료 규칙 비교군

## 구현 전 고정한 검증 계획

- 가설: 동일한 관측 window와 저장된 telemetry는 항상 동일한 제한된 state와 규칙 판단을 생성한다.
- 비교군: 외부 모델 없이 동작하는 `p001-rules-v1`. Jev 비교·calibration·최종 test 성능은 M4/M5 범위다.
- 성공 조건: schema·마스킹·정답 누수·timeout·부분 실패·크기 제한 테스트 통과, 기존 M2 관측 기록 재생, state/판단 재생성 일치, 로컬 수집 경로 검증.
- 반증 조건: 비밀/정답 문자열 유출, 누락 데이터를 정상으로 간주, 범위 밖 조회, 무제한 대기/출력, 같은 입력에서 다른 판단.
- design fixture와 M2 design 기록만 사용한다. 주입 성공을 사용자 영향 정답으로 치환하지 않으며 정확도 향상을 주장하지 않는다.

## 범위와 데이터 경계

Python 표준 라이브러리로 Prometheus matrix, Loki streams, Tempo search metadata를 요약한다. Context Builder는 ground truth record를 받지 않는다. CLI 재생기는 record에서 window만 추출하며 label/시나리오/파일 경로는 state 밖의 재현 메타데이터에만 둔다.

원문 로그를 정규식으로 일부 가리는 대신 고정된 합성 로그 문법만 `request_ok`/`request_error`로 치환한다. 나머지는 `unrecognized` 개수로만 남긴다. 서비스는 checkout/catalog/inventory만 허용한다. IP, 이메일, 사용자 ID, 토큰, 내부 주소, trace ID, annotation, 오류 메시지, 임의 key/value, chaos 메타데이터는 복사하지 않는다.

Kubernetes resources/events, CPU/memory, 변경 이력, 상세 dependency spans는 현재 M2 snapshot에 없으므로 미수집으로 표시한다. 현재 시점의 Kubernetes 상태를 과거 장애 window의 증거로 섞지 않는다. M3는 CLI 수집/재생·비교군 범위이며 Alertmanager 이벤트 큐·중복 제거·Jev provider·자동 실행은 포함하지 않는다.

## 계약과 제한

`src/triage/contracts.py`의 closed JSON Schema `p001-state-v1`이 권위 있는 계약이다. `python3 scripts/context.py schema`로 내보낼 수 있다. 런타임 validator는 그 schema가 사용하는 keyword만 검증하며 임의의 외부 schema를 실행하거나 다운로드하지 않는다.

| 필드 | 의미 |
|---|---|
| `schema_version`, `window` | 고정 버전과 요청한 UTC Unix window, 최대 300초 |
| `services` | checkout/catalog/inventory 순서의 정확히 3개 요약 |
| `metrics` | 관측 counter 증가량, window 길이로 나눈 요청률, 오류 비율, 평균 latency, reset 수, sample coverage |
| `logs` | 제한된 표본의 개수와 request_ok/request_error/unrecognized 빈도 |
| `traces` | root-service별 검색 표본의 개수·평균·최대 duration; ID/원문/span attributes 제외 |
| `data_quality` | backend 상태, 누락 신호, truncation/invalid 신호, 고정된 한계 목록 |

모든 key는 필수다. 측정되지 않은 metric·trace duration은 `null`이며 0으로 채우지 않는다. 문자열은 enum만 허용한다. 임의의 incident ID, source path, chaos ID, exception text, labels, annotation과 raw log는 없다. 로그당 입력은 160자 이하의 정확한 합성 문법만 해석하며 나머지는 원문 전체를 버린다.

- 입력 파일/객체: 최대 1 MiB. state: canonical ASCII JSON 최대 8 KiB. 넘으면 전송 가능한 state를 만들지 않고 실패한다.
- backend 응답: 각각 최대 348,501 bytes. query subprocess 전체 wall-clock timeout 4초, Kubernetes 요청 timeout 3초, 재시도 없음. 3개 backend 직렬 수집은 query 부분 최대 약 12초다. 사전 로컬 소유권 검사 시간은 별도다.
- metrics/streams: 최대 128행, counter series당 최대 128 samples. 초과 counter series는 잘라서 delta를 만들지 않고 제외·표시한다.
- logs: 전체 100개, traces: 20개. 검색 한도에 도달하면 완전성을 확인할 수 없으므로 truncated로 표시한다.
- 실패 backend는 missing/timeout/error/invalid/oversize enum만 남기며 정상 backend 요약은 유지한다.

## 통계 해석과 비교군

Counter delta는 window 안의 인접 samples 차이를 더한다. 감소 시 새 counter 값만 더하고 감소 횟수를 표시한다. 독립된 정상 counter라는 가정 아래 최초 sample 이전 증가량·재시작 사이 요청은 알 수 없으므로 증가량은 lower bound다. replica가 같은 series로 충돌하는 경우에는 이 가정이 성립하지 않을 수 있고, 감소가 있는 window의 숫자는 잠정값이다. PromQL `rate`/`increase`의 경계 외삽과 동일하지 않다. latency는 sum/count로 계산한 **평균**이며 p95나 p99가 아니다. [실측 한계](M3-VALIDATION.md)를 참조한다.

Loki/Tempo 조회는 제한된 표본이다. 실시간으로 같은 window를 다시 조회하면 ingest 지연이나 검색 순서 때문에 표본이 바뀔 수 있다. **동일한 저장 fixture의 재생**에 대해 결정성을 보장하며, 반복 live query가 동일하다고 주장하지 않는다. Tempo의 짧은 hex ID는 내부 dedup에만 사용하고 출력하지 않는다. duration이 없는 항목은 다른 유효 항목과 분리해 invalid로 표시한다.

`p001-rules-v1`은 실험 전에 고정한 단순 비교군이다. 현재 분포에서 최적화한 threshold가 아니며 calibrated confidence를 제공하지 않는다.

| 조건 | 증상 | 원인 분류/처리 |
|---|---|---|
| 오류 비율 ≥ 1% 또는 합성 오류 로그 | request_errors | unknown, human_review, inspect-service-errors |
| 오류 조건 없이 평균 latency ≥ 200ms | high_latency | unknown, human_review, inspect-latency |
| 아래 완전성 조건 + 위 두 조건 없음 | normal_observed | no_incident, observe, observe-service |
| 나머지 | insufficient_data | unknown, human_review, manual-investigation |

정상 추천에는 세 backend 성공, invalid/truncation 없음, 세 서비스 각각 요청 증가량 ≥ 3·counter coverage ≥ 0.8·reset 없음·유효 오류율/latency·인식 가능한 로그 존재, 최소 1개 trace 표본이 필요하다. `no_incident`는 관측된 신호에 대한 규칙 결과이지 무장애 보장이 아니다. CPU/메모리·배포·상세 dependency 증거가 없어 root cause는 항상 unknown이다. 정상 외에는 자동 처리하지 않는다.

팀 추천 `application`은 증상이 있고 기본 관측이 충분할 때의 합성 소유 영역이며 실제 조직 라우팅/호출은 아니다. 나머지는 human_triage다. runbook은 [고정된 조사 목록](M3-RUNBOOKS.md)에서만 추천한다. raw state와 rule prediction만 다음 M4 adapter에 제공하며, 실행 record의 metadata/latency를 통째로 모델 입력에 넣지 않는다.

## 실행

프로젝트 폴더에서 실행한다. replay·unit test·schema는 Docker나 클라우드 없이 Python 표준 라이브러리만 필요하다. 기존 전체 테스트는 Python 3.12.10 컨테이너에서 실행한다.

```bash
python3 -m unittest discover -s tests -p test_context.py -v
python3 scripts/context.py schema
python3 scripts/context.py replay \
  --run-dir results/m2/m2-s005-1790322543120343000 \
  --output .local/m3-replay-example.json
python3 scripts/report_context.py --output .local/m3-report.json
python3 scripts/lab.py test
```

결과 파일은 덮어쓰지 않는다. 재실행할 때 새 output 이름을 사용한다. report는 모든 M2 record를 열고 telemetry checksum을 확인한 뒤 각각 3번 재생한다. window만 Builder에 들어가며 scenario·기대 원인은 입력되지 않는다. telemetry가 없는 실행은 제외 사유를 남긴다. `semantic_sha256`은 timing/host/실행시각을 제외한 입력 checksum과 state/판단 checksum의 재현성 비교값이다. latency는 `perf_counter`로 별도 record에 저장한다.

실제 local backend 조회:

```bash
python3 scripts/lab.py start
python3 scripts/lab.py verify
# start/end에는 실제 합성 트래픽이 존재하는 최근 window의 Unix timestamp를 지정한다.
python3 scripts/context.py live --start <START_UNIX> --end <END_UNIX> \
  --output .local/m3-live.json
python3 scripts/lab.py teardown
```

live는 기존 lab의 workspace ownership·로컬 Docker Unix socket·loopback Kubernetes endpoint 검사를 재사용한다. 외부 URL·임의 query·context override를 받지 않으며 `p001` 서비스 proxy의 GET만 수행한다. `.local`의 kubeconfig/owner는 기록에 복사하지 않는다. 새로운 서비스, API 서버, 포트포워드, 상시 daemon은 만들지 않는다.

## 보안·실패·teardown

- 악성 문자열, dummy token/email/IP/사용자 ID/hostname, 추가 key, raw trace/로그, chaos label 누출 테스트를 수행한다.
- unknown 문자열은 일부를 잘라 보존하지 않고 제거한다. 출력 배열과 숫자 범위도 검증한다.
- 지연·대용량 응답은 subprocess를 kill/reap한다. stderr는 수집하지 않아 인증/응답 내용이 실패 로그로 흘러가지 않는다.
- replay에는 정리할 인프라가 없다. live 검증용 랩은 기존 `lab.py teardown`으로 삭제하고 node/volume 잔존 여부를 기록한다. 다른 랩·공유 network·이미지 캐시는 보존한다.
- 이 마스킹 정책은 고정된 합성 fixture용이다. 운영 telemetry의 익명화 안전성을 인증하지 않으며, 실제 운영 데이터의 사용·외부 전송은 별도 승인 대상이다.

## 공식 API 근거

- [Prometheus query API](https://prometheus.io/docs/prometheus/latest/querying/api/): matrix timestamp/value 구조와 range query.
- [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/): query_range, stream/value 구조, 시간·개수 제한.
- [Tempo HTTP API](https://grafana.com/docs/tempo/latest/api_docs/): search metadata와 검색 표본 순서의 비결정성. M3는 저장한 응답의 재생을 검증한다.

실제 검증은 저장소에 고정된 Prometheus 3.2.1/Loki 3.4.2/Tempo 2.7.2의 응답을 기준으로 한다.
