# SNS·채널 출력 프리셋

실제 값은 `assets/platform-presets.json`에서 읽는다. 이 문서는 선택 원칙과 갱신 규칙만 설명한다.

## 선택 순서

1. [size-and-authoring-choice.md](size-and-authoring-choice.md)의 관련 플랫폼 표를 사용자에게 먼저 보여주고, 플랫폼과 지면을 지정하면 정확히 일치하는 프리셋을 선택한다.
2. 플랫폼만 지정한 경우 한 번의 묶음 설문에서 피드·스토리·릴스·채널 메시지 유형을 확인한다.
3. `빠르게`, `초안`, `일단 시안` 요청에서 지면이 없으면 다음 기본값을 사용한다.
   - Instagram: 현재 앱 직접 게시 `instagram-feed-portrait-current`, 구형 발행 도구 호환 `instagram-feed-portrait`
   - Facebook: `facebook-feed-portrait`
   - 카카오톡 채널: 일반 관리자센터 이미지는 `kakao-channel-basic-image`, 카카오모먼트 광고는 `kakao-moment-wide-image-ad`
4. 한 요청에 여러 플랫폼이 있으면 공통 원본을 단순 축소하지 않는다. 비율마다 캐릭터 위치, 제목 줄바꿈, 안전영역과 정보량을 다시 배치한다.

## 신뢰도

- `official-platform`: 공식 문서에 픽셀·비율·용량이 명시된 값
- `mixed`: 공식 비율 원칙과 프로젝트 픽셀 기본값을 결합한 값
- `project-default`: 제작을 빠르게 시작하기 위한 내부 기본값이며 플랫폼 보장값이 아님

`publication` 모드에서는 `mixed`와 `project-default`를 게시 직전 공식 화면 또는 최신 공식 문서로 다시 확인한다. 프리셋 확인일로부터 90일이 지났거나 플랫폼 UI가 바뀌었으면 모든 신뢰도에서 갱신한다.

## 카카오톡 채널 구분

- 채널 프로필 이미지는 공식 권장 `640×640`이며 원형 노출을 고려한다.
- 일반 채널 관리자센터와 카카오모먼트 채널 메시지 광고는 이름이 비슷해도 규격이 다를 수 있다.
- 채널 관리자센터 와이드이미지형과 카카오모먼트 와이드이미지형 광고는 `800×600`, 기본 텍스트형 이미지와 와이드 리스트 첫 이미지는 `800×400`을 사용한다.
- 캐러셀 커머스 Intro는 `800×1100`, 상품 이미지는 `800×800`이다.
- 광고성 메시지는 실제 발송 전에 `(광고)` 표시, 수신거부·연락처 등 현행 운영 요건을 담당자가 확인한다.

## Meta 계열 안전영역

- Instagram 세로 Feed는 현재 공식 범위용 `1080×1440(3:4)`과 호환용 `1080×1350(4:5)`을 분리한다.
- Instagram Reels 본편용 세로 자산과 `420×654` 커버를 별도 파일로 관리한다.
- Instagram·Facebook Story/Reels는 `9:16`을 기준으로 만들고 핵심 제목, 얼굴, 가슴 `T/P`, CTA를 중앙 안전영역에 둔다.
- 정확한 상·하단 픽셀 안전영역은 앱 UI와 광고 배치에 따라 바뀔 수 있으므로 고정 수치로 단정하지 않는다.
- 피드·프로필·릴스 미리보기 크롭은 서로 다를 수 있다. 표지 텍스트와 캐릭터 얼굴을 가장자리 가까이 두지 않는다.

## 공식 자료

- 카카오 비즈니스 채널 메시지: <https://kakaobusiness.gitbook.io/main/channel/run/message>
- 카카오톡 채널 프로필 카드: <https://kakaobusiness.gitbook.io/main/channel/run/mychannel>
- 카카오모먼트 채널 메시지 제작 가이드: <https://kakaobusiness.gitbook.io/main/ad/moment/messagead/channelmessage/content-guide>
- Meta Instagram·Facebook Reels: <https://www.facebook.com/business/ads/facebook-instagram-reels-ads>
- Instagram 사진 해상도: <https://help.instagram.com/1631821640426723>
- Instagram Reels·커버: <https://help.instagram.com/1038071743007909/>
- Facebook 링크 공유 이미지: <https://developers.facebook.com/docs/sharing/webmasters/images>
- Facebook Page 커버: <https://www.facebook.com/help/125379114252045>
- Meta Ads Guide: <https://www.facebook.com/business/ads-guide>

확인일: `2026-09-02`
