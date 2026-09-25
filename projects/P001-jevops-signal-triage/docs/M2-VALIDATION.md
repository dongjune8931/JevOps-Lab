# M2 검증 기록 — 2026-09-25

## 결과

- 전체 단위·안전 경계 테스트 **33개 통과**: `python3 scripts/lab.py test`로 재현한다. 기존 M1 테스트 9개와 M2 정책·복구·기록/요약 테스트 24개다.
- 최종 구현 소스 기준 **14개 run**: S000~S004 각각 2회, S005 3회, S002 조기 중단·복구 1회. S005의 추가 1회는 종료 유예시간 수정 직후 회귀 검사다.
- 새 클러스터에서 S000~S005를 각각 두 번 실행한 12개 run과 조기 중단 1개가 통과했다. 기준 코드 커밋은 `f15a7d6`이고 이 13개 run의 Git worktree는 clean이었다.
- 코드·fixture checksum: `e3e82303c6bc4794a33fa6abf056e7b4771a17f15192d18505570bec32080ee8`. 최종 소스와 같은 checksum의 run만 현재 acceptance 집계에 포함한다.
- 이전 개발/실패 기록 16개를 포함해 **총 30개 run**과 artifact checksum을 검증했다. 전체 결과와 run별 제외 이유: [요약 JSON](../results/m2-summary.json), [원본 디렉터리](../results/m2/).
- Jev 미호출, 모델·question 버전 `null`, split은 전부 `design`, 추가 API·클라우드 비용 **0원**.

이 결과는 장애 주입 harness의 재현성과 안전 검증이며 Jev 정확도나 생산성 개선을 측정한 결과가 아니다.

## 최종 소스 관측

아래 수치는 `m2-summary.json`의 fault-phase probe에서 확인한 값이며 통계적 성능 benchmark가 아니다.

| 시나리오 | 검증 횟수 | 관측 / 한계 |
|---|---:|---|
| S000 정상 | 2 | 장애 미주입으로 명시하고 정상 요청 확인 |
| S001 Pod 종료 | 2 | 선택한 Pod 종료·2개 replica 복원. fault-phase probe 실패 0개로 사용자 영향이 항상 발생하지는 않음 |
| S002 지연 | 2 + abort 1 | 정상 완료 run의 최대 요청 지연 약 416ms / 485ms, 이후 정상 복구 |
| S003 packet loss | 2 | 최대 요청 지연 약 2.09초 / 2.06초. 표본 요청 실패 0개; 설정한 25%를 HTTP 실패율로 해석하지 않음 |
| S004 CPU stress | 2 | controller 주입 상태 확인, 요청 지연 영향은 뚜렷하지 않음. 실제 CPU saturation·운영 부하를 입증하는 평가가 아님 |
| S005 dependency 중단 | 3 | 각 run의 fault-phase probe에서 요청 실패 5개, 이후 정상 복구 |

## 실패와 보완

1. **API proxy 경로**: 초기 S000에서 `/work` 조회 실패로 precondition이 중단됐다. 어떤 fault도 생성하지 않았다. probe를 실제 합성 traffic Pod 내부의 서비스 요청으로 변경했다.
2. **주입 상태와 실제 네트워크 효과의 차이**: 초기 ClusterIP 경로에서는 controller가 `AllInjected`를 반환했지만 요청 지연이 거의 없었다. 같은 주입 중 Service 경로 약 1~4ms와 Pod 직접 경로 약 404ms를 비교했다. [진단 원본](../results/m2-network-path.json). headless `inventory-direct`를 추가하고 실제 지연 효과 검사도 추가했다.
3. **엔진 롤아웃 과도기**: Helm upgrade 직후 종료 중인 이전 controller Pod가 남아 precondition이 중단됐다. setup에서 workload·engine 안정화까지 기다리도록 보완했다.
4. **종료 유예시간과 장애 window의 불일치**: `30초` grace에서 `20초` pod-failure가 끝난 뒤 pause image가 실행됐다. 강화한 효과 검사에서 실제로 실패했고 복구 후 중단했다. [이벤트·유예시간 근거](../results/m2-pod-grace.json). 상태 없는 합성 앱만 grace `2초`로 변경해 요청 실패와 복구를 다시 검증했다.

초기 record의 `passed`는 당시 코드의 검사 통과를 뜻하며 최신 실효성 기준 통과로 소급 해석하지 않는다. 초기 S000의 주입 확인 필드 의미도 개발 중 수정했으며, 현재 control은 `injection_required=false`, `injection_confirmed=false`다. 원본은 수정·삭제하지 않고 소스 checksum 차이와 제외 이유를 요약에 남겼다. 실패 기록을 최종 모델 test split에 넣지 않는다.

## 회귀와 정리

- [M1 관측 회귀 결과](../results/m2-observability-regression.json): 3개 서비스의 metric·log·trace, 5개 Grafana 패널, SLI 쿼리와 Alertmanager 로컬 webhook 검증 통과.
- [추가 정리 검사](../results/m2-post-chaos.json): 활성 fault 0개, 내부 PodNetworkChaos 0개, checkout/catalog/inventory의 남은 stress 프로세스 0개.
- M2에서 생성한 로컬 클러스터 3개는 모두 정리했다: [첫 번째](../results/m2-initial-teardown.json), [두 번째](../results/m2-second-teardown.json), [최종](../results/m2-final-teardown.json).
- 최종 정리 시각 `2026-09-25T07:50:23Z`: P001 node container·node volume 잔존 0개. 기존 다른 랩 `otel-demo-lab-control-plane`은 보존했다.
- 로컬 이미지·빌드 캐시와 공유 kind network는 보존한다. P001 kubeconfig·소유 마커는 삭제됐으며 외부 유료 리소스는 생성하지 않았다.

## 재현과 무결성

전체 실행 순서는 [M2 실행 안내](M2-CHAOS.md)를 따른다. 이미 저장된 원본의 schema·checksum과 요약은 아래 명령으로 다시 검증한다.

```bash
cd projects/P001-jevops-signal-triage
python3 scripts/chaos.py check-results --results results/m2
python3 scripts/report_chaos.py
```

새 로컬 결과를 검토해 공유하려면 `python3 scripts/report_chaos.py --export`를 사용한다. 이는 record에 등록된 JSON artifact만 복사하고 기존 원본을 다른 내용으로 덮어쓰지 않는다. `.local/` 전체, kubeconfig·인증서·Secret·chart cache는 커밋하지 않는다. 요약 파일은 결정적으로 재생성되는 분석 결과이며 원본과 구분한다.

raw telemetry는 합성 데이터의 제한된 window이며 trace 검색 최대 20개·로그 최대 100개다. 완전한 운영 incident dataset, 고부하·HA·다중 node·AWS 검증은 아니다. M3에서 state 마스킹과 정답 누수 방지, M4 이후 Jev 비교를 별도로 수행한다.
