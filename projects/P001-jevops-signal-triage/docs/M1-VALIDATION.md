# M1 검증 기록 — 2026-09-25

## 범위와 판정

M1 acceptance criteria를 모두 충족했다. 이 결과는 무료 로컬 수집 경로 검증이며 Jev·chaos·triage 분류 성능의 측정값은 아니다. 모든 API 비용은 0원이고 실제 운영 데이터나 운영 클러스터를 사용하지 않았다.

| 검증 | 결과 | 근거 |
|---|---|---|
| 네트워크 차단 컨테이너의 단위·경계 테스트 | 9개 통과, 수정 후 재실행도 통과 | `python3 scripts/lab.py test` |
| 이미지 빌드·Python 의존성 | 빌드 및 `pip check` 통과 | `src/Dockerfile`, `src/requirements.txt` |
| 초기 신규 클러스터의 수집·alert 연결 | 통과 | [초기 JSON](../results/m1-initial.json) |
| 초기 클러스터 정리 | node·volume 잔존 없음 | [초기 teardown JSON](../results/m1-initial-teardown.json) |
| 최종 코드로 새로 만든 클러스터 검증 | 11개 Deployment 준비, server dry-run과 모든 통합 assertion 통과 | [최종 JSON](../results/m1-final.json) |
| 최종 trace·log 상관관계 | 같은 trace ID에 checkout·catalog·inventory 모두 존재 | 최종 JSON의 `verification` |
| 최종 Prometheus·Grafana | counter 3개, recording rule 3개, 5개 panel, SLI 쿼리마다 유효한 시계열 3개 | 최종 JSON의 `verification` |
| Alertmanager 전달 | `P001SyntheticTraffic` firing 수신 | 최종 JSON의 `verification.alert` |
| 문서화한 대시보드 접속 | `127.0.0.1:13000/d/p001-baseline` HTTP 200 | `lab.py dashboard` + 로컬 curl 확인 |
| 최종 정리 | node·volume 잔존 없음, 포워딩 LISTEN 소켓 없음 | [최종 teardown JSON](../results/m1-final-teardown.json), `lsof` 확인 |

## 환경과 재현

- macOS 15.4 arm64, Docker Engine 28.0.1, Docker VM 11 CPU / 약 11.4 GiB RAM.
- kind 0.31.0, Kubernetes node 1.35.0, 실제 subprocess kubectl 1.36.0, 호스트 Python 3.14.6.
- 이미지·의존성은 명시적 버전을 고정하고 실행한 image ID를 원본 JSON에 저장했다.
- 원본 결과의 commit은 시작 기준인 `59a3c40`이며 구현 변경이 있는 `dirty: true` 상태에서 실행했다. 최종 결과의 `source_sha256`는 src·deploy·dashboards·scripts·tests의 경로와 내용을 묶은 checksum이다. 문서와 결과 파일은 이 checksum 계산에서 제외한다.
- `python3 -c 'import sys; sys.path.insert(0, "scripts"); import lab; print(lab.source_hash())'`로 최종 소스 checksum을 확인할 수 있다.
- 실행 순서는 [M1 실행 안내](M1-LOCAL.md)를 따른다. 각 검증은 합성 요청·trace ID를 새로 생성하므로 정확한 식별자나 timing 값이 같을 것을 요구하지 않는다. Jev model·question·평가 dataset·random seed는 해당 없음이다.

## 실패와 수정 이력

1. 첫 start는 `kubectl` 버전 사전 확인에서 중단됐다. 셸은 v1.35.1을, Python subprocess는 Homebrew v1.36.0을 선택했다. 클러스터 생성 전 실패했으며 실제 subprocess 버전을 고정한 뒤 실행했다.
2. 초기 수집 경로 검증은 통과했다. 이후 latency histogram bucket을 초 단위에 맞게 조정하고, 오류가 없는 경우 error ratio가 0을 표시하도록 수정했다. 최종 검증에는 SLI 패널의 PromQL 결과가 유효한 숫자인지 확인하는 assertion을 추가했다.
3. 변경 후 이미 생성된 클러스터를 삭제하고 새로운 클러스터에서 다시 검증했다. 초기 결과와 초기 teardown도 삭제하지 않고 함께 보존했다.
4. 대시보드 포워딩을 Ctrl-C로 종료할 때 Python `KeyboardInterrupt`가 출력됐다. 이후 해당 포트에 LISTEN 프로세스가 없음을 확인했다. 기능적 연결 실패는 아니며 CLI 출력 개선은 남아 있다.

실패한 사전 점검을 성공한 통합 run으로 세지 않았다. 통합 검증 데이터의 수동 제외는 없다. 공개 결과 JSON에는 kubeconfig·token·raw request가 포함되지 않는다.

## 한계와 남은 단계

실제 브라우저 화면의 시각적 검수, 운영 부하 성능·장애 주입·Jev 판단·보편적 마스킹은 이 검증 범위에 포함되지 않는다. Grafana는 API provisioning·각 metric 쿼리·trace/log 데이터·HTTP 접속을 검증했다. 모든 저장소는 임시 데이터이며 HA나 장기 retention 검증을 제공하지 않는다. 다음 미완료 단계는 M2 chaos ground truth harness다.
