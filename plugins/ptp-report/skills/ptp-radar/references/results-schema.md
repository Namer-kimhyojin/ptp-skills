# 스캔 결과 형식 (results-schema.md)

스캔이 끝나면 `공고레이더/results_YYYYMMDD.json`을 이 형식으로 쓰고 `scripts/render_html.py`에 넘긴다.
렌더러가 합계·E(마감 여유)·B-1 상한·긴급·등급·NEW를 계산하므로, 아래 "렌더러가 계산" 항목은 비워 둬도 된다.

```json
{
  "scan_date": "2026-11-26",
  "scan_type": "전체",
  "queries_used": 41,
  "query_budget": 50,
  "sources": {
    "ok":          [{"id": "iris", "found": 12}],
    "failed":      [{"id": "kiat", "reason": "JS 렌더링"}],
    "not_queried": ["kocca"]
  },
  "auto_added":        [{"name": "포항강소특구육성센터", "url": "https://..."}],
  "source_candidates": [{"name": "○○진흥원", "reason": "목록 페이지 못 찾음"}],

  "announcements": [
    {
      "title": "2027년 한-스페인 에너지국제공동연구사업 신규지원대상 연구개발과제",
      "agency": "KETEP",
      "ministry": "기후에너지환경부",
      "type": "기술개발",
      "budget": "총 15억 내외 (36개월)",
      "deadline": "2027-02-02",
      "deadline_note": "접수 12-03부터",
      "rolling": false,
      "gate": null,
      "gate_reason": null,
      "scores": {"A": 20, "B1": 15, "B2": 4, "C": 20, "D": 9, "E": 15, "F": -5},
      "flags": ["컨소", "해외파트너"],
      "basis": "주관기관 제한 없음, 기업·스페인 기관 참여 필수",
      "note": "양국에 각각 신청",
      "url": "https://www.ketep.re.kr/...",
      "notice_no": "D202610544"
    }
  ],

  "presurveys": [
    {
      "title": "2027년도 제조AX분야 산업기술R&D 과제기획 기술수요조사",
      "agency": "산업통상부",
      "kind": "기술수요조사",
      "deadline": "2026-11-27",
      "B1": 15, "B2": 7,
      "note": "기정원 연계",
      "url": "https://..."
    }
  ],

  "unverified": [{"title": "...", "agency": "KHIDI", "deadline": "2026-11-30", "note": "원문 미확보", "url": null}],
  "closed":     [{"title": "...", "agency": "창업진흥원", "deadline": "2026-11-23", "url": "https://..."}]
}
```

## 필드 규칙

| 필드 | 규칙 |
| --- | --- |
| `deadline` | `YYYY-MM-DD`. 모르면 `null`. 상시·예산 소진 시까지면 `null` + `"rolling": true` |
| `gate` | `null`(통과) 또는 `"G1"`·`"G2"`·`"G3"`·`"G1?"`·`"G3?"`. 게이트 공고는 `scores`를 생략하고 `gate_reason`에 근거 문구를 적는다 |
| `scores` | A·B1·B2·C·D·F는 `scoring.md`의 배점 값만 쓴다. **E는 렌더러가 마감일로 다시 계산**한다 (마감 미상 5, 상시 12) |
| `flags` | `컨소`·`매칭`·`총액`·`추정`·`해외파트너` 등. `긴급`·`미상`은 렌더러가 자동으로 붙인다 |
| `basis` | A·게이트 판정에 쓴 공고문 문구 요약. HTML에서 점수에 마우스를 올리면 보인다 |
| `url` | 실제로 열린 원문 URL만. 없으면 `null`로 두고 `note`에 "IRIS 목록 (상세 ID 미확보)"처럼 적는다 |
| `presurveys[].B1/B2` | 관련도 계산용 (합 19↑ 상, 10~18 중, 10 미만 하 → 브리핑 제외) |
| `sources.*.id` | `sources.json`의 `id`. 렌더러가 기관명으로 바꿔 표시한다 |

## 렌더러가 계산

`total`, `E`, B-1 유형 상한(C ≤ 5이면 B1 ≤ 6), `긴급`(D-7 이내 + A ≥ 20 + A+B1+B2+C ≥ 55), 등급(70+ / 40~69 / 40 미만), `미상` 플래그(A = 8, D = 5, 마감 미상 중 하나), 사전조사 관련도, NEW(이력에 처음 오른 날 = 스캔일).
입력값이 배점표에 없는 값이거나 계산과 다르면 경고를 출력하고 계산값을 쓴다.
