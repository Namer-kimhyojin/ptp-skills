# 작업 요청 데이터

`assets/job-template.json`은 정식 제작 전 합의 내용을 기록하는 계약이다. 새 정식 작업은 `schema_version=1.3`, 빠른 초안은 `assets/quick-job-template.json`을 사용한다. 기존 `1.0`·`1.1`·`1.2` 요청서도 검증할 수 있다.

## 핵심 필드

- `status`: `draft`, `locked`, `delivered`
- `production_mode`: `quick-draft`, `standard`, `publication`
- `authoring_mode`: `individual` 또는 `integrated`
- `requested_outputs`: `png`, `pdf`, `html`의 중복 없는 배열. schema 1.2 이상에서는 모든 `platform_targets[].requested_outputs`와 동일하게 유지한다. 채널마다 다른 출력 형식이 필요하면 작업을 분리한다.
- `resolution_policy`: 최종 크기 프로필, 선택 방식, 원본 기준 렌더링, 종횡비 적응 방식, 업로드본·마스터본 구성, 사용자 지정 픽셀 또는 인쇄 mm·DPI
- `platform_targets[]`: 프리셋 ID, 플랫폼, 지면, 콘텐츠 유형, `content_variant_id`, 픽셀 규격, 형식별 수량, 충돌 없는 파일명, 규격 출처와 확인일
- `output.mode`: `card-news`, `poster`, `signage`, `web-banner`, `social-toon`, `four-panel`, `educational-comic`, `vertical-webtoon`, `page-comic`
- `output.medium`: `digital`, `print`, `physical`
- `output.capability`: `direct`, `tool-dependent`, `specification-only`
- `output.spec_source`: `user-provided`, `platform-provided`, `vendor-provided`, `project-custom`
- `characters[].id`: `CHR-BLUE`, `CHR-ORANGE`
- `characters[].outfit_slot`: `default`, `field`, `research`
- `copy`: 정확한 제목·본문·행동 유도와 출처가 필요한 사실 표현
- `copy.cards[]`: 카드별 목적, 제목, `hero_metric`, 보조 정보, 행동 유도와 출처
- `design.hero_metric`: 한 화면에서 가장 먼저 읽힐 금액·날짜·대상·행동 하나
- `design.reading_order`: 사용자가 정보를 읽게 될 순서
- `design.content_budget`: 주 메시지·보조 정보·본문 글자 수의 상한
- `design.visual_system`: 그리드, 밀도, 색상 역할과 시각 모티프
- `design.character_integration`: 테오·피오의 동작과 연결할 정보 요소
- `design.avoid`: 이 작업에서 피할 구체적 구성
- `approvals`: 캐릭터, 브랜드, 사실, 발행 규격, 최종 검토 상태
- `publication_asset_ids`: 실제 사용한 승인 라이브러리 자산 ID 배열. 캐릭터 앵커, 3D 참조, 사용 포즈, 서체, 사용한 로고 등을 빠짐없이 기록한다.
- `publication_review`: `brand_evidence`, `rights_evidence`, `final_review_evidence`, `reviewer`, `checked_at`(시간대 포함 ISO), `review_mode`(`human`/`delegated`). 위임 검토에는 `delegation_evidence`도 기록한다. 사람 검토를 실시하지 않은 위임 작업은 `final_human_review=not-applicable`로 구분하며 승인했다고 쓰지 않는다.
- `capabilities`: 현재 사용할 수 있는 로컬·MCP·외부 출력 능력
- `hooks`: 제작 수명주기 훅 프로필과 이벤트
- `orchestration`: 단일·멀티에이전트 분담과 coordinator 소유권
- `delivery_form`: `single-image` 또는 `card-news`. [형식 선택](single-image-social.md)의 결과이며 단일 이미지는 output·copy.cards·각 채널 PNG 수량을 1로 맞춘다. 기존 작업은 이 선택 필드 없이도 검증할 수 있다.
- `format_selection`: 실제 질문·응답·10초 만료에 따른 선택 근거와 시각을 기록한다. 게시 권한은 이 객체에서 만들지 않고 기존 `publication`의 실제 요청·위임 근거를 사용한다.
- `publication`: 외부 게시 요청·승인 상태. 초기 템플릿은 모두 `false`이며 [초기 선택](default-publication.md)에서 게시 범위를 확정하면 `authorization_evidence`, `targets`, `requested=true`, `authorized=true`를 기록한다.
- SNS 기획은 별도 `card-plan.json`에 `narrative_mode`(`information`/`dialogue`/`story`), 독자의 질문·행동 목표와 장/컷별 설명·대사·동작·출처를 둔다. QR 목적·라벨·해독 결과와 로그인 확인 상태는 별도 보고서로 연결한다. 로그인 비밀번호·쿠키·토큰은 job이나 납품 manifest에 넣지 않는다.
- 사업공고 작업은 `workflow=notice-to-social`과 `source_notice`에 `source_key`, `source_manifest`, `facts_path`, `checked_at`, `eligibility_path`를 기록한다. `publication`에 `authorization_evidence`, `package_manifest`, `targets: [{platform, account_id}]`를 둔다. 경로는 job 파일 기준 상대경로 또는 절대경로다. 실제 게시할 미게시 채널만 targets에 넣는다. 사용자 지정 예약은 `planned_publish_at`에 시간대 포함 ISO 값을 기록한다. `before_publish`는 원문 접수기간·제작 완료 파일·대상별 중복을 검사한다. 결과의 `attempt_id`, `remote_url`, `result`는 채널별로 보관한다. 자동 검사는 외부 원문의 진위나 실제 게시 성공을 확인하지 않으므로 [제작 이력·기간 관리](notice-tracking.md)와 [SNS 게시 절차](social-publishing.md)의 원문·화면/API 확인을 수행한다.
- `concept_strategy`: 입력 신호, 서로 다른 매체군의 제안 3안, 선택안·근거, 다중 레이어와 상업 품질 목표
- `design.visual_system.layer_plan`: 배경·분위기·환경·캐릭터·정보·문자·브랜드의 분리 제작 계획
- `design.visual_system.photoreal_composite`: 실사 합성 여부와 원근·광원·접지·가장자리·색보정·깊이·권리 검사
- `design.visual_system.commercial_quality`: 콘셉트 적합성·차별성·채널 크롭·캠페인 일관성 검사
- `comic`: 웹툰 형식, 읽기 방향, 컷 수, 프레임 다양성, 비트와 컷별 상태·출처·레터링 안전영역. `assets/webtoon-mode-template.json`을 작업 요청서에 병합한다.

## 잠금 조건

`status=locked`에는 목적·독자·채널, 출력 규격, 확장자·수량, 캐릭터·의상, 정확한 문구와 필요한 승인 값이 모두 있어야 한다. `1.1` 이상 정식 요청서는 카드 계획 수가 산출물 수량과 일치하고, 카드마다 출처와 하나의 `hero_metric`이 있어야 한다. 인쇄·실물 안내판에는 실제 물리 크기와 업체 사양이 추가로 필요하다.

`quick-draft`는 `status=review-draft`를 사용하며 채널, 핵심 제목, 프리셋, 출력 형식과 수량만으로 시작할 수 있다. 이 모드는 외부 게시를 허용하지 않으며 최종 승인본으로 표시하지 않는다.

`authoring_mode=individual`이면 모든 `platform_targets[].content_variant_id`가 서로 달라야 한다. 각 유형의 문구·카드 순서·레이아웃을 독립 설계한다. `authoring_mode=integrated`이면 대상이 두 개 이상이어야 하고 모든 대상의 `content_variant_id`는 `shared-main`이어야 한다. 통합 작성도 단순 확대·축소하지 않고 규격마다 재배치한다.

`schema_version=1.2`에서 `platform_targets[]`가 채널별 실제 납품 계약이고, 단일 `output` 객체는 기존 1.0·1.1 도구와 호환하기 위한 대표 출력 요약이다. 다중 채널의 수량·형식·파일명 검증에는 `platform_targets[]`를 우선한다. 같은 `platform + placement` 대상은 중복 정의하지 않으며, 실제 파일명은 `page_no`가 `01`부터 빠짐없이 이어져야 한다.

`schema_version=1.2` 이상 새 작업은 `concept_strategy`에서 서로 다른 `medium_family`의 콘셉트 ID를 정확히 3개 제안하고 그중 하나를 선택해야 한다. `composition_mode=multi-layer`, `allow_flat_geometric_only=false`를 사용한다. 정식 작업의 `layer_plan`에는 최소 `background`, `atmosphere`, `context`, `character`, `information`, `typography` 역할이 있어야 한다.

`schema_version=1.3`에서는 `resolution_policy.profile_id`를 반드시 선택한다. 허용값은 `channel-native-1x`, `high-resolution-master-2x`, `custom-pixel`, `print-production`, `draft-preview-0.5x`다. `upscale_existing_raster=false`, `preserve_aspect_ratio=true`를 고정한다. 2× 프로필은 마스터와 채널 표준 업로드본을 함께 만들고, 사용자 지정은 정확한 양의 픽셀값, 인쇄용은 실제 mm와 72~1200 DPI가 필요하다. `draft-preview-0.5x`는 `quick-draft` 전용이며 최종 승인본이 될 수 없다.

웹툰·만화 출력은 `comic.enabled=true`로 두고 등장 캐릭터의 연속성과 1부터 연속된 컷 번호를 기록한다. 원화·레터링은 선택한 [제작 방식](webtoon-content-mode.md#통합-생성과-별도-조판)을 따른다. `output.mode`와 `platform_targets[].content_type`은 `social-toon`, `four-panel`, `educational-comic`, `vertical-webtoon`, `page-comic`을 사용할 수 있다.
## 캐릭터 세트 확장 (2.8)

새 작업은 [character-sets.md](character-sets.md)에 따라 `character_set` 선택 스냅샷, `character_mode=set|none`, `character_selection_evidence`를 추가한다. `characters`는 선택 멤버의 ID·이름·role·outfit_slot·anchor_ids·approval을 기록한다. 세트 선택은 기존 schema_version 1.0~1.3의 호환 확장이다. 기존 세트 필드가 없는 작업은 종전 규칙을 유지한다. 새 작업의 캐릭터 행동은 `design.character_integration.actions: {"CHR-...": "행동"}`와 `functional_target`으로 기록한다. `none`에는 `characters=[]`, `character_exclusion_evidence`와 캐릭터 검토 `not-applicable`이 필요하다.

