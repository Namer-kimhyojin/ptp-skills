# 포항테크노파크 업무 스킬

포항테크노파크(포항TP) 직원이 AI 도우미(Claude, ChatGPT, Gemini 등)에게 업무를 맡길 때 쓰는 스킬 모음입니다. 스킬은 작성 요령과 양식을 AI에게 미리 알려 주는 폴더이며, 스킬을 쓰기만 하는 직원은 GitHub 계정이 필요 없습니다.

## 사이트

받는 방법과 사용 안내는 사이트에서 확인합니다.

https://namer-kimhyojin.github.io/ptp-skills/

## 설치(Claude 데스크톱 앱·Claude Code)

Claude 데스크톱 앱(Cowork·Code 탭)에서는 왼쪽 **Customize** › **Plugins**에서 마켓플레이스를 추가하고 `Namer-kimhyojin/ptp-skills`를 넣은 뒤 묶음을 고릅니다.

터미널의 Claude Code에서는 아래 명령으로 설치합니다.

```
/plugin marketplace add Namer-kimhyojin/ptp-skills
/plugin install ptp-pr@pohang-tp
```

`ptp-pr`은 보도·홍보 묶음, `ptp-admin`은 회의·행정 묶음, `ptp-report`는 기획·발표·보고 묶음입니다. 업무별 묶음은 필요한 것만 골라 설치하고, 모두 받으려면 `ptp-all@pohang-tp` 하나만 설치하세요. 전체 묶음과 업무별 묶음을 함께 설치하면 같은 스킬이 겹칩니다. 스킬을 직접 올리거나 고치려면 [CONTRIBUTING.md](CONTRIBUTING.md)를 읽어 주세요.

## 들어 있는 스킬

| 분류 | 스킬 | 설명 |
|---|---|---|
| 보도·홍보 | 보도자료 작성 | 계획안·행사자료로 포항TP 양식 보도자료(HWPX)를 작성·검수 |
| 보도·홍보 | SNS 홍보물 제작·게시 | 사업공고·행사를 홍보 이미지·카드뉴스·웹툰·영상으로 만들고 검수 후 재단 인스타그램·페이스북에 게시 (Codex용, Claude는 일부 지원) |
| 회의·행정 | 회의 결과문서 작성 | 기안문·영수증으로 회의록·방명록(서명란 빈칸)·지출증빙서(HWPX)를 작성 |
| 기획·발표·보고 | 공고레이더 | 정부·전담기관·지자체 신규 공고와 기술수요조사를 찾아 포항TP 적합도로 채점하고 원문 링크가 걸린 HTML 브리핑으로 정리 |
| 기획·발표·보고 | 발표자료 제작 | 보고서·수치·메모로 포항TP 발표자료(A4 가로 기본)를 HTML 한 파일로 제작, 발표 보기·편집·인쇄/PDF |

## 이용 안내

포항테크노파크 직원 업무용으로 공개합니다. 재사용 시 문의해 주세요. 오픈 라이선스는 적용하지 않았습니다.

## 관리자 메모

- 보도자료 스킬의 원장명 기본값은 공개 정보이며, 인사이동 시 `skills/write-pohang-tp-press-release/SKILL.md`에서 수정해야 합니다.
- 스킬 폴더의 `catalog.yaml`은 사이트 표시용 정보이며, 배포 zip과 묶음 폴더에는 들어가지 않습니다.
- `plugins/` 폴더는 묶음 설치용으로 `npm run build`가 `skills/`를 복사해 만듭니다. 직접 고치지 말고 `skills/`를 고치세요.
