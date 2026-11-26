# 공고별 제작 이력과 접수기간 관리

공고의 고유키는 `ptp:15:<board_idx>`다. 제목이나 작업 폴더명이 바뀌어도 같은 키를 사용한다. 제작 상태와 SNS 채널별 게시 상태를 별도로 기록한다. 아래 명령은 스킬 폴더 기준이며 다른 폴더에서는 스크립트 절대 경로를 사용한다. `<...>`는 실제 값으로 바꾼다.

## 공통 장부와 표시

| 화면 표시 | 판정 | 다음 행동 |
|---|---|---|
| 제작 기록 없음 | 제작 장부에 해당 공고 없음 | 기존 SNS·산출물도 대조한 뒤 새 제작 가능 여부 확인 |
| 제작 중 | `producing` | 같은 `production_id`의 결과를 확인하고 이어가기 |
| 제작 완료 | `produced`, 원본 파일 해시 일치 | 기존 카드·캡션 재사용 |
| 확인 필요 | 파일 손상·분실, 미정리 실패, 장부 오류·게시만 존재 | 원래 결과·파일을 확인·복구; 자동 재제작 금지 |

- 제작 장부: `<skill-root>/state/content-history.jsonl`
- 게시 장부: `<skill-root>/state/publication-history.jsonl`
- 채널별 표시: `게시 기록 없음 / 게시 처리 중 / 확인 필요 / 게시 완료 / 예약 완료 / 실패 확인`.
- 두 장부와 실사용 계정 설정은 스킬 업데이트 때 보존한다. 새 채팅·폴더에서도 공통 장부를 사용한다. 별도 빈 장부를 만들어 중복 검사를 피하지 않는다.
- 장부는 과거 이벤트를 삭제하거나 덮어쓰지 않고 추가한다. 잠금·파손·불완전한 마지막 줄을 빈 이력으로 처리하지 않는다. `producing`은 시간이 지났다고 자동 해제하지 않는다.
- ‘제작 기록 없음’은 이 스킬의 기록 기준이다. 스킬 도입 전 수동 제작·외부 게시까지 없었다는 뜻이 아니다. 후보 확정 시 확인 가능한 기존 패키지와 두 계정의 게시·예약·초안을 [실제 SNS 대조](social-publishing.md#실제-sns-대조)에 따라 확인한다. 기본 최근 90일 또는 일부 목록만 보고 과거 게시가 없다고 확정하지 않는다. 확인하지 못한 이력은 범위를 남긴다.

## 1. 현황표와 후보

```powershell
python scripts/notice_inventory.py --output-dir work/ptp-inventory
```

`inventory.json`, `inventory.csv`, `status.md`를 만든다. 범위는 접수중·접수전 전체 페이지와 최근 접수마감 첫 페이지, 공유 장부의 공고다. 전체 과거 공고를 조사했다고 보고하지 않는다. 고정 공지가 상태 필터를 넘어 노출될 수 있으므로 행의 실제 접수상태를 사용한다. 수집 오류·상한 도달·장부 오류가 있으면 `complete=false`로 후보 자동 선택을 멈춘다.

`candidate_action=create`는 새 제작 후보, `reuse`는 기존 제작물의 미게시 채널 처리 후보다. 홈페이지 접수기간만 이용한 1차 선별이므로 첨부 공고문·정정·취소를 검토하기 전에는 게시 가능 확정으로 쓰지 않는다. `publication_ready`는 이 단계에서 항상 false다.

사용자가 접수중인 미제작·미게시 공고를 요청한 경우에만 후보 중 등록일 내림차순, 같은 날짜면 ID 내림차순으로 고른다. “최신 공고”만 지정했을 때 그 글이 이미 게시됐거나 기간 밖이면 해당 사실을 보고한다. 임의로 다른 공고를 게시하지 않는다. 후보가 없으면 `게시 대상 없음`으로 끝낸다.

```powershell
python scripts/collect_ptp_notice.py --output-dir work/ptp-selected/source --board-id <공고ID> --inventory work/ptp-inventory/inventory.json
```

### 원격 대조 후 후보 재선정

새 제작을 시작하기 전에 `remote-duplicate-check.json`을 후보의 공고 ID와 연결한다. 각 계정의 게시·예약·초안에 대해 검색어, 후보 등록일을 포함하는 적용 기간, 확인 시각, 일치 URL/ID와 조회 한계를 기록한다. 예약 조회는 미래 항목까지 포함한다. 로딩·오류·조회 제한은 `uncertain`이며 `게시 기록 없음`으로 바꾸지 않는다.

- **같은 공고가 두 채널에 게시·예약되어 있음:** 기존 결과를 근거와 함께 연결하고 새 제작·제출에서 제외한다. 사용자가 ‘접수중 미제작·미게시 공고’를 요청했다면 현황표의 다음 후보를 등록일·ID 순으로 확인한다. 다음 후보에도 기간·제작 이력·원격 대조를 동일하게 적용한다.
- **한 채널만 게시·예약되어 있음:** 완료 채널의 URL을 보존하고 기존 카드·문안이 있으면 재사용한다. 요청 범위에 포함된 다른 채널만 검토한다. 완료 채널을 맞추려고 삭제·재게시하지 않는다.
- **초안 또는 중단된 시도가 있음:** 같은 항목의 내용과 작업 상태를 확인해 이어간다. 게시 결과가 불명확하면 신규 제출하지 않으며, 별도 후보로 넘어가 원래 시도를 숨기지 않는다.
- **조회가 끝난 범위에서 일치 항목 없음:** `not_found_in_scope`와 조회 근거를 남기고 기존 후보 작업을 진행한다. 최종 보고도 ‘확인한 범위에서 중복 없음’으로 제한한다.

정확한 최신 공고나 특정 ID를 요청받았다면 중복 발견만으로 다른 공고를 게시하지 않는다. 기존 결과와 상태를 보고하고 해당 요청 범위를 유지한다. 이는 새 승인 단계를 추가하는 규칙이 아니며, 이미 승인된 미게시 후보 선택·두 채널 게시 범위 안에서는 확인 후 계속 진행한다.

## 2. 제작 시작·완료·기존 파일 이관

```powershell
python scripts/content_history.py check --source-key ptp:15:<공고ID>
python scripts/content_history.py start --source-key ptp:15:<공고ID>
```

`start`가 성공하면 `production_id`를 작업에 보관하고 제작한다. 다른 실행은 같은 공고를 시작할 수 없다. 이미 성공·예약·결과 미확인 게시가 있으면 제작 기록이 없어도 새 제작을 막는다. 제작 완료 상태에서 `check`의 차단 종료코드는 오류가 아니라 기존 파일 재사용 신호다.

완료 패키지의 `package-manifest.json`은 `source_key`와 `files` 배열을 가진다. 각 파일은 `file`(패키지 안 상대경로, `/` 구분), `sha256`, 선택 `bytes`를 갖는다. 모든 최종 카드 PNG·채널별 캡션·대체텍스트를 포함하고 순서를 유지한다. 실제 카드 파일이 최소 한 개 있어야 하며 모든 해시·크기를 검사한다. 파일 검사가 시각·사실 검수를 대신하지 않는다.

```powershell
python scripts/content_history.py finish --source-key ptp:15:<공고ID> --production-id <반환된ID> --status produced --manifest <package-manifest.json> --evidence "실제 카드·문안·미리보기 검수 근거"
```

실제 사용 가능한 결과물이 없다는 사실을 확인한 실패만 같은 제작 ID로 `finish --status failed --definitive-failure --evidence <근거>`를 기록한다. 응답 중단·파일 위치 불명은 실패로 바꾸지 말고 기존 상태를 확인한다.

이전부터 존재한 완성 패키지는 검증 후 아래 명령으로 이관한다. 문안만 있고 카드 파일이 없으면 제작 완료로 이관하지 않는다.

```powershell
python scripts/content_history.py import-produced --source-key ptp:15:<공고ID> --manifest <package-manifest.json> --evidence "파일과 해시 확인 근거" --provenance "기존 제작 작업·납품 위치·시점"
```

완료 패키지는 원래 경로와 해시를 유지한다. 파일을 옮겼거나 손상됐으면 원본을 복구한다. 정정·수정 요청은 기존 제작·게시 사실을 보존하는 별도 변경 작업으로 다루며, 완료 기록을 삭제하거나 새 키로 같은 공고를 재등록하지 않는다.

### 미게시 패키지의 플랫폼 문안 수정

제출 전 플랫폼 제한 때문에 문안을 조정해야 하면 원본 패키지를 그대로 두고 별도 폴더에 복사한다. 필요한 채널 문안·관련 메타데이터만 수정하고 새 manifest와 미리보기를 검수한 뒤 아래 명령으로 연결한다. 모든 이미지의 패키지 내 상대경로와 해시는 원본과 같아야 한다. 원본 manifest나 원본 파일을 고쳐 새 해시로 덮어쓰지 않는다.

```powershell
python scripts/content_history.py revise-produced --source-key ptp:15:<공고ID> --previous-event-id <직전produced이벤트ID> --original-manifest-sha256 <직전manifest해시> --manifest <별도폴더의새package-manifest.json> --reason "Facebook 링크 한도로 URL을 홈페이지 탐색 경로로 변경" --evidence "미게시 확인 및 수정 문안·원본 QR·이미지 검수 근거"
```

명령은 이전 이벤트·원본 해시·실파일, 새 manifest의 같은 공고·별도 경로·실파일, 이미지 보존을 검사하고 같은 `production_id`의 새 `produced` 이벤트를 추가한다. 과거 이벤트와 패키지는 보존된다. 어느 채널이든 `submitting`·`unknown`·`published`·`scheduled`이면 차단한다. 이미 제출한 결과가 불명확하면 먼저 원래 시도를 확인하며, 이 명령으로 게시 이력을 우회하지 않는다. 성공 후에는 새 manifest를 제출 전 검사와 게시 기록에 사용한다.

## 3. 신청·접수기간 안에서만 게시

등록일·조회수·사업 수행기간·지원 종료일은 게시 허용기간이 아니다. 원문에 적힌 **신청 또는 접수 시작·마감**을 사용한다. 목록의 접수상태와 본문·첨부·정정 공고를 대조하고 다음을 모두 충족해야 한다.

- 공식 상세 URL·공고 ID가 작업과 일치한다.
- 현재 접수상태가 접수중이며 취소·조기 마감·상충 근거가 없다.
- 확인된 접수 시작 이후, 마감 이내다. 시간대는 한국시간이다.
- 실제 원문 확인 후 30분 이내의 근거가 있다. 단지 파일의 `checked_at`만 새 시각으로 바꾸지 않는다.
- 원문에 날짜만 있으면 그 날짜 전체를 사용하며 홍보 문구에 임의의 마감 시각을 만들지 않는다. 명시된 시각은 그대로 적용한다.
- 상시·예산 소진 시 종료는 원문에 적힌 시작과 종료조건을 기록하고 현재 접수중 여부를 재확인한다. 종료조건을 추측하지 않는다.

`assets/notice-eligibility.example.json`을 실제 확인 근거로 채운다. 예시의 값은 게시 허용 근거가 아니다. `application_period.purpose=application`, `verified=true`, `kind=bounded`, 시작·마감과 원문 인용 위치를 둔다. `open-ended`는 명시된 종료조건 `condition`과 이를 포함하는 원문 근거가 필요하다. 근거 파일·URL·구간은 보존한다.

```powershell
python scripts/notice_eligibility.py --source-key ptp:15:<공고ID> --evidence <eligibility.json>
```

이 스크립트는 입력한 근거의 구조와 시간 조건을 검사한다. 네트워크로 원문 진위·정정을 직접 확인하지 않는다. 실행자가 원문을 확인한 사실과 자동 검사의 통과를 구분한다. 예정·마감·취소·미확인·충돌·오래된 근거는 차단하며 글을 안내형으로 바꿔 우회하지 않는다.

## 4. 채널별 중복 확인 후 제출

`before_publish` 훅은 접수기간, 등록된 제작 완료 패키지, 실제 제출 파일, 각 채널 중복 이력을 확인한다. 새 `publication_history.py record --status submitting`도 같은 기간·패키지 검사를 다시 수행한다. 훅을 생략해도 이 제출 전 검사는 생략하지 않는다.

```powershell
python scripts/publication_history.py record --source-key ptp:15:<공고ID> --platform instagram --account <계정ID> --manifest <package-manifest.json> --eligibility <eligibility.json> --status submitting
```

성공한 `attempt_id`를 보관한 뒤 실제 게시 버튼을 누른다. 시간이 지난 작성 화면을 재개할 때는 기간을 다시 확인한다. 마감에 임박했거나 제출 중 마감될 우려가 있으면 게시하지 않는다. 새 제출은 반드시 `submitting`을 거치고, 원격 결과는 같은 ID에 연결한다. 과거 성공을 뒤늦게 확인하는 기록은 현재 접수기간 밖이어도 보존할 수 있지만 새 게시 허가가 되지 않는다.

한 채널이 완료면 그 채널은 제외하고 미게시 채널만 선택한다. 두 채널을 한 번에 게시할 때도 양쪽의 제출 기록이 성공해야 하며 하나라도 막히면 공통 게시 버튼을 누르지 않는다. `unknown/submitting`은 원격 게시·예약·초안을 원래 시도 시각을 포함하는 범위에서 먼저 확인한다. 로컬 검사 통과는 이 원격 대조를 대신하지 않는다. 정확한 결과 기록은 [SNS 게시 절차](social-publishing.md)를 따른다.

기본은 즉시 게시다. 사용자가 예약을 요청한 경우 현재와 예약 시각 모두 접수기간 안이어야 하며 공개 직전 재검증이 필요하다. 그 재검증 실행 경로가 없으면 예약 제출을 보류한다. 기간 검사 기능을 예약 취소·자동 감시 기능으로 설명하지 않는다.
