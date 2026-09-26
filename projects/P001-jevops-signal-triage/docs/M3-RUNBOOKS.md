# M3 합성 랩 조사 runbook

아래 ID만 규칙 결과에 사용한다. 명령 실행이나 운영 변경 권한을 부여하지 않는다. 실제 팀·운영 runbook으로의 매핑은 후속 명시적 설정이 필요하다.

## inspect-service-errors

Grafana에서 같은 window의 checkout/catalog/inventory 오류율과 Loki 오류 패턴을 대조한다. Tempo에서 실패한 요청의 downstream을 조사한다. Context Builder는 전체 trace를 포함하지 않으므로 root cause를 단정하지 않는다. 장애 주입 정답은 blind 판단 이후 평가자만 확인한다.

## inspect-latency

요청량·평균 latency와 원본 histogram/trace를 함께 확인한다. 평균 증가를 p95 증가로 해석하지 않는다. 의존 서비스, 네트워크, CPU 병목은 추가 증거가 있어야 구분한다. 규칙 결과만으로 network fault를 확정하지 않는다.

## manual-investigation

missing/invalid/truncated 상태와 query timeout을 먼저 확인한다. 원본 backend의 제한된 window를 조사하고 관측 누락을 정상으로 해석하지 않는다. 서비스 이름 allowlist 또는 고정 로그 문법 밖의 데이터는 임의로 외부 모델에 전송하지 않는다.

## observe-service

정상 관측 추천을 참고하되 Prometheus alert와 원본 신호 탐색을 유지한다. 자동 경보 억제·복구를 실행하지 않는다. 새 오류나 데이터 품질 저하가 나타나면 다시 사람 검토로 전환한다.
