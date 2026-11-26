# 캐릭터 기준 승인 기록

- 승인일: 2026-09-02
- 승인 주체: 사용자
- 기준 버전: 1.2
- 상태: 캐릭터 정체성 및 v1.2 제작 앵커 잠금

## 확정 사항

- 파란 캐릭터 이름: `테오 TEO`
- 테오 의미: `Technology + Opportunity`, 기술과 기업의 기회를 연결하는 안내자
- 주황 캐릭터 이름: `피오 PIO`
- 피오 의미: `Pohang + Innovation + Opportunity`, 포항의 혁신과 기회를 기업 성장으로 피워 올리는 동반자
- 테오의 가슴 상징: 화면 기준 오른쪽 가슴 상단의 작은 영문 `T` 하나
- 피오의 가슴 상징: 같은 위치의 작은 영문 `P` 하나
- 중앙 대형 `T/P` 배치는 폐기
- 결합 의미: `T + P = TP`, Technopark
- 머리·얼굴·팔다리·소품에는 상징물이나 표식을 넣지 않음
- 피오는 기존 흰색 일체형 기본복과 주황 측면 패널·흰색 하의·주황 밑창 유지
- 피오와 테오는 같은 2.7등신·어깨 폭·둥근 몸통 볼륨·팔다리 굵기 범위를 공유

## 승인 자산

- `AST-GUIDE-TEO-V10`: `assets/guides/teo-character-guide-v1.0.png`
  - SHA-256: `6256bc5459632f9b7c7bcaa7154c5c3ed6b0f506466bb8add0fcc0b24de9f22d`
- `AST-GUIDE-PIO-V10`: `assets/guides/pio-character-guide-v1.0.png`
  - SHA-256: `3eaf926ab281db48b17cf4c4033dcbd768df88dca384c889eee59e018045571f`

두 v1.0 가이드의 중앙 가슴 문자 위치는 2026-09-02 사용자 요청으로 폐기됐다. 실루엣·색상·기본복 참조에는 계속 사용하되 문자 위치에는 적용하지 않는다.

## 승인된 정밀 마스터 시트

- `AST-ANCHOR-TEO-V12`: `assets/characters/teo/teo-master-sheet-v1.2.png`
  - SHA-256: `d0052382133261a0a18084eacb14709f4fda6a08a642c090a6a781bbaae424b4`
- `AST-ANCHOR-PIO-V12`: `assets/characters/pio/pio-master-sheet-v1.2.png`
  - SHA-256: `b6801449d6b56ac9f414dc40b5308e79e635105f67e816fb619049fade235e37`

두 시트는 최신 문자 위치, 4개 시점과 4개 표정, 테오·피오의 공통 체형 기준을 담은 승인 제작 앵커다. 2026-09-02 사용자의 `진행해줘` 요청을 최종 잠금 승인으로 기록하며, 이후 생성물은 두 시트를 우선 참조한다.

## 내장 서체

- Paperlogy v1.001 TTF 9종을 `assets/fonts/paperlogy`에 내장
- 한국어 제목·본문·숫자·라벨에 사용
- 가슴 `T/P`에는 적용하지 않음
- SIL Open Font License 1.1 전문을 `assets/fonts/paperlogy/OFL.txt`로 동봉

## 승인된 3D 스타일 기준 시트

- `AST-3D-TEO-V10`: `assets/characters/3d/teo-3d-style-sheet-v1.0.png`
- `AST-3D-PIO-V10`: `assets/characters/3d/pio-3d-style-sheet-v1.0.png`
- `AST-3D-FAMILY-V10`: `assets/characters/3d/teo-pio-3d-family-sheet-v1.0.png`
- `AST-3D-SPEC-V10`: `assets/characters/3d/3d-style-spec-v1.0.json`

2026-09-03 사용자 요청으로 AI 이미지 생성을 위한 3D 기준 시트와 운용 규격을 스킬에 포함했고, 이어 권장 구현 순서의 모든 작업 진행 요청을 승인으로 기록했다. 기존 승인 2D 앵커는 정체성 기준으로 계속 우선하며, 3D 자산은 입체 볼륨·재질·중성 조명 기준을 제공한다. 자산은 `approved`, `three_d_style_set`은 `locked` 상태다. 이후 시각 기준을 바꿀 때는 새 버전을 만들고 다시 승인한다.

## 승인된 3D 포즈 참조 라이브러리

- 테오 8종: 중립, 안내, 설명, 추천, 실행, 공감, 태블릿, 인사
- 피오 8종: 중립, 안내, 설명, 추천, 실행, 공감, 태블릿, 인사
- 기계 판독 목록: `assets/characters/3d/poses/pose-library.json`
- 전체 아틀라스: `AST-POSE-TEO-ATLAS-V10`, `AST-POSE-PIO-ATLAS-V10`

2026-09-03 권장 구현 전체 진행 요청에 따라 승인 2D 앵커와 3D 스타일 기준으로 생성하고 연속성을 확인했다. 16개 개별 PNG는 새 캐릭터 생성 전에 우선 사용하는 AI 이미지 생성 참조다. PNG의 체크보드는 실제 배경에 포함되어 있으므로 투명 합성 레이어로 사용하지 않는다. `pose_library_set`은 `locked` 상태다.

## 별도 확인 사항

이 승인은 캐릭터 정체성에 관한 것이다. 외부 게시·광고·인쇄 전에는 기관 CI 세부 규정, 이용 권리, 생성형 AI 표기 정책, 사실 문구와 제작 업체 사양을 해당 작업 기준으로 확인한다.
