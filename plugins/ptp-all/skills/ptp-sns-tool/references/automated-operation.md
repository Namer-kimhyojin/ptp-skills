# 자동 실행·편성·복구

예약 실행, 중단 재개, 현황 요청에서 읽는다. 이 문서는 현재 사용 가능한 CUA를 통해 관찰한 사실을 `social_runtime.py`에 연결한다. Python 스크립트 자체가 내장 브라우저를 열거나 SNS에 게시하는 것은 아니다.

## 편성 기준과 범위

- 편성의 기준은 사용자가 확정한 일정 데이터 JSON의 `schedule`이다. 실행 JSON은 제작 ID·패키지·채널별 결과·과거 차단·재편성 이력을 보존한다. 날짜가 두 파일에서 다르면 게시를 멈추고 의도한 편성을 대조한다. HTML/CSV를 직접 고쳐 일정을 변경하지 않는다.
- `social_runtime.py select --plan <일정데이터> --execution <실행JSON> --phase prepare|publish|monitor`는 실제 KST 날짜의 지정 공고와 채널별 `skip/pending/reconcile`을 반환한다. 기간 밖·다른 공고·하루 여러 공고·`unknown/submitting`은 새 제출로 진행하지 않는다. 공고 하루 한 건과 별도 웹툰 연재를 구분한다.
- `publish`는 15분 전부터 최종 확인을 시작할 수 있지만 `submission_not_before` 이전에는 제출할 수 없다. `submission-check`와 최종 게시 장부 기록에서 실제 시각을 다시 검사한다. 늦은 실행은 지연을 기록한다. 시간대 원인이 확인되지 않은 지연에 추정 보정값을 반복 적용하지 않는다.
- 일정 변경은 사용자 위임 범위·하루 한도·종료일을 확인하고 일정 데이터와 실행 JSON을 함께 원자적으로 갱신한 다음 `select`의 오류가 없는지 확인한다. 실행 중 변경은 현재 작업이 가진 계획 해시와 충돌하므로 새 제출 전에 대조한다. 실행 기간·대상을 임의 확장하지 않는다.

## 실행 점유

사용자가 기존 하루 한 건 편성을 명시적으로 일괄 게시로 변경하면, 해당 날짜·정확한 공고 키·당일 이미 게시한 키·사용자 요청 원문을 별도 JSON에 보존하고 SHA-256으로 편성의 `batch_publication`에 연결한다. 그날 해당 공고에만 예외를 적용하며 다른 공고·미래 날짜로 확대하지 않는다. 새 제출은 `interactive` 실행에서 수행하고, 원래 시도·기존 성공·접수기간·계정·검수 검사는 유지한다. 기존 미래 자동화는 중복 방지를 위해 일시 중지하고 결과를 반영한다. 격일 웹툰 편성은 보존한다.

사용자의 2026-11-02 지시에 따라 모집 종료 또는 게시 시점에 남은 접수기간이 3일(72시간) 미만인 공고는 제외한다. 편성 `minimum_remaining_days=3`, 새 manifest·최신 eligibility에도 같은 값을 보존한다. 게시 장부의 `notice_publish_guard`가 새 제출 시 다시 검사하며, 시각이 없는 원문에 임의 마감 시각을 표시하지 않는다.

`select`의 `plan_sha256`을 읽고 `begin --plan ... --execution ... --phase ... --context automation --expected-plan-sha256 <값>`을 실행한다. 반환된 `owner.run_id`를 보존한다. 기본 `--scope foundation-meta`를 사업공고·기관 웹툰·복구 점검의 **같은 Meta 계정 브라우저 조작**에 공통 사용한다. 점검이 기존 작업 진행 중이면 새 편집기를 열지 않는다.

다른 실행이 점유 중이면 해당 작업의 상태를 확인한다. 오래됐다는 이유만으로 소유 파일·장부 잠금을 삭제하지 않는다. 기존 run ID를 대조하고 원격 제출 결과를 조정한 근거를 남긴 후 `finish --run-id ... --outcome reconciled --evidence <실제근거>`로 종료한다. `finish`는 원래 게시 장부의 성공·불명을 바꾸지 않는다.

지원사업 길찾기 연재는 아래 전용 절차로 당일 회차와 채널을 확인한다. 공고 선택 규칙은 별도로 적용한다.

## 실제 브라우저 점검

1. 현재 CUA 문서를 읽고 `cua.getState()`로 제공되는 브라우저를 확인한다. 지정된 IAB의 기존 Meta 탭에 연결한다. IAB가 목록에 있지만 기존 탭 연결 API가 사용할 수 없다고 반환하면, 현재 제공된 API와 문제해결 문서를 확인한 뒤 **같은 IAB에 새 Meta 탭**을 만들어 기존 세션을 확인한다. 브라우저를 재선택하거나 다른 브라우저로 옮기지 않는다. IAB 자체가 없다면 `open_in_codex`로 **현재 대화**에 기존 Meta URL을 열고 IAB를 다시 조회한다. `queued`는 숨겨진 대화의 화면 열기 대기이며 접속 성공이 아니다. 같은 복구를 두 차례 이상 반복하지 않는다.
2. 실제 UI에서 로그인·저장 프로필·추가 인증과 두 대상 계정 및 게시 작성 기능을 확인한다. 비밀번호·쿠키·토큰을 추출·이동하지 않는다. IAB 미제공과 로그인 만료를 다른 문제로 기록한다. 다른 브라우저 전환이나 계정 연결 변경을 일반 복구로 확대하지 않는다.
3. 작업 폴더에 비밀정보 없는 관찰 JSON을 작성하고 `preflight --observation <파일> --context automation --report <새보고서>`로 검증한다. 현재 대화의 수동 점검은 `interactive`다. 무인 실행 중 실제로 관찰한 경우에만 `automation`으로 기록한다. 보고서는 관찰 선언을 검사할 뿐 무인 실행을 자체 증명하지 않는다.
4. 통과 보고서를 `stage --run-id ... --stage preflight --evidence <보고서>`에 연결한다. 실패 시 `finish --outcome blocked`와 실제 오류 파일을 남겨 사용자에게 해당 화면·조치만 알린다. 앱이 브라우저를 제공하지 않으면 스킬 지침만으로 해결했다고 보고하지 않는다.

관찰 JSON의 필수 항목:

```json
{
  "checked_at": "이번 실제 확인 시각(시간대 포함)",
  "execution_context": "automation 또는 interactive",
  "browser": "iab",
  "browser_available": true,
  "open_result": "existing_tab",
  "reattached_after_open": false,
  "session_status": "target_verified",
  "accounts": {
    "instagram": {"account": "pohangtp_official", "can_create_post": true},
    "facebook": {"account": "pohangtpoffcial", "can_create_post": true}
  },
  "evidence": "실제로 읽은 계정·작성권한 UI와 확인 범위"
}
```

예시의 true 값을 관찰 없이 복사하지 않는다. 상태는 `login_required`, `challenge_required`, `target_verified`를 사용하고, 미제공이면 `browser_available=false`와 실제 오류를 기록한다.

## 단계와 제출

원문·중복 대조·제작은 기존 절차를 따른다. 단계 근거를 `stage`로 연결한다. 새 완성본은 [파일에 연결된 검수](content-review.md)의 보고서를 `quality`와 `ready`에 연결한다. 준비 완료 후 `finish --outcome prepared`로 점유를 반환한다. 게시 시에는 같은 패키지를 읽되 새 publish 실행을 시작한다.

새 패키지의 job과 manifest에는 `runtime_contract_version=1`을 기록한다. job에는 `quality_review_path`, `final_image_paths`, 실제 `creative_signature`를 넣는다. manifest에는 `runtime` 객체를 넣는다:

```json
{
  "plan_path": "편성 JSON 절대경로",
  "execution_path": "실행 JSON 절대경로",
  "scope": "foundation-meta"
}
```

manifest의 `final_image_paths`에도 실제 게시할 최종 PNG 목록을 기록한다. 각 파일은 manifest.files에 해시와 함께 포함되어야 하며 runtime 검수 이미지 집합과 일치해야 한다.

패키지의 검수 파일·spec·최종 이미지·manifest는 고정한다. 실행 ID·새 preflight·원격 URL은 외부 실행/결과 파일에 보존한다. 이미 완성된 구버전 패키지는 보존하고 기존 검수 방식으로 재사용하며, 새 계약 필드만 맞추기 위해 원본 manifest를 수정하지 않는다.

게시 직전에 10분 이내 실제 브라우저 관찰로 preflight를 갱신하고 최신 접수기간·정정·추가 SNS 게시를 다시 확인한다. `submission-check --contract <runtime설정JSON> --source-key <공고키> --report <새파일>`을 실행한다. `allowed=true` 보고서를 submission 단계에 연결한다. 양 채널의 `publication_history.py submitting` 기록을 먼저 성공시킨 다음 실제 UI로 제출한다. 새 계약의 manifest는 장부에서 예정 시각·작업 점유·최신 preflight·검수 파일·당일 한도를 추가 확인한다.

같은 실행에서 아직 제출 전 양 채널 submitting을 확보하는 것은 허용한다. 다른 run ID의 submitting 또는 unknown은 원래 시도를 먼저 조정한다. 한 채널만 성공하면 성공 결과를 보존하고 나머지만 처리한다. 모호한 UI 응답을 자동 재제출하지 않는다. `finish --outcome checked`는 점검 종료이며 공개 게시 성공은 반드시 기존 publication 장부와 실제 원격 결과에서 확인한다.

사용자가 지난 길찾기 회차의 누락 게시를 직접 요청하면 실행 JSON의 `interactive_recoveries[회차 source_key]`에 오늘의 한국 날짜(`authorized_date`)와 요청 근거(`reason`)를 기록하고 `series_runtime.py begin --context interactive --recover-source-key <키> --plan <편성> --execution <실행>`으로 그 회차를 선택한다. 원래 편성일과 실제 게시일은 별도로 남긴다. 기존 제작 ID와 게시 장부를 사용하며 해당 채널의 게시·예약·초안을 먼저 대조한다.

## 현황 출력

```powershell
python scripts/social_runtime.py render --plan <편성JSON> --execution <실행JSON> --series <기존연재실행JSON> --series-plan <기존연재계획JSON> --output-dir <출력폴더>
```

`운영현황.html`, `일일_홍보일정.csv`, `운영현황.json`을 편성과 실행 결과에서 다시 만든다. 상태는 대기·제작 중·게시 준비·게시 완료·조치 필요이며, 채널 결과와 원격 주소·원인을 펼쳐 확인한다. 기록된 실행만 지연·차단 지표에 집계하고 미측정 값을 0%나 성공으로 채우지 않는다. 게시 직후와 복구 후 출력한다. 실제 자동 실행 성공·사용자 개입·검수 재작업은 근거가 있는 기록만 누적한다.

사용자 개입·검수 재작업·중복 차단·원문 변경이 실제 발생하면 `note --source-key <키> --type user-intervention|quality-rework|duplicate-prevented|source-change --evidence <실제근거파일>`로 기록한다. 무인 preflight 통과율은 해당 실행의 관찰 보고서가 있을 때만 계산한다. 전체 편성 중 양 채널 게시 완료 수와 개별 실행 성공률을 혼동하지 않는다. `render --plan-html <기존계획HTML>`을 지정하면 같은 데이터로 기존 계획 화면도 갱신한다. 이전 수작업 계획은 교체 전에 보존한다.

## 지원사업 길찾기 연재 실행

기존 지원사업 길찾기 9~34화 편성을 운영할 때는 2026-11-11~12-31 한국시간 격일 오전 8시 실행표를 사용한다. 제작을 마치고 채널의 검수와 제출 조건이 충족되면 즉시 게시한다. 예약되어 있는 과거 글은 원격에서 먼저 조정하며 같은 채널에 다시 제출하지 않는다. 호출의 원본 시간과 실제 준비 시작, 실제 공개 시각은 별도 필드다. Codex 호출이 08:00 전 몇 분 일찍 왔다면 당일 `wait`의 `planned_at`까지 기다렸다가 다시 선택한다. 새 설치의 정기 편성은 운영 담당자가 별도로 위임한 경우에만 설정한다.

```powershell
$plan = 'outputs/PTP_WEBTOON_2026_YEAR_END_PLAN/연재계획_데이터.json'
$execution = 'outputs/PTP_WEBTOON_2026_YEAR_END_PLAN/series-execution.json'
python scripts/series_runtime.py select --plan $plan --execution $execution
python scripts/series_runtime.py begin --plan $plan --execution $execution --context automation --triggered-at <실제_호출_ISO_시각>
```

설치 경로의 스크립트를 호출하고, 편성 경로는 작업 폴더를 기준으로 지정한다. `begin`이 반환한 run ID와 채널별 결과를 보존한다. `skip`은 기존 성공 또는 예약, `reconcile`은 장부 불일치나 원래 제출 확인, `pending`은 해당 계정의 원격 공개·예약·초안을 대조한 후 진행할 채널이다. 한 채널의 원래 시도가 결과 불명이면 그 채널은 재제출하지 않고 다른 채널을 독립적으로 판단한다. 등록된 production ID와 완료 파일은 재사용한다.

게시 직전 실제 CUA preflight를 `stage preflight`에, 완성 보고서를 `stage ready`에 연결한다. 한 채널씩 처리할 때는 `preflight --platform <채널>`로 그 계정의 실제 관찰을 연결한다. 두 채널을 함께 처리할 때는 기본값으로 둘 다 점검한다. 새 manifest에는 `runtime_contract_version=1`, 실제 순서의 `final_image_paths`, `runtime.plan_path/execution_path/scope`를 넣는다. `scope`는 `foundation-meta`이며 경로는 절대 경로다. 현재 채널의 미리보기 JSON에 `platform`, `manifest_sha256`, 실제 `observation`을 쓰고 직접 확인한 항목만 `order_verified`, `alt_text_verified`, `caption_verified`, `public_audience`, `no_crop_warning`, `immediate_publish_enabled`, `no_extra_sharing`를 true로 기록한다.

```powershell
python scripts/series_runtime.py gate --plan $plan --execution $execution --source-key <키> --platform <채널> --manifest <manifest> --preview <실제_채널_미리보기> --report <새_게이트_JSON>
python scripts/social_runtime.py stage --run-id <run_ID> --stage submission --evidence <새_게이트_JSON>
python scripts/publication_history.py record --source-key <키> --platform <채널> --account <계정> --manifest <manifest> --status submitting --series-gate <새_게이트_JSON> --evidence <실제_근거>
```

게이트는 게시 당일·시간, 실제 실행 점유, 승인 계정, 최근 preflight, 제작 장부와 검수 파일의 해시 및 순서를 확인한다. 두 채널을 동시에 보낼 경우 둘의 `submitting`이 확보됐을 때만 해당 제출 버튼을 누른다. 결과는 해당 attempt ID로 먼저 기록한다. 채널별로 끝난 작업을 보존하고 최종 검증 전에 결과 JSON을 갱신할 수 있다. 마지막 채널의 제출 전에 전체 run을 `verification` 단계로 이동하지 않는다. 불명 응답은 동일 ID로 원격 조회한다. 영구 삭제가 필요한 과거 글 교체는 별도 사용자 요청과 실제 삭제 증거가 있는 대화형 실행으로 처리한다. 9화 이후 교체에는 동일 편성 해시를 가진 대화형 점유, `gate --replacement`, 그리고 게시 장부의 `--replacement-evidence`를 함께 적용한다.

공개 검증 결과 파일에는 `source_key`, `card_count`, `qr_url`과 `channels`를 둔다. 확인한 채널마다 `attempt_id/post_id/url`, `public_verified`, `card_order`, `alt_text_verified`, `ai_display`(`native-label`, `caption-disclosure`, `native-and-caption`, `unverified`), `observation`, 실제 플랫폼 제공 이미지의 `served_qr_report` 경로를 남긴다. 원본과 0.5배 축소본에서 각각 해독하고 공식 도착 주소는 별도 관찰로 확인한다. 직접 공개를 확인하지 못했다면 Meta에서 확인한 게시 상태와 확인 범위를 기록한다. 최종 파일과 과거 삭제·대기 증빙은 보존한다.

```powershell
python scripts/series_runtime.py refresh --plan $plan --execution $execution --source-key <키> --results <현재_결과_JSON>
python scripts/social_runtime.py finish --run-id <run_ID> --outcome checked --evidence <실제_종료_근거>
```

최신 장부를 `refresh`로 반영한 뒤 공고와 연재 데이터를 함께 `render`한다. 원격 증빙 없이 단순 상태 동기화만 할 때는 `--results`를 생략한다. 중단·인증 차단도 실제 근거를 보존한 뒤 점유를 반환한다. 12월 31일에는 회차별 누락과 채널 상태를 함께 기록한다.
