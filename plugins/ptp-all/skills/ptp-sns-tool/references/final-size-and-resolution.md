# 최종 크기·해상도 선택

채널 유형을 고른 뒤 최종 제작물의 용도에 맞춰 아래 프로필 하나를 선택한다. 선택하지 않으면 디지털 최종본은 `채널 표준 1×`, 빠른 초안은 `0.5× 미리보기`를 사용한다.

| 프로필 | 용도 | 기본 동작 | 납품 구성 |
|---|---|---|---|
| `channel-native-1x` | SNS·웹에 바로 게시 | 플랫폼 프리셋 픽셀 그대로 원본에서 렌더링 | 업로드용 1× |
| `high-resolution-master-2x` | 재편집·확대 활용·장기 보관 | 가로·세로를 각각 2배로 원본에서 렌더링 | 2× 마스터 + 1× 업로드본 |
| `custom-pixel` | 홈페이지·전광판·내부 시스템 등 지정 규격 | 사용자가 지정한 정확한 픽셀로 재구성 | 지정 크기 파일 |
| `print-production` | 포스터·안내판·인쇄물 | mm와 DPI로 필요한 픽셀을 계산하여 제작 | 인쇄 마스터 |
| `draft-preview-0.5x` | 방향을 빠르게 확인하는 초안 | 채널 규격의 절반 크기로 렌더링 | 검토용만, 최종 납품 불가 |

## 사용자에게 보여줄 선택문

```text
최종 이미지 품질을 골라주세요.
1) 채널 표준 1×: 바로 게시할 기본 크기 — 권장
2) 고해상도 2×: 편집·보관용 마스터와 게시용 1×를 함께 제작
3) 사용자 지정: 원하는 가로×세로 픽셀 입력
4) 인쇄용: 실제 크기(mm)와 DPI 입력
5) 빠른 미리보기 0.5×: 디자인 확인용, 최종본 아님
```

## 핵심 구분

- 디지털 결과물의 선명도는 우선 `가로×세로 픽셀`로 관리한다. DPI 메타데이터만 높여 디지털 이미지가 선명해졌다고 판단하지 않는다.
- 인쇄는 `실제 크기(mm) + DPI`로 픽셀을 계산한다. 인쇄소가 요구하는 도련, 색상 프로필, PDF 규격이 확인되지 않으면 `인쇄 준비 완료`로 표시하지 않는다.
- 파일 용량과 화질은 같은 개념이 아니다. PNG·PDF·HTML별 압축과 내보내기는 최종 픽셀·물리 크기를 잠근 뒤 결정한다.
- 완성된 저해상도 래스터 이미지를 확대해 마스터로 만들지 않는다. 배경·캐릭터·정보·문자 레이어가 분리된 원본에서 목표 크기로 다시 렌더링한다.
- 종횡비가 바뀌면 늘여서 변형하지 않는다. `재구성`을 우선하고, 요청에 따라 `크롭` 또는 `레터박스`를 선택한다.

## 효율적인 제작 순서

1. 채널·유형과 작성 방식을 선택한다.
2. 최종 해상도 프로필을 고른다.
3. `scripts/resolve_output_size.py`로 실제 제작 픽셀과 파생본을 계산한다.
4. 가장 큰 필수 마스터 크기에서 배경·캐릭터 원화를 만들고, 문자와 정보 레이어는 각 목표 규격에서 정확히 조판한다.
5. 작은 게시용 파생본은 고품질 축소로 생성하고 작은 글자, 선 굵기, 얼굴과 가슴의 작은 `T/P`를 다시 확인한다.
6. 프로필별 실제 픽셀, 파일명, 형식, 해시를 납품 목록에 기록한다.

2× 프로필은 플랫폼에 2× 파일만 올리라는 뜻이 아니다. 반드시 채널 표준 1× 파생본을 함께 제공한다. 여러 채널에서 서로 다른 해상도 프로필이 필요하면 채널별 작업 요청서를 분리해 납품 계약을 명확히 한다.

## 계산 명령 예시

```powershell
python scripts/resolve_output_size.py --guide
python scripts/resolve_output_size.py --profile channel-native-1x --preset instagram-feed-portrait-current
python scripts/resolve_output_size.py --profile high-resolution-master-2x --preset instagram-feed-portrait-current
python scripts/resolve_output_size.py --profile custom-pixel --preset instagram-feed-portrait-current --width-px 1200 --height-px 1600 --adaptation recompose
python scripts/resolve_output_size.py --profile print-production --width-mm 210 --height-mm 297 --dpi 300
```
