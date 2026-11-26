# Claude에서 실행할 때

이 스킬은 Codex용으로 만들었다. Claude(Claude Code, Claude 데스크톱 앱의 Code·Cowork 탭, claude.ai)에서 실행할 때는 이 문서의 차이를 먼저 적용한다. Codex에서 실행할 때는 이 문서를 적용하지 않는다.

시작할 때 [오케스트레이션](orchestration.md)의 능력 목록을 현재 세션 기준으로 `local`, `available-mcp:<server>`, `unavailable`로 기록한다. 아래 항목이 그 기록의 기본값이다.

## 이미지 생성

- Claude에는 이미지 생성 도구가 기본으로 없다. 세션에 이미지 생성 MCP가 연결되어 있으면 `image_generation=available-mcp:<server>`로 기록하고 스킬 본문대로 쓴다. 없으면 `image_generation=unavailable`로 기록한다.
- `image_generation=unavailable`이면 단일 이미지·카드뉴스의 기본값 `generation_method=whole-image` 대신 **별도 조판**으로 만든다. `assets/templates/social-card-base.html`과 `assets/fonts/paperlogy/`의 Paperlogy로 HTML을 조립하고, 브라우저 자동화(예: Python playwright)로 최종 규격 PNG를 렌더한다. 문자 검사는 [문자 넘침 방지](lettering-safety.md)의 "별도 조판" 기준을 따른다.
- 이 경우 작업 기록의 `generation_method`에는 실제 방식(별도 조판)을 적는다. 만들지 않은 생성 이미지를 만든 것처럼 기록하지 않는다.

## 캐릭터가 필요한 제작

포즈 PNG에는 체크보드 배경이 그림으로 들어 있어 합성 레이어로 쓸 수 없다(스킬 본문의 3D 포즈 규칙). 이미지 생성 도구가 없으면 캐릭터·웹툰·3D 요청에서 아래 셋 중 하나를 사용자에게 한 번 묻는다.

1. **캐릭터 없이 제작:** `--character-set none`으로 별도 조판한다.
2. **사용자가 만든 장면 이미지로 조판:** 사용자가 다른 도구(이미지 생성이 되는 AI 등)로 만든 장면을 받아 문자·QR·정보 카드를 조판한다. 받은 그림도 [캐릭터 정체성](character-identity.md) 검사를 거친다.
3. **생성 명세만 전달:** 컷별 목적·행동·표정·대사·카메라와 [3D 생성 프롬프트](3d-generation-prompts.md) 기준의 프롬프트, 함께 넣을 참조 이미지 경로를 정리해 전달한다. 그림이 돌아오면 2번으로 이어 간다.

무인 실행이거나 답이 없으면 1번으로 진행하고, 캐릭터를 뺀 이유를 `character_exclusion_evidence`에 남긴다.

## 공고 수집과 인터넷 접속

- `collect_ptp_notice.py`, `notice_inventory.py`, 단축주소 스크립트는 인터넷 접속이 필요하다. claude.ai의 코드 실행 환경에서 접속이 막히면 사용자에게 공고 주소와 첨부 파일을 받아 진행하고, 단축주소를 만들지 못했으면 링크 정책의 대체 규칙(원래 주소와 실패 기록)을 따른다.
- Python 패키지(Pillow, QR 라이브러리 등)가 없으면 설치 여부를 사용자에게 묻고, 설치하지 못하면 해당 검사를 `not_run`으로 기록한다.

## 게시

- 게시는 세션에 있는 브라우저 도구(데스크톱 앱 내장 브라우저 또는 Claude in Chrome)로 Meta Business Suite에서 진행한다. 로그인과 2단계 인증은 사용자가 직접 한다. 비밀번호를 채팅으로 받지 않는다.
- **공개 게시 직전에는 채널·계정·이미지·문안을 보여 주고 사용자의 확인을 받은 뒤 제출한다.** `config/publication-defaults.json`의 `auto-publish-after-review`는 Claude에서 "검수 후 확인을 받고 게시"로 읽는다. 채널마다 확인을 받는다.
- 브라우저 도구가 없으면(claude.ai 웹 등) 검수된 패키지와 채널별 문안까지 납품하고, 게시는 사용자가 직접 하도록 안내한다.
- 인증 상태와 게시 기록의 `browser` 값에는 실제 사용한 브라우저(`claude-browser`, `chrome` 등)를 적는다. `iab`로 적지 않는다.
- `social_runtime.py`의 예약·무인 편성 검사는 Codex 내장 브라우저(`iab`)를 전제로 한다. Claude에서는 이 검사를 통과시키려고 값을 꾸미지 않는다. 정기 게시나 게시판 감시를 요청받으면 대화형 실행으로 대신한다고 안내한다.

## 영상

FFmpeg·ffprobe와 Supertonic 3가 PC에 있을 때만 MP4와 내레이션을 만든다. 없으면 콘티·자막·내레이션 원고와 장면 명세까지 납품하고, 빠진 단계를 알린다.

## 호출

Codex의 `$ptp-sns-tool` 호출 대신, Claude에서는 "포항TP SNS 홍보물 만들어줘", "이 사업공고를 카드뉴스로 만들어줘"처럼 요청하면 이 스킬이 선택된다.
