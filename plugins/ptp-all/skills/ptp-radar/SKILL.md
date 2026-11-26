---
name: ptp-radar
description: "공고레이더 — 포항TP 기준으로 정부·전담기관·지자체 신규 공고와 기술수요조사를 찾아 적합도를 매기고 원문 링크가 걸린 HTML 브리핑을 만든다. 수집 소스 목록·점검·추가·삭제도 맡는다. 공고 찾아줘, 공모 스캔, 기술수요조사, 공고 소스 추가 요청에 쓴다."
---

# 공고레이더

(재)포항테크노파크(포항시 출자·출연 비영리 재단법인, 산업기술단지 특례법상 사업시행자)가
**신청할 수 있고, 주관할 수 있고, 주력 분야에 맞는** 공고를 빨리 찾는 것이 목적이다.
공모 공고뿐 아니라 내년 공모로 이어지는 **기술수요조사·RFP 공개검증·사전공고(사전조사)**도 함께 찾는다.
사전조사는 공고가 나오기 전에 과제 기획에 참여할 수 있는 기회라서, 공모만큼 놓치면 아깝다.

## 작업 폴더

결과와 사용자 데이터는 스킬 폴더가 아니라 **작업 폴더**에 둔다. 스킬을 업데이트해도 사용자가 추가한 소스와 이력이 남게 하기 위해서다.

| 환경 | 작업 폴더 |
| --- | --- |
| Claude Code·Cowork (로컬 폴더가 있음) | 현재 작업 디렉터리의 `공고레이더/` |
| Claude.ai (샌드박스) | `/mnt/user-data/outputs/공고레이더/` — 대화가 끝나면 사라지므로, 소스를 바꾼 뒤에는 `sources.json`을 내려받아 다음에 다시 올리도록 안내한다 |

작업 폴더의 파일:

```
공고레이더/
├── sources.json          수집 소스 (처음 실행 때 스킬의 data/sources.json을 복사)
├── config.json           사용자 설정 (추가 키워드, 예산 하한, data.go.kr 인증키) — 없으면 기본값
├── history.json          지금까지 본 공고 (NEW 표시·중복 판정용)
├── results_YYYYMMDD.json 스캔 결과 원자료 (HTML 재생성용)
└── 브리핑_YYYYMMDD.html   최종 결과물
```

스크립트는 모두 파이썬 표준 라이브러리만 쓴다. 경로는 스킬 폴더 기준이다(`<skill>`은 이 SKILL.md가 있는 폴더).

## 요청별 처리

| 사용자 요청 | 처리 |
| --- | --- |
| "공고레이더", "공고 스캔해줘" | 아래 **전체 스캔** |
| "IRIS만 다시 봐줘", "KETEP 공고 확인" | 해당 소스만 스캔 (같은 절차, 소스 1개) |
| "소스 목록 보여줘" | `python <skill>/scripts/sources.py list --workdir 공고레이더` 결과를 표로 보여준다 |
| "소스 점검해줘" | **소스 점검** |
| "○○ 소스 추가해줘" (기관명 또는 URL) | **소스 추가** |
| "○○ 소스 삭제해줘" | **소스 삭제** |
| "키워드 추가", "예산 하한 3억", "API 키 등록" | `config.json` 수정 후 현재 설정을 표로 보여준다 (없으면 `assets/config.example.json`을 복사해 시작, 키 값은 화면에 다시 적지 않는다) |
| "지난 브리핑 다시 만들어줘" | `render_html.py`에 기존 `results_*.json`을 넣어 재생성 |

---

## 전체 스캔

### 1. 준비

```bash
python <skill>/scripts/sources.py init --workdir 공고레이더      # 없을 때만 기본 소스 복사
python <skill>/scripts/sources.py plan --workdir 공고레이더      # 이번 스캔에서 조회할 소스와 순서
```

그리고 다음을 읽는다.
- `references/scoring.md` — 적합도 게이트·배점·사전조사 관련도 (점수의 유일한 기준)
- `references/org-profile.md` — 포항TP 주력 분야·키워드·동의어·지역 요건
- `references/collection.md` — 소스별 조회 방법, 조회 예산, 사전조사 검색어, 자동 추가 규칙
- `공고레이더/config.json`, `공고레이더/history.json` (있으면)

### 2. 수집

`plan` 결과 순서대로 `collection.md`의 4단계(① API → ② WebFetch → ③ WebSearch → ④ 실패 기록)로 조회한다.
조회는 총 **50회 이내**이고, 그중 6회는 사전조사 검색에 남겨 둔다.

각 소스를 조회한 직후 결과를 기록한다. 실패가 쌓인 소스를 점검 대상으로 띄우는 데 쓴다.

```bash
python <skill>/scripts/sources.py mark --workdir 공고레이더 --id iris --result ok --found 12
python <skill>/scripts/sources.py mark --workdir 공고레이더 --id kiat --result fail --note "JS 렌더링"
```

**실존 공고 원칙.** 실제로 열어 보거나 검색 결과에서 확인한 공고만 담는다. 확인 못 한 공고명·예산·마감일은 지어내지 말고 `null`(미상)로 두고, 링크도 실제로 열린 URL만 쓴다.
담당자가 이 HTML을 보고 바로 신청 준비에 들어가기 때문에, 그럴듯한 가짜 한 건이 진짜 열 건보다 피해가 크다.

### 3. 분류와 채점

공고마다 `scoring.md` 순서로 판단한다.

1. **공모인가, 사전조사인가** — 수요조사·RFP 공개검증·사전공고·사전규격·설명회는 `presurveys`로 보내고 관련도(상/중)만 매긴다.
2. **자격 게이트** G1~G3 (원문을 못 열었으면 제목 패턴으로 `G1?`·`G3?`)
3. **A~F 점수** — 포항TP가 실제로 맡을 역할과 사업 내용으로 판정
4. 마감이 지난 공고는 `closed`로 보낸다.

합계·B-1 상한·긴급 판정·등급 분류는 렌더러가 다시 계산하므로, 항목별 점수와 근거만 정확히 넣으면 된다.

### 4. 결과 저장과 HTML 생성

`references/results-schema.md`의 형식으로 `공고레이더/results_YYYYMMDD.json`을 쓴 뒤:

```bash
python <skill>/scripts/render_html.py 공고레이더/results_YYYYMMDD.json --workdir 공고레이더
```

렌더러가 점수를 검산하고, `history.json`과 비교해 새 공고에 NEW를 달고, 이력을 갱신하고, `브리핑_YYYYMMDD.html`을 만든다.
검산 결과 입력 합계와 다른 공고가 있으면 경고를 출력하니, 그 공고의 항목 점수를 다시 확인한다.

파이썬을 쓸 수 없는 환경이면 `assets/briefing_example.html`의 구조와 스타일을 그대로 따라 HTML을 직접 쓴다.

### 5. 보고

채팅에는 HTML 파일 링크와 함께 짧게 알린다: 접수 중 공고 수, 즉시 검토·마감 임박 공고(제목·점수·마감), 사전조사 수, 수집 실패 소스, 자동 추가된 소스.
신청 전에는 원문에서 자격과 마감을 다시 확인하라고 한 줄 덧붙인다.

---

## 소스 관리

소스는 `공고레이더/sources.json` 하나에 있다. 직접 편집하지 말고 스크립트를 쓴다. 필드 오타로 스캔이 조용히 빠지는 일을 막기 위해서다.

### 소스 목록 확인

```bash
python <skill>/scripts/sources.py list --workdir 공고레이더 [--tier 2] [--all]
```

기본은 사용 중인 소스만, `--all`은 비활성·삭제된 소스까지 보여준다. 연속 실패 3회 이상이면 "점검 필요"로 표시된다.

### 소스 점검

```bash
python <skill>/scripts/sources.py check --workdir 공고레이더 [--id kiat]
```

목록 URL에 HTTP로 접속해 응답 코드를 기록한다. 이 검사는 "페이지가 열리는가"까지만 본다. 샌드박스에서 외부 접속이 막혀 있으면 모두 실패로 나오므로, 그때는 WebFetch로 직접 열어 보고 `mark`로 기록한다.
응답이 실패했거나 열려도 게시물이 안 보이는 소스는 WebSearch(`"기관명 사업공고"`)로 새 목록 주소를 찾아 사용자에게 보여주고, 동의하면 `set`으로 바꾼다.

```bash
python <skill>/scripts/sources.py set --workdir 공고레이더 --id kiat --url "새 URL" --verified F
```

### 소스 추가

사용자가 기관명만 주면 WebSearch로 그 기관의 **사업공고 목록 페이지**를 찾고, WebFetch로 열어 최근 게시물이 보이는지 확인한 뒤 추가한다. URL을 주면 확인만 하고 추가한다.
메인 페이지나 개별 공고 URL이 아니라 공고 **목록** URL이어야 다음 스캔에서 새 글을 볼 수 있다.

```bash
python <skill>/scripts/sources.py add --workdir 공고레이더 \
  --id pohang-innopolis --name "포항강소특구육성센터" --short "포항강소특구" --tier 3 --priority 중 \
  --url "https://..." --fields "강소특구,기술사업화" --verified F [--presurvey]
```

`--id`는 영문 소문자·하이픈으로 짧게 붙인다(없으면 `src-2`처럼 자동 생성). `--tier`는 1 통합포털 / 2 전담기관 / 3 지역, `--priority`는 상(매 스캔)·중(예산 남으면)·하(7일마다)다. 같은 URL이나 이름이 이미 있으면 거부된다.

### 소스 삭제

```bash
python <skill>/scripts/sources.py remove --workdir 공고레이더 --id kocca
python <skill>/scripts/sources.py restore --workdir 공고레이더 --id kocca   # 되돌리기
```

삭제는 목록에서 빼되 `removed` 상태로 남겨 둔다. 실수로 지워도 `restore`로 되돌릴 수 있다. 무엇을 지웠는지 이름과 URL을 채팅에 적는다.
잠시만 빼려면 `set --id kocca --enabled false`.

### 자동 추가

스캔 중 포털(IRIS·NTIS·기업마당 등)에서 찾은 공고의 원문이 **등록되지 않은 기관**에 있고, 그 공고가 게이트를 통과했거나 사전조사 관련도 "상"이면,
그 기관의 공고 목록 페이지를 찾아 `--origin auto --priority 하`로 추가한다. 자세한 조건은 `collection.md` §5.

```bash
python <skill>/scripts/sources.py add --workdir 공고레이더 --origin auto --name "..." --url "..." --tier 2 --priority 하
```

자동 추가는 한 번 스캔에 최대 3개까지, 목록 페이지를 WebFetch로 열어 확인한 것만 한다. 추가한 소스는 브리핑의 "수집 현황"과 채팅 보고에 적어서 사용자가 원치 않으면 바로 지울 수 있게 한다.
자동 추가 소스가 3회 연속 실패하면 스크립트가 알아서 비활성화한다.

---

## 참고 파일

| 파일 | 언제 읽나 |
| --- | --- |
| `references/scoring.md` | 채점할 때 항상 |
| `references/org-profile.md` | 채점할 때 항상 (분야·키워드·동의어·지역) |
| `references/collection.md` | 수집·자동 추가할 때 |
| `references/results-schema.md` | results JSON을 쓸 때 |
| `data/sources.json` | 기본 소스 원본 (작업 폴더에 복사본이 없을 때만 쓰임) |
| `assets/briefing_example.html` | 파이썬 없이 HTML을 직접 써야 할 때 |
