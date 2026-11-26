# 제작 훅 계약

## 이벤트

`after_intake`, `before_generate`, `after_generate`, `before_export`, `after_export`, `before_publish`

## 입력

```json
{
  "contract_version": "1.0",
  "event": "before_export",
  "job_id": "PTP-CONTENT-001",
  "production_mode": "standard",
  "workspace": "absolute-job-output-path",
  "artifacts": [{"path": "...", "role": "approved-source"}],
  "requested_outputs": ["png", "pdf", "html"],
  "capabilities": {},
  "publication_authorized": false
}
```

## 출력

```json
{
  "status": "pass",
  "checks": [{"id": "dimensions", "status": "pass", "message": "..."}],
  "derived_artifacts": [],
  "warnings": [],
  "retryable": false
}
```

허용 상태는 `pass`, `warn`, `block`, `not_run`이다. 훅은 입력 파일을 덮어쓰지 않고 작업 출력 폴더 안에만 새 파일을 만든다. 비정상 JSON, 시간 초과 또는 누락은 권한 확대나 자동 게시 사유가 될 수 없다.

`scripts/run_hooks.py`는 기본 로컬 훅 프로필을 제공한다. quick 모드는 제작을 지연시키는 전체 검증을 생략하며, standard/publication 모드만 구조·납품 검증을 연결한다.

사업공고(`workflow=notice-to-social` 또는 `source_notice` 존재)의 `before_publish`는 `notice_publish_guard.py`로 다음을 추가 확인한다: 공고 ID, 최근 원문 접수기간 근거, 현재 접수중 여부, 공통 제작 장부의 완료 패키지와 실제 파일 해시, `publication.targets` 각 계정의 중복·결과 미확인 게시. 누락·충돌·기록 오류는 block이다. `--authorized`는 이미 받은 게시 요청을 반영하는 값이며 반복 승인을 요구하는 단계가 아니다. 원문 확인과 실제 SNS 성공 확인은 실행자가 따로 수행한다.

동시 실행을 막는 최종 예약은 `content_history.py start`와 `publication_history.py record --status submitting`에서 한다. 훅 통과만으로 이 단계를 생략하지 않는다. 상세 필드는 [작업 요청 데이터](request-schema.md), 순서는 [제작 이력·기간 관리](notice-tracking.md)를 따른다.
