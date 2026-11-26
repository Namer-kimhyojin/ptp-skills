# MCP·훅·멀티에이전트 오케스트레이션

## 능력 기반 도구 선택

특정 서버명을 전제로 하지 않고 현재 세션에서 다음 능력을 탐색한다.

- `official_spec_lookup`: 공식 SNS 규격 확인
- `source_extraction`: PDF·문서·표에서 사실과 문구 추출
- `image_generation`: 테오·피오 장면 제작·편집
- `raster_or_vector_composition`: 한국어 레터링과 레이아웃 조립
- `html_render`: HTML 미리보기와 화면 캡처
- `pdf_export`: 디지털 또는 인쇄 PDF 생성
- `visual_inspection`: 실제 결과 화면 검토
- `file_packaging`: 형식·규격별 납품 묶음
- `external_publish`: 게시·업로드·발송

사업공고의 두 SNS 배포는 [notice-to-social-workflow.md](notice-to-social-workflow.md)와 [social-publishing.md](social-publishing.md)를 따른다. `source_extraction` 전에 `scripts/collect_ptp_notice.py`로 원본을 확보하고, 게시 단계에서는 `scripts/publication_history.py`와 공통 장부를 사용한다. 로그인은 [social-authentication.md](social-authentication.md), 캐릭터 중심 설명·만화 기획은 [social-storytelling.md](social-storytelling.md), QR은 [qr-code-workflow.md](qr-code-workflow.md)를 해당 단계에 적용한다. 사용자 지정 브라우저를 우선하며 인증 상태와 게시 이력을 구분한다.

공고 선정 전 `notice_inventory.py`로 현황을 읽고 [제작 이력·기간 관리](notice-tracking.md)를 적용한다. 제작 시작과 완료 기록은 coordinator만 변경한다. 하위 에이전트는 새 제작 권한을 따로 얻거나 독립 게시하지 않는다. 게시 직전 접수기간 검사와 채널별 제출 기록을 통과해야 하며, 제작 완료 패키지·두 공통 장부를 업데이트 중에도 보존한다.

각 능력을 `local`, `available-mcp:<server>`, `unavailable`로 기록한다. 내장·로컬 기능, 이미 설치되어 호출 가능한 MCP, 명세만 제공하는 폴백 순으로 선택한다. MCP가 없다는 이유로 설치를 시도하거나 제작을 막지 않는다.

## 권한 경계

- 재단 SNS 최종 제작의 기본 선택은 [두 채널 자동 게시](default-publication.md)다. `external_publish`는 이번 작업의 대상·게시 범위가 확정되고 검수를 통과한 경우에 실행한다.
- 이미 받은 해당 게시 요청은 작업에 연결해 재사용한다. 같은 범위의 승인을 다시 묻지 않는다. 스킬 수정·시험 요청은 실계정 게시 요청이 아니다.
- 계정 연결, 수신자 선택, 광고 집행, 비용 발생, 예약 발송은 각각 별도 외부 변경으로 취급한다.
- 민감한 원문이나 개인정보를 외부 MCP에 보내기 전에 해당 범위의 허용을 확인한다.
- MCP와 훅은 사용자의 권한을 확장하지 않는다.

## 멀티에이전트

`standard` 또는 `publication`에서 다음 중 하나에 해당하고 에이전트 슬롯이 있을 때 사용한다: 플랫폼 2개 이상, 출력 형식 2개 이상이면서 카드 4장 이상, 원문 10쪽 이상, 또는 별도 사실 검토와 시각 검토가 모두 필요한 작업. 그보다 작은 작업은 coordinator가 직접 수행한다.

- `coordinator`: 설문, 작업 JSON, 승인 상태, 최종 병합과 보고
- `spec-copy`: 공식 규격, 원문, 날짜·금액·연락처와 채널 문구 검토
- `visual-production`: 캐릭터와 레이아웃 시안 제작
- `export-qa`: PNG·PDF·HTML 변환과 실제 파일 검사

하위 에이전트는 별도 하위 폴더에만 쓰고 `job.json`과 최종 manifest는 coordinator만 수정한다. 결과 계약은 `status`, `artifacts`, `checks`, `open_issues`로 통일한다. 하위 에이전트가 없거나 한 번 실패하면 coordinator가 직접 수행하며 무한 재시도하지 않는다.

`quick-draft`는 시작 지연을 막기 위해 기본적으로 단일 에이전트로 실행한다.

## 훅

수명주기는 `after_intake`, `before_generate`, `after_generate`, `before_export`, `after_export`, `before_publish`다. 상세 계약은 [hook-contracts.md](hook-contracts.md)를 따른다.

- 훅은 선택형 확장점이다. 없으면 로컬 절차로 계속한다.
- `quick-draft`에서 누락된 훅은 `not_run`으로 기록하고 진행한다.
- `standard`에서 훅 오류는 경고 후 로컬 검사로 한 번 폴백한다.
- `before_publish`는 `publication.authorized=false`이면 항상 차단한다.
