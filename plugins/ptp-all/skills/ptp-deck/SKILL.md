---
name: "ptp-deck"
description: "자료(문서·수치·메모)로 포항테크노파크 발표자료를 단일 HTML로 만든다(A4 가로 기본, 16:9·4:3, 인쇄·PDF). 크기·분량·목적을 먼저 묻고 발표 유형별 흐름으로 구성하며 발표 보기·편집 모드를 넣는다. '발표자료 만들어줘', '현장방문·성과보고 자료' 요청에 사용."
---

# 포항테크노파크 발표자료 제작

사용자가 준 자료(보고서, 공문, 엑셀, 메모, 수치)를 읽고 **기획안 단계 없이 완성된 발표자료**를 만든다. 결과물은 쪽(기본 A4 가로) 여러 장으로 이루어진 **단일 HTML 파일 한 개**이고, 브라우저에서 넘겨 보며 발표하고, 브라우저 인쇄(Ctrl+P)로 PDF가 된다. 사업·부서·행사 종류와 무관하게 재단 안에서 범용으로 쓴다.

이 문서만으로 동작한다. CSS·JS·마크업이 모두 여기 들어 있어 별도 아티팩트, 디자인 시스템, 글꼴 파일, 네트워크 접속에 의존하지 않는다(글꼴은 있으면 쓰고 없으면 시스템 글꼴로 대체한다).

- 쪽 틀은 같고 내용만 바뀐다. 이 문서의 CSS·JS·마크업 조각을 그대로 쓰고, 새 스타일을 임의로 만들지 않는다.
- 슬라이드 기획 문서(MD)만 필요하면 이 스킬이 아니라 슬라이드 기획 스킬을 쓴다. PowerPoint(.pptx)를 명시적으로 요청받으면 pptx 스킬을 쓴다.

## 시작 전 확인 질문 (먼저 묻는다)

발표자료를 만들어 달라는 요청을 받으면 자료를 읽기 전에 아래 네 가지를 **한 번에** 묻는다. 질문 도구(AskUserQuestion 등)가 있으면 그것으로, 없으면 번호 목록으로 쓴다. 사용자가 이미 말한 항목은 다시 묻지 않고, 답이 없거나 "알아서"라고 하면 기본값으로 진행하며 마지막 답변에 어떤 값으로 만들었는지 한 줄로 알린다. 질문은 이 한 번으로 끝내고 되묻지 않는다(무인 실행이면 묻지 않고 기본값으로 만든다). 최신 요청과 공식 제출 양식의 조건이 있으면 그것을 먼저 따른다.

1. **크기(비율)** — A4 가로(기본, 인쇄·배포 겸용) / 16:9(화면 발표 위주일 때 권장) / 4:3.
2. **서식·참조자료와 공개 범위** — 따라야 할 기관 서식·PPT·이미지·로고·색상이 있는지, 출처 표시 기준, 내부용인지 외부 공유본인지. 없으면 포항테크노파크 기본 스타일·내부용.
3. **분량·발표시간·밀도** — 원하는 쪽수와 발표 시간(분), 자료의 쓰임(화면 발표형 / 표준 / 배포·읽는 자료형). 쪽수·시간이 없으면 자료 양으로 추정하고, 쓰임이 없으면 표준.
4. **발표 목적과 기본 정보** — 발표 유형·목적(아래 "발표 유형별 흐름"의 9가지 중), 청중과 발표 후 청중이 해야 할 판단·행동, 발표자(성명·소속·직위), 발표일자·장소, 실적 기준일.

답을 받은 뒤 적용 방법:

- **크기:** `:root`의 `--sw`·`--sh`와 `@page size`를 바꾼다. A4 가로 `297mm × 210mm`(`@page{size:A4 landscape}`), 16:9 `338mm × 190mm`(`@page{size:338mm 190mm}`), 4:3 `280mm × 210mm`(`@page{size:280mm 210mm}`). 검수 스크립트의 PDF 크기도 같은 값으로 맞춘다. 16:9는 세로가 10% 짧으므로 넘침 검사에서 걸리기 쉽다. 쪽당 내용을 줄인다.
- **서식·참조:** 색 참조가 있으면 `:root`의 `--blue`(주색)·`--red`(강조색)와 파생색(`--pale`, `--sky`, `--sky-soft`, `--line-card`)만 바꾼다(다른 새 색은 추가하지 않는다). 레이아웃 참조(PPT·이미지)는 쪽 유형 카탈로그에서 가장 가까운 유형을 고르는 근거로 쓰고, 참조 문서의 로고·그림은 사용자가 사용을 허락한 경우만 넣는다. 기관 서식이 PPT로만 제공되고 그대로 써야 하면 이 스킬 대신 pptx 스킬을 쓴다고 알린다.
- **공개 범위:** 외부 공유본에는 목적에 필요한 정보만 담는다(내부 검토 수치, 개인정보, 협의 중 내용은 뺀다). 공개가 필요한 출처는 해당 쪽 `note` 또는 부록에 표시한다.
- **분량·시간:** 쪽당 발표 1.5~2분으로 잡는다(표지·목차·간지·감사 제외). 시간이 주어지면 `시간 ÷ 2`쪽 안팎(예: 10분 → 5~6쪽 내용 + 표지·감사), 쪽수가 주어지면 `쪽수 × 2분`을 발표 시간으로 알린다. 둘 다 없으면 자료의 분량·주제 수로 8~14쪽을 추정하고 예상 발표 시간을 답변에 적는다. 세부 근거가 많으면 본문을 줄이고 부록으로 보낸다.
- **밀도:** "콘텐츠 밀도"의 덱 기준표로 쪽별 단계를 정한다.
- **목적·기본 정보:** 발표 유형으로 흐름을 고른다(아래). 발표자·소속은 표지 하단(`cover-bottom`)과 감사 쪽에, 발표일자는 표지 `cover-top`과 감사 쪽에 넣는다. 실적 기준일은 수치가 있는 쪽에 쓴다. 입력하지 않은 항목은 쓰지 않는다(날짜를 임의로 만들지 않는다).

## 입력과 기본값

| 항목 | 기본값 | 사용자가 주면 |
|---|---|---|
| 크기 | A4 가로 | 16:9 또는 4:3 (질문 1) |
| 서식·색·레이아웃 | 포항테크노파크 기본 | 질문 2 |
| 공개 범위 | 내부용 | 외부 공유본이면 정보 범위와 출처 표시 조정 |
| 발표 유형·목적 | 자료에서 판단(현장방문 자료면 현장방문형, 실적표 중심이면 성과보고형) | 질문 4 |
| 기관명 | 포항테크노파크 | 그대로 교체 |
| 자료 제목·사업명 | 자료에서 뽑는다 | 우선 적용 |
| 일자·장소·청중·기준일 | 자료에서 뽑고 없으면 쓰지 않는다 | 표지·감사 쪽·수치 쪽에 넣는다 |
| 쪽수·발표시간 | 내용에 따라 8~14쪽(표지·감사 포함), 쪽당 1.5~2분 | 지정 쪽수·시간 우선 |
| 밀도 | 표준(대부분 2단계) | 발표형·배포형 (질문 3) |
| 표지·목차 | 내용 5쪽 이하: 간결형 표지(A2), 목차 없음 / 6쪽 이상: 기본형 표지(A1, 섹션 안내 없이) + 목차(Y) | 표지 형태 지정 가능 |
| 마무리 | 목적에 맞는 마무리 쪽 + 감사 쪽 | 감사 쪽 생략 가능 |
| 로고 | 재단 CI(`assets/`) — 표지·감사 쪽 | 다른 기관 자료면 쓰지 않음 |
| 사진·그림 | 쓰지 않는다 | 제공된 파일만, 한 장씩 도판으로 |
| 배경 그림 | 쓰지 않는다 | 제공된 이미지만 `has-art`로 |

자료가 부족해도 물어보기 전에 가능한 데까지 만든다. 자료에 없는 수치·날짜·기관명·인용은 만들어 넣지 않는다. 판단에 꼭 필요한 정보가 빠졌으면 확인된 내용으로 먼저 구성하고, 빠진 항목은 쪽에 자리표시를 넣지 말고 마지막 답변의 "확인이 필요한 항목"으로 알린다. 내용이 비면 그 쪽을 줄이거나 뺀다.

## 작업 순서

0. **확인 질문.** 위 "시작 전 확인 질문"을 한 번에 묻고 답을 받는다.
1. **발표 설계.** 발표 목적을 한 문장으로, 청중(역할·사전 지식·궁금해할 것·결정 권한)과 핵심 메시지(청중이 기억할 것과 발표 후 판단·행동), 범위(대상 사업·지역·기관, 집계 기간·기준일, 비교 대상)를 정한다. 여러 목적이 섞이면 발표 직후 청중이 해야 할 판단·행동을 기준으로 하나를 고른다.
2. **자료 읽기와 사실 정리.** 첨부 파일을 형식에 맞는 방법으로 끝까지 읽고 "자료 정리와 수치 기준"에 따라 핵심 사실과 지표를 뽑는다. 숫자는 원문에서 다시 확인한다.
3. **흐름과 쪽 구성표.** "발표 유형별 흐름"에서 흐름을 고르고, 섹션 3~4개(01~04)로 묶는다. 표지 형태·목차 여부를 정하고, 쪽마다 "결론 문장(h2) + 쪽 유형 + 밀도 단계"를 먼저 쓴 뒤, 제목만 이어 읽어도 발표가 되는지 확인한다. 쪽당 주장은 하나.
4. **HTML 작성.** 아래 "파일 구성"의 틀에 쪽을 채운다. 파일은 작업 폴더에 내용을 나타내는 영문 파일명(예 `site-visit-2026.html`)으로 저장한다. 긴 파일이므로 틀(head, 툴바, CSS, JS)을 먼저 쓰고 쪽을 나눠 추가해도 된다.
5. **넘침 검사.** "검수"의 스크립트를 실행해 넘친 쪽을 고친다. 넘침이 없을 때까지 반복한다.
6. **눈으로 확인과 원자료 대조.** 쪽별 화면 이미지를 실제 발표 순서로 보며 정렬·겹침·빈 쪽을 확인하고, 표시한 수치·날짜·명칭을 원자료와 다시 대조한다(검수 체크리스트).
7. **전달.** 완성한 `.html` 파일을 사용자에게 전달한다. 파일 전달 도구가 있으면 그것으로 보내고, 없으면 저장 경로를 알려 준다. 사용자가 PDF를 요청하거나 실행 환경에서 만들 수 있으면 PDF도 같이 만들고, 여러 형식이면 서로 같은 최종 내용인지 대조한다. 답변은 다음 순서로 짧게 쓴다.
   - 무엇을 어떤 유형·흐름으로 몇 쪽(예상 발표 시간)으로 만들었는지 한두 문장
   - 기본값으로 정한 항목
   - 확인이 필요한 항목(자료에 없어 뺀 것, 자료 간 차이가 있는 수치와 택한 기준)
   - 주요 수치의 출처 메모(수치 → 자료명·쪽/시트·기준일). 파일로 만들지 않고 답변에만 쓴다.
   - 사용법 한 줄(브라우저로 열고 ‘편집’으로 글 수정·이동·크기 조절 후 ‘저장’, ‘발표 시작’, 인쇄는 Ctrl+P → 선택한 크기·여백 없음·배경 그래픽 켜기)

## 자료 정리와 수치 기준

1. **출처와 범위를 기록한다.** 주요 주장마다 자료명, 버전 또는 확인일, 해당 쪽·시트·셀, 적용 범위를 작업 메모로 남긴다(답변의 출처 메모로 쓴다).
2. **자료마다 확인할 것을 정한다.** 승인된 계획에서는 목표와 범위, 실적표에서는 현재 결과, 회의록에서는 합의와 검토 사항, 담당자 설명에서는 최신 변경 상태를 본다. 자료 간 우선순위를 사용자가 정하면 따른다.
3. **자료 간 차이를 확인한다.** 총괄표와 세부 내역이 다르면 대상, 기간, 중복, 집계 정의, 갱신일을 대조한다. 결론을 바꾸는 차이는 기준을 하나 정해 쓰고 수치 옆이나 `note`에 집계 범위를 밝히며, 답변의 "확인이 필요한 항목"에 적는다.
4. **날짜를 구분한다.** 발표일, 사업 운영 기간, 실적 기준일, 조사일이 다르면 그 쪽을 읽는 데 필요한 날짜를 해당 쪽에 넣는다(`year-caption`, `note`, `page-context`).

자료의 성격에 따라 쪽 위의 표기와 모양을 정한다.

| 자료의 성격 | 표기 예시 | 표현(클래스) |
|---|---|---|
| 확인된 사실·완료 실적 | 완료, 확정 실적, 승인 완료 | 파랑 실선: `status done`, `state complete`, `metric primary`, `outcome` |
| 특정 시점 집계 | 기준일 현재 집계, 중간 집계, 잠정치 | 파랑 실선 + 기준일 표기(`note` 또는 `year-caption`) |
| 진행 중인 조치 | 시행 중, 협의 중, 검증 중 | 빨강 점선: `state live`, 표의 `tr.tint` |
| 가정에 따른 추정 | 예상, 전망 + 기준·조건 짧게 | `metric forecast`, `outcome projected`, `status pending`, 막대 빗금 `<i>` |
| 앞으로 할 일 | 계획, 추진 예정 + 담당·시점 | 점점선: `status planned`, `improve future` |
| 제안·관계자 의견 | 제안, 검토안, 면담 의견 + 발언 주체·시점 | `status pending` 또는 `board dashed` |
| 확인되지 않은 항목 | 확인 중, 미집계, 해당 없음 | 글자로만 표기(빈칸·0과 구분) |

상태는 글자와 선 모양(실선·점선·점점선·빗금)으로 먼저 구분되게 하고 색은 보조로 쓴다. 빨강은 글자로는 `red-ink`(#b32a23)만 쓴다. 추정치가 들어간 쪽에는 반드시 `note`로 추정 기준과 "최종 수치는 종료 후 확정"을 쓴다.

### 지표를 비교할 때

- 지표명에 측정 대상을 드러낸다(신청자·참여자·수료자·취업자는 단계마다 다른 수치). 사람과 건수, 신규와 누계, 월간과 연간, 중복 제거 전과 후를 구분한다.
- 비율 옆에 분자·분모 또는 집계 기준을 쓴다. **달성률 = 실적 ÷ 목표 × 100**, **전환율 = 다음 단계 도달 대상 ÷ 이전 단계 대상 × 100**. 분모가 0이거나 확인되지 않으면 계산하지 않고 사유를 쓴다.
- 증감은 같은 범위·기간·단위·집계 방식끼리 비교한다. 조건이 다르면 병기하고, 비율의 차이는 %p로 쓴다.
- 전망은 현재 집계, 앞으로 반영될 값, 전망 합계와 성립 조건을 함께 보여 준다(유형 G·H). 이미 달성한 목표와 조건 충족 시 달성 가능한 목표를 문구와 배치로 구분한다.
- 사업 전체 예산·목표와 당해연도 배정·집행·실적을 따로 쓴다. 합계는 집계 범위가 맞고 중복을 처리할 수 있을 때만 쓴다. 공란·미집계·0을 구분한다.
- 목표보다 낮은 값이나 주요 한계가 판단에 영향을 주면 원인, 대응, 확인 시점을 같은 쪽에 쓴다. 활동량(교육 횟수)과 실제 변화(수료·취업)를 구분한다.

## 발표 유형별 흐름

질문 4의 답이나 자료로 유형을 고른다. 모든 유형의 틀은 `표지 → (목차) → 본문 흐름 → 마무리 → 감사 → (부록)`이다. 아래는 예시 흐름이며, 청중이 먼저 답을 듣고 싶어 하는 질문을 기준으로 순서를 바꾸고 필요한 단계만 쓴다. 괄호는 주로 쓰는 쪽 유형(아래 카탈로그)이다.

| 유형 | 권장 흐름 |
|---|---|
| 사업 소개·대외 설명 | 추진 배경 → 사업 개요·대상(B) → 주요 서비스·활동(C·D) → 제공 가치 → 참여·문의 방법 |
| 기획·제안·공모 | 해결할 문제와 수요 → 목표 → 사업 내용·차별점(C·K·V) → 추진체계(T) → 일정·예산(N·I) → 성과 측정·요청 사항 |
| 착수·중간보고·정례회의 | 핵심 현황(F·R) → 주요 진척(C·Q) → 일정·실적 차이(I·N) → 현안·대응(C) → 담당·다음 일정(M) |
| 성과·최종·평가보고 | 핵심 성과(F·R) → 목표 대비 실적(G·H) → 정량·정성 근거(P·Q·U·E) → 한계와 학습 → 후속 활용(M) |
| 정책·의사결정·예산 보고 | 결정 요청(R) → 배경·제약 → 대안 비교(S) → 권고안과 판단 근거(X) → 비용·일정·후속 조치(M) |
| 현장방문·점검·이슈 대응 | 방문 목적·핵심 쟁점(B) → 운영 현황(D·E) → 확인 사항과 개선 조치(C·V) → 현장 확인·논의 → 후속 계획(M) |
| 협력 제안·투자 유치 | 협력 기회 → 각 주체의 필요(K) → 공동 실행안 → 역할·자원·일정(T·N) → 합의·요청 사항 |
| 교육·워크숍 | 학습 목표 → 핵심 개념 → 사례·시연(E) → 활동·이해 확인 → 적용 방법 |
| 행사 안내·홍보·모집 | 대상이 얻는 가치 → 대상·일시·장소(B) → 프로그램(D) → 신청·참여 방법 |

내용별로 담을 것:

- **사업 개요**: 목적, 수혜·참여 대상, 사업 기간, 수행 주체와 역할, 주요 활동. 예산과 범위는 판단·이해에 필요한 만큼.
- **운영 현황**: 실제 업무 흐름, 담당 주체, 이용·참여 방식, 확인할 지점.
- **성과**: 목표와 실적, 그 성과가 의미하는 변화, 대표 사례(사례가 적용되는 범위 포함).
- **현안과 개선**: 확인된 상황 → 현재 조치 → 후속 계획. 조치 적용 시점과 향후 시행 조건을 밝힌다.
- **수요 맞춤 추진안**(J·K): 대상별 요구 → 확인한 수요 → 바꿀 내용 → 다음 일정. 면담·협의·합의·체결·실행 상태를 구분한다.
- **실험·시범사업**(J): 가설, 바꿀 내용, 판단 기준을 한곳에 두고 대상·기간·표본·상태를 함께 쓴다. 결과·학습·다음 실행과 비교 조건·판단 한계를 같이 제시한다.
- **마무리**: 발표 목적에 맞춘다. 회의·보고는 결정·요청·담당·일정(M), 홍보·모집은 참여 방법, 교육은 적용 과제나 질의응답으로 끝낸다. 그 뒤에 감사 쪽(O)을 둔다(사용자가 원하지 않거나 정례회의처럼 형식이 맞지 않으면 생략).
- **부록**: 본문 판단에 필요하지 않은 세부 근거(상세 표, 산식, 출처 목록)는 감사 쪽 뒤에 섹션 이름 "부록"으로 둔다. 머리글 섹션 번호는 `부록`으로 쓴다.

## 쪽 구성 원칙

- **h2는 주제어가 아니라 결론 한 문장**이다: "교육 공간과 안내의 실제 작동 여부 점검", "완료 수료 집계 261명 · 진행중 예상 수료 60명". 교육·질의응답 자료는 핵심 질문을 제목으로 써도 된다("수료 후 취업까지 무엇이 달라졌나"). 두 줄을 넘기지 않는다(27pt, 약 28자 안팎 한 줄).
- 한 쪽에 핵심 주장 하나와 그것을 받치는 카드·표 하나. 열은 2~3개. 한 줄 밴드(`band`)는 쪽당 한 개.
- 읽는 순서: 제목 → 핵심 시각 요소 → 짧은 설명 → 기준일·단위. 내용이 많으면 우선순위를 정해 문장을 압축하고, 세부 근거는 부록으로 보낸다.
- 보여 주는 방식은 "레이아웃 설계 6"의 표를 따른다. 두 집단을 비교할 때는 크기·눈금·단위·정렬을 맞춘다.
- 사진은 현장·제품·사례를 보여 줄 때만(E), 배경 그림은 분위기 보완용으로만(`has-art`) 쓰고 둘을 섞지 않는다. 글자와 대비가 충분한지 본다.
- 섹션 번호(01~04)는 표지 하단 `cover-route`의 순서와 같게 하고, 머리글 왼쪽에 쪽마다 반복한다.
- 문장은 개조식 명사형으로 끝낸다("~ 강화", "~ 적용 중", "~ 계획"). 마침표를 찍지 않는다. 이모지·감탄 표현을 쓰지 않는다.
- 숫자는 단위를 붙여 구체적으로 쓴다(261명, 66시간, 10.21.–11.4.). 날짜는 `2026. 11. 04.`, 기간은 `2024–2028년`.
- 바닥글: `{기관명} · {자료 제목}` 과 `02 / 12`. 쪽 번호는 마지막에 총 쪽수로 다시 맞춘다(툴바의 `1 / N`도).

## 레이아웃 설계

쪽 틀(머리글 · h2 · 본문 · 바닥글)은 고정이고, 본문(`main`) 안에서 아래 원칙으로 배치를 고른다.

**1. 항목 수로 배치를 정한다**

| 같은 무게의 항목 수 | 배치 | 유형 |
|---|---|---|
| 1개(핵심 문장·결론) | 한 덩어리 크게 | X, R |
| 2개 | 2단 비교 | G, H, V, `two-cols` |
| 3개 | 3단 | D의 `three-cols`, M, L |
| 4개 | 2×2 | C |
| 5~7개 | 표 또는 세로 목록 | 표, N, E의 목록 |
| 8개 이상 | 줄여서 본문, 나머지는 부록 | 부록 표 |

**2. 화면 분할 패턴**

- **위 요약 + 아래 근거**: 지표 카드(F)나 요약(R) 위, 표·그래프 아래. 보고형 기본.
- **왼쪽 시각 + 오른쪽 설명(`split`)**: 그래프·표·사진이 주인공이고 해석이 2~4줄일 때.
- **좌우 대칭 비교**: 전후(V), 대안(S), 목표 대비(G). 양쪽 항목 순서와 크기를 맞춘다.
- **가운데 흐름**: 단계·절차·체계(D, I, K, T, U). 화살표 방향은 왼→오, 위→아래 하나로.

**3. 시선과 강조**

- 결론·강조 블록은 위쪽 또는 왼쪽에, 마무리 한 줄(`band`·`ask`)은 맨 아래에 둔다.
- 색을 채운 강조 블록(`metric primary`, `summary-key`, `band`, `total-band`)은 쪽당 두 개까지. 초점이 여럿이면 아무것도 강조되지 않는다.
- 같은 쪽의 카드는 크기·글자 크기·정렬을 맞춘다(격자 배치는 높이가 자동으로 맞는다).

**4. 여백 균형(채움률)**

- 본문 채움률(블록이 차지한 높이 ÷ 본문 높이)은 60~95%가 적당하다. 검수 스크립트가 측정한다.
- 60% 미만이면 순서대로 고친다: `main`에 `v-center`·`v-spread` → 블록을 더 큰 유형으로 바꿈(예: 3단 글 → 지표 카드) → 앞뒤 쪽과 합침. 자료에 없는 내용으로 채우지 않는다.
- 95%를 넘으면 문장 압축 → 항목 줄이기 → 부록으로 보내기 → 쪽 나누기.

**5. 덱 전체의 리듬**

- 글 위주 쪽과 시각 위주 쪽(그래프·지표·체계도)을 번갈아 둔다. 같은 유형은 연속 세 쪽을 넘기지 않는다.
- 10쪽 이상이면 섹션마다 간지(W)를 둘 수 있고(쪽수에 포함), 핵심 메시지 쪽(X)은 전환점에 한두 번만 쓴다.
- 첫 내용 쪽은 결론부터: 의사결정·보고형이면 R, 성과형이면 F, 소개형이면 B.

**6. 무엇으로 보여 줄지**

| 보여 줄 것 | 유형 |
|---|---|
| 규모·핵심 숫자 | F 지표 카드 |
| 목표 대비 달성 | G 성과 카드, H 막대 |
| 시간에 따른 변화 | P 추세 그래프(점 4개 이상), L 연도별 카드(3개 이하) |
| 항목·구간 비교 | Q 세로 막대 |
| 단계별 전환 | U 퍼널 |
| 구조·역할 | T 추진체계, B 개요 |
| 절차·흐름 | D 일정, I 단계, K 통합 흐름, N 일정표 |
| 바뀌는 점 | V 전후 비교 |
| 선택지 | S 대안 비교 |
| 결론·요청 | R 핵심 요약, X 핵심 메시지 |
| 여러 조건의 정확한 대조 | 표 |
| 현장·사례 | E 사진 |

## 콘텐츠 밀도 (3단계)

쪽마다 담는 양을 세 단계로 나눈다. 덱 전체의 쓰임(질문 3)으로 기본 단계를 정하고, 쪽마다 `<section class="sheet" data-density="2">`처럼 단계를 적는다(표지·목차·간지·감사 쪽은 적지 않고 측정에서 빠진다). 표시하지 않은 쪽은 2단계로 본다.

| 단계 | 이름 | 본문 글자(공백·제목 제외) | 본문 블록 | 표 행(합계 포함) | 어울리는 쪽 |
|---|---|---|---|---|---|
| 1 | 여유 | 100자 이하 | 2개 이하 | 표 없음 | 핵심 요약(R), 핵심 메시지(X), 큰 지표(F 표 없이), 사진(E) |
| 2 | 표준 | 200자 이하 | 3개 이하 | 4행 이하 | 대부분의 본문 쪽(B·C·D·G·H·K·L·M·N·P·Q·S·T·U·V) |
| 3 | 상세 | 350자 이하 | 4개 이하 | 7행 이하 | 표 중심 쪽(F 표 포함·I), 수요 기획안(J), 부록 |

| 덱의 쓰임 | 단계 구성 |
|---|---|
| 발표형(화면에 띄우고 말로 설명) | 1~2단계만. 3단계에 해당하는 근거는 부록으로 보낸다 |
| 표준(기본) | 2단계 중심. 결론·전환 쪽은 1단계, 표 쪽만 3단계 |
| 배포형(인쇄·발표 없이 읽는 자료) | 2~3단계. 읽기만 해도 이해되도록 `note`·기준일·산식을 충실히 |

- 단계 기준을 넘으면 문장 압축 → 항목 줄이기 → 부록으로 보내기 → 쪽 나누기 순으로 고친다. 덱의 쓰임이 허용하면 단계를 올려도 된다(발표형 덱에서 3단계는 안 된다).
- 기준보다 훨씬 적으면 단계를 낮춰 표시하고, 아래가 비면 "레이아웃 설계 4"의 여백 규칙을 쓴다.
- **작성 지원**: 검수 스크립트가 쪽별 단계·글자·블록·표 행을 재서 초과한 쪽을 알려 준다. 완성 파일의 편집 모드에서는 쪽 오른쪽 위에 `밀도 2 표준 · 171/200자` 배지가 보이고, 기준을 넘으면 빨갛게 바뀐다. 배지를 누르면 그 쪽의 단계가 1 → 2 → 3으로 바뀌어 저장 파일에 남는다. 배지는 발표 화면·인쇄에는 나오지 않는다.

## 쪽 유형 카탈로그

쪽 틀(모든 내용 쪽 공통):

```html
<div class="sheet-wrap"><section class="sheet" id="p2" aria-label="2쪽: 결론 문장">
<header><div class="section-lockup"><b class="section-number">01</b><span class="section-name">섹션명</span></div><span class="page-context">쪽 맥락</span></header>
<h2>결론 문장</h2>
<main>…본문 유형…</main>
<footer><span>포항테크노파크 · 자료 제목</span><span>02 / 12</span></footer></section></div>
```

**A. 표지** (틀 없이) — 세 가지 형태 중 하나. 발표자·소속, 문서 구분(`cover-tag`: 내부 검토 / 외부 공유), 일자는 입력된 것만 넣고 없는 칸은 지운다.

- **A1 기본형** `sheet cover` — 보고·설명 자료. 목차 쪽(Y)이 없을 때만 섹션 안내(`cover-route`)를 넣고, 목차 쪽이 있으면 넣지 않는다(목차와 중복)
- **A2 간결형** `sheet cover simple` — 섹션 안내 없이 제목을 크게. 짧은 자료(내용 5쪽 이하)·대외 인사·행사
- **A3 띠형** `sheet cover stripe` — 왼쪽 파란 면에 기관·일자·발표자, 오른쪽에 제목. 행사·대외 발표·제안 발표. 목차 쪽이 없으면 오른쪽 아래에 섹션 안내를 넣어도 된다
- 목차 쪽이 있는 덱에서는 표지의 섹션 안내가 CSS로 자동으로 숨겨지지만, 마크업에도 넣지 않는다
- 사용자가 배경 이미지를 주면 A1·A2에 `has-art`를 더한다

```html
<!-- A1 기본형 (로고는 "로고 (CI)" 참고. 로고 파일이 없으면 img 자리에 기관명 글자) -->
<div class="sheet-wrap"><section class="sheet cover" id="p1" aria-label="1쪽: 표지"><div class="cover-top"><span>자료 종류(예: 성과보고)</span><span>2026. 11. 04.</span></div><div class="cover-label">관련 기관·행사명<span class="cover-tag">외부 공유</span></div><h1>사업명 앞부분<br><em>강조할 뒷부분</em></h1><div class="cover-sub">부제 첫 줄<br>부제 둘째 줄</div><div class="cover-route"><div><b>01</b><strong>섹션1</strong><span>하위 키워드</span></div><i>→</i><div><b>02</b><strong>섹션2</strong><span>하위 키워드</span></div><i>→</i><div><b>03</b><strong>섹션3</strong><span>하위 키워드</span></div></div><div class="cover-bottom"><span class="who"><b>발표자 성명 직위</b>소속 부서</span><img class="logo" src="data:image/png;base64,…" alt="(재)포항테크노파크"></div></section></div>
<!-- A2 간결형 -->
<div class="sheet-wrap"><section class="sheet cover simple" id="p1" aria-label="1쪽: 표지"><div class="cover-top"><span>자료 종류</span><span>2026. 11. 04.</span></div><div class="cover-label">관련 기관·행사명</div><h1>사업명 앞부분<br><em>강조할 뒷부분</em></h1><div class="cover-sub">부제 한 줄</div><div class="cover-bottom"><span class="who"><b>발표자 성명 직위</b>소속 부서</span><img class="logo" src="data:image/png;base64,…" alt="(재)포항테크노파크"></div></section></div>
<!-- A3 띠형 -->
<div class="sheet-wrap"><section class="sheet cover stripe" id="p1" aria-label="1쪽: 표지"><div class="cover-side"><img class="logo cs-logo" src="data:image/png;base64,…(logo-koen-v-white)" alt="(재)포항테크노파크"><span class="cs-date">2026. 11. 04.</span><span class="cover-tag">외부 공유</span><div class="cs-who"><b>발표자 성명</b>직위 · 소속 부서</div></div><div class="cover-main"><div class="cover-label">관련 기관·행사명</div><h1>사업명 앞부분<br><em>강조할 뒷부분</em></h1><div class="cover-sub">부제 한 줄</div></div></section></div>
```

**Y. 목차** (`sheet agenda-page`) — 내용 쪽이 6쪽 이상이거나 섹션이 3개 이상이면 표지 바로 뒤에 둔다. 5쪽 이하면 두지 않는다(필요하면 A1 표지의 섹션 안내로 흐름만 보여 준다). 목차 쪽을 두면 표지에는 섹션 안내를 넣지 않는다. 섹션 번호·이름은 각 쪽 머리글·표지 `cover-route`와 같게, 쪽 범위는 실제 쪽 번호와 맞춘다. 항목을 누르면 그 쪽으로 이동한다.

```html
<div class="sheet-wrap"><section class="sheet agenda-page" id="p2" aria-label="2쪽: 목차"><div class="agenda-top"><span>목차</span><span>자료 제목</span></div><main class="agenda"><a href="#p3"><b>01</b><div><strong>섹션1 이름</strong><span>하위 주제 · 하위 주제</span></div><em>3–4쪽</em></a><a href="#p5"><b>02</b><div><strong>섹션2 이름</strong><span>하위 주제 · 하위 주제</span></div><em>5–7쪽</em></a><a href="#p8"><b>03</b><div><strong>섹션3 이름</strong><span>하위 주제</span></div><em>8–9쪽</em></a></main><footer><span>포항테크노파크 · 자료 제목</span><span>02 / 10</span></footer></section></div>
```

**B. 개요** — 소개 박스 + 사실 3칸 + 참여기관 줄

```html
<div class="intro"><span class="eyebrow">사업 개요</span><h3>사업명 한 줄</h3><p>목적 한 줄</p></div>
<div class="facts"><div class="fact"><span>사업기간</span><strong>2024–2028년</strong><p>보충 한 줄</p></div><div class="fact"><span>대상</span><strong>값</strong><p>보충</p></div><div class="fact"><span>주관·전문기관</span><strong>값</strong><p>보충</p></div></div>
<div class="partners"><span class="eyebrow">수행기관</span><div>기관A <i>+</i> 기관B<br>기관C <i>+</i> 기관D</div></div>
<div class="bottom-line">보조 설명 한 줄</div>
```

**C. 개선·추진 카드 2×2** — 항목 4개(홀수면 3개)와 요약 밴드

```html
<div class="improve-grid"><article class="improve"><div class="improve-top"><span>01</span><span class="status done">시행중</span></div><h3>제목</h3><p>설명 두 줄 이내</p></article>…<article class="improve future"><div class="improve-top"><span>04</span><span class="status planned">추진 계획</span></div><h3>제목</h3><p>설명</p></article></div>
<div class="band"><b>요약어</b><span>항목 · 항목 · 항목</span></div>
```

**D. 일정·운영** — 시간 흐름 + 핵심 문구 + 3열 설명

```html
<div class="day-flow"><div><time>10:00–13:00</time><b>오전</b></div><div class="lunch"><time>13:00–14:00</time><b>점심</b></div><div><time>14:00–17:00</time><b>오후</b></div></div>
<div class="callout"><b>핵심 문구</b><span>보조 한 줄</span></div>
<div class="three-cols"><article class="plain"><span class="eyebrow">분류</span><h3>제목</h3><p>줄1<br>줄2<br>줄3</p></article>…(3칸)</div>
```

**E. 현장 사진 + 점검** — 사진은 사용자가 준 파일만. 사진이 없으면 이 유형 대신 C 또는 D를 쓴다. 이미지는 base64 data URI로 내장해 파일 하나로 배포되게 한다(아래 "이미지 내장").

```html
<div class="tour"><figure><img src="data:image/jpeg;base64,…" alt="설명"><figcaption>사진 설명</figcaption></figure><div class="tour-list"><article><span>01</span><div><h3>제목</h3><p>줄1<br>줄2</p></div></article>…(3개)</div></div>
<div class="learning"><b>확인 → 기록 → 반영</b><p>한 줄 설명</p></div>
```

**F. 핵심 지표 + 표** — 지표 3장(목표·확정·예상) 후 표, 아래 주석

```html
<div class="metrics"><article class="metric"><span>목표</span><strong>240<small>명</small></strong><p>구성 내역</p></article><article class="metric primary"><span>완료 · 집계</span><strong>261<small>명</small></strong><p>구성 내역</p></article><article class="metric forecast"><span>진행중 · 예상</span><strong>60<small>명</small></strong><p>구성 내역</p></article></div>
<table><thead><tr><th>구분</th><th>대상</th><th>인원</th><th>집계</th><th>예상</th></tr></thead><tbody><tr><td><span class="state complete">완료</span></td><td>…</td><td>…</td><td><b>…</b></td><td>—</td></tr><tr class="tint"><td><span class="state live">진행중</span></td>…</tr><tr class="total"><td colspan="2">합계</td>…</tr></tbody></table>
<div class="note">추정치 · 최종 수치는 종료 후 확정</div>
```
표 열이 둘째 칸부터 가운데 정렬이다. 긴 글 칸에는 `class="left"`를 준다. 이 유형은 높이가 빠듯하므로 표 행은 합계 포함 4행 이내.

**G. 목표 대비 달성** — 두 칸 성과 카드 + 합계 밴드

```html
<div class="outcomes"><article class="outcome projected"><div class="outcome-top"><h3>대상A</h3><span class="status pending">초과달성 전망</span></div><div class="outcome-num"><strong>116</strong><span>/ 목표 100명</span></div><div class="outcome-label">산식 한 줄(완료 56명 + 진행중 예상 60명)</div><div class="outcome-result"><div><span>예상 달성률</span><b>116%</b></div><div><span>목표 대비</span><b>16명 초과 가능</b></div></div></article><article class="outcome">…(확정 카드: status done)</article></div>
<div class="total-band"><span>전체 전망</span><b>321명</b><p>목표 240명 대비 <strong>81명 초과 가능</strong></p></div>
```

**H. 막대 카드** — 달성률을 막대로(두 칸)

```html
<div class="target-grid"><div class="target"><span class="status done">초과달성</span><h3>대상A <strong>146</strong>%</h3><div class="bar"><span style="width:100%"></span></div><p>산식 문장</p></div><div class="target focus"><span class="status pending">전망</span><h3>대상B <strong>116</strong>%</h3><div class="bar"><span style="width:48%"></span><i style="width:52%"></i></div><p>확정(실선) + 예상(빗금)</p></div></div>
```

**I. 과정표 + 단계** — 열 5개 표와 3단계 흐름(`milestones`)

```html
<table><thead><tr><th>상태</th><th class="left">과정</th><th>기간</th><th>인원</th><th>예상</th></tr></thead><tbody><tr><td><span class="state live">진행중</span></td><td class="left"><b>과정명</b><span class="row-note">66시간</span></td><td>10.21.–11.4.</td><td>8명</td><td><b>8명</b></td></tr>…<tr class="total">…</tr></tbody></table>
<div class="milestones"><div><b>단계1</b><span>설명</span></div><i>→</i><div><b>단계2</b><span>설명</span></div><i>→</i><div><b>단계3</b><span>설명</span></div></div>
<div class="note">주석</div>
```

**J. 수요 연계 기획안** — 배너 + 가설·변경점·성공기준 보드

```html
<div class="banner"><span class="status pending">↻ 진행 중</span><div><span>분류</span><strong>대상 기관·기업명</strong></div><p>설명<br>두 줄</p></div>
<div class="board dashed"><div class="experiment-top"><div><span class="eyebrow">분류</span><h3>보드 제목</h3></div><span class="status planned">◇ 세부 추진안</span></div><div class="experiment-grid"><div><b>가설</b><p>…</p></div><div><b>변경점</b><p>…</p></div><div><b>성공기준</b><p>…</p></div></div><div class="experiment-meta"><p><b>대상군</b> …</p><p><b>기간</b> …</p><p><b>규모</b> …</p></div><div class="next"><b>다음 실행</b><p>…</p></div></div>
```

**K. 수요 통합 흐름** — 입력 둘 → 통합 → 결과

```html
<div class="curriculum-simple"><div class="demand-inputs"><article><span class="eyebrow">분류</span><h3>입력1</h3><p>설명</p></article><article><span class="eyebrow">분류</span><h3>입력2</h3><p>설명</p></article></div><div class="demand-arrow"><span>통합</span><b aria-hidden="true">→</b></div><article class="curriculum-result"><span class="status planned">추진 방향</span><h3>결과<br>제목</h3><ul><li>항목</li><li>항목</li><li>항목</li></ul></article></div>
<div class="feedback"><b>운영 후 보완</b><span>한 줄</span></div>
```

**L. 연도별·구간별 수치** — 세 칸 + 목표 달성 밴드 + 사례 줄

```html
<div class="year-caption"><b>기준 제목</b><span>조사 기준일 2026. 10. 20.</span></div>
<div class="years"><article class="year"><div class="year-top"><h3>2024년</h3><span>구분</span></div><div class="year-count"><strong>57</strong><span>명</span></div><p>설명</p></article><article class="year">…</article><article class="year current"><div class="year-top"><h3>2026년</h3><span>구분</span></div><div class="year-count"><strong>10</strong><span>명</span></div><p><b>중간 집계</b> · 진행중</p></article></div>
<div class="target-band"><div><b>목표 달성률</b><p>산식 한 줄</p></div><strong>220<span>%</span></strong></div>
<div class="list-box"><b>주요 사례</b><p>사례A · 사례B · 사례C</p></div>
```

**M. 실행과제** — 3칸 + 닫는 밴드(마지막 내용 쪽)

```html
<div class="closing-grid"><article class="action"><span class="action-number">01</span><h3>과제명</h3><p><b>무엇을</b>내용</p><p><b>언제까지</b>시기</p><div class="action-foot">담당: 부서</div></article>…(3칸)</div>
<div class="band"><b>다음 점검</b><span>한 줄</span></div>
```

**N. 일정표(세로)** — 날짜 · 내용 · 상태 행

```html
<div class="timeline"><article><time>’26.12.</time><div><h3>단계명</h3><p>내용</p></div><span class="status done">완료</span></article>…</div>
```

**O. 감사 쪽** (`sheet thanks`, 틀 없이)

```html
<div class="sheet-wrap"><section class="sheet thanks" id="pN" aria-label="N쪽: 감사합니다"><div class="thanks-top"><span>자료 제목</span><span>2026. 11. 04.</span></div><main class="thanks-main"><div class="thanks-rule" aria-hidden="true"></div><h2>감사합니다</h2><p>발표자 성명 · 소속 부서(입력된 경우만)</p></main><div class="thanks-bottom"><span>관련 기관·행사명</span><img class="logo" src="data:image/png;base64,…" alt="(재)포항테크노파크"></div></section></div>
```

**P. 추세 그래프** — 시간에 따른 변화(월·분기·연도). 점 4~8개. 실선은 확정, 점선은 예상

```html
<div class="trend"><svg viewBox="0 0 1000 300" aria-label="연도별 수료 인원 추세"><line class="gl" x1="0" y1="290" x2="1000" y2="290"/><line class="gl" x1="0" y1="165" x2="1000" y2="165"/><line class="gl" x1="0" y1="40" x2="1000" y2="40"/><polyline class="ln" points="125,240 375,170 625,90"/><polyline class="ln fc" points="625,90 875,60"/><circle class="pt" cx="125" cy="240" r="9"/><circle class="pt" cx="375" cy="170" r="9"/><circle class="pt" cx="625" cy="90" r="9"/><circle class="pt fc" cx="875" cy="60" r="9"/></svg>
<div class="trend-x"><div><b>57명</b>2024년</div><div><b>98명</b>2025년</div><div><b>146명</b>2026년</div><div class="fc"><b>165명</b>2027년(예상)</div></div></div>
<div class="note">축 기준 · 수료 인원(명) · 기준일 표기</div>
```
좌표는 계산해서 넣는다. 점 n개일 때 `x = (i + 0.5) × 1000 ÷ n`(아래 `trend-x` 칸 가운데와 맞음), `y = 290 − (값 − 축최소) ÷ (축최대 − 축최소) × 250`. 축최소는 보통 0. 값 글자는 SVG가 아니라 `trend-x`에 쓴다.

```python
vals=[57,98,146,165]; lo,hi=0,max(vals)*1.1; n=len(vals)
pts=[(round((i+.5)*1000/n),round(290-(v-lo)/(hi-lo)*250)) for i,v in enumerate(vals)]
```

**Q. 세로 막대(항목·구간 비교)** — 항목 3~7개. 높이는 `값 ÷ 최댓값 × 100%`. `mute`는 비교 기준, `fc`는 예상

```html
<div class="colchart"><div class="mute"><b>120건</b><i style="height:48%"></i></div><div><b>180건</b><i style="height:72%"></i></div><div><b>250건</b><i style="height:100%"></i></div><div class="fc"><b>230건</b><i style="height:92%"></i></div></div>
<div class="col-x"><span>목표</span><span>상반기</span><span>하반기</span><span>내년(예상)</span></div>
```

**R. 핵심 요약 · 결정 요청** — 첫 내용 쪽에 결론과 근거 3개, 요청 사항(의사결정·보고에 우선 사용)

```html
<div class="summary"><div class="summary-key"><span>결론</span><strong>결론 문장<br>두 줄 이내</strong></div><div class="summary-why"><article><b>1</b><div><h3>근거 제목</h3><p>한 줄 설명</p></div></article><article><b>2</b>…</article><article><b>3</b>…</article></div></div>
<div class="ask"><b>요청 사항</b><span>결정·승인이 필요한 내용 한 줄</span></div>
```

**S. 대안 비교** — 대안 2~3개를 같은 기준으로. 권고안은 `rec` + `status done`. 기준 항목 수와 순서를 카드마다 같게

```html
<div class="options"><article class="option"><div class="option-top"><span>A안</span><span class="status planned">검토</span></div><h3>대안 이름</h3><p>한 줄 요약</p><dl><dt>비용</dt><dd>…</dd><dt>기간</dt><dd>…</dd><dt>효과</dt><dd>…</dd><dt>위험</dt><dd>…</dd></dl></article><article class="option rec"><div class="option-top"><span>B안</span><span class="status done">권고안</span></div>…</article></div>
<div class="band"><b>권고 근거</b><span>한 줄</span></div>
```

**T. 추진체계** — 주관 → 참여기관(2~4개, `--n`에 개수) → 수혜·수요 대상

```html
<div class="org"><div class="org-top"><span>총괄·주관</span><strong>기관명</strong></div><div class="org-line"></div><div class="org-row" style="--n:3"><div><strong>기관A</strong><span>역할 한 줄</span></div><div><strong>기관B</strong><span>역할</span></div><div><strong>기관C</strong><span>역할</span></div></div><div class="org-base"><b>수혜 대상</b>대상 설명</div></div>
```

**U. 단계 전환(퍼널)** — 신청 → 참여 → 수료 → 취업처럼 단계별 인원과 전환율. 막대 높이는 첫 단계 대비 비율. 전환율 아래에 분자·분모를 쓴다

```html
<div class="funnel"><div class="st"><span>신청</span><strong>420<small>명</small></strong><div class="bx"><i style="height:100%"></i></div></div><div class="rate"><b>67%</b>280 ÷ 420</div><div class="st"><span>참여</span><strong>280<small>명</small></strong><div class="bx"><i style="height:67%"></i></div></div><div class="rate"><b>93%</b>261 ÷ 280</div><div class="st"><span>수료</span><strong>261<small>명</small></strong><div class="bx"><i style="height:62%"></i></div></div><div class="rate"><b>—</b>집계 중</div><div class="st fc"><span>취업</span><strong>집계 중</strong><div class="bx"><i style="height:0"></i></div></div></div>
<div class="note">전환율 = 다음 단계 인원 ÷ 이전 단계 인원 × 100 · 기준일</div>
```

**V. 전후 비교(현행 → 개선)** — 바뀌는 점 3~5개를 같은 순서로 양쪽에

```html
<div class="ba"><div class="before"><span class="eyebrow">현행</span><ul><li>…</li><li>…</li><li>…</li></ul></div><b aria-hidden="true">→</b><div class="after"><span class="eyebrow">개선</span><ul><li>…</li><li>…</li><li>…</li></ul></div></div>
<div class="band"><b>적용 시점</b><span>…</span></div>
```

**W. 섹션 간지** (`sheet divider`, 틀 없이) — 10쪽 이상일 때 섹션 시작마다. 머리글·바닥글 없음

```html
<div class="sheet-wrap"><section class="sheet divider" id="p4" aria-label="4쪽: 02 대응 전략"><div class="div-num">02</div><div class="div-body"><span>섹션</span><h2>섹션 이름</h2><ul><li>이 섹션에서 다룰 것 1</li><li>2</li><li>3</li></ul></div></section></div>
```

**X. 핵심 메시지** — 큰 문장 하나(발표 전환점·결론 강조). 덱당 1~2쪽만. `main`에 그대로

```html
<div class="statement"><blockquote>핵심 문장 앞부분<br><em>강조할 뒷부분</em></blockquote><p>뒷받침 한 줄</p></div>
```

**보조 배치(어느 유형과도 조합)**

- `split` — 왼쪽 시각 요소(표·그래프) 6 : 오른쪽 설명 4. `split even`은 5:5, `split rev`는 4:6. 오른쪽 설명은 `side` 상자로.
- `main` 세로 배치 — 내용이 적어 아래가 비면 `<main class="v-center">`(가운데) 또는 `<main class="v-spread">`(위아래로 고르게 벌림)을 준다.

유형을 섞어 쓰되 같은 유형을 연속 세 쪽 이상 반복하지 않는다. 자료의 성격에 맞는 유형이 없으면 가장 가까운 유형의 구성 요소(`intro`, `band`, `note`, 표, 카드)를 조합한다. 새 클래스를 만들면 CSS 블록 끝에 추가하되 색은 기존 변수만 쓴다.

## 로고 (CI)

스킬 폴더의 `assets/`에 재단 CI(활용 가이드라인 2022. 05. 27. 교정판)의 로고를 배경이 투명한 PNG로 담았다.

| 파일 | 형태 | 쓰는 곳 |
|---|---|---|
| `logo-ko-h.png` | 가로형 한글 약식 ((재)포항테크노파크) | 기본. 표지 A1·A2와 감사 쪽의 오른쪽 아래 |
| `logo-koen-h.png` | 가로형 한영 약식 (영문 병기) | 대외·외부 공유본 표지 |
| `logo-en-h.png` | 가로형 영문 약식 | 영문 자료 |
| `logo-koen-v.png` | 세로형 한영 공식 | 감사 쪽 가운데 배치 등 세로 공간 |
| `logo-symbol.png` | 심볼(TP)만 | 기관명 글자가 바로 옆에 있는 좁은 자리에만 |
| `…-white.png` | 위 다섯 가지의 흰색 단색판 | 진한 배경(파란 면·사진 위). 띠형 표지 A3는 `logo-koen-v-white.png` |

파일 하나로 배포되도록 data URI로 내장한다. `SKILL_DIR`은 이 SKILL.md가 있는 폴더다.

```python
import base64,pathlib
SKILL_DIR=pathlib.Path('…/ptp-deck')        # 이 스킬 폴더
def logo(name): return 'data:image/png;base64,'+base64.b64encode((SKILL_DIR/'assets'/f'{name}.png').read_bytes()).decode()
# <img class="logo" src="{logo('logo-ko-h')}" alt="(재)포항테크노파크">
```

- **넣는 자리(두 곳만)**: 표지와 감사 쪽에 한 번씩, 같은 자리·같은 크기로 둔다. 표지 A1·A2는 `cover-bottom` 오른쪽(발표자 정보 맞은편, 서명 자리), 감사 쪽은 `thanks-bottom` 오른쪽. 띠형 표지 A3만 파란 면 맨 위에 흰색 로고(`<img class="logo cs-logo" src="…logo-koen-v-white…">`)를 둔다. 표지 위쪽에는 로고 대신 자료 종류와 일자를 쓰고, 목차·간지·내용 쪽에는 넣지 않는다(바닥글의 기관명 글자로 충분).
- **CI 지키기**: 가로·세로 비율을 유지한다(편집 모드에서 크기를 바꿔도 비율이 고정된다). 늘이기·회전·색 바꾸기·외곽선·그림자·일부 자르기를 하지 않는다. 밝은 바탕에는 원색 로고를, 진한 바탕(파란 면·어두운 사진)에는 로고 전체를 흰색으로 바꾼 `-white` 파일을 쓴다(원색 로고를 진한 바탕에 그대로 놓지 않는다). 흰 판(`cs-plate`) 위에 원색 로고를 놓아도 된다. 주변에 심볼 높이의 1/4 이상 여백을 둔다. 가로형은 높이 7mm, 심볼은 6mm보다 작게 쓰지 않는다.
- **로고를 쓰지 않는 경우**: 기관명을 다른 기관으로 바꾼 자료, 공동 주최에서 주관 기관 로고 규정이 따로 있는 자료. 다른 기관 로고는 사용자가 준 파일만 쓴다.
- **파일이 없을 때**: `assets/`가 없으면(SKILL.md만 설치된 경우) 사용자가 로고 파일을 주면 그것을 쓰고, 없으면 기관명 글자로 둔다.
- **CI 색상**: 파랑 `#0D4D96`(C100 M80 Y10), 주황 `#F5821E`(M60 Y100), 회색 `#656868`, 검정 `#181312`. 덱의 주색 `--blue`(#005BAC)는 화면 가독성 기준의 파랑으로 CI 파랑과 약간 다르다. CI 색으로 맞추려면 `:root`에서 `--blue:#0D4D96`으로 바꾸고, 주황은 장식(감사 쪽 띠 `thanks-rule` 등)에만 쓴다(상태 표현의 빨강을 주황으로 바꾸지 않는다).

## 글꼴

기본 폰트 목록은 `Paperlogy, "Noto Sans KR", "Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", Arial, sans-serif`다. 별도 준비 없이도 어느 PC에서나 보이도록 이 순서로 대체된다.

- **기본(필수):** `<head>`에 다음을 넣는다. 온라인이면 Noto Sans KR이 적용되고, 오프라인이면 Windows의 맑은 고딕(Mac은 Apple SD Gothic Neo)으로 표시된다.
  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;800&display=swap">
  ```
- **Paperlogy(선택):** 사용자가 `Paperlogy-Regular/Bold/ExtraBold` 폰트 파일(.ttf/.woff2)을 주거나 작업 폴더에 있을 때만 쓴다. base64로 인코딩해 `<style>` 맨 위에 `@font-face{font-family:Paperlogy;src:url(data:font/ttf;base64,…) format("truetype");font-weight:400}`(700, 800도 같은 형식)를 넣는다. 파일을 어디서 구할지 찾아다니지 않는다. 없으면 기본으로 만든다. 3개 합쳐 약 4MB가 늘어난다.
- Paperlogy 없이 만들었다면 답변에 "기본 글꼴(Noto Sans KR/맑은 고딕)로 만들었다"고 한 줄 쓴다. 자료에 없는 쪽 높이·줄바꾼이 달라질 수 있어 검수는 반드시 최종 글꼴으로 한다.

## 이미지 내장

사용자가 준 사진·배경 이미지만 쓴다. 파일 하나로 배포되도록 `data:` URI로 내장한다(큰 이미지는 장변 1600px, JPEG 품질 85 정도로 줄인다).

```python
import base64
b64=base64.b64encode(open('photo.jpg','rb').read()).decode()
src='data:image/jpeg;base64,'+b64   # <img src="..."> 또는 style="--art:url(...)"
```

배경 그림은 `<section class="sheet has-art" style="--art:url(data:image/png;base64,…)">`. 흰 바탕, 오른쪽 아래 모서리에만 그림이 있는 이미지가 맞다. 글자가 올라가는 카드는 이미 반투명 흰 면이다.

## 편집 모드와 발표

완성된 HTML 한 파일로 바로 발표하고, 그 자리에서 고칠 수 있다. 아래 CSS·JS·툴바를 그대로 넣으면 쪽 내용에 별도 작업은 필요 없다.

- **보기 화면(발표 전)**: 쪽 하나가 화면 높이에 맞게 축소되어 툴바 아래에 한 장씩 온전히 보이고, 휠·키보드로 넘기면 쪽 단위로 딱 맞춰 이동한다(스크롤 스냅). 편집 모드에서는 자유 스크롤이다.
- **상단 툴바**: 한 줄로 묶어 왼쪽부터 쪽 이동(‹ 쪽 번호 › · 목차), 도구(포인터·펜), 작업(편집·인쇄·PDF·단축키 ?), 맨 오른쪽 파란 ‘발표 시작’ 버튼(발표 중에는 빨간 ‘발표 종료’). 쪽 번호를 누르면 목차가 열리고, 버튼마다 마우스를 올리면 단축키가 보인다. 발표 중에는 편집·인쇄가 숨고 포인터가 나타나며, 편집 중에는 도구가 숨는다.
- **발표 보기**(`F` 또는 ‘발표 시작’): 브라우저 전체 화면으로 전환하고, 쪽을 화면에 맞는 최대 크기로 확대해 한 쪽씩 보여 준다(검은 배경). 창·전체 화면·앱 미리보기 창 크기가 바뀌면 자동으로 다시 맞춘다. 쪽 비율을 유지하므로 A4 가로를 16:9 화면에 띄우면 좌우에 검은 여백이 남는다(여백 없이 꽉 채우려면 크기를 16:9로 만든다). 상단 막대는 숨겨져 있다가 마우스를 화면 맨 위로 올리거나 `M`을 누를 때만 나타나고, 빨간 ‘발표 종료’ 버튼이 종료 버튼이다. 시작할 때 아래쪽에 짧은 안내 띠가 뜨고, `?`로 전체 단축키 창을 연다. 주소 끝 `#p3`으로 특정 쪽을 바로 연다. 전체 화면 권한이 막힌 환경(임베딩 미리보기 등)에서는 창 안에서 최대 크기로 보인다.
- **화면 전환 효과**: 발표 중 쪽이 바뀔 때 0.3초 동안 서서히 나타난다(기본 `fade`). `<div id="deck" data-transition="fade">`의 값을 `slide`(진행 방향으로 살짝 밀며 나타남, 여러 쪽을 건너뛰면 서서히)나 `none`(효과 없음)으로 바꿀 수 있다. 사용자가 원하면 그 값으로 만든다. 운영체제의 '움직임 줄이기' 설정이 켜져 있으면 효과 없이 바로 바뀐다. 보기 화면·편집·인쇄에는 적용되지 않는다.
- **쪽 넘김 규칙**: 키보드는 언제나 같다. ←/→·PageUp/Down, 발표 중 Space·↑·↓, 숫자+Enter(쪽 번호), Home/End, `[`·`]`(섹션), `G`(목차 창에서 쪽·섹션 선택). 마우스는 켜 둔 도구에 따라 다르다. 도구 없음이면 클릭(왼쪽 1/3 이전, 나머지 다음, 한 번에 한 쪽)·휠(마우스 휠 한 칸에 한 쪽, 터치패드는 한 번 쓸기에 한 쪽)·드래그(왼쪽·위로 다음, 오른쪽·아래로 이전, 60px 이상)로 넘기고, 레이저 포인터는 더블클릭으로만 넘기고(왼쪽 1/3 이전, 나머지 다음) 누른 채 움직이면 붉은 궤적이 잠깐 남았다 사라지며, 펜은 마우스가 필기 전용이라 넘기지 않는다(키보드 또는 펜 막대의 ◀ ▶).
- **도구는 한 번에 하나**: `L` 레이저 포인터(발표 중), `P` 펜(보기·발표). 다른 도구를 켜면 앞의 도구는 꺼진다. 펜을 켜면 화면 아래에 슬림한 펜 막대(색 빨강 R·파랑 U·형광 Y | 획 취소 Z·우클릭, 이 쪽 지움 X, 전체 지움 Shift+X | ◀ 쪽 ▶ | 펜 끄기(필기 유지, Esc) · 지우고 끄기(모든 쪽 필기 삭제 후 끄기, Shift+P))가 뜬다. 막대는 자동으로 숨는다(켤 때·펜 단축키를 쓸 때·마우스를 화면 아래쪽에 가져갈 때 나타나고, 그리는 동안과 2초 뒤에는 숨음). 단축키는 각 버튼에 마우스를 올리면 보인다. 필기는 쪽별로 남고 인쇄·PDF에는 나오지 않는다. 편집 모드에서는 도구가 꺼진다.
- **발표용 리모컨·화면 끄기**: 리모컨의 이전·다음(PageUp/Down), 발표 시작(F5 → 새로고침 대신 발표 시작), 화면 끄기(B·`.` 검은 화면, W·`,` 흰 화면, 아무 키나 클릭으로 복귀)를 그대로 쓴다. 이 때문에 펜 파랑은 `U`다.
- **클릭 넘김 설정**: 가리키다 무심코 클릭해 넘어가는 것을 막으려면 발표 중 상단 ‘클릭 넘김’ 또는 `K`로 끈다(키보드·리모컨·휠·드래그는 그대로). 설정은 그 브라우저에 기억된다.
- **저장 안 한 편집 경고**: 편집 후 저장하지 않았으면 편집 바의 ‘저장’ 버튼에 노란 점이 붙고, 창을 닫거나 새로고침하면 브라우저가 경고한다.
- **Esc는 한 단계씩**: 검은·흰 화면 복귀 → 열린 창(도움말·목차) 닫기 → 쪽 번호 입력 취소 → 도구 끄기 → 발표 종료. 전체 화면에서 브라우저가 Esc를 먼저 가로채지 않도록 Esc 키를 잠그고(Chrome·Edge, 이때 브라우저 안내는 ‘Esc를 길게 누르면 전체 화면 종료’로 바뀐다), 잠금이 안 되는 브라우저에서 도구를 켠 채 Esc로 전체 화면이 풀리면 발표는 유지한 채 도구만 끄고 다음 클릭에서 전체 화면으로 돌아간다.
- **편집 모드**: 툴바의 ‘편집’를 켠다. 글을 클릭하면 선택(파란 테두리), 드래그하면 이동, 더블클릭(또는 Enter)하면 글 수정, Esc로 수정 종료·선택 해제·편집 종료 순으로 빠진다.
- **크기 조절**: 모서리 점을 끌면 글 상자 폭이 바뀌면서 글자 크기가 비례해 바뀐다(안쪽 글자 포함). 좌우 점은 폭만 바꿔 줄바꿈이 달라진다. `A−`·`A＋`는 선택한 글자를 10%씩 줄이고 키운다. 사진(`img`)도 같은 방식으로 이동·크기 조절된다.
- **방향키**는 선택한 글을 1px(Shift는 10px) 옮기고, `텍스트 추가`로 새 글 상자를 만든다. Ctrl+Z 또는 `되돌리기`로 이동·크기를 되돌린다(글자 입력은 브라우저 기본 되돌리기).
- **편집 도구**는 화면 아래에 뜨는 별도 편집 바에 모인다(편집 모드에서만 보이고 인쇄에는 나오지 않는다): 텍스트 추가, 굵게·기울임·밑줄, 글자색, 좌·중·우 정렬, A−/A＋, 상위 선택, 복제, 삭제, 되돌리기, 편집본 저장. 서식은 글 입력 중 일부를 드래그해 선택하면 그 부분에만, 아니면 선택한 글 상자 전체에 적용된다.
- **개체 복사·삭제**: 글·사진·카드 모두 선택해 다룬다. `상위 선택`을 누르면 글 → 카드 → 카드 묶음 순으로 한 단계씩 큰 개체가 선택된다. `복제`(Ctrl+D)는 원본 바로 뒤에 사본을 넣고, Ctrl+C 후 Ctrl+V는 현재 쪽에 붙여 넣는다(다른 쪽에도 가능). 사본은 16px 어긋난 위치에 생기는데 카드처럼 격자·플렉스 안의 개체는 배치가 재정렬되고, 필요하면 드래그로 옥긴다. Delete는 선택한 개체를 지우고, Ctrl+Z로 복원한다(복제·붙여넣기·삭제도 되돌릴 수 있다).
- **편집본 저장**(Ctrl+S): 편집 표시를 지운 깨끗한 HTML을 `제목-편집본.html`로 내려받는다. 인쇄·PDF에는 편집 표시가 나오지 않는다.
- 편집은 화면에서만 바뀌고 원본 파일은 그대로다. 저장하지 않고 닫으면 수정이 사라진다는 점을 사용자에게 알린다.

## 파일 구성

`<head>`에 `meta charset="utf-8"`, `meta viewport`, `<title>`(자료 제목), 글꼴(위 "글꼴"), `<style>`(아래 CSS)를 넣고 `<body>`는 다음 순서로 쓴다.

```html
<nav class="toolbar" aria-label="자료 탐색"><div class="grp"><button id="prev" class="ic" title="이전 쪽 (←)" aria-label="이전 쪽"><svg viewBox="0 0 16 16"><path d="M10 3.5L5.5 8l4.5 4.5"/></svg></button><button id="count" class="counter" title="목차 열기 (G)">1 / N</button><button id="next" class="ic" title="다음 쪽 (→)" aria-label="다음 쪽"><svg viewBox="0 0 16 16"><path d="M6 3.5L10.5 8 6 12.5"/></svg></button><button id="toc" title="목차 · 쪽 이동 (G)"><svg viewBox="0 0 16 16"><path d="M5.5 4h8M5.5 8h8M5.5 12h8M2.5 4h.01M2.5 8h.01M2.5 12h.01"/></svg><span>목차</span></button></div><i class="sep sep-t"></i><div class="grp tools"><button id="lz" class="laser" title="레이저 포인터 (L)"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="2.2"/><circle cx="8" cy="8" r="5.5"/></svg><span>포인터</span></button><button id="ck" class="laser on" title="클릭으로 쪽 넘기기 켜기·끄기 (K)"><svg viewBox="0 0 16 16"><rect x="4.5" y="2" width="7" height="12" rx="3.5"/><path d="M8 2v4"/></svg><span>클릭 넘김</span></button><button id="pn" class="pen-btn" title="펜 (P)"><svg viewBox="0 0 16 16"><path d="M10.5 2.8l2.7 2.7-7.7 7.7H2.8v-2.7zM9 4.3l2.7 2.7"/></svg><span>펜</span></button></div><i class="sep"></i><div class="grp"><button id="edit" title="편집 모드 (E)"><svg viewBox="0 0 16 16"><path d="M2.5 13.5h11M4 10.5l7-7 2 2-7 7H4z"/></svg><span>편집</span></button><button id="print" class="print" title="인쇄 · PDF 저장 (Ctrl+P)"><svg viewBox="0 0 16 16"><path d="M4.5 6V2.5h7V6M4.5 11.5h-2v-5h11v5h-2M4.5 9.5h7v4h-7z"/></svg><span>인쇄·PDF</span></button><button id="kh" class="ic" title="단축키 도움말 (?)">?</button></div><button id="mode" class="primary" title="발표 시작 (F)"><svg class="i-play" viewBox="0 0 16 16"><path d="M5 3.2l7.5 4.8L5 12.8z"/></svg><svg class="i-stop" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8"/></svg><span>발표 시작</span></button></nav>
<div id="deck" data-transition="fade">…쪽(sheet-wrap)들…</div>
<nav class="edit-bar" id="editbar" aria-label="편집 도구"><button id="addtext" class="txt" title="텍스트 상자 추가"><svg viewBox="0 0 16 16"><path d="M8 3v10M3.5 6V4h9v2M8 13H6M8 13h2"/></svg>텍스트</button><i class="sep"></i><div class="grp"><button id="bold" title="굵게"><b>B</b></button><button id="ital" title="기울임"><i>I</i></button><button id="und" title="밑줄"><u>U</u></button><input type="color" id="color" value="#005BAC" title="글자색" aria-label="글자색"></div><i class="sep"></i><div class="grp"><button id="aL" title="왼쪽 정렬"><svg viewBox="0 0 16 16"><path d="M2 3h12M2 6.5h8M2 10h12M2 13.5h8"/></svg></button><button id="aC" title="가운데 정렬"><svg viewBox="0 0 16 16"><path d="M2 3h12M4 6.5h8M2 10h12M4 13.5h8"/></svg></button><button id="aR" title="오른쪽 정렬"><svg viewBox="0 0 16 16"><path d="M2 3h12M6 6.5h8M2 10h12M6 13.5h8"/></svg></button></div><i class="sep"></i><div class="grp"><button id="fdown" title="글자 작게">A−</button><button id="fup" title="글자 크게">A＋</button></div><i class="sep"></i><div class="grp"><button id="up" title="상위 개체 선택"><svg viewBox="0 0 16 16"><path d="M8 13V3M4 7l4-4 4 4"/></svg></button><button id="dup" title="복제 (Ctrl+D)"><svg viewBox="0 0 16 16"><rect x="5" y="5" width="9" height="9" rx="1.5"/><path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2h-6A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5"/></svg></button><button id="del" class="danger" title="삭제 (Delete)"><svg viewBox="0 0 16 16"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5M6.8 7v3.5M9.200 7v3.5"/></svg></button></div><i class="sep"></i><button id="undo" title="되돌리기 (Ctrl+Z)"><svg viewBox="0 0 16 16"><path d="M3.5 6.5h6a3.5 3.5 0 0 1 0 7H6M3.5 6.5L6 4M3.5 6.5L6 9"/></svg></button><button id="help" title="단축키 안내">?</button><button id="save" class="primary" title="편집본 저장 (Ctrl+S)">저장</button><div class="help" id="helpbox">클릭 선택 · 드래그 이동 · 모서리 크기(글자 비례) · 더블클릭 또는 Enter 글 수정 · Ctrl+C / Ctrl+V 복사·붙여넣기 · Ctrl+D 복제 · Delete 삭제 · Ctrl+Z 되돌리기 · 방향키 미세이동(Shift 10px) · Ctrl+S 저장 · Esc 해제</div></nav>
<div class="hint-toast" id="toast">← → 이동 &nbsp;·&nbsp; <kbd>G</kbd> 목차 &nbsp;·&nbsp; <kbd>L</kbd> 포인터 &nbsp;·&nbsp; <kbd>P</kbd> 펜 &nbsp;·&nbsp; <kbd>?</kbd> 전체 단축키 &nbsp;·&nbsp; <kbd>Esc</kbd> 종료</div>
<script>…아래 JS…</script>
```

쪽 크기는 `--sw`×`--sh`(기본 A4 가로 297×210mm)로 고정이고 화면 폭에 맞춰 JS가 축소한다. 인쇄 설정은 선택한 크기(기본 A4 가로), 여백 없음, 배경 그래픽 켜기다. 모든 자원이 파일 안에 들어 있으므로(글꼴 링크 제외) 그대로 메일·공유폴더로 배포할 수 있다.

### CSS (그대로 `<style>`에 넣는다)

```css
:root{--sw:297mm;--sh:210mm;--blue:#005BAC;--slate:#56718F;--red:#D63B32;--red-ink:#b32a23;--ink:#111827;--muted:#405974;--line:#d6e0ea;--line-card:#c9d9e9;--pale:#edf4fb;--sky:#eaf2fa;--sky-soft:#edf5fe}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:#e8edf3;color:var(--ink);font-family:Paperlogy,"Noto Sans KR","Malgun Gothic","맑은 고딕","Apple SD Gothic Neo",Arial,sans-serif;font-size:15pt;font-weight:400;line-height:1.5;word-break:keep-all}
button,a{font:inherit}a{color:inherit;text-decoration:none}button{cursor:pointer}
.toolbar{position:sticky;top:0;z-index:9;display:flex;flex-wrap:wrap;gap:4px;align-items:center;justify-content:center;padding:8px 12px;background:#fff;border-bottom:1px solid var(--line);font-size:12.5pt}
.toolbar .grp{display:flex;align-items:center;gap:2px}.toolbar .sep{width:1px;height:22px;margin:0 6px;background:var(--line)}
.toolbar button{display:inline-flex;align-items:center;justify-content:center;gap:6px;height:36px;padding:0 12px;border:0;border-radius:9px;background:transparent;color:#2b3a4f;white-space:nowrap}.toolbar button:hover{background:#eef3f9}.toolbar button.ic{width:36px;padding:0;font-weight:700}
.toolbar svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.toolbar .i-play path{fill:currentColor}.toolbar .counter{min-width:76px;font-weight:700;color:var(--blue);background:var(--pale)}
.toolbar .primary{margin-left:8px;padding:0 18px;background:var(--blue);color:#fff;font-weight:700}.toolbar .primary:hover{background:#00498a}.toolbar .i-stop{display:none}body.present .toolbar .i-play{display:none}body.present .toolbar .i-stop{display:inline}
.toolbar button.on{background:#e6effa;color:var(--blue);box-shadow:inset 0 0 0 1.5px var(--blue)}body.editing .toolbar .tools,body.editing .toolbar .sep-t{display:none}
#deck{padding:14px 16px 45px}.sheet-wrap{width:var(--sw);height:var(--sh);margin:0 auto 16px;position:relative;scroll-snap-align:start;scroll-margin-top:calc(var(--tbh,56px) + 14px)}html{scroll-snap-type:y mandatory}body.present,body.editing{scroll-snap-type:none}html:has(body.editing){scroll-snap-type:none}
.sheet{position:absolute;top:0;left:0;width:var(--sw);height:var(--sh);padding:12mm 14mm 10mm;background:#fff;display:flex;flex-direction:column;transform-origin:top left;box-shadow:0 4px 20px #15233518;overflow:hidden;border-top:2mm solid var(--blue);isolation:isolate}
.sheet.has-art::before{content:"";position:absolute;inset:0;background:var(--art) center/cover;opacity:.38;z-index:0;pointer-events:none}
.sheet>*{position:relative;z-index:1}
header,footer{display:flex;justify-content:space-between;gap:18px;font-size:13pt;color:var(--muted);line-height:1.45}
header{align-items:center;font-weight:700;border-bottom:2px solid var(--blue);padding-bottom:8px;min-height:46px}
footer{margin-top:4mm;border-top:1px solid var(--line);padding-top:3mm}footer span:first-child{flex:1}footer span:last-child{white-space:nowrap;align-self:flex-end}
.section-lockup{display:flex;align-items:center;gap:13px}
.section-number{font-size:19pt;line-height:1;padding:6px 10px;background:var(--blue);color:#fff;border-radius:4px}
.section-name{font-size:17pt;font-weight:800;color:var(--blue)}
.page-context{font-size:13pt;font-weight:700;color:var(--muted);background:rgba(255,255,255,.82);padding:5px 10px;border-radius:4px}
h2{margin:4.5mm 0 6mm;font-size:27pt;line-height:1.23;font-weight:800;letter-spacing:-.7px}
h3{margin:0 0 12px;font-size:18pt;line-height:1.35;letter-spacing:-.25px;font-weight:800}
p{margin:0 0 12px}p:last-child{margin-bottom:0}main{flex:1;min-height:0}b,strong{font-weight:700}
.eyebrow{display:block;color:var(--blue);font-size:13pt;font-weight:700;margin-bottom:9px}
.status{display:inline-block;border:1.5px solid currentColor;padding:4px 10px;font-size:13pt;font-weight:700;white-space:nowrap;line-height:1.4;border-radius:4px}
.status.done{background:var(--blue);color:#fff;border-color:var(--blue)}
.status.pending,.status.planned{background:#f6f8fb;color:var(--muted)}.status.pending{border-style:dashed}.status.planned{border-style:dotted}
.state{display:inline-block;min-width:74px;text-align:center;white-space:nowrap;font-size:13pt;font-weight:700;padding:5px 9px;line-height:1.2;border-radius:4px}
.state.complete{color:#fff;background:var(--blue);border:2px solid var(--blue)}
.state.live{color:var(--red-ink);background:#fff5f3;border:2px dashed var(--red)}
.intro,.learning,.next{padding:20px 24px;background:var(--pale)}
.intro{border-left:7px solid var(--blue);margin-bottom:22px}.intro h3{font-size:21pt;margin-bottom:10px}
.learning{border-left:6px solid var(--blue);margin-top:24px}.learning b{font-size:18pt;color:var(--blue)}.learning p{margin-top:8px;font-size:14.5pt}
.next{padding:14px 18px;margin-top:19px}.next b{font-size:15pt;color:var(--blue)}.next p{font-size:14pt;margin-top:5px}
.note{margin-top:16px;padding:12px 16px;border-left:3px solid var(--blue);background:#f2f5f9;color:#334155;font-size:13pt;line-height:1.5}
.banner{display:flex;align-items:center;gap:22px;padding:17px 22px;margin-bottom:17px;background:var(--sky);border-left:7px solid var(--blue);border-radius:5px}
.banner>div{flex:1}.banner>div>span{display:block;margin-bottom:4px;font-size:13pt;font-weight:700;color:var(--muted)}
.banner strong{display:block;font-size:22pt;line-height:1.25;color:var(--blue)}.banner p{font-size:14pt;line-height:1.5}
.band{display:flex;align-items:center;gap:20px;padding:16px 22px;margin-top:20px;background:var(--blue);color:#fff;border-radius:5px;font-size:14pt}.band b{font-size:17pt;white-space:nowrap}
.three-cols,.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.two-cols{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.fact{padding-bottom:18px;border-bottom:2px solid var(--line)}.fact>span{display:block;margin-bottom:10px;font-size:13pt;color:var(--slate)}.fact>strong{display:block;font-size:18pt}.fact>p{margin-top:7px;font-size:13pt}
.partners{display:flex;gap:25px;align-items:flex-start;margin-top:25px;padding:22px 0;border-bottom:1px solid var(--line)}.partners div{font-size:17pt;line-height:1.75;font-weight:700}.partners i{font-style:normal;color:var(--blue);padding:0 10px}
.bottom-line{margin-top:18px;font-size:14pt;color:var(--muted)}
.plain{border-top:3px solid var(--blue);padding-top:17px;background:rgba(255,255,255,.87)}.plain p{font-size:14.5pt;line-height:1.75;margin-bottom:18px}
.improve-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px 22px}
.improve{padding:15px 22px 18px;border:1.5px solid var(--line-card);border-left:5px solid var(--blue);border-radius:6px;background:rgba(255,255,255,.94)}
.improve.future{border:2px dashed var(--slate);background:#f4f8fc}
.improve-top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:8px}.improve-top>span:first-child{font-size:22pt;font-weight:800;color:var(--blue);line-height:1.2}
.improve h3{font-size:19pt}.improve p{font-size:15pt;line-height:1.55}
.metrics{display:grid;grid-template-columns:1fr 1.12fr 1fr;gap:20px;margin-bottom:22px}
.metric{padding:18px 22px;border:1.5px solid var(--line);border-radius:7px;background:rgba(255,255,255,.93)}
.metric>span{font-size:13pt;font-weight:700;color:var(--muted)}.metric strong{display:block;margin:8px 0;font-size:45pt;font-weight:800;line-height:1.2;letter-spacing:-1px;color:var(--blue)}
.metric small{padding-left:5px;font-size:15pt;font-weight:400;color:var(--ink)}.metric p{font-size:13.5pt}
.metric.primary{background:var(--blue);border:2px solid var(--blue);color:#fff}.metric.primary>span,.metric.primary strong,.metric.primary small{color:#fff}
.metric.forecast{background:#fff9f7;border:2px solid var(--red)}.metric.forecast>span,.metric.forecast strong{color:var(--red-ink)}
.outcomes{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.outcome{padding:20px 23px;border:2px solid var(--blue);border-radius:7px;background:rgba(255,255,255,.95)}.outcome.projected{border-style:dashed;background:var(--sky-soft)}
.outcome-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.outcome-top h3{font-size:23pt;margin:0}
.outcome-num{display:flex;align-items:baseline;gap:10px;margin:14px 0 7px}.outcome-num strong{font-size:55pt;font-weight:800;line-height:1;letter-spacing:-2px;color:var(--blue)}.outcome-num span{font-size:20pt;font-weight:700;color:var(--muted)}
.outcome-label{font-size:13.5pt;color:var(--muted)}
.outcome-result{display:grid;grid-template-columns:.85fr 1.15fr;gap:15px;margin-top:18px;padding-top:16px;border-top:1px solid var(--line-card)}.outcome-result span{display:block;margin-bottom:7px;font-size:13pt;color:var(--muted)}.outcome-result b{display:block;font-size:22pt;line-height:1.3;white-space:nowrap;color:var(--blue)}
.total-band{display:flex;gap:22px;align-items:center;margin-top:22px;padding:17px 23px;background:var(--blue);color:#fff;border-radius:5px}.total-band>span,.total-band>p{font-size:16pt;margin:0}.total-band>b{font-size:28pt;line-height:1.15}.total-band strong{font-weight:800}
.target-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.target{padding:25px;border:1.5px solid var(--line);border-radius:7px;background:rgba(255,255,255,.87)}.target.focus{border:2px solid var(--blue)}
.target h3{margin:16px 0 0;font-size:24pt;color:var(--slate)}.target h3 strong{font-size:50pt;letter-spacing:-2px;color:var(--blue)}
.bar{display:flex;width:100%;height:20px;margin:20px 0 22px;border:1px solid var(--line)}.bar span{display:block;background:var(--blue)}
.bar i{display:block;background:repeating-linear-gradient(135deg,#fff,#fff 6px,#dbe5ef 6px,#dbe5ef 8px)}.target p{font-size:15pt;line-height:1.65}
table{width:100%;border-collapse:collapse;font-size:14pt;line-height:1.5;background:rgba(255,255,255,.93)}
th{background:var(--blue);color:#fff;text-align:left;padding:11px 15px;font-weight:700}td{padding:11px 15px;border-bottom:1px solid #cbd7e4}
th:not(:first-child),td:not(:first-child){text-align:center;white-space:nowrap}table .left{text-align:left;white-space:normal}
tr.tint{background:#fff7f4}tr.total{background:#eaf2fa;font-weight:700}.row-note{display:block;margin-top:3px;font-size:13pt;color:var(--muted)}
.milestones{display:flex;align-items:center;gap:15px;margin-top:22px}.milestones div{flex:1;border-top:3px solid var(--blue);padding-top:12px}.milestones b{display:block;font-size:16pt;color:var(--blue)}.milestones span{display:block;margin-top:4px;font-size:13pt}.milestones i{font-size:22pt;font-style:normal;color:var(--blue)}
.timeline article{display:grid;grid-template-columns:120px 1fr 90px;gap:20px;padding:16px 0;border-bottom:1px solid var(--line);align-items:start}.timeline article:first-child{padding-top:0}
.timeline time{font-size:15pt;color:var(--blue);font-weight:700}.timeline h3{font-size:17pt;margin-bottom:4px}.timeline p{font-size:14.5pt;line-height:1.6}.timeline .status{text-align:center}
.day-flow{display:grid;grid-template-columns:1fr .8fr 1fr;gap:7px}.day-flow div{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:17px 22px;background:var(--blue);color:#fff}.day-flow .lunch{background:var(--slate)}.day-flow time{font-size:16pt;font-weight:700;white-space:nowrap}.day-flow b{font-size:14pt}
.callout{display:flex;justify-content:space-between;gap:15px;padding:18px 0 22px;margin-bottom:20px;border-bottom:1px solid var(--line)}.callout b{color:var(--blue);font-size:17pt}.callout span{align-self:center;font-size:13pt}
.tour{display:grid;grid-template-columns:1.1fr 1fr;gap:28px}.tour figure{margin:0}.tour img{display:block;width:100%;height:305px;object-fit:cover}.tour figcaption{margin-top:10px;font-size:13pt;color:var(--muted)}
.tour-list{background:rgba(255,255,255,.8)}.tour-list article{display:flex;gap:15px;padding-bottom:18px}.tour-list article:last-child{padding-bottom:0}.tour-list>article>span{font-size:20pt;font-weight:800;color:var(--blue)}.tour-list h3{font-size:18pt;margin-bottom:4px}.tour-list p{font-size:14.5pt}
.board{padding:23px;border:2px solid var(--line);border-radius:7px;background:rgba(255,255,255,.87)}.board.solid{border-color:var(--blue)}.board.dashed{border:2px dashed var(--slate)}
.experiment-top{display:flex;justify-content:space-between;gap:20px;margin-bottom:14px;align-items:flex-start}.experiment-top h3{margin:0;font-size:19pt}
.experiment-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}.experiment-grid>div{border-left:3px solid var(--blue);padding-left:15px}.experiment-grid b{display:block;margin-bottom:7px;font-size:15pt;color:var(--blue)}.experiment-grid p{font-size:14pt;line-height:1.5}
.experiment-meta{display:flex;justify-content:space-between;gap:20px;margin-top:15px;padding-top:14px;border-top:1px solid var(--line)}.experiment-meta p{margin:0;font-size:13pt}.experiment-meta b{display:block;color:var(--slate)}
.curriculum-simple{display:grid;grid-template-columns:1.1fr 90px 1fr;gap:18px;align-items:stretch;margin-top:15px}
.demand-inputs{display:grid;gap:22px}.demand-inputs article{padding:24px;background:rgba(255,255,255,.94);border:1.5px solid var(--line-card);border-left:6px solid var(--blue);border-radius:6px}.demand-inputs h3{font-size:23pt;margin-bottom:12px}.demand-inputs p{font-size:16pt;line-height:1.65}
.demand-arrow{display:flex;flex-direction:column;justify-content:center;align-items:center;gap:10px;color:var(--blue)}.demand-arrow span{font-size:14pt;font-weight:700;white-space:nowrap}.demand-arrow b{font-size:38pt;line-height:1}
.curriculum-result{display:flex;flex-direction:column;justify-content:center;padding:28px;border:2px dashed var(--blue);border-radius:7px;background:var(--sky-soft)}
.curriculum-result .status{align-self:flex-start;margin-bottom:20px;color:var(--blue);border-color:var(--blue)}.curriculum-result h3{margin:0 0 22px;font-size:28pt;line-height:1.3;color:var(--blue)}.curriculum-result ul{margin:0;padding-left:23px;font-size:16pt;line-height:1.85}.curriculum-result li::marker{color:var(--blue)}
.feedback{display:flex;gap:22px;align-items:center;margin-top:27px;padding:20px 24px;border-radius:5px;background:var(--blue);color:#fff;font-size:16pt}.feedback b{white-space:nowrap;font-size:17pt}
.year-caption{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;font-size:14pt;color:var(--muted)}.year-caption b{color:var(--blue);font-size:16pt}
.years{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.year{padding:19px 23px 17px;border:2px solid var(--blue);border-radius:7px;background:rgba(255,255,255,.96)}.year.current{border-style:dashed;background:var(--sky-soft)}
.year-top{display:flex;align-items:baseline;justify-content:space-between;gap:12px}.year h3{margin:0;font-size:25pt}.year-top>span{font-size:14pt;color:var(--muted)}
.year-count{display:flex;align-items:baseline;gap:10px;margin:12px 0 8px;color:var(--blue)}.year-count strong{font-size:57pt;line-height:1;font-weight:800;letter-spacing:-2px}.year-count span{font-size:21pt}.year>p{margin:0;font-size:13pt;color:var(--muted)}
.target-band{display:flex;justify-content:space-between;align-items:center;margin-top:18px;padding:14px 25px;background:var(--blue);color:#fff;border-radius:6px}.target-band>div>b{font-size:20pt}.target-band p{margin:5px 0 0;font-size:13.5pt}.target-band>strong{font-size:42pt;line-height:1.1;font-weight:800;white-space:nowrap}.target-band>strong>span{font-size:25pt;margin-left:5px}
.list-box{display:flex;gap:26px;align-items:center;margin-top:16px;padding:14px 22px;background:rgba(255,255,255,.93);border:1px solid var(--line-card);border-radius:5px}.list-box>b{font-size:15pt;color:var(--blue);white-space:nowrap}.list-box p{margin:0;font-size:15pt;line-height:1.6;font-weight:700}
.closing-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.action{position:relative;padding:8px 14px 0;border-top:5px solid var(--blue);border-radius:5px;background:rgba(255,255,255,.87)}
.action-number{position:absolute;right:14px;top:10px;font-size:26pt;font-weight:800;line-height:1.15;color:#8da5bd}
.action h3{margin:12px 0 14px;font-size:20pt}.action p{margin-bottom:13px;font-size:14pt;line-height:1.5}.action p b{display:block;font-size:13.5pt;color:var(--blue)}.action-foot{padding-top:10px;border-top:1px solid var(--line);font-size:13pt;line-height:1.5;color:var(--muted)}
.cover{padding:14mm 16mm 12mm;border-top:none;background:linear-gradient(130deg,#fff 0%,#fff 72%,#f2f7fc 72%)}
.cover-top{display:flex;justify-content:space-between;color:var(--blue);font-size:16pt;font-weight:700}.cover-top span{color:var(--slate);font-size:14pt}
.cover-label{margin:17mm 0 6mm;font-size:17pt;font-weight:700;color:var(--slate)}
.cover h1{margin:0;font-size:42pt;line-height:1.3;letter-spacing:-1.3px;font-weight:800}.cover h1 em{font-style:normal;color:var(--blue)}
.cover-sub{margin-top:6mm;font-size:24pt;line-height:1.45;font-weight:700}
.cover-route{display:flex;gap:23px;margin-top:auto;padding:25px 0;border-top:2px solid var(--blue);border-bottom:1px solid var(--line);align-items:center;background:rgba(255,255,255,.85)}
.cover-route div{flex:1}.cover-route b{display:block;margin-bottom:3px;font-size:13pt;color:var(--blue)}.cover-route strong{display:block;font-size:21pt}.cover-route span{display:block;margin-top:7px;font-size:13pt;color:var(--muted)}.cover-route i{font-size:25pt;font-style:normal;color:var(--blue)}
.cover-bottom{display:flex;justify-content:space-between;margin-top:8mm;font-size:13pt;color:var(--muted)}
.thanks{border-top:0;padding:14mm 16mm 13mm}.thanks.has-art::before{opacity:.65}
.thanks-top,.thanks-bottom{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:14pt}.thanks-top>span:first-child{font-weight:700;color:var(--blue)}
.thanks-main{flex:1;display:flex;flex-direction:column;justify-content:center;padding-bottom:18mm}
.thanks-rule{width:95px;height:6px;background:var(--blue);border-right:19px solid var(--red)}
.thanks-main h2{margin:19px 0 20px;font-size:64pt;line-height:1.2;letter-spacing:-2px;color:var(--blue)}.thanks-main p{margin:0;font-size:23pt;font-weight:700;color:var(--ink)}
.thanks-bottom{border-top:1px solid var(--line);padding-top:7mm}
body.present #deck{padding-top:14px}body.present .sheet-wrap{display:none}body.present .sheet-wrap.active{display:block}
@page{size:A4 landscape;margin:0}/* 크기를 바꾸면 위 --sw·--sh와 함께 예: size:338mm 190mm */
@media print{html{scroll-behavior:auto}body{background:#fff}#deck{padding:0}.toolbar{display:none!important}
.sheet-wrap,body.present .sheet-wrap{display:block!important;width:var(--sw)!important;height:var(--sh)!important;margin:0!important;overflow:hidden;break-after:page;page-break-after:always}
.sheet-wrap:last-child{break-after:auto;page-break-after:auto}.sheet{position:relative;transform:none!important;box-shadow:none;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.toolbar{flex-wrap:wrap}.toolbar .edit-only,.toolbar .edit-hint{display:none}body.editing .toolbar .edit-only{display:inline-block}body.editing .toolbar .edit-hint{display:inline}
.toolbar .edit-hint{font-size:11pt;color:var(--slate)}.toolbar .edit-on,body.present .toolbar #mode{background:var(--red);color:#fff}.toolbar .edit-on:hover,body.present .toolbar #mode:hover{background:#b8302a}
.sheet>.edit-box{position:absolute;z-index:60;border:1.5px solid #1a73e8;pointer-events:none;box-sizing:border-box}.edit-box.typing{border-style:dashed}
.edit-box i{position:absolute;width:11px;height:11px;background:#fff;border:1.5px solid #1a73e8;border-radius:2px;pointer-events:auto}
.edit-box i[data-h=nw]{left:-6px;top:-6px;cursor:nwse-resize}.edit-box i[data-h=ne]{right:-6px;top:-6px;cursor:nesw-resize}.edit-box i[data-h=sw]{left:-6px;bottom:-6px;cursor:nesw-resize}.edit-box i[data-h=se]{right:-6px;bottom:-6px;cursor:nwse-resize}.edit-box i[data-h=w]{left:-6px;top:calc(50% - 6px);cursor:ew-resize}.edit-box i[data-h=e]{right:-6px;top:calc(50% - 6px);cursor:ew-resize}
body.editing .sheet{cursor:default}body.editing .sheet [contenteditable=true]{outline:2px solid #1a73e8;cursor:text;-webkit-user-select:text;user-select:text}
.sheet>.tbox{position:absolute;left:60mm;top:60mm;z-index:5;min-width:40px;padding:2px 4px;font-size:20pt;font-weight:700;line-height:1.4;white-space:pre-wrap;color:var(--ink)}
@media print{.edit-box{display:none!important}}
.edit-bar{display:none;position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:30;max-width:calc(100vw - 24px);align-items:center;gap:4px;padding:6px;background:rgba(255,255,255,.97);border:1px solid #e3e9f0;border-radius:14px;box-shadow:0 10px 30px #0f1f3a29,0 1px 3px #0f1f3a1f;font-size:12pt}
body.editing .edit-bar{display:flex}.edit-bar .grp{display:flex;align-items:center;gap:2px}.edit-bar .sep{flex:none;width:1px;height:20px;margin:0 4px;background:#e3e9f0}
.edit-bar button{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:34px;padding:0 9px;border:0;border-radius:9px;background:transparent;color:#2b3a4f;font-size:12pt;line-height:1;white-space:nowrap}
.edit-bar button:hover{background:#eef3f9}.edit-bar button:active{background:#dde8f4}.edit-bar svg{width:17px;height:17px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.edit-bar .txt{gap:5px;font-weight:700;color:var(--blue)}.edit-bar .danger:hover{background:#fdecea;color:var(--red-ink)}
.edit-bar .primary{margin-left:2px;padding:0 16px;background:var(--blue);color:#fff;font-weight:700}.edit-bar .primary:hover{background:#00498a}
.edit-bar input[type=color]{-webkit-appearance:none;appearance:none;width:26px;height:26px;margin:4px;padding:0;border:2px solid #fff;border-radius:50%;box-shadow:0 0 0 1px #cfd8e3;background:none;cursor:pointer}
.edit-bar input[type=color]::-webkit-color-swatch-wrapper{padding:0}.edit-bar input[type=color]::-webkit-color-swatch{border:0;border-radius:50%}
.edit-bar .help{display:none;position:absolute;left:0;right:0;bottom:calc(100% + 8px);padding:12px 16px;background:#1b2a3f;color:#e8eef6;border-radius:12px;font-size:10.5pt;line-height:1.7;box-shadow:0 10px 30px #0f1f3a40}.edit-bar.help-on .help{display:block}
.hint-toast{display:none;position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:40;padding:10px 20px;border-radius:999px;background:rgba(17,24,39,.88);color:#fff;font-size:13pt;white-space:nowrap;opacity:0;transition:opacity .3s;pointer-events:none}.hint-toast kbd{font:inherit;font-weight:700;padding:1px 8px;border:1px solid #ffffff80;border-radius:5px}body.present .hint-toast{display:block}.hint-toast.on{opacity:1}
body.present{background:#000;overflow:hidden}body.present #deck{display:flex;align-items:center;justify-content:center;height:100vh;padding:0}body.present .sheet-wrap{margin:0}
body.present .toolbar{position:fixed;top:0;left:0;right:0;opacity:0;transform:translateY(-100%);pointer-events:none;transition:opacity .15s,transform .15s;box-shadow:0 6px 24px #0f1f3a40}body.present .toolbar.show{opacity:1;transform:none;pointer-events:auto}body.present .edit-bar,body.present .toolbar #edit,body.present .toolbar .print{display:none}
#count{cursor:pointer}.toolbar .laser{display:none}body.present .toolbar .laser{display:inline-flex}
#outline{display:none;position:fixed;top:0;right:0;bottom:0;width:min(380px,92vw);z-index:50;background:#fff;box-shadow:-10px 0 30px #0f1f3a40;overflow:auto;padding:0 0 24px;font-size:13pt;color:var(--ink)}#outline.open{display:block}
#outline .ttl{position:sticky;top:0;padding:16px 20px 10px;background:#fff;border-bottom:1px solid var(--line);font-size:15pt;font-weight:800}
#outline h4{margin:0;padding:12px 20px 4px;font-size:12pt;color:var(--blue);cursor:pointer}#outline h4:hover{background:var(--pale)}
#outline a{display:flex;gap:10px;padding:7px 20px 7px 28px;line-height:1.4;cursor:pointer}#outline a:hover{background:var(--pale)}#outline a b{min-width:2em;color:var(--slate)}#outline a.cur{background:var(--pale);color:var(--blue);font-weight:700}
.ink{position:absolute;left:0;top:0;width:100%;height:100%;z-index:5;pointer-events:none;touch-action:none;mix-blend-mode:multiply}body.pen .ink{pointer-events:auto;cursor:crosshair}
body.editing .toolbar #pn{display:none}

#keys{display:none;position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:55;width:min(1000px,94vw);max-height:92vh;overflow:auto;padding:16px 22px 18px;background:#fff;border-radius:14px;box-shadow:0 20px 60px #0f1f3a66;font-size:11.5pt;line-height:1.35;color:var(--ink)}#keys.open{display:block}#keys .kh-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)}#keys h4{margin:0;font-size:14pt}#keys .kh-top span{font-size:10.5pt;color:var(--slate)}#keys .cols{column-count:3;column-gap:26px}#keys section{break-inside:avoid;margin:0 0 12px}#keys .sub{margin:0 0 5px;font-size:11pt;font-weight:800;color:var(--blue)}#keys dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 10px;margin:0}#keys dt{white-space:nowrap;font-weight:700}#keys dd{margin:0;color:var(--muted)}#keys kbd{display:inline-block;min-width:22px;text-align:center;font:inherit;font-size:10.5pt;font-weight:700;padding:0 6px;border:1px solid var(--line);border-bottom-width:2px;border-radius:5px;background:#f6f8fb}@media(max-width:820px){#keys .cols{column-count:2}}@media(max-width:520px){#keys .cols{column-count:1}}
#penbar{position:fixed;left:50%;bottom:16px;z-index:45;display:none;align-items:center;gap:2px;padding:4px 6px;background:rgba(17,24,39,.92);color:#e8eef6;border-radius:999px;box-shadow:0 8px 24px #0005;font-size:11.5pt;transform:translateX(-50%);transition:opacity .2s,transform .2s}body.pen #penbar{display:flex}#blank{display:none;position:fixed;inset:0;z-index:90;cursor:none}#blank.on{display:block}.edit-bar .primary.dirty::after{content:"";width:7px;height:7px;margin-left:7px;border-radius:50%;background:#ffd166}#trail{position:fixed;inset:0;z-index:59;pointer-events:none}#penbar.hide{opacity:0;transform:translate(-50%,14px);pointer-events:none}
#penbar button{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;padding:0;border:0;border-radius:50%;background:transparent;color:#e8eef6;cursor:pointer}#penbar button:hover{background:#ffffff22}#penbar svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
#penbar i{display:block;width:16px;height:16px;border-radius:50%}#penbar i.hl{width:18px;height:10px;border-radius:3px;background:#ffd600}#penbar button.on{box-shadow:inset 0 0 0 2px #fff}#penbar .sep{width:1px;height:18px;margin:0 4px;background:#ffffff33}#penbar b{min-width:46px;text-align:center;font-weight:700}#penbar .off{color:#ff8a80}#penbar .wipe{width:auto;margin-left:2px;padding:0 12px;border-radius:999px;background:var(--red);color:#fff;font:inherit;font-size:11pt;font-weight:700;white-space:nowrap}#penbar .wipe:hover{background:#b8302a}#penbar .off:hover{background:#d63b3240}body.pen .hint-toast{bottom:68px}

#laser{display:none;position:fixed;width:26px;height:26px;margin:-13px 0 0 -13px;border-radius:50%;background:radial-gradient(circle,#ff2a1f 0 32%,#ff2a1f80 34% 58%,#ff2a1f00 72%);pointer-events:none;z-index:60}
body.present{-webkit-user-select:none;user-select:none}body.present.laser #deck,body.present.laser #deck *{cursor:none!important}body.present.laser #laser{display:block}
@media print{.edit-bar,.hint-toast,#outline,#laser,.ink,#keys,#penbar,#trail,#blank{display:none!important}body.present{background:#fff!important;overflow:visible}body.present #deck{display:block!important;height:auto!important}}
/* ===== 레이아웃 보강: 세로 배치 · P~X 유형 ===== */
main.v-center{display:flex;flex-direction:column;justify-content:center}main.v-spread{display:flex;flex-direction:column;justify-content:space-between}
.split{display:grid;grid-template-columns:1.5fr 1fr;gap:28px;align-items:start}.split.even{grid-template-columns:1fr 1fr}.split.rev{grid-template-columns:1fr 1.5fr}
.side{padding:20px 22px;background:var(--pale);border-left:6px solid var(--blue)}.side h3{font-size:17pt;margin-bottom:8px}.side p,.side li{font-size:14pt;line-height:1.6}.side ul{margin:0;padding-left:20px}
.trend svg{display:block;width:100%;height:auto;overflow:visible}.trend .gl{stroke:var(--line);stroke-width:1.5}.trend .ln{fill:none;stroke:var(--blue);stroke-width:5;stroke-linejoin:round;stroke-linecap:round}.trend .ln.fc{stroke:var(--red);stroke-dasharray:12 9}
.trend .pt{fill:#fff;stroke:var(--blue);stroke-width:4}.trend .pt.fc{stroke:var(--red)}
.trend-x{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;margin-top:8px;text-align:center;font-size:13pt;color:var(--muted)}.trend-x b{display:block;font-size:18pt;color:var(--blue)}.trend-x .fc b{color:var(--red-ink)}
.colchart{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:22px;align-items:end;height:280px;padding:0 12px;border-bottom:2px solid var(--ink)}
.colchart>div{display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}.colchart b{margin-bottom:6px;font-size:18pt;color:var(--blue)}.colchart i{display:block;width:60%;background:var(--blue);border-radius:4px 4px 0 0}
.colchart .mute b{color:var(--slate)}.colchart .mute i{background:var(--line-card)}.colchart .fc b{color:var(--red-ink)}.colchart .fc i{background:repeating-linear-gradient(135deg,#fff,#fff 6px,#fff5f3 6px,#fff5f3 12px);border:2px dashed var(--red);border-bottom:0}
.col-x{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:22px;padding:8px 12px 0;text-align:center;font-size:13.5pt;color:var(--muted)}
.summary{display:grid;grid-template-columns:1fr 1.3fr;gap:26px;align-items:stretch}
.summary-key{display:flex;flex-direction:column;justify-content:center;padding:28px;background:var(--blue);color:#fff;border-radius:7px}.summary-key span{font-size:13pt;font-weight:700}.summary-key strong{display:block;margin-top:12px;font-size:25pt;line-height:1.38;font-weight:800}
.summary-why{display:grid;gap:14px}.summary-why article{display:flex;gap:16px;align-items:flex-start;padding:14px 18px;border:1.5px solid var(--line-card);border-left:5px solid var(--blue);border-radius:6px;background:rgba(255,255,255,.94)}
.summary-why article>b{font-size:22pt;line-height:1.2;color:var(--blue);font-weight:800}.summary-why h3{margin-bottom:4px;font-size:17pt}.summary-why p{font-size:14pt;line-height:1.5}
.ask{display:flex;gap:20px;align-items:center;margin-top:20px;padding:14px 22px;border:2px solid var(--blue);border-radius:5px;font-size:15pt}.ask b{color:var(--blue);font-size:17pt;white-space:nowrap}
.options{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:20px}
.option{display:flex;flex-direction:column;padding:18px 22px;border:1.5px solid var(--line-card);border-radius:7px;background:rgba(255,255,255,.94)}.option.rec{border:2.5px solid var(--blue);background:var(--sky-soft)}
.option-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}.option-top>span:first-child{font-size:14pt;font-weight:800;color:var(--slate)}.option.rec .option-top>span:first-child{color:var(--blue)}
.option h3{margin-bottom:10px;font-size:19pt}.option dl{display:grid;grid-template-columns:auto 1fr;gap:8px 14px;margin:auto 0 0;padding-top:12px;border-top:1px solid var(--line-card);font-size:14pt}.option dt{font-weight:700;color:var(--muted)}.option dd{margin:0}
.org{display:flex;flex-direction:column;align-items:center}
.org-top{min-width:40%;padding:14px 24px;text-align:center;background:var(--blue);color:#fff;border-radius:6px}.org-top span{display:block;font-size:13pt}.org-top strong{font-size:20pt}
.org-line{width:2px;height:22px;background:var(--blue)}
.org-row{position:relative;display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:18px;width:100%;padding-top:22px}
.org-row::before{content:"";position:absolute;top:0;left:calc(50% / var(--n,3));right:calc(50% / var(--n,3));height:2px;background:var(--blue)}
.org-row>div{position:relative;padding:14px 16px;border:1.5px solid var(--line-card);border-top:4px solid var(--blue);border-radius:6px;background:rgba(255,255,255,.95);text-align:center}
.org-row>div::before{content:"";position:absolute;top:-26px;left:50%;width:2px;height:22px;background:var(--blue)}
.org-row strong{display:block;font-size:17pt}.org-row span{display:block;margin-top:4px;font-size:13pt;line-height:1.45;color:var(--muted)}
.org-base{width:100%;margin-top:20px;padding:13px 22px;text-align:center;background:var(--pale);border:1.5px dashed var(--slate);border-radius:6px;font-size:15pt}.org-base b{margin-right:12px;color:var(--blue)}
.funnel{display:flex;align-items:stretch}
.funnel .st{flex:1;display:flex;flex-direction:column;align-items:center;text-align:center}.funnel .st>span{font-size:14pt;font-weight:700;color:var(--muted)}
.funnel .st strong{margin:6px 0 10px;font-size:34pt;line-height:1.1;font-weight:800;color:var(--blue)}.funnel .st strong small{margin-left:3px;font-size:15pt;font-weight:400;color:var(--ink)}
.funnel .bx{display:flex;align-items:flex-end;width:78%;height:150px}.funnel .bx i{display:block;width:100%;background:var(--blue);border-radius:4px 4px 0 0}.funnel .fc strong{color:var(--red-ink)}.funnel .fc .bx i{background:#fff5f3;border:2px dashed var(--red);border-bottom:0}
.funnel .rate{flex:0 0 100px;display:flex;flex-direction:column;justify-content:center;align-items:center;font-size:12pt;line-height:1.4;color:var(--slate);text-align:center}.funnel .rate b{font-size:18pt;color:var(--blue)}.funnel .rate::before{content:"→";font-size:22pt;color:var(--blue)}
.ba{display:grid;grid-template-columns:1fr 70px 1fr;gap:14px;align-items:stretch}
.ba>div{padding:22px 24px;border-radius:7px}.ba .before{background:#f2f5f9;border:1.5px solid var(--line)}.ba .after{background:var(--sky-soft);border:2px solid var(--blue)}.ba .before .eyebrow{color:var(--slate)}
.ba ul{margin:0;padding-left:22px;font-size:15.5pt;line-height:1.8}.ba .after li::marker{color:var(--blue)}.ba>b{display:flex;align-items:center;justify-content:center;font-size:36pt;color:var(--blue)}
.divider{flex-direction:row;align-items:center;padding:0;border-top:0;background:#fff}
.div-num{display:flex;align-items:center;justify-content:center;align-self:stretch;width:34%;background:var(--blue);color:#fff;font-size:110pt;font-weight:800;line-height:1}
.div-body{flex:1;padding:0 18mm}.div-body>span{font-size:15pt;font-weight:700;color:var(--slate)}.divider h2{margin:8px 0 20px;font-size:40pt;color:var(--blue)}.div-body ul{margin:0;padding-left:22px;font-size:17pt;line-height:1.85}
.statement{display:flex;flex-direction:column;justify-content:center;height:100%;padding:0 5%}
.statement blockquote{margin:0;padding-left:28px;border-left:8px solid var(--blue);font-size:31pt;line-height:1.45;font-weight:800;letter-spacing:-.6px}.statement blockquote em{font-style:normal;color:var(--blue)}.statement p{margin:22px 0 0 36px;font-size:16pt;color:var(--muted)}
/* 표지 보강 · 목차 · 밀도 배지 */
.cover-tag{display:inline-block;margin-left:12px;padding:2px 10px;border:1.5px solid currentColor;border-radius:4px;font-size:12pt;font-weight:700;line-height:1.4;vertical-align:3px}
.cover-bottom{align-items:flex-end;gap:20px}.cover-bottom .who{text-align:left;line-height:1.5}.cover-bottom .who b{display:block;font-size:16pt;color:var(--ink)}
.cover.simple{background:#fff;border-top:2mm solid var(--blue)}.cover.simple .cover-label{margin-top:auto}.cover.simple h1{font-size:48pt}.cover.simple .cover-sub{margin-bottom:auto}.cover.simple .cover-bottom{padding-top:6mm;border-top:2px solid var(--blue)}
.cover.stripe{flex-direction:row;padding:0;background:#fff}
.cover-side{display:flex;flex-direction:column;align-items:flex-start;width:34%;padding:14mm 12mm 12mm;background:var(--blue);color:#fff}.cs-org{font-size:18pt;font-weight:800}.cs-date{margin:6px 0 14px;font-size:14pt}
.cs-who{margin-top:auto;font-size:13.5pt;line-height:1.6}.cs-who b{display:block;font-size:18pt}
.cover-main{flex:1;display:flex;flex-direction:column;justify-content:center;padding:14mm 16mm}.cover.stripe .cover-label{margin:0 0 6mm}
.agenda-page{padding:14mm 18mm 10mm}
.agenda-top{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:8px;border-bottom:3px solid var(--blue)}.agenda-top span:first-child{font-size:30pt;font-weight:800;color:var(--blue)}.agenda-top span:last-child{font-size:13pt;font-weight:700;color:var(--muted)}
.agenda{display:flex;flex-direction:column;justify-content:center;padding:4mm 0}
.agenda a{display:grid;grid-template-columns:90px 1fr auto;align-items:center;gap:20px;padding:16px 8px;border-bottom:1px solid var(--line);cursor:pointer}.agenda a:hover{background:var(--pale)}
.agenda a>b{font-size:30pt;line-height:1;font-weight:800;color:var(--blue)}.agenda strong{display:block;font-size:22pt;font-weight:800}.agenda span{display:block;margin-top:3px;font-size:14pt;color:var(--muted)}.agenda em{font-style:normal;font-size:14pt;font-weight:700;color:var(--slate);white-space:nowrap}
.dens{display:none;position:absolute;top:8px;right:8px;z-index:20;padding:3px 11px;border:0;border-radius:999px;background:#1b2a3f;color:#fff;font-size:11pt;font-weight:700;cursor:pointer;box-shadow:0 2px 8px #0003}.dens.warn{background:var(--red)}body.editing .dens{display:block}
@media print{.dens{display:none!important}}
.logo{display:block;flex:none;align-self:flex-start;width:auto;max-width:100%;object-fit:contain}.cover-top{align-items:center}.cover-top .logo{height:12mm}.cover-bottom .logo,.thanks-bottom .logo{height:12mm}.cover-bottom .logo{align-self:flex-end}
body:has(.agenda-page) .cover-route{display:none}.cover:not(.simple):not(.stripe):not(:has(.cover-route:not([hidden]))) .cover-bottom,body:has(.agenda-page) .cover:not(.simple):not(.stripe) .cover-bottom{margin-top:auto;padding-top:6mm;border-top:2px solid var(--blue)}
.cover:not(.simple):not(.stripe):not(:has(.cover-route:not([hidden]))) .cover-label,body:has(.agenda-page) .cover:not(.simple):not(.stripe) .cover-label{margin-top:auto}
.cs-logo{height:30mm;margin-bottom:10mm}.cs-plate{align-self:stretch;margin-bottom:10mm;padding:7mm 6mm;background:#fff;border-radius:6px}.cs-plate .logo{height:26mm;margin:0 auto}
/* 화면 전환 효과 */
body.present .sheet-wrap.tp-next{animation:tpNext .34s cubic-bezier(.2,.7,.2,1) both}body.present .sheet-wrap.tp-prev{animation:tpPrev .34s cubic-bezier(.2,.7,.2,1) both}body.present .sheet-wrap.tp-fade{animation:tpFade .3s ease-out both}
@keyframes tpNext{from{opacity:0;transform:translateX(3%)}to{opacity:1;transform:none}}@keyframes tpPrev{from{opacity:0;transform:translateX(-3%)}to{opacity:1;transform:none}}@keyframes tpFade{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){body.present .sheet-wrap.tp-next,body.present .sheet-wrap.tp-prev,body.present .sheet-wrap.tp-fade{animation:none}}
```

### JS (그대로 `<script>`에 넣는다)

```js
const wraps=[...document.querySelectorAll('.sheet-wrap')],$=id=>document.getElementById(id);let current=0,presenting=false,editing=false,typing=null,sel=null,drag=null,box=null;const undoStack=[];let dirty=false;const markDirty=v=>{dirty=v;const s=document.getElementById('save');if(s){s.classList.toggle('dirty',v);s.title=v?'저장하지 않은 변경 있음 · 편집본 저장 (Ctrl+S)':'편집본 저장 (Ctrl+S)'}};undoStack.push=function(...a){markDirty(true);return Array.prototype.push.apply(this,a)};
function fit(){const s0=wraps[0].firstElementChild,W=s0.offsetWidth,H=s0.offsetHeight,tb=document.querySelector('.toolbar'),tbh=tb?tb.offsetHeight:0,vp=document.getElementById('vp'),VW=vp&&vp.clientWidth||innerWidth,VH=vp&&vp.clientHeight||innerHeight,sc=presenting?Math.min(VW/W,VH/H):Math.min(1,Math.max(300,innerWidth-32)/W,Math.max(240,innerHeight-tbh-30)/H);document.documentElement.style.setProperty('--tbh',tbh+'px');for(const w of wraps){w.style.width=(W*sc)+'px';w.style.height=(H*sc)+'px';w.firstElementChild.style.transform='scale('+sc+')'}$('count').textContent=(current+1)+' / '+wraps.length;{const q=document.getElementById('pbcount');if(q)q.textContent=(current+1)+' / '+wraps.length}placeBox();redraw()}
function show(i){const prev=current;current=Math.max(0,Math.min(wraps.length-1,i));wraps.forEach((w,j)=>w.classList.toggle('active',j===current));if(presenting&&prev!==current)animIn(wraps[current],Math.abs(current-prev)>1?0:current-prev);if(!presenting){navLock=Date.now()+900;wraps[current].scrollIntoView({behavior:'smooth',block:'start'})}try{history.replaceState(null,'','#p'+(current+1))}catch(_){}fit()}
$('prev').onclick=()=>show(current-1);$('next').onclick=()=>show(current+1);
$('print').onclick=()=>window.print();addEventListener('resize',fit);addEventListener('beforeprint',()=>{endTyping();sel=null;placeBox()});
let navLock=0;const obs=new IntersectionObserver(es=>{if(presenting||Date.now()<navLock)return;for(const e of es)if(e.isIntersecting){current=wraps.indexOf(e.target);$('count').textContent=(current+1)+' / '+wraps.length}},{threshold:.5});wraps.forEach(w=>obs.observe(w));
/* ===== 편집 모드: 글 수정 · 이동 · 크기(글자 비례) ===== */
const scaleOf=s=>s.getBoundingClientRect().width/s.offsetWidth||1;
const hasText=n=>[...n.childNodes].some(c=>c.nodeType===3&&c.textContent.trim());
function pick(t,sheet){let el=t.nodeType===1?t:t.parentElement;while(el&&el!==sheet){if(el.tagName==='IMG'||el.classList.contains('tbox')||hasText(el)){while(el.parentElement&&el.parentElement!==sheet&&getComputedStyle(el).display==='inline')el=el.parentElement;return el}el=el.parentElement}return null}
function mkBox(){box=document.createElement('div');box.className='edit-box';for(const h of['nw','ne','sw','se','w','e']){const i=document.createElement('i');i.dataset.h=h;box.appendChild(i)}}
function placeBox(){if(!box)mkBox();if(!sel||!editing||!sel.isConnected){box.remove();return}const s=sel.closest('.sheet'),sr=s.getBoundingClientRect(),r=sel.getBoundingClientRect(),k=sr.width/s.offsetWidth;if(box.parentElement!==s)s.appendChild(box);box.style.left=((r.left-sr.left)/k-s.clientLeft)+'px';box.style.top=((r.top-sr.top)/k-s.clientTop)+'px';box.style.width=(r.width/k)+'px';box.style.height=(r.height/k)+'px'}
const setT=(el,x,y)=>{el.dataset.tx=x;el.dataset.ty=y;el.style.transform='translate('+x+'px,'+y+'px)'};
const snap=el=>({el,tx:el.dataset.tx,ty:el.dataset.ty,st:[el,...el.querySelectorAll('*')].map(n=>[n,n.getAttribute('style')])});
function doUndo(){const u=undoStack.pop();if(!u)return;if(u.fn){u.fn();sel=null;placeBox();return}for(const[n,s]of u.st)s===null?n.removeAttribute('style'):n.setAttribute('style',s);u.tx===undefined?delete u.el.dataset.tx:u.el.dataset.tx=u.tx;u.ty===undefined?delete u.el.dataset.ty:u.el.dataset.ty=u.ty;placeBox()}
function scaleFonts(el,f){undoStack.push(snap(el));for(const n of[el,...el.querySelectorAll('*')])n.style.fontSize=(parseFloat(getComputedStyle(n).fontSize)*f)+'px';placeBox()}
function select(el){sel=el;placeBox()}
function startTyping(el,e){if(el.tagName==='IMG')return;endTyping();typing=el;el.contentEditable='true';box&&box.classList.add('typing');el.focus();if(e&&document.caretRangeFromPoint){const r=document.caretRangeFromPoint(e.clientX,e.clientY);if(r){const s=getSelection();s.removeAllRanges();s.addRange(r)}}}
function endTyping(){if(!typing)return;const t=typing;typing=null;t.removeAttribute('contenteditable');t.normalize();box&&box.classList.remove('typing');if(!t.textContent.trim()&&t.classList.contains('tbox')){t.remove();sel=null}placeBox()}
function setEditing(on){if(on)setTool('none',true);if(on&&presenting)setPresent(false);editing=on;document.body.classList.toggle('editing',on);$('edit').querySelector('span').textContent=on?'편집 종료':'편집';$('edit').classList.toggle('edit-on',on);if(!on){endTyping();sel=null}else try{document.execCommand('defaultParagraphSeparator',false,'br')}catch(_){}placeBox();if(on)densUpdate()}
$('edit').onclick=()=>setEditing(!editing);
$('addtext').onclick=()=>{const s=wraps[current].firstElementChild,d=document.createElement('div');d.className='tbox';d.textContent='새 텍스트';s.appendChild(d);select(d);startTyping(d);getSelection().selectAllChildren(d)};
$('fdown').onclick=()=>sel&&scaleFonts(sel,.9);$('fup').onclick=()=>sel&&scaleFonts(sel,1.1);$('undo').onclick=doUndo;
function saveHtml(){endTyping();markDirty(false);sel=null;placeBox();const c=document.documentElement.cloneNode(true);c.querySelectorAll('.edit-box,.dens,.ink,#trail,#laser,#penbar,#keys,#outline,#blank,#vp').forEach(n=>n.remove());c.querySelector('body').className='';c.querySelectorAll('[contenteditable]').forEach(n=>n.removeAttribute('contenteditable'));c.querySelectorAll('.sheet').forEach(s=>s.style.removeProperty('transform'));c.querySelectorAll('.sheet-wrap').forEach(w=>{w.style.removeProperty('width');w.style.removeProperty('height');w.classList.remove('active')});const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['<!doctype html>\n'+c.outerHTML],{type:'text/html'}));a.download=(document.title||'deck')+'-편집본.html';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),3000)}
$('save').onclick=saveHtml;
document.addEventListener('pointerdown',e=>{if(!editing)return;const h=e.target.closest&&e.target.closest('.edit-box i');if(h&&sel){e.preventDefault();const s=sel.closest('.sheet'),k=scaleOf(s),r=sel.getBoundingClientRect();if(getComputedStyle(sel.parentElement).display.includes('flex'))sel.style.flex='none';drag={t:'rs',h:h.dataset.h,x:e.clientX,y:e.clientY,k,w0:r.width/k,h0:r.height/k,tx:+sel.dataset.tx||0,ty:+sel.dataset.ty||0,fonts:[sel,...sel.querySelectorAll('*')].map(n=>[n,parseFloat(getComputedStyle(n).fontSize)]),sn:snap(sel)};return}
const sheet=e.target.closest&&e.target.closest('.sheet');if(!sheet){if(!e.target.closest('.toolbar,.edit-bar')){endTyping();sel=null;placeBox()}return}
if(typing&&typing.contains(e.target))return;endTyping();const el=pick(e.target,sheet);if(!el){sel=null;placeBox();return}e.preventDefault();select(el);drag={t:'mv',x:e.clientX,y:e.clientY,k:scaleOf(sheet),tx:+el.dataset.tx||0,ty:+el.dataset.ty||0,sn:snap(el)}},true);
document.addEventListener('pointermove',e=>{if(!drag||!sel)return;const dx=(e.clientX-drag.x)/drag.k,dy=(e.clientY-drag.y)/drag.k;if(!drag.pushed&&(Math.abs(dx)>1||Math.abs(dy)>1)){undoStack.push(drag.sn);drag.pushed=1}
if(drag.t==='mv')setT(sel,drag.tx+dx,drag.ty+dy);else{const L=drag.h.includes('w'),nw=Math.max(24,drag.w0+(L?-dx:dx));sel.style.width=nw+'px';if(L)setT(sel,drag.tx+(drag.w0-nw),drag.ty);if(sel.tagName==='IMG')sel.style.height=(drag.h0*nw/drag.w0)+'px';else if(drag.h.length===2){const f=nw/drag.w0;for(const[n,fs]of drag.fonts)n.style.fontSize=(fs*f)+'px'}}placeBox()});
document.addEventListener('pointerup',()=>{drag=null});
document.addEventListener('dblclick',e=>{if(!editing)return;const sheet=e.target.closest&&e.target.closest('.sheet');if(!sheet)return;const el=pick(e.target,sheet);if(el){select(el);startTyping(el,e)}});
document.addEventListener('focusout',e=>{if(typing&&e.target===typing)endTyping()});document.addEventListener('input',()=>placeBox());
addEventListener('keydown',e=>{if(!editing)return;const k=e.key,mod=e.ctrlKey||e.metaKey,stop=()=>{e.preventDefault();e.stopImmediatePropagation()};
if(mod&&k.toLowerCase()==='s'){stop();saveHtml();return}if(k==='Escape'){stop();if(typing)endTyping();else if(sel){sel=null;placeBox()}else setEditing(false);return}if(typing)return;
if(mod&&k.toLowerCase()==='z'){stop();doUndo();return}if(mod&&k.toLowerCase()==='v'&&clip){stop();pasteClip();return}if(!sel)return;if(mod&&k.toLowerCase()==='c'){stop();copySel();return}if(mod&&k.toLowerCase()==='d'){stop();dupSel();return}const st=e.shiftKey?10:1,M={ArrowLeft:[-st,0],ArrowRight:[st,0],ArrowUp:[0,-st],ArrowDown:[0,st]};
if(M[k]){stop();undoStack.push(snap(sel));setT(sel,(+sel.dataset.tx||0)+M[k][0],(+sel.dataset.ty||0)+M[k][1]);placeBox();return}
if(k==='Delete'||k==='Backspace'){stop();delSel();return}if(k==='Enter'){stop();startTyping(sel)}},true);
/* --- 기본 편집 · 개체 복사/삭제 --- */
let clip=null,clipSrc=null;
const cloneOf=el=>{const c=el.cloneNode(true);c.removeAttribute('contenteditable');c.querySelectorAll('[contenteditable]').forEach(n=>n.removeAttribute('contenteditable'));return c};
function delSel(){if(!sel||sel===typing)return;const el=sel,p=el.parentNode,nx=el.nextSibling;p.removeChild(el);undoStack.push({fn:()=>p.insertBefore(el,nx)});sel=null;placeBox()}
function copySel(){if(!sel)return;clip=cloneOf(sel);clipSrc=sel}
function dupSel(){if(!sel)return;const c=cloneOf(sel);setT(c,(+sel.dataset.tx||0)+16,(+sel.dataset.ty||0)+16);sel.after(c);undoStack.push({fn:()=>c.remove()});select(c)}
function pasteClip(){if(!clip)return;const s=wraps[current].firstElementChild,c=cloneOf(clip);setT(c,(+clip.dataset.tx||0)+16,(+clip.dataset.ty||0)+16);clip.dataset.tx=(+clip.dataset.tx||0)+16;clip.dataset.ty=(+clip.dataset.ty||0)+16;if(clipSrc&&clipSrc.isConnected&&s.contains(clipSrc))clipSrc.after(c);else(s.querySelector('main')||s).appendChild(c);undoStack.push({fn:()=>c.remove()});select(c)}
function upSel(){const p=sel&&sel.parentElement;if(p&&!p.classList.contains('sheet')&&p.tagName!=='MAIN')select(p)}
const range=()=>{const s=getSelection();return typing&&s.rangeCount&&!s.isCollapsed};
function styleAll(prop,val){if(!sel)return;undoStack.push(snap(sel));for(const n of[sel,...sel.querySelectorAll('*')])n.style[prop]=val;placeBox()}
function toggle(cmd,prop,on,off){if(range()){document.execCommand(cmd);return}if(!sel)return;styleAll(prop,(prop==='fontWeight'?parseInt(getComputedStyle(sel).fontWeight)>=700:prop==='fontStyle'?getComputedStyle(sel).fontStyle==='italic':getComputedStyle(sel).textDecorationLine.includes('underline'))?off:on)}
$('bold').onclick=()=>toggle('bold','fontWeight','800','400');$('ital').onclick=()=>toggle('italic','fontStyle','italic','normal');$('und').onclick=()=>toggle('underline','textDecoration','underline','none');
$('color').oninput=e=>styleAll('color',e.target.value);
$('aL').onclick=()=>sel&&(undoStack.push(snap(sel)),sel.style.textAlign='left');$('aC').onclick=()=>sel&&(undoStack.push(snap(sel)),sel.style.textAlign='center');$('aR').onclick=()=>sel&&(undoStack.push(snap(sel)),sel.style.textAlign='right');
$('up').onclick=upSel;$('dup').onclick=dupSel;$('del').onclick=delSel;
$('editbar').addEventListener('mousedown',e=>{if(e.target.tagName!=='INPUT')e.preventDefault()});
$('help').onclick=()=>$('editbar').classList.toggle('help-on');
/* ===== 보기·발표 조작: 도구 · 쪽 넘김 · Esc를 한곳에서 관리 =====
 도구는 한 번에 하나: 없음 / 레이저 포인터(L, 발표 중) / 펜(P, 보기·발표).
 쪽 넘김 — 키보드는 언제나 같다(← → PageUp/Down, 발표 중 Space·↑·↓, 숫자+Enter, Home/End, [ ], G 목차).
   마우스는 도구에 따라: 도구 없음 = 클릭(왼쪽 1/3 이전)·휠·드래그 / 포인터 = 더블클릭만(누른 채 움직이면 잔상 궤적) / 펜 = 필기 전용(펜 막대 ◀ ▶ 사용).
 Esc — 도움말·목차 닫기 → 도구 끄기 → 발표 종료, 한 번에 한 단계. 전체 화면에서는 Esc 키 잠금으로 브라우저가 먼저 가로채지 않게 한다. */
const BC=document.body.classList,inUI=t=>t.closest&&t.closest('.toolbar,#outline,#keys,#penbar,.edit-bar,#blank');
let tool='none',toolOff=0,refs=false;
document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('.toolbar button');if(b)b.blur()});
const hint0=$('toast').innerHTML;let nb='',nt,ft;
function flash(m,ms){const k=$('toast');k.textContent=m;k.classList.add('on');clearTimeout(ft);ft=setTimeout(()=>{k.classList.remove('on');setTimeout(()=>k.innerHTML=hint0,350)},ms||1400)}
let barT;const bar=document.querySelector('.toolbar'),barShow=ms=>{bar.classList.add('show');clearTimeout(barT);barT=setTimeout(()=>bar.classList.remove('show'),ms)};
addEventListener('mousemove',e=>{if(!presenting)return;if(e.clientY<48)barShow(1500);else if(!bar.matches(':hover'))clearTimeout(barT),barT=setTimeout(()=>bar.classList.remove('show'),250)});
/* 발표 시작·종료 */
function lockEsc(){try{navigator.keyboard&&navigator.keyboard.lock&&navigator.keyboard.lock(['Escape']).catch(()=>{})}catch(_){}}
function goFull(){try{const r=document.documentElement.requestFullscreen();r&&r.then(lockEsc).catch(()=>{})}catch(_){}}
function setPresent(on){if(on&&editing)setEditing(false);if(on===presenting)return;presenting=on;BC.toggle('present',on);$('mode').querySelector('span').textContent=on?'발표 종료':'발표 시작';$('mode').title=on?'발표 종료 (Esc)':'발표 시작 (F)';bar.classList.remove('show');refs=false;
if(!on){setTool('none',true);toc(false);ky.classList.remove('open');try{navigator.keyboard&&navigator.keyboard.unlock()}catch(_){}if(document.fullscreenElement)try{document.exitFullscreen()}catch(_){}}else if(!document.fullscreenElement)goFull();
{const k=$('toast');k.innerHTML=hint0;k.classList.toggle('on',on);clearTimeout(ft);if(on)ft=setTimeout(()=>k.classList.remove('on'),4000)}show(current)}
$('mode').onclick=()=>setPresent(!presenting);
/* 화면 전환 효과(발표 중): #deck의 data-transition = fade(기본, 서서히 나타남) · slide(진행 방향으로 살짝 밀며 나타남) · none. 여러 쪽을 건너뛰면 fade. 움직임 줄이기 설정이면 즉시 전환 */
function animIn(w,d){const m=$('deck').dataset.transition||'fade';if(m==='none')return;const c=m==='fade'||!d?'tp-fade':d>0?'tp-next':'tp-prev';w.classList.remove('tp-next','tp-prev','tp-fade');void w.offsetWidth;w.classList.add(c);clearTimeout(w._at);w._at=setTimeout(()=>w.classList.remove(c),500)}
/* 화면 크기 추적: 창·전체 화면·앱 미리보기 창이 바뀌면 resize 이벤트가 오지 않아도 다시 맞춘다 */
{const v=document.createElement('div');v.id='vp';v.setAttribute('aria-hidden','true');v.style.cssText='position:fixed;inset:0;visibility:hidden;pointer-events:none;z-index:-1';document.body.appendChild(v);
let fr=0;const refit=()=>{cancelAnimationFrame(fr);fr=requestAnimationFrame(fit)};try{new ResizeObserver(refit).observe(v)}catch(_){}
document.addEventListener('fullscreenchange',refit);window.visualViewport&&visualViewport.addEventListener('resize',refit);
$('mode').addEventListener('click',()=>{[60,200,500,1000].forEach(ms=>setTimeout(fit,ms))})}
document.addEventListener('fullscreenchange',()=>{if(document.fullscreenElement||!presenting)return;
const busy=tool!=='none'||ol.classList.contains('open')||ky.classList.contains('open')||Date.now()-toolOff<600;
if(busy){setTool('none',true);toc(false);ky.classList.remove('open');refs=true;flash('도구를 껐습니다 · 화면을 한 번 클릭하면 전체 화면으로 돌아갑니다',3500)}else setPresent(false)});
/* 도구 전환 */
function setTool(t,quiet){if(editing||(t==='laser'&&!presenting))t='none';if(t===tool)return;if(tool!=='none')toolOff=Date.now();tool=t;cs=null;BC.toggle('laser',t==='laser');BC.toggle('pen',t==='pen');$('lz').classList.toggle('on',t==='laser');$('pn').classList.toggle('on',t==='pen');updPen();if(t==='pen')pbShow(2500);
if(!quiet)flash(t==='laser'?'레이저 포인터 · 누른 채 움직이면 궤적 · 더블클릭·← →로 쪽 이동 · Esc 해제':t==='pen'?'펜 · 화면 아래로 마우스를 가져가면 펜 막대':'일반 모드 · 클릭·휠·드래그로 쪽 이동',t==='none'?1200:2000)}
const toggleTool=t=>setTool(tool===t?'none':t);
$('lz').onclick=()=>toggleTool('laser');
/* 클릭으로 넘기기 켜기·끄기(K, 상단 ‘클릭 넘김’) — 이 브라우저에 기억 */
let clickNav=true;try{clickNav=localStorage.getItem('tpdeck-clicknav')!=='0'}catch(_){}$('ck').classList.toggle('on',clickNav);
function setClickNav(v,msg){clickNav=v;$('ck').classList.toggle('on',v);try{localStorage.setItem('tpdeck-clicknav',v?'1':'0')}catch(_){}if(msg)flash(v?'클릭으로 넘기기 켜짐':'클릭으로 넘기기 꺼짐 · 키보드·휠·드래그로 이동',1800)}
$('ck').onclick=()=>setClickNav(!clickNav,true);
/* 검은·흰 화면(B · . / W · ,) — 발표용 리모컨의 화면 끄기 버튼 대응. 아무 키나 클릭으로 복귀 */
const bk=document.createElement('div');bk.id='blank';document.body.appendChild(bk);let blankOn=false;
function blank(c){blankOn=!!c;bk.style.background=c||'';bk.classList.toggle('on',blankOn);if(blankOn){bar.classList.remove('show');pb.classList.add('hide')}}
bk.addEventListener('click',()=>blank(false));
/* 저장하지 않은 편집이 있으면 창을 닫거나 새로고침할 때 경고 */
document.addEventListener('input',()=>{if(editing){markDirty(true);densUpdate()}});
/* 콘텐츠 밀도 배지(편집 모드): 쪽별 단계·글자 수, 기준 초과 시 빨강, 클릭하면 단계 변경 */
const DENS={1:['여유',100,2,0],2:['표준',200,3,4],3:['상세',350,4,7]};
function densUpdate(){if(!editing)return;wraps.forEach(w=>{const s=w.firstElementChild,m=s.querySelector('main');let g=w.querySelector(':scope>.dens');if(!m||s.matches('.cover,.thanks,.divider,.agenda-page')){g&&g.remove();return}
const lv=+s.dataset.density||2,[nm,c,bl,rw]=DENS[lv]||DENS[2],ch=m.innerText.replace(/\s+/g,'').length,b=m.children.length,r=m.querySelectorAll('tbody tr').length,over=ch>c||b>bl||r>rw;
if(!g){g=document.createElement('button');g.type='button';g.className='dens';g.addEventListener('click',()=>{s.dataset.density=(+s.dataset.density||2)%3+1;markDirty(true);densUpdate()});w.appendChild(g)}
g.textContent='밀도 '+lv+' '+nm+' · '+ch+'/'+c+'자';g.classList.toggle('warn',over);g.title=(over?'단계 기준 초과 · ':'')+'글자 '+ch+'/'+c+' · 블록 '+b+'/'+bl+' · 표 행 '+r+'/'+rw+' (클릭: 단계 바꾸기)'})}
document.addEventListener('pointerup',()=>{if(editing)setTimeout(densUpdate,0)});document.addEventListener('keyup',()=>{if(editing)densUpdate()});
/* 목차 쪽 항목: 누르면 그 쪽으로 */
$('deck').addEventListener('click',e=>{const a=e.target.closest&&e.target.closest('.agenda a');if(!a||editing)return;e.preventDefault();e.stopPropagation();const m=/#p(\d+)/.exec(a.getAttribute('href')||'');if(m)show(+m[1]-1)},true);addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});$('pn').onclick=()=>toggleTool('pen');
const lz=document.createElement('div');lz.id='laser';document.body.appendChild(lz);addEventListener('mousemove',e=>{lz.style.left=e.clientX+'px';lz.style.top=e.clientY+'px'});
/* 레이저 잔상: 포인터 모드에서 누른 채 움직이면 붉은 궤적이 0.7초 남았다 사라진다(쪽은 넘어가지 않음). 포인터 모드의 쪽 넘김은 더블클릭(왼쪽 1/3 이전)과 키보드 */
const tr=document.createElement('canvas');tr.id='trail';document.body.appendChild(tr);const tx=tr.getContext('2d');let trail=[],trOn=false,trRaf=0,trS=0;
function trDraw(){const d=devicePixelRatio||1,W=innerWidth,H=innerHeight;if(tr.width!==Math.round(W*d)||tr.height!==Math.round(H*d)){tr.width=Math.round(W*d);tr.height=Math.round(H*d)}tx.setTransform(d,0,0,d,0,0);tx.clearRect(0,0,W,H);const now=performance.now();trail=trail.filter(p=>now-p.t<700);tx.lineCap=tx.lineJoin='round';for(let i=1;i<trail.length;i++){const a=trail[i-1],b=trail[i];if(a.s!==b.s)continue;const k=1-(now-b.t)/700;tx.strokeStyle='rgba(255,42,31,'+(.85*k).toFixed(3)+')';tx.lineWidth=2+5*k;tx.beginPath();tx.moveTo(a.x,a.y);tx.lineTo(b.x,b.y);tx.stroke()}trRaf=trail.length?requestAnimationFrame(trDraw):0}
document.addEventListener('pointerdown',e=>{if(tool!=='laser'||e.button!==0||inUI(e.target))return;trOn=true;trS++;trail.push({x:e.clientX,y:e.clientY,t:performance.now(),s:trS})},true);
addEventListener('pointermove',e=>{if(!trOn)return;trail.push({x:e.clientX,y:e.clientY,t:performance.now(),s:trS});if(!trRaf)trRaf=requestAnimationFrame(trDraw)});addEventListener('pointerup',()=>{trOn=false});
$('deck').addEventListener('dblclick',e=>{if(!presenting||editing||tool!=='laser')return;show(current+(e.clientX<innerWidth/3?-1:1))});
/* 펜: 쪽별 캔버스에 쪽 좌표 비율로 저장(창 크기가 바뀌어도 위치 유지, 인쇄 제외) */
const strokes={},PEN={r:['#e11d1d',.0042],u:['#1a56db',.0042],y:['rgba(255,214,0,.42)',.022]};let pc='r',cs=null,csI=0;
const nrm=(e,c)=>{const r=c.getBoundingClientRect();return[(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]};
const inks=wraps.map((w,i)=>{const c=document.createElement('canvas');c.className='ink';w.appendChild(c);
c.addEventListener('pointerdown',e=>{if(tool!=='pen'||e.button!==0)return;e.preventDefault();e.stopPropagation();c.setPointerCapture(e.pointerId);csI=i;pb.classList.add('hide');cs={c:PEN[pc][0],w:PEN[pc][1],p:[nrm(e,c)]};(strokes[i]=strokes[i]||[]).push(cs);redraw(i)});
c.addEventListener('pointermove',e=>{if(cs&&csI===i){cs.p.push(nrm(e,c));redraw(i)}});const end=()=>{cs=null};c.addEventListener('pointerup',end);c.addEventListener('pointercancel',end);return c});
function redraw(only){const d=window.devicePixelRatio||1;inks.forEach((c,i)=>{if(only!==undefined&&only!==i)return;const w=parseFloat(wraps[i].style.width)||0,h=parseFloat(wraps[i].style.height)||0;if(!w)return;const W=Math.round(w*d),H=Math.round(h*d);if(c.width!==W||c.height!==H){c.width=W;c.height=H}const x=c.getContext('2d');x.setTransform(d,0,0,d,0,0);x.clearRect(0,0,w,h);x.lineCap=x.lineJoin='round';for(const s of strokes[i]||[]){x.strokeStyle=s.c;x.lineWidth=s.w*w;x.beginPath();s.p.forEach((q,j)=>{j?x.lineTo(q[0]*w,q[1]*h):x.moveTo(q[0]*w,q[1]*h)});if(s.p.length===1)x.lineTo(s.p[0][0]*w+.1,s.p[0][1]*h);x.stroke()}})}
const penUndo=()=>{(strokes[current]||[]).pop();redraw(current)},penClear=all=>{if(all)for(const q in strokes)delete strokes[q];else delete strokes[current];redraw()};
const pb=document.createElement('div');pb.id='penbar';pb.setAttribute('role','toolbar');pb.setAttribute('aria-label','펜 도구');
pb.innerHTML='<button data-c="r" title="빨간 펜 (R)"><i style="background:#e11d1d"></i></button><button data-c="u" title="파란 펜 (U)"><i style="background:#1a56db"></i></button><button data-c="y" title="형광펜 (Y)"><i class="hl"></i></button><span class="sep"></span><button data-a="undo" title="마지막 획 취소 (Z · 우클릭)"><svg viewBox="0 0 16 16"><path d="M3.5 6.5h6a3.5 3.5 0 0 1 0 7H6M3.5 6.5L6 4M3.5 6.5L6 9"/></svg></button><button data-a="clear" title="이 쪽 필기 지움 (X)"><svg viewBox="0 0 16 16"><path d="M9.5 3.5l3 3-6 6H3.5v-3zM7 13h6"/></svg></button><button data-a="all" title="모든 쪽 필기 지움 (Shift+X)"><svg viewBox="0 0 16 16"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5"/></svg></button><span class="sep"></span><button data-a="prev" title="이전 쪽 (←)"><svg viewBox="0 0 16 16"><path d="M10 3.5L5.5 8l4.5 4.5"/></svg></button><b id="pbcount"></b><button data-a="next" title="다음 쪽 (→)"><svg viewBox="0 0 16 16"><path d="M6 3.5L10.5 8 6 12.5"/></svg></button><span class="sep"></span><button data-a="off" class="off" title="펜 끄기 · 필기 유지 (Esc · P)"><svg viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8"/></svg></button><button data-a="wipe" class="wipe" title="모든 쪽 필기를 지우고 펜 끄기 (Shift+P)">지우고 끄기</button>';
document.body.appendChild(pb);
pb.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;b.blur();if(b.dataset.c){pc=b.dataset.c;updPen();return}({undo:penUndo,clear:()=>penClear(false),all:()=>penClear(true),prev:()=>show(current-1),next:()=>show(current+1),off:()=>setTool('none'),wipe:()=>{penClear(true);setTool('none');flash('필기를 지우고 펜을 껐습니다',1400)}})[b.dataset.a]()});
/* 펜 막대 자동 숨김: 켤 때·단축키 사용 시·마우스가 화면 아래쪽에 오면 보이고, 그리는 동안·2초 뒤 숨김 */
let pbT;function pbShow(ms){pb.classList.remove('hide');clearTimeout(pbT);pbT=setTimeout(()=>{if(!pb.matches(':hover'))pb.classList.add('hide')},ms||2000)}
addEventListener('mousemove',e=>{if(tool==='pen'&&!cs&&e.clientY>innerHeight-80)pbShow(1500)});
function updPen(){pb.querySelectorAll('[data-c]').forEach(b=>b.classList.toggle('on',b.dataset.c===pc));$('pbcount').textContent=(current+1)+' / '+wraps.length}
/* 목차 · 섹션 */
const info=wraps.map((w,i)=>{const s=w.firstElementChild,n=s.querySelector('.section-number')||s.querySelector('.div-num'),nm=s.querySelector('.section-name')||s.querySelector('.divider h2'),h=s.querySelector('h2')||s.querySelector('h1');return{i,sec:n?n.textContent.trim():(s.classList.contains('cover')?'표지':s.classList.contains('agenda-page')?'목차':'마무리'),name:nm?nm.textContent.trim():'',t:(h?h.innerText:s.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim()}});
const ol=document.createElement('aside');ol.id='outline';ol.setAttribute('aria-label','목차');
{const mk=(tag,txt,i)=>{const e=document.createElement(tag);e.dataset.i=i;e.textContent=txt;return e},tt=document.createElement('div');tt.className='ttl';tt.textContent='목차 · 쪽 이동';ol.appendChild(tt);let last=null;
for(const f of info){const key=f.sec+'|'+f.name;if(key!==last){ol.appendChild(mk('h4',f.name?f.sec+'  '+f.name:f.sec,f.i));last=key}const a=document.createElement('a');a.dataset.i=f.i;const b=document.createElement('b');b.textContent=f.i+1;const s=document.createElement('span');s.textContent=f.t;a.append(b,s);ol.appendChild(a)}}
document.body.appendChild(ol);
function toc(on){if(on===undefined)on=!ol.classList.contains('open');ol.classList.toggle('open',on);if(on){ol.querySelectorAll('a').forEach(a=>a.classList.toggle('cur',+a.dataset.i===current));const c=ol.querySelector('a.cur');c&&c.scrollIntoView({block:'center'})}}
$('toc').onclick=()=>toc();$('count').onclick=()=>toc();
ol.addEventListener('click',e=>{const t=e.target.closest('[data-i]');if(t){show(+t.dataset.i);toc(false)}});
document.addEventListener('pointerdown',e=>{if(ol.classList.contains('open')&&!e.target.closest('#outline,#toc,#count'))toc(false)},true);
const secKey=i=>info[i].sec+'|'+info[i].name,secStart=i=>{while(i>0&&secKey(i-1)===secKey(i))i--;return i};
function secMove(d){let s=secStart(current);if(d<0){show(current>s?s:(s>0?secStart(s-1):0));return}let j=current;while(j<wraps.length-1&&secKey(j+1)===secKey(current))j++;show(Math.min(j+1,wraps.length-1))}
/* 마우스로 쪽 넘기기 (도구에 따라) */
let sw=null,swDone=0;
document.addEventListener('pointerdown',e=>{if(!presenting||editing||e.button!==0||inUI(e.target))return;if(refs){refs=false;goFull();swDone=Date.now();return}if(tool!=='none')return;sw={x:e.clientX,y:e.clientY}},true);
document.addEventListener('pointerup',e=>{if(!sw)return;const dx=e.clientX-sw.x,dy=e.clientY-sw.y,ax=Math.abs(dx),ay=Math.abs(dy);sw=null;if(Math.max(ax,ay)<60)return;swDone=Date.now();const d=(ax>=ay?dx:dy)<0?1:-1,before=current;show(current+d);if(current!==before)flash((d>0?'다음 ':'이전 ')+(current+1)+' / '+wraps.length)},true);
$('deck').addEventListener('click',e=>{if(!presenting||editing||tool!=='none'||Date.now()-swDone<400)return;if(e.clientY<48){barShow(3000);return}if(!clickNav)return;show(current+(e.clientX<innerWidth/3?-1:1))});
/* 휠(보기·발표 공통): 마우스 휠은 한 칸에 한 쪽, 터치패드는 한 번 쓸기(관성 포함)에 한 쪽. 터치패드는 0.25초 멈춘 뒤에야 다음 쓸기를 받는다 */
let wLock=false,wEnd,wPrev=0,wNav=0;function wheelNav(e){const now=Date.now(),gap=now-wPrev,dy=e.deltaMode?e.deltaY*40:e.deltaY;wPrev=now;if(Math.abs(dy)<4)return;const d=dy>0?1:-1;
if(Math.abs(dy)>=50&&gap>=60&&!wLock){if(now-wNav<150)return;wNav=now;show(current+d);return}clearTimeout(wEnd);wEnd=setTimeout(()=>wLock=false,250);if(wLock)return;wLock=true;wNav=now;show(current+d)}
addEventListener('wheel',e=>{if(!presenting||editing||e.ctrlKey||tool!=='none'||inUI(e.target))return;wheelNav(e)},{passive:true});
document.addEventListener('wheel',e=>{if(presenting||editing||e.ctrlKey||inUI(e.target))return;e.preventDefault();wheelNav(e)},{passive:false});
addEventListener('contextmenu',e=>{if(tool!=='pen'||inUI(e.target))return;e.preventDefault();penUndo()});
/* 키보드 (한 곳) */
addEventListener('keydown',e=>{const k=e.key,c=k.toLowerCase(),stop=()=>{e.preventDefault();e.stopImmediatePropagation()};
if(blankOn){if(!e.ctrlKey&&!e.metaKey&&!e.altKey){stop();blank(false)}return}
if(k==='F5'&&!e.ctrlKey){stop();if(!presenting)setPresent(true);return}
if(k==='Escape'){if(editing)return;stop();if(ky.classList.contains('open')){ky.classList.remove('open');return}if(ol.classList.contains('open')){toc(false);return}if(nb){nb='';flash('쪽 번호 입력 취소',900);return}if(tool!=='none'){setTool('none');return}if(presenting)setPresent(false);return}
if(e.ctrlKey||e.metaKey||e.altKey||(editing&&(typing||sel)))return;
const nx=k==='ArrowRight'||k==='PageDown'||(presenting&&(k==='ArrowDown'||(k===' '&&!e.shiftKey))),pv=k==='ArrowLeft'||k==='PageUp'||(presenting&&(k==='ArrowUp'||(k===' '&&e.shiftKey)));
if(nx||pv){stop();show(current+(nx?1:-1));return}if(editing)return;
if(k==='Home'||k==='End'){stop();show(k==='Home'?0:wraps.length-1);return}
if(k==='?'||c==='h'){ky.classList.toggle('open');return}if(c==='g'){toc();return}if(k==='['||k===']'){secMove(k===']'?1:-1);return}
if(c==='f'){if(presenting&&refs){refs=false;goFull()}else setPresent(!presenting);return}if(c==='e'){if(!presenting)setEditing(true);return}
if(c==='p'){if(e.shiftKey&&tool==='pen'){penClear(true);setTool('none');flash('필기를 지우고 펜을 껐습니다',1400);return}toggleTool('pen');return}
if(tool==='pen'&&'ruyzx'.includes(c))pbShow(1500);if(tool==='pen'){if(PEN[c]){pc=c;updPen();flash({r:'빨간 펜',u:'파란 펜',y:'형광펜'}[c],1000);return}if(c==='z'){penUndo();return}if(c==='x'){penClear(e.shiftKey);return}}
if(!presenting)return;if(c==='b'||k==='.'){blank('#000');return}if(c==='w'||k===','){blank('#fff');return}if(c==='k'){setClickNav(!clickNav,true);return}if(c==='l'){toggleTool('laser');return}if(c==='m'){barShow(3000);return}
if(/^\d$/.test(k)){nb=(nb.length>=3?'':nb)+k;flash('→ '+nb+'쪽  (Enter 이동 · Esc 취소)',2500);clearTimeout(nt);nt=setTimeout(()=>nb='',2500);return}
if(k==='Enter'&&nb){stop();const n=Math.max(1,Math.min(wraps.length,+nb));nb='';show(n-1);flash(n+' / '+wraps.length+'쪽')}},true);
/* 단축키 도움말(?) */
const ky=document.createElement('div');ky.id='keys';ky.setAttribute('role','dialog');ky.setAttribute('aria-label','단축키');
{const R=[['쪽 이동 · 키보드',[['← →','이전 · 다음'],['PgUp PgDn','이전 · 다음'],['Space ↓ ↑','발표 중 다음 · 이전'],['숫자 Enter','쪽 번호로'],['Home End','처음 · 끝'],['[ ]','이전 · 다음 섹션'],['G','목차']]],
['쪽 이동 · 마우스(발표)',[['클릭','다음 (왼쪽 1/3 이전)'],['K','클릭 넘김 켜기 · 끄기'],['휠 · 드래그','다음 · 이전'],['포인터 중','더블클릭으로만 (누른 채 그리면 궤적)'],['펜 중','넘기지 않음']]],
['모드 · 도구',[['F · F5','발표 시작 · 종료'],['B · .','검은 화면 (아무 키로 복귀)'],['W · ,','흰 화면'],['E','편집 모드'],['L','레이저 포인터'],['P','펜 켜기 · 끄기'],['M','상단 메뉴'],['Esc','한 단계씩 해제'],['?','도움말']]],
['펜',[['R U Y','빨강 · 파랑 · 형광'],['Z','획 취소 (우클릭)'],['X','이 쪽 지움'],['Shift X','모든 쪽 지움'],['Shift P','지우고 끄기']]],
['편집 모드',[['클릭 · 드래그','선택 · 이동'],['더블클릭 Enter','글 수정'],['Ctrl C · V','복사 · 붙여넣기'],['Ctrl D','복제'],['Delete','삭제'],['Ctrl Z','되돌리기'],['Ctrl S','편집본 저장']]]];
const key=a=>a.split(' · ').map(g=>g.split(' ').map(x=>/^[가-힣]/.test(x)?x:'<kbd>'+x+'</kbd>').join(' ')).join(' · ');
let html='<div class="kh-top"><h4>단축키</h4><span>Esc 또는 바깥 클릭으로 닫기</span></div><div class="cols">';for(const[s,rows]of R){html+='<section><div class="sub">'+s+'</div><dl>'+rows.map(([a,b])=>'<dt>'+key(a)+'</dt><dd>'+b+'</dd>').join('')+'</dl></section>'}ky.innerHTML=html+'</div>';document.body.appendChild(ky)}
$('kh').onclick=()=>ky.classList.toggle('open');
document.addEventListener('pointerdown',e=>{if(ky.classList.contains('open')&&!e.target.closest('#keys,#kh'))ky.classList.remove('open')},true);
{const m=/^#p(\d+)$/.exec(location.hash);show(m?+m[1]-1:0)}
```

## 검수 (건너뛰지 않는다)

쪽은 높이(`--sh`) 고정이라 내용이 넘치면 잘리거나 바닥글과 겹친다. HTML을 저장한 뒤 매번 실행한다. 브라우저 자동화가 없으면 먼저 설치한다: `pip install playwright` 후 `playwright install chromium`(작업 환경의 일반 절차).

```python
from playwright.sync_api import sync_playwright
import pathlib
src=pathlib.Path('deck.html').resolve()
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1200,'height':900}); pg.goto(src.as_uri()); pg.wait_for_timeout(800)
    over=pg.evaluate('''()=>[...document.querySelectorAll('.sheet')].map((s,i)=>{const m=s.querySelector('main');return {page:i+1,sheetOver:s.scrollHeight>s.clientHeight+1,mainOver:m?m.scrollHeight>m.clientHeight+1:false}}).filter(r=>r.sheetOver||r.mainOver)''')
    print('overflow:',over)
    fill=pg.evaluate('''()=>[...document.querySelectorAll('.sheet')].map((s,i)=>{const m=s.querySelector('main');if(!m||!m.children.length||s.matches('.cover,.thanks,.divider,.agenda-page')||m.matches('.v-center,.v-spread')||m.querySelector('.statement'))return null;const r=m.getBoundingClientRect(),cs=[...m.children].map(c=>c.getBoundingClientRect()).filter(c=>c.height>0);if(!cs.length)return null;const f=(Math.max(...cs.map(c=>c.bottom))-Math.min(...cs.map(c=>c.top)))/r.height;return {page:i+1,fill:Math.round(f*100)}}).filter(r=>r&&(r.fill<60||r.fill>95))''')
    print('fill(60~95% 밖):',fill)
    dens=pg.evaluate('''()=>{const L={1:[100,2,0],2:[200,3,4],3:[350,4,7]};return [...document.querySelectorAll('.sheet')].map((s,i)=>{const m=s.querySelector('main');if(!m||s.matches('.cover,.thanks,.divider,.agenda-page'))return null;const lv=+s.dataset.density||2,[c,bl,rw]=L[lv]||L[2],ch=m.innerText.replace(/\\s+/g,'').length,b=m.children.length,r=m.querySelectorAll('tbody tr').length;return (ch>c||b>bl||r>rw)?{page:i+1,level:lv,chars:ch+'/'+c,blocks:b+'/'+bl,rows:r+'/'+rw}:null}).filter(Boolean)}''')
    print('density(단계 초과):',dens)
    for i,s in enumerate(pg.locator('.sheet').all()): s.screenshot(path=f'check-{i+1:02d}.png')   # 쪽별 확인용 이미지
    pg.emulate_media(media='print'); pg.pdf(path='deck.pdf',width='297mm',height='210mm',print_background=True)  # 선택한 크기의 --sw·--sh 값으로
    b.close()
```

- `fill(60~95% 밖):` 항목은 "레이아웃 설계 4"대로 고친다(60% 미만: `v-center`·`v-spread` → 더 큰 유형 → 쪽 합치기). `[]`가 목표다. 표지·목차·간지·감사 쪽, 핵심 메시지 쪽, `v-center`·`v-spread`로 여백을 고르게 나눈 쪽은 측정에서 빠진다.
- `density(단계 초과):` 항목은 "콘텐츠 밀도"대로 줄이거나, 덱의 쓰임이 허용하면 단계를 올린다.
- `overflow:`가 `[]`이면 통과. 항목이 있으면 그 쪽을 줄인다: 문장 줄이기 → 항목 수 줄이기 → 표 행 줄이기 → 주석 삭제 → 쪽 나누기 순. 글자 크기·여백을 임의로 줄이지 않는다.
- `check-NN.png`를 열어 한 번 눈으로 본다: 글자 잘림, 카드 높이 불균형, 비어 있는 쪽 아래 절반, 표지·감사 쪽의 배경. 확인이 끝나면 `check-*.png`는 사용자에게 보내지 않는다(요청하면 `deck.pdf`만 전달).
- **브라우저 자동화를 쓸 수 없는 환경**이면 검수를 건너뛰지 말고 보수적으로 만든다: 표 행 4개 이하, 카드 설명 두 줄 이내, 쪽당 주요 블록 3개 이하, 주석 한 줄. 그리고 답변에 "자동 넘침 검사를 하지 못했으니 브라우저에서 인쇄 미리보기로 잘림을 확인해 달라"고 알린다.
- **흑백 인쇄 확인**: 인쇄 배포용이면 `check-NN.png` 몇 장을 흑백으로 바꿔 보고(`PIL.ImageOps.grayscale`) 확정·예상·진행중이 선 모양과 글자로 구별되는지 본다.
- **배포 파일 확인**: 최종 HTML을 새로 열어 한글 표시(UTF-8), 글꼴·이미지 로딩, 발표 보기·인쇄 미리보기에서 쪽이 겹치거나 잘리지 않는지 본다. 스크립트가 꺼진 환경에서도 본문 쪽이 겹치지 않아야 한다.

납품 전 체크리스트(모두 통과해야 전달한다):

- [ ] 처음 보는 청중도 배경과 발표 목적을 이해할 수 있다(제목만 이어 읽어도 흐름이 선다)
- [ ] 사업명·기관명·날짜·단위·인원·건수, 합계와 산식이 원자료와 맞는다(합계는 직접 계산해 검산)
- [ ] 기준일·기간·대상, 확인된 실적·전망·계획이 글자와 모양으로 구별된다. 추정치 쪽에 `note`가 있다
- [ ] 판단을 바꾸는 가정이나 집계 조건이 해당 수치 가까이에 있다
- [ ] 비교의 범위·눈금이 맞고, 공개 범위에 맞춘 내용과 필요한 출처가 들어 있다
- [ ] 목차 쪽이 있으면 표지에 섹션 안내가 없다
- [ ] 쪽별 밀도가 단계 기준 안이고, 덱의 쓰임(발표형·표준·배포형)과 맞다
- [ ] 쪽 번호 `NN / 총쪽수`, 섹션 번호 순서, 표지 `cover-route`·목차 쪽의 섹션 이름과 쪽 범위가 맞고, 마무리가 발표 목적과 맞는다
- [ ] 자료에 없는 기관명·수치·날짜가 들어가지 않았다
- [ ] 최종 공유 파일을 열어 한글·글꼴·이미지·쪽·발표 기능을 확인했다

## 하지 않는 것

- 새 색·새 글꼴·그라디언트·이모지·장식 도형을 추가하지 않는다.
- 사진·로고를 인터넷에서 가져오지 않는다. 재단 로고는 `assets/`의 CI 파일, 그 밖의 사진·로고는 사용자가 준 파일만 쓴다.
- 자료에 없는 내용으로 쪽을 채우지 않는다. 쪽이 비면 쪽 수를 줄인다.
- 발표 스크립트·기획서 같은 별도 문서를 요청 없이 함께 만들지 않는다.
- 확인되지 않은 항목을 그럴듯한 값이나 자리표시(○○명, 추후 기입)로 채우지 않는다.