#!/usr/bin/env python3
"""공고레이더 결과 JSON → HTML 브리핑.

  python render_html.py 공고레이더/results_20261126.json --workdir 공고레이더 [--out 파일.html] [--no-history]

하는 일
  1. scoring.md 규칙으로 점수를 검산한다 (E 재계산, B-1 유형 상한, 합계, 긴급, 등급, 미상 플래그).
  2. history.json과 비교해 처음 본 공고에 NEW를 달고, 이력을 갱신한다.
  3. 원문 링크를 바로 누를 수 있는 단일 HTML 파일을 만든다 (외부 리소스 없음).
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ALLOWED = {
    "A": {25, 20, 12, 8},
    "B1": {15, 10, 6, 0},
    "B2": {10, 7, 4, 0},
    "C": {20, 17, 15, 14, 12, 10, 7, 5, 3},  # 패키지 +2 포함, 최대 20
    "F": {0, -5},
}
ORG = "(재)포항테크노파크"
warnings = []


def warn(msg):
    warnings.append(msg)


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def parse_date(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        warn(f"날짜 형식 오류: {s}")
        return None


def e_score(dday, rolling):
    if dday is None:
        return 12 if rolling else 5
    if dday >= 30:
        return 15
    if dday >= 21:
        return 12
    if dday >= 14:
        return 9
    if dday >= 7:
        return 5
    if dday >= 3:
        return 2
    return 0


def norm_title(t):
    return re.sub(r"[\s\W_]+", "", (t or "").lower())


def item_key(it):
    url = (it.get("url") or "").strip()
    if url.startswith("http"):
        return url
    return f"{it.get('agency','')}|{norm_title(it.get('title'))}"


def safe_url(u):
    u = (u or "").strip()
    return u if re.match(r"^https?://", u) else None


# ---------- 채점 검산 ----------

def score(it, scan):
    title = it.get("title", "(제목 없음)")
    dl = parse_date(it.get("deadline"))
    it["_dday"] = (dl - scan).days if dl else None
    if it.get("gate"):
        it["_class"] = "gate"
        return
    s = dict(it.get("scores") or {})
    for k in ["A", "B1", "B2", "C", "D", "F"]:
        if k not in s or s[k] is None:
            s[k] = 0 if k == "F" else None
    for k, allowed in ALLOWED.items():
        if s.get(k) is not None and s[k] not in allowed:
            warn(f"[{title[:30]}] {k}={s[k]} 는 배점표에 없는 값")
    if s.get("D") is not None and not (0 <= s["D"] <= 15):
        warn(f"[{title[:30]}] D={s['D']} 범위 밖")
    missing = [k for k in ["A", "B1", "B2", "C", "D"] if s.get(k) is None]
    if missing:
        warn(f"[{title[:30]}] 점수 누락 {missing} → 0점 처리")
        for k in missing:
            s[k] = 0
    if s["C"] <= 5 and s["B1"] > 6:
        warn(f"[{title[:30]}] C={s['C']}(기타·네트워킹)라 B1 {s['B1']}→6 (유형 상한)")
        s["B1"] = 6
    e = e_score(it["_dday"], it.get("rolling"))
    if "E" in s and s["E"] is not None and s["E"] != e:
        warn(f"[{title[:30]}] E 입력 {s['E']} → 마감일 기준 {e}")
    s["E"] = e
    total = max(0, s["A"] + s["B1"] + s["B2"] + s["C"] + s["D"] + s["E"] + s["F"])
    if it.get("total") is not None and it["total"] != total:
        warn(f"[{title[:30]}] 합계 입력 {it['total']} → 계산 {total}")
    it["scores"], it["total"] = s, total
    flags = list(dict.fromkeys(it.get("flags") or []))
    core = s["A"] + s["B1"] + s["B2"] + s["C"]
    d = it["_dday"]
    if d is not None and 0 <= d <= 7 and s["A"] >= 20 and core >= 55 and "긴급" not in flags:
        flags.insert(0, "긴급")
    if (s["A"] == 8 or s["D"] == 5 or (dl is None and not it.get("rolling"))) and "미상" not in flags:
        flags.append("미상")
    if s["F"] < 0 and "해외파트너" not in flags:
        flags.append("해외파트너")
    it["flags"] = flags
    it["_class"] = "top" if total >= 70 else "ref" if total >= 40 else "low"


def relevance(p, scan):
    dl = parse_date(p.get("deadline"))
    p["_dday"] = (dl - scan).days if dl else None
    r = (p.get("B1") or 0) + (p.get("B2") or 0)
    p["_rel"] = "상" if r >= 19 else "중" if r >= 10 else "하"


# ---------- 이력 ----------

def update_history(workdir, scan_iso, groups):
    hp = Path(workdir) / "history.json"
    hist = {"version": 1, "items": {}}
    if hp.exists():
        try:
            hist = json.loads(hp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warn("history.json 을 읽지 못해 새로 만듭니다 (기존 파일은 history.json.bak 으로 보관)")
            hp.replace(hp.with_suffix(".json.bak"))
    items = hist.setdefault("items", {})
    for kind, lst in groups:
        for it in lst:
            k = item_key(it)
            prev = items.get(k)
            first = prev["first_seen"] if prev else scan_iso
            it["_new"] = first == scan_iso
            if kind == "ann":
                res = it["gate"] if it.get("gate") else str(it.get("total"))
            elif kind == "pre":
                res = f"사전조사-{it['_rel']}"
            elif kind == "closed":
                res = "마감"
            else:
                res = "원문확인"
            items[k] = {"title": it.get("title"), "agency": it.get("agency"), "deadline": it.get("deadline"),
                        "url": it.get("url"), "first_seen": first, "last_seen": scan_iso, "result": res}
    hist["last_scan"] = scan_iso
    hp.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- HTML ----------

def dday_badge(d, rolling=False):
    if d is None:
        return '<span class="dd dd-na">상시</span>' if rolling else '<span class="dd dd-na">미상</span>'
    if d < 0:
        return '<span class="dd dd-na">마감</span>'
    cls = "dd-hot" if d <= 7 else "dd-warm" if d <= 20 else "dd-cool"
    return f'<span class="dd {cls}">{"D-day" if d == 0 else f"D-{d}"}</span>'


def link(title, url, new=False):
    u = safe_url(url)
    t = esc(title)
    badge = '<span class="new">NEW</span>' if new else ""
    if u:
        return f'{badge}<a href="{esc(u)}" target="_blank" rel="noopener noreferrer">{t}</a>'
    return f'{badge}<span class="nolink">{t}</span>'


FLAG_CLS = {"긴급": "f-hot", "해외파트너": "f-warn", "미상": "f-muted", "매칭": "f-info", "컨소": "f-info",
            "총액": "f-muted", "추정": "f-muted"}


def flags_html(flags):
    return "".join(f'<span class="flag {FLAG_CLS.get(f, "f-info")}">{esc(f)}</span>' for f in flags or [])


def score_cell(it):
    s = it["scores"]
    b = f"{s['B1']}+{s['B2']}"
    parts = f"A{s['A']} · B{b} · C{s['C']} · D{s['D']} · E{s['E']}" + (f" · F{s['F']}" if s.get("F") else "")
    tip = esc(it.get("basis") or "")
    cls = "sc-top" if it["total"] >= 70 else "sc-ref" if it["total"] >= 40 else "sc-low"
    return f'<div class="score {cls}" title="{tip}"><b>{it["total"]}</b><small>{esc(parts)}</small></div>'


def search_text(*vals):
    return esc(" ".join(str(v) for v in vals if v).lower())


def ann_row(it):
    note = it.get("note") or ""
    if it.get("deadline_note"):
        note = (it["deadline_note"] + " · " + note).strip(" ·")
    sub = f'<div class="sub">{esc(note)}</div>' if note else ""
    dl = esc(it.get("deadline") or "")
    return (f'<tr data-q="{search_text(it.get("title"), it.get("agency"), it.get("ministry"), it.get("type"), note, it.get("basis"), " ".join(it.get("flags") or []))}"'
            f'{" data-new" if it.get("_new") else ""}>'
            f'<td class="t">{link(it.get("title"), it.get("url"), it.get("_new"))}{sub}</td>'
            f'<td class="ag">{esc(it.get("agency"))}<div class="sub">{esc(it.get("ministry"))}</div></td>'
            f'<td class="ty">{esc(it.get("type"))}</td>'
            f'<td>{esc(it.get("budget") or "미상")}</td>'
            f'<td class="nowrap">{dday_badge(it["_dday"], it.get("rolling"))}<div class="sub">{dl}</div></td>'
            f'<td>{score_cell(it)}</td>'
            f'<td>{flags_html(it.get("flags"))}</td></tr>')


ANN_HEAD = ("<thead><tr><th>공고명</th><th>기관</th><th>유형</th><th>예산(과제당)</th><th>마감</th>"
            "<th>적합도</th><th>플래그</th></tr></thead>")


def ann_table(items, empty):
    if not items:
        return f'<p class="empty">{esc(empty)}</p>'
    return f'<div class="tw"><table>{ANN_HEAD}<tbody>{"".join(ann_row(i) for i in items)}</tbody></table></div>'


def urgent_cards(items):
    out = []
    for it in items:
        s = it["scores"]
        out.append(
            f'<article class="card" data-q="{search_text(it.get("title"), it.get("agency"), it.get("type"), it.get("note"), it.get("basis"), " ".join(it.get("flags") or []))}"'
            f'{" data-new" if it.get("_new") else ""}>'
            f'<div class="card-top">{dday_badge(it["_dday"])}<span class="sub">{esc(it.get("deadline"))} 마감</span>'
            f'<span class="card-score">{it["total"]}점</span></div>'
            f'<h3>{link(it.get("title"), it.get("url"), it.get("_new"))}</h3>'
            f'<p class="sub">{esc(it.get("agency"))} · {esc(it.get("type"))} · {esc(it.get("budget") or "예산 미상")}</p>'
            f'<p>{esc(it.get("basis") or it.get("note") or "")}</p>'
            f'<p class="sub">자격·분야·유형 {s["A"] + s["B1"] + s["B2"] + s["C"]}/70점 {flags_html(it.get("flags"))}</p>'
            f'</article>')
    return '<div class="cards">' + "".join(out) + "</div>"


def pre_table(items):
    if not items:
        return '<p class="empty">이번 스캔에서 찾은 사전조사가 없습니다.</p>'
    rows = []
    for p in items:
        note = f'<div class="sub">{esc(p.get("note"))}</div>' if p.get("note") else ""
        rows.append(
            f'<tr data-q="{search_text(p.get("title"), p.get("agency"), p.get("kind"), p.get("note"))}"'
            f'{" data-new" if p.get("_new") else ""}>'
            f'<td><span class="rel rel-{"hi" if p["_rel"] == "상" else "md"}">{p["_rel"]}</span></td>'
            f'<td class="t">{link(p.get("title"), p.get("url"), p.get("_new"))}{note}</td>'
            f'<td>{esc(p.get("kind") or "사전조사")}</td><td>{esc(p.get("agency"))}</td>'
            f'<td class="nowrap">{dday_badge(p["_dday"])}<div class="sub">{esc(p.get("deadline") or "")}</div></td></tr>')
    return ('<div class="tw"><table><thead><tr><th>관련도</th><th>제목</th><th>구분</th><th>기관</th><th>마감</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def gate_table(items):
    rows = "".join(
        f'<tr data-q="{search_text(i.get("title"), i.get("agency"), i.get("gate"))}"{" data-new" if i.get("_new") else ""}>'
        f'<td class="nowrap"><span class="gate">{esc(i["gate"])}</span>{" <small>(추정)</small>" if str(i["gate"]).endswith("?") else ""}</td>'
        f'<td class="t">{link(i.get("title"), i.get("url"), i.get("_new"))}</td><td>{esc(i.get("agency"))}</td>'
        f'<td>{esc(i.get("gate_reason") or "")}</td></tr>' for i in items)
    return ('<div class="tw"><table><thead><tr><th>코드</th><th>공고명</th><th>기관</th><th>근거</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def simple_list(items):
    lis = "".join(
        f'<li data-q="{search_text(i.get("title"), i.get("agency"), i.get("note"))}">{link(i.get("title"), i.get("url"))}'
        f' <span class="sub">— {esc(i.get("agency"))}{(" · ~" + esc(i.get("deadline"))) if i.get("deadline") else ""}'
        f'{(" · " + esc(i.get("note"))) if i.get("note") else ""}</span></li>' for i in items)
    return f"<ul class='plain'>{lis}</ul>"


def source_section(res, srcdoc):
    names = {s["id"]: s for s in (srcdoc or {}).get("sources", [])}

    def nm(i):
        s = names.get(i)
        return esc(s.get("short") or s["name"]) if s else esc(i)

    src = res.get("sources") or {}
    ok = src.get("ok") or []
    failed = src.get("failed") or []
    nq = src.get("not_queried") or []
    parts = []
    if ok:
        parts.append("<p><b>성공</b> " + " · ".join(
            f'{nm(o["id"])}{" " + str(o["found"]) + "건" if o.get("found") is not None else ""}' for o in ok) + "</p>")
    if failed:
        parts.append("<p><b>실패</b></p><ul class='plain'>" + "".join(
            f'<li>{nm(f["id"])} <span class="sub">— {esc(f.get("reason"))}</span></li>' for f in failed) + "</ul>")
    if nq:
        parts.append("<p><b>미조회</b> " + " · ".join(nm(i) for i in nq) + "</p>")
    need = [s for s in names.values() if s.get("fail_count", 0) >= 3 and s.get("status") == "active" and s.get("enabled", True)]
    if need:
        parts.append("<p><b>점검 필요</b> (연속 실패 3회↑) " + " · ".join(
            f'{esc(s.get("short") or s["name"])}' for s in need) + "</p>")
    if res.get("auto_added"):
        parts.append("<p><b>자동 추가된 소스</b></p><ul class='plain'>" + "".join(
            f'<li>{link(a.get("name"), a.get("url"))} <span class="sub">— 원치 않으면 "{esc(a.get("name"))} 소스 삭제"</span></li>'
            for a in res["auto_added"]) + "</ul>")
    if res.get("source_candidates"):
        parts.append("<p><b>소스 후보</b> (목록 페이지 미확인)</p><ul class='plain'>" + "".join(
            f'<li>{esc(c.get("name"))} <span class="sub">— {esc(c.get("reason"))}</span></li>'
            for c in res["source_candidates"]) + "</ul>")
    return "".join(parts) or '<p class="empty">수집 현황 정보가 없습니다.</p>'


CSS = """
:root{--ink:#1b1f24;--muted:#5d6672;--line:#e2e5e9;--bg:#f7f7f5;--panel:#fff;--accent:#0b57a4;
--hot:#b42318;--hot-bg:#fdecea;--warm:#9a5b00;--warm-bg:#fff4e0;--ok:#11663a;--ok-bg:#e6f4ec;--info-bg:#eaf1fa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Pretendard,"Pretendard Variable","Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif;font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:32px 24px 64px}
header h1{font-size:24px;margin:0 0 4px;letter-spacing:-.01em}
header .meta{color:var(--muted);font-size:13.5px;margin:0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin:20px 0}
.stat{background:var(--panel);padding:14px 16px}
.stat b{display:block;font-size:24px;line-height:1.2}
.stat span{color:var(--muted);font-size:13px}
.stat.hot b{color:var(--hot)}
.tools{position:sticky;top:0;z-index:5;background:var(--bg);padding:10px 0;display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.tools input[type=search]{flex:1;min-width:220px;padding:9px 12px;border:1px solid #cfd4da;border-radius:8px;font:inherit;background:#fff}
.tools label{color:var(--muted);font-size:14px;display:flex;gap:6px;align-items:center;cursor:pointer}
nav.toc{display:flex;gap:14px;flex-wrap:wrap;font-size:13.5px}
nav.toc a{color:var(--muted);text-decoration:none}
nav.toc a:hover{color:var(--accent)}
section{margin-top:36px}
section>h2{font-size:17px;margin:0 0 4px;display:flex;align-items:baseline;gap:8px}
section>h2 .n{color:var(--muted);font-weight:500;font-size:14px}
section>p.desc{color:var(--muted);font-size:13.5px;margin:0 0 12px}
.tw{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:860px}
th{font-size:12.5px;color:var(--muted);font-weight:600;text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);background:#fbfbfa;white-space:nowrap}
td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:14px}
tr:last-child td{border-bottom:0}
td.t{min-width:300px;max-width:420px}
td.nowrap{white-space:nowrap}
td.ag{min-width:120px;word-break:keep-all}
td.ty{min-width:96px;word-break:keep-all}
td{word-break:keep-all}
a{color:var(--accent);text-underline-offset:2px}
a:visited{color:#5b3c99}
td.t a,.card h3 a{font-weight:600;text-decoration:none}
td.t a:hover,.card h3 a:hover{text-decoration:underline}
.nolink{font-weight:600}
.sub{color:var(--muted);font-size:12.5px;margin-top:3px}
.new{display:inline-block;font-size:10.5px;font-weight:700;color:#fff;background:var(--accent);border-radius:4px;padding:1px 5px;margin-right:6px;vertical-align:2px}
.dd{display:inline-block;font-weight:700;font-size:13px;border-radius:6px;padding:2px 8px}
.dd-hot{color:var(--hot);background:var(--hot-bg)}
.dd-warm{color:var(--warm);background:var(--warm-bg)}
.dd-cool{color:var(--ok);background:var(--ok-bg)}
.dd-na{color:var(--muted);background:#eef0f2}
.score b{font-size:20px;line-height:1.1;display:block}
.score small{color:var(--muted);font-size:11.5px;white-space:nowrap}
.score[title]:not([title=""]){cursor:help}
.sc-top b{color:var(--ok)}
.flag{display:inline-block;font-size:12px;border-radius:999px;padding:1px 8px;margin:0 4px 4px 0;white-space:nowrap}
.f-hot{background:var(--hot-bg);color:var(--hot);font-weight:700}
.f-warn{background:var(--warm-bg);color:var(--warm)}
.f-info{background:var(--info-bg);color:#1d4f86}
.f-muted{background:#eef0f2;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--hot);border-radius:10px;padding:16px 18px}
.card-top{display:flex;gap:10px;align-items:center}
.card-score{margin-left:auto;font-weight:700}
.card h3{font-size:16px;margin:10px 0 4px;line-height:1.45}
.card p{margin:6px 0;font-size:14px}
.rel{display:inline-block;font-weight:700;font-size:12.5px;border-radius:6px;padding:2px 8px}
.rel-hi{background:var(--ok-bg);color:var(--ok)}
.rel-md{background:#eef0f2;color:var(--muted)}
.gate{font-weight:700;color:var(--hot)}
details{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:0 16px;margin-top:12px}
details>summary{cursor:pointer;padding:12px 0;font-weight:600}
details .tw{border:0;border-radius:0;margin:0 -16px}
ul.plain{margin:6px 0 10px;padding-left:18px}
ul.plain li{margin:4px 0}
.box{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px}
.box p{margin:6px 0}
.empty{color:var(--muted);background:var(--panel);border:1px dashed var(--line);border-radius:10px;padding:14px 18px;margin:0}
footer{margin-top:40px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:16px}
footer p{margin:4px 0}
.hide{display:none!important}
@media (max-width:640px){.wrap{padding:20px 14px 48px}header h1{font-size:20px}}
@media print{.tools{display:none}details{border:0}details:not([open])>*:not(summary){display:block}}
"""

JS = """
(function(){
 var q=document.getElementById('q'),nw=document.getElementById('onlynew');
 function run(){var t=(q.value||'').trim().toLowerCase(),on=nw.checked;
  document.querySelectorAll('[data-q]').forEach(function(el){
   var hit=(!t||el.getAttribute('data-q').indexOf(t)>-1)&&(!on||el.hasAttribute('data-new'));
   el.classList.toggle('hide',!hit);});}
 q.addEventListener('input',run);nw.addEventListener('change',run);
})();
"""


def render(res, srcdoc):
    scan = parse_date(res.get("scan_date")) or dt.date.today()
    anns = res.get("announcements") or []
    pres = res.get("presurveys") or []
    open_anns = [a for a in anns if not (a.get("_dday") is not None and a["_dday"] < 0)]
    urgent = [a for a in open_anns if a.get("_class") in ("top", "ref", "low") and "긴급" in a.get("flags", [])]
    top = [a for a in open_anns if a.get("_class") == "top" and a not in urgent]
    ref = [a for a in open_anns if a.get("_class") == "ref" and a not in urgent]
    low = [a for a in open_anns if a.get("_class") == "low" and a not in urgent]
    gates = [a for a in open_anns if a.get("_class") == "gate"]
    pre_show = [p for p in pres if p["_rel"] in ("상", "중") and not (p["_dday"] is not None and p["_dday"] < 0)]
    unver = res.get("unverified") or []

    def bydd(x):
        return (x["_dday"] is None, x["_dday"] if x["_dday"] is not None else 0)

    for lst in (urgent, top, ref):
        lst.sort(key=bydd)
    low.sort(key=lambda x: -x["total"])
    pre_show.sort(key=lambda p: (p["_rel"] != "상",) + bydd(p))

    scored = [a for a in open_anns if a.get("_class") != "gate"]
    n_new = sum(1 for x in open_anns + pre_show if x.get("_new"))
    q_used, q_bud = res.get("queries_used"), res.get("query_budget", 50)
    weekday = "월화수목금토일"[scan.weekday()]

    h = []
    h.append(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>공고레이더 브리핑 {scan.isoformat()}</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>공고레이더 브리핑</h1>
<p class="meta">{scan.year}년 {scan.month}월 {scan.day}일({weekday}) · {esc(res.get("scan_type") or "전체")} 스캔 · {esc(ORG)} 기준
{f" · 조회 {q_used}/{q_bud}회" if q_used is not None else ""}</p></header>
<div class="stats">
<div class="stat"><b>{len(scored) + len(gates)}</b><span>접수 중 공고</span></div>
<div class="stat"><b>{len(top)}</b><span>즉시 검토 70+</span></div>
<div class="stat hot"><b>{len(urgent)}</b><span>마감 임박·고적합</span></div>
<div class="stat"><b>{len(ref)}</b><span>참고 (40~69)</span></div>
<div class="stat"><b>{len(pre_show)}</b><span>사전조사</span></div>
<div class="stat"><b>{n_new}</b><span>이번에 처음 본 공고</span></div>
</div>
<div class="tools"><input id="q" type="search" placeholder="공고명·기관·유형·플래그로 찾기 (예: 수소, KEIT, 컨소)">
<label><input id="onlynew" type="checkbox"> NEW만 보기</label>
<nav class="toc"><a href="#urgent">마감 임박</a><a href="#top">즉시 검토</a><a href="#ref">참고</a><a href="#pre">사전조사</a><a href="#etc">기타</a><a href="#src">수집 현황</a></nav></div>
""")
    if urgent:
        h.append(f'<section id="urgent"><h2>마감 임박 — 적합도는 높은데 D-7 이내 <span class="n">{len(urgent)}건</span></h2>'
                 '<p class="desc">자격·분야·유형은 최상위권인데 마감이 7일 안에 닥친 공고입니다. 마감 여유 점수가 낮아 총점이 실제 적합도보다 낮게 나옵니다. 오늘 안에 내부 보고 여부를 정하세요.</p>'
                 f'{urgent_cards(urgent)}</section>')
    else:
        h.append('<section id="urgent"><h2>마감 임박</h2><p class="empty">D-7 이내 고적합 공고가 없습니다.</p></section>')
    h.append(f'<section id="top"><h2>즉시 검토 <span class="n">70점 이상 · {len(top)}건{" (긴급 건은 위 칸에)" if any(u["_class"] == "top" for u in urgent) else ""}</span></h2>'
             '<p class="desc">공고명을 누르면 원문이 새 탭으로 열립니다. 점수에 마우스를 올리면 판정 근거가 보입니다.</p>'
             f'{ann_table(top, "70점 이상 공고가 없습니다.")}</section>')
    h.append(f'<section id="ref"><h2>참고 <span class="n">40~69점 · {len(ref)}건</span></h2>'
             f'{ann_table(ref, "해당 공고가 없습니다.")}</section>')
    h.append(f'<section id="pre"><h2>사전조사 <span class="n">수요조사·RFP 공개·사전공고 · {len(pre_show)}건</span></h2>'
             '<p class="desc">공모 전 단계입니다. 여기에 과제를 제안하거나 의견을 내면 내년 RFP에 포항TP 기획이 반영될 수 있습니다. 관련도는 분야·키워드 기준입니다.</p>'
             f'{pre_table(pre_show)}</section>')
    h.append('<section id="etc"><h2>기타</h2>')
    if unver:
        h.append(f'<div class="box"><p><b>원문 확인 필요</b> — 공고는 확인했지만 링크나 기간을 확보하지 못했습니다.</p>{simple_list(unver)}</div>')
    if gates:
        h.append(f'<details><summary>자격 미달 {len(gates)}건 — G1 비영리 불가 · G2 지역 · G3 타 기관·기존 수행자 지정</summary>{gate_table(gates)}</details>')
    if low:
        h.append(f'<details><summary>40점 미만 {len(low)}건 (브리핑 제외 대상, 참고용)</summary>{ann_table(low, "")}</details>')
    if not (unver or gates or low):
        h.append('<p class="empty">해당 없음</p>')
    h.append("</section>")
    h.append(f'<section id="src"><h2>수집 현황</h2><div class="box">{source_section(res, srcdoc)}</div></section>')
    h.append(f"""<footer>
<p>적합도 = A 주관 적격성 25 + B 분야·키워드 25 + C 과제 유형 20 + D 예산 15 + E 마감 여유 15 + F 실행 난이도(−5). 70점 이상 즉시 검토, 40~69점 참고.</p>
<p>긴급 = 마감 D-7 이내이면서 A ≥ 20, A+B+C ≥ 55. 자격 게이트 코드 뒤 "?"는 원문을 열지 못해 제목으로 추정한 것입니다.</p>
<p>이 브리핑은 수집 시점의 공고문 문구를 기준으로 작성했습니다. 신청 전에 원문에서 자격과 마감을 반드시 다시 확인하세요.</p>
</footer></div><script>{JS}</script></body></html>""")
    return "".join(h)


def main():
    ap = argparse.ArgumentParser(description="공고레이더 결과 JSON → HTML 브리핑")
    ap.add_argument("results")
    ap.add_argument("--workdir", default="공고레이더")
    ap.add_argument("--out")
    ap.add_argument("--no-history", action="store_true", help="이력을 읽거나 쓰지 않음 (예시 생성용)")
    a = ap.parse_args()

    res = json.loads(Path(a.results).read_text(encoding="utf-8"))
    scan = parse_date(res.get("scan_date")) or dt.date.today()
    res["scan_date"] = scan.isoformat()
    for it in res.get("announcements") or []:
        score(it, scan)
    for p in res.get("presurveys") or []:
        relevance(p, scan)
    # 마감이 지난 공고가 announcements에 섞여 있으면 closed로 옮긴다
    closed = list(res.get("closed") or [])
    keep = []
    for it in res.get("announcements") or []:
        if it.get("_dday") is not None and it["_dday"] < 0:
            closed.append(it)
            warn(f"[{it.get('title','')[:30]}] 마감이 지나 브리핑에서 뺐습니다")
        else:
            keep.append(it)
    res["announcements"], res["closed"] = keep, closed

    wd = Path(a.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    if not a.no_history:
        update_history(wd, scan.isoformat(), [("ann", res["announcements"]), ("pre", res.get("presurveys") or []),
                                              ("closed", closed), ("unv", res.get("unverified") or [])])
    else:
        for it in res["announcements"] + (res.get("presurveys") or []):
            it["_new"] = False
    srcdoc = None
    sp = wd / "sources.json"
    if sp.exists():
        srcdoc = json.loads(sp.read_text(encoding="utf-8"))
    else:
        dp = Path(__file__).resolve().parent.parent / "data" / "sources.json"
        if dp.exists():
            srcdoc = json.loads(dp.read_text(encoding="utf-8"))
    out = Path(a.out) if a.out else wd / f"브리핑_{scan.strftime('%Y%m%d')}.html"
    out.write_text(render(res, srcdoc), encoding="utf-8")

    anns = res["announcements"]
    top = [x for x in anns if x.get("_class") == "top"]
    urg = [x for x in anns if "긴급" in (x.get("flags") or [])]
    print(f"HTML 생성: {out.resolve()}")
    print(f"접수 중 {len(anns)}건 · 즉시 검토 {len(top)} · 긴급 {len(urg)} · "
          f"사전조사(상·중) {sum(1 for p in res.get('presurveys') or [] if p['_rel'] in ('상', '중'))}")
    for x in sorted(top + [u for u in urg if u not in top], key=lambda x: -x["total"]):
        print(f"  - {x['total']}점 {'[긴급] ' if '긴급' in x['flags'] else ''}{x.get('title')} (마감 {x.get('deadline') or '미상'})")
    if warnings:
        print(f"\n검산 경고 {len(warnings)}건:")
        for w in warnings:
            print("  ! " + w)


if __name__ == "__main__":
    main()
