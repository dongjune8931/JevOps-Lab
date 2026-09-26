# M3 검증 기록 — 2026-09-26

## 검증 버전과 범위

- 코드 commit: `7d8415c8ad2c0409d8d938a56e41d742834ca330`
- 코드·fixture·설정 source SHA-256: `f6f0a49318c05408f3d2b5765e4f2c8cbc68fa4867ed4fe5a84ee9278020e981`
- state: `p001-state-v1`, rules: `p001-rules-v1`
- 호스트 Python 3.14.6, 격리 테스트 컨테이너 Python 3.12.10. runtime·도구·이미지 버전은 [관측 회귀 결과](../results/m3-observability-regression.json)에 기록했다.
- 최종 replay·live·관측 회귀는 위 commit의 clean worktree에서 실행했다. 이후 결과·문서만 추가했다.
- Jev 모델·question·seed: 해당 없음, 외부 AI 호출 0회, 비용 0원. CPU stress 등 새로운 chaos 실행도 하지 않았다.

## 테스트

```bash
python3 -m unittest discover -s tests -p test_context.py -v
python3 scripts/lab.py test
python3 -m compileall -q src/triage scripts/context.py scripts/report_context.py tests/test_context.py
git diff --check
```

전체 **71개 통과**: 기존 M1/M2 33개 + M3 38개. 전체 suite는 `--network none --read-only` 컨테이너와 임시 `/tmp`로 실행했다.

최종 문서 local link 76개에 누락이 없고 Python 구문·diff 공백 검사를 통과했다. 새 소스/fixture/결과에서 private-key·AWS/GitHub/API-key 기본 패턴 검색에 일치가 없었다. gitleaks는 설치돼 있지 않아 실행하지 않았으며, 범용 secret scanner 인증으로 표현하지 않는다.

- closed schema·golden fixture·출력 크기·배열·counter sample 상한
- 추가 key, dummy token/email/IPv4/IPv6/사용자 ID/hostname/정답 label 누출
- 허용 필드 내부 악성 텍스트·긴 Unicode 로그 제거, 입력 불변성
- timestamp window, NaN/Inf/음수/bool, 중복 series, 충돌 samples, counter 감소
- backend 누락·잘못된 envelope·빈 로그/trace·부분 실패
- 실제 subprocess의 wall-clock timeout, 출력 byte cap, 오류 stderr 폐기 및 종료
- Tempo 짧은 ID 중복 제거와 duration 누락 항목 격리
- 정상/오류/지연/증거 부족 규칙과 unknown/human_review 경계
- M2 artifact checksum, state/판단 결정성, 불변 output, symlink·대용량 입력 거부

## 저장된 M2 관측 데이터 재생

[최종 보고서](../results/m3-replay.json)는 모든 30개 record를 포함한다. telemetry가 있는 **28개를 각각 3회**, 총 84회 재생했다. 초기 구현·실패·abort 기록도 임의로 제거하지 않았다. 이것은 M2 최종 acceptance의 14개 subset과 다른 **M3 입력 호환성 검증**이다.

- 28개 모두 동일 입력 → 동일 state checksum·동일 판단 checksum
- telemetry가 없는 precondition_failed 2개는 `no_telemetry_artifact`로 제외했다. run ID와 checksum은 보고서에 남겼다.
- 오류 증상 9개, 지연 증상 6개, 증거 부족 13개. 모두 incident_type/root cause는 unknown이며 human_review 추천이다.
- state 최대 크기 **1,662 bytes**, 상한 8,192 bytes
- context build p50/p95/p99: **1.737 / 2.683 / 3.733ms**
- rules p50/p95/p99: **0.045 / 0.098 / 0.149ms**
- semantic checksum: `41deb4709151608c8c342bf7a027757a37b9664193093b826f8dc76f1ec70d32`

호스트에서 한 batch를 측정한 수치다. backend query·파일 read·Jev latency는 포함하지 않는다. accuracy·calibration은 null이며, unknown 비율을 개선하거나 정상/주입 label에 맞추려고 threshold를 튜닝하지 않았다.

다음 명령으로 재생성과 semantic checksum을 비교한다. latency·실행시각·환경 record는 실행마다 달라질 수 있다.

```bash
python3 scripts/report_context.py --output .local/m3-new-report.json
jq -r '.semantic_sha256' results/m3-replay.json .local/m3-new-report.json
python3 scripts/context.py replay \
  --run-dir results/m2/m2-s005-1790322543120343000 --output .local/m3-new-example.json
```

별도 재실행에서도 semantic checksum 일치를 확인했다. [예시 state·판단](../results/m3-example.json)은 의존 서비스 중단 실행에서 관측된 오류 증상을 나타내지만 입력에는 해당 정답 label을 넣지 않았다. 원본 M2 window는 주입·관측·복구 구간을 포함하므로 순수 fault phase 통계로 해석하지 않는다.

## 실제 로컬 통합

기존 Docker에서 전용 `p001-m1` kind 클러스터를 새로 만들었다. 로컬 PATH의 기본 kubectl은 1.35.1이므로 `/opt/homebrew/bin`을 우선해 저장소의 고정 버전 1.36.0을 사용했다. 네트워크 이미지 확인이 지연됐으나 timeout 이내 정상 완료했다.

```bash
env PATH=/opt/homebrew/bin:/Users/idongjun/.rd/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin python3 scripts/lab.py start
env PATH=/opt/homebrew/bin:/Users/idongjun/.rd/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin python3 scripts/lab.py verify
env PATH=/opt/homebrew/bin:/Users/idongjun/.rd/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin python3 scripts/context.py live \
  --start 1790383693 --end 1790383753 --output .local/m3-live.json
env PATH=/opt/homebrew/bin:/Users/idongjun/.rd/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin python3 scripts/lab.py teardown
```

위 timestamp는 당시 window다. 새로운 랩에서는 최근 합성 트래픽 window로 바꾼다. 다른 OS는 설치 경로에 맞게 PATH만 조정하고 클라우드 context를 사용하지 않는다.

- [실측 결과](../results/m3-live.json): 세 backend 모두 ok, Prometheus 36.943ms / Loki 39.857ms / Tempo 38.828ms. state build 1.591ms, rules 0.054ms. 한 건의 smoke 수치이며 성능 SLO가 아니다.
- 세 서비스의 metric·로그 요약과 checkout root trace 표본을 얻었다. trace 20개 한도와 checkout counter 감소 때문에 정상 확정 없이 human_review로 처리했다.
- [기존 관측 회귀](../results/m3-observability-regression.json): 3개 서비스의 metrics/logs/traces, SLI query 3개, Grafana 패널 5개, Alertmanager firing 수신 통과.
- live 원문은 마스킹 전 데이터를 디스크에 남기지 않는 정책에 따라 저장하지 않았다. input checksum·시간·고정 버전·sanitized state만 보존하므로 **live raw response의 byte-identical replay는 주장하지 않는다**. 결정성 평가는 저장된 M2 snapshot으로 별도 수행했다.

## 발견한 문제와 남은 한계

- [초기 개발 보고서](../results/m3-initial-replay.json)는 수정 전 dirty source의 기록이다. 초기 parser가 Tempo 검색의 unpadded hex ID를 제외하고 duration 누락 한 건 때문에 trace backend 전체를 invalid로 처리했다. 최종 구현은 ID를 내부에서 normalize하고 누락 항목만 격리한다. 기존 관측 원본을 고치거나 실패 이력을 삭제하지 않았다.
- `counter_resets`는 요청/시간합/count **series의 감소 횟수 합계**다. Pod restart 횟수가 아니다. 현 계측은 checkout 2개 replica의 service instance 구분이 없으므로 counter 감소에 replica series 충돌이 섞였을 가능성이 있다. 이를 이번 M3에서 재시작으로 확정하지 않았다.
- Counter delta가 lower bound라는 해석은 독립된 정상 counter series라는 가정이 필요하다. 감소가 있는 서비스의 수치·평균은 잠정값이며 정상 추천을 허용하지 않는다. source별 instance 식별을 추가하고 과거 기록과 schema/version을 분리하는 개선은 후속 관측 품질 과제로 남긴다.
- logs/trace 표본이 상한에 닿으면 정상 추천을 보류한다. 따라서 정상 트래픽에서도 review 비율이 높다. 전체 root cause를 구분하는 규칙 엔진이 아니라 보수적인 비교 기준이다.
- Kubernetes/change/resource/dependency span 미수집, 평균 latency만 제공, 고정 서비스/로그 문법 전용이다. 실제 운영 데이터·대규모 부하·Jev confidence는 검증하지 않았다.
- M2 주입 정답과 사용자 영향 정답은 다르다. 이번 결과를 top-1 accuracy나 생산성 향상으로 해석하지 않는다.

## 종료

[최종 teardown](../results/m3-teardown.json): 2026-09-26 00:50:14 UTC, 전용 node 1개 삭제, node/volume 잔존 0개. `.local/kubeconfig`와 owner marker도 제거됐다. 다른 랩, 공유 kind network, 이미지·빌드 캐시는 보존했다. 유료 API·AWS 리소스·상시 Context Builder 프로세스는 없다.
