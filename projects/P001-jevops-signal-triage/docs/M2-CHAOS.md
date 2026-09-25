# M2 — 로컬 Chaos ground truth harness

M2는 Jev 평가에 사용할 **장애 주입 사실과 관측 window**를 만든다. 장애 분류 모델, Context Builder, 외부 API, AWS 실행은 구현하지 않는다. 결과를 Jev 정확도로 해석하지 않는다.

## 검증 가설과 성공·반증 조건

- 가설: 정상 control과 제한된 다섯 fault를 같은 합성 workload에 순차 실행하고, 주입 확인·관측 window·복구를 재현 가능한 기록으로 남길 수 있다.
- 비교군: S000 무주입 control. fault가 있어도 사용자 영향은 없을 수 있으며, 주입 종류와 관측된 incident 여부를 구분한다.
- 지표: precondition 통과 여부, Chaos Mesh `AllInjected`, 실제 대상 수, 직접 요청 성공·latency, 수집 성공, 복구·잔존 fault 여부, 시간 제한, 비용.
- 성공: S000~S005를 각각 반복 검증하고 매번 정상 복구; 별도 abort 검증과 안전 경계 음성 테스트 통과.
- 반증/실패: 주입 상태 미확인, precondition 우회, 허용되지 않은 대상, 수집 실패, 복구 실패 또는 잔존 fault. 실패 run도 보존하고 이후 자동 실행을 중단한다.
- 이 단계는 모두 `design` split이다. M5의 blind test로 재사용하지 않으며 분류 정확도·calibration 합격 기준은 여기서 결정하지 않는다.

## 선택과 버전

Chaos Mesh를 선택했다. 동일 CRD와 versioned manifest를 로컬 및 추후 승인된 AWS Kubernetes에서 재검증할 수 있고, 상태 레코드를 M3 window 수집과 M5 평가에 연결하기 적합하다는 판단이다. AWS 호환성이 이미 검증됐다는 뜻은 아니다. LitmusChaos의 별도 포털·workflow는 이번 harness의 필수 기능이 아니다.

- 엔진·차트: 2.8.4, Helm 3.16.1; [`chaos-version.json`](../deploy/chaos-version.json)에 차트 SHA-256과 이미지 버전 고정.
- kind·Kubernetes·관측 스택: [`versions.json`](../deploy/versions.json)의 M1 버전 유지.
- 설정: [`chaos-values.yaml`](../deploy/chaos-values.yaml). controller 1개, dashboard·DNS server 미설치, namespace filter 활성화, host-network 대상 금지.
- workload: checkout replica 2개, catalog/inventory 각 1개. opt-in label은 세 합성 서비스에만 있다.
- catalog는 headless `inventory-direct` Service를 통해 inventory에 연결한다. 초기 ClusterIP 경로는 이 kind 환경에서 Pod-to-Pod delay가 실제 요청에 적용되지 않았다. 동일 주입 중 Service/Pod 경로 비교로 차이를 확인했으며 일반 ClusterIP Service는 비교용으로 유지한다.

## 시나리오

[`scenarios.json`](../fixtures/scenarios.json)과 [`chaos.py`](../scripts/chaos.py)의 bounded generator가 함께 버전 관리된다. 생성물은 Kubernetes가 지원하는 JSON 형식의 YAML-equivalent manifest다. 임의 manifest 입력은 받지 않는다.

| ID | 장애 / 대상 | 설정 | 지속시간 |
|---|---|---|---|
| S000 | 무주입 control | 정상 트래픽 유지 | 관찰 20초 |
| S001 | checkout Pod 1개 종료 | ReplicaSet 복원, 2개 중 이름순 1개 | 1회 종료·관찰 20초 |
| S002 | catalog → inventory 지연 | 200ms, jitter 0 | 30초 |
| S003 | catalog → inventory 손실 | 25%, correlation 0 | 30초 |
| S004 | inventory CPU stress | worker 1, load 50%; container CPU limit 300m | 20초 |
| S005 | inventory 일시 중단 | Pod image를 고정 pause image로 교체·복원 | 20초 |

Pod 종료·낮은 강도의 stress·packet loss가 항상 incident를 만드는 것은 아니다. `expected_cause`는 **실행한 원인 후보**이지 관측된 사용자 영향의 정답이 아니다. M3/M5에서는 상태·증거를 확인해 incident 여부와 영향 label을 별도로 정의해야 한다.

## 안전 경계

- M1의 소유 기록, 프로젝트 전용 kubeconfig, 명시적 context, Unix-socket Docker, loopback Kubernetes 검사 유지. 클라우드 옵션은 없다.
- `p001-m1` 전용 kind node 하나만 허용한다. 기본 kubeconfig와 다른 실습 클러스터를 수정하지 않는다.
- Chaos Mesh daemon은 node 내부에서 privileged 권한과 containerd socket이 필요하다. 이 때문에 공유·운영 cluster에 설치하면 안 된다. namespace selector는 권한 격리 자체를 대신하지 않는다.
- `p001`만 주입 opt-in annotation을 허용한다. namespace·project·app·opt-in label을 모두 확인하고 이름순으로 고른 Pod 하나를 field selector로 고정한다. namespace/label을 우회하는 `pods` selector는 사용하지 않는다.
- 실행 전 정확한 replica 수·Ready·ReplicaSet 소유·Deployment 안정화·정상 요청 3회·관측 backend·Prometheus scrape를 검사한다. 기존 fault가 있으면 새 주입을 거부한다.
- 동시에 실행 가능한 runner 1개, fault 1개, 주입 대상 1개, 네트워크 상대 Pod 1개. CLI 반복은 최대 3회, fault duration 최대 45초, active loop timeout 300초, 개별 Kubernetes 요청 15초로 제한한다.
- 관측 backend/traffic/node 이상이나 scrape 실패 시 중단한다. 의도된 dependency 장애의 요청 실패 자체는 무조건 abort하지 않는다. 그 장애는 duration으로 제한한다.
- Ctrl-C/SIGTERM·예외에도 정상 CR 삭제와 finalizer 복구를 시도한다. 별도 `--abort-after`로 조기 중단을 검증한다. SIGKILL/호스트 장애는 `finally`가 실행되지 않으므로 controller의 duration 복구가 보조 경계다. controller도 고장 나면 수동 cluster teardown이 필요하다.
- 강제 삭제나 finalizer 제거를 하지 않는다. cleanup 실패 시 계속 주입하지 않고 잔존 자원을 보고한다.
- controller의 namespace filter·이미지 버전을 실행마다 확인하고 실제 주입된 대상도 allowlist와 대조한다. 지연 시나리오는 fault window에서 150ms 이상 요청, dependency 중단은 요청 실패가 관측돼야 통과한다. 이 기준은 M2 주입 효과 smoke 검사이며 M5 성과 threshold가 아니다.
- NetworkChaos가 남기는 비활성 내부 PodNetworkChaos는 규칙이 비었고 controller가 해당 generation을 처리한 것을 확인한 뒤 소유 대상의 것만 삭제한다. 활성 규칙이 남으면 실패로 중단한다.

## 실행

```bash
cd projects/P001-jevops-signal-triage
python3 scripts/lab.py test
python3 scripts/lab.py start
python3 scripts/chaos.py setup
python3 scripts/chaos.py run --scenario all --repetitions 2
python3 scripts/chaos.py run --scenario S002 --abort-after 5
python3 scripts/chaos.py check-results
python3 scripts/lab.py verify
python3 scripts/lab.py teardown
```

기존 owned cluster가 이미 켜져 있으면 `start`를 반복하지 않는다. `setup`은 합성 workload와 선택한 차트를 재현한다. 최초에는 공개 차트·이미지를 다운로드한다. 비용은 기존 로컬 머신 비용을 제외하면 0원이며 AWS·Jev 자격증명은 필요 없다.

`run` 실패 시 오류와 `.local/m2/<run-id>/record.json`을 먼저 확인한다. precondition 실패는 장애 미주입을 의미한다. 복구 실패 시 다음 fault를 실행하지 말고 아래 명령으로 해당 랩 전체를 정리한다.

```bash
python3 scripts/lab.py teardown
```

클러스터 삭제는 P001의 CRD·RBAC·인증서 Secret·daemon·fault·관측 데이터도 함께 제거한다. node container/volume 잔존을 확인하며 Docker 이미지·빌드 캐시와 다른 랩의 공유 network는 유지한다. kubeconfig나 chart가 저장된 `.local/` 전체를 Git에 추가하지 않는다.

## 기록과 후속 milestone 경계

- `record.json`: schema `p001-ground-truth-v1`, scenario·parameter, manifest/catalog/source checksum, commit·dirty, 환경·엔진 버전, 실제 대상, 시각·주입 상태·abort·복구·요청 샘플·telemetry window.
- `manifest.json`: 실제 생성 요청. S000에는 없음.
- `telemetry.json`: window 내 합성 metrics·logs·trace 검색 결과. 5초 metric step, log 최대 100개, trace 검색 최대 20개로 제한. 완전한 모든 telemetry가 아니라 bounded fixture다.
- 결과 파일은 run별 새 디렉터리에 저장하고 덮어쓰지 않는다. `check-results`는 schema의 필수 불변조건과 artifact SHA-256을 검사한다.
- 정답과 CR status는 Jev state와 분리돼야 한다. M3는 필요한 관측 증거만 allowlist·마스킹하고 fault ID·label을 입력에서 제외한다. 이번 단계에서는 외부로 아무 데이터도 전송하지 않는다.
- target 선택은 정렬로 재현하지만 packet loss·커널 스케줄링은 seed 고정 대상이 아니다. `seed=null`과 이유를 기록하며 동일 parameter가 동일 신호를 보장한다고 주장하지 않는다.
- M4a에서는 별도 승인된 AWS 구성에 맞게 재검증한다. 로컬 접근 차단을 해제해 AWS에 재사용하지 않는다.

## 공식 근거

- [Chaos Mesh 설치](https://chaos-mesh.org/docs/production-installation-using-helm/)
- [namespace opt-in filter](https://chaos-mesh.org/docs/configure-enabled-namespace/)
- [selector 경계](https://chaos-mesh.org/docs/define-chaos-experiment-scope/)
- [상태·주입·복구 확인](https://chaos-mesh.org/docs/inspect-chaos-experiments/)
- [Pod 장애](https://chaos-mesh.org/docs/simulate-pod-chaos-on-kubernetes/)
- [network 장애](https://chaos-mesh.org/docs/simulate-network-chaos-on-kubernetes/)
- [stress 장애](https://chaos-mesh.org/docs/simulate-heavy-stress-on-kubernetes/)
