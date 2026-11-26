#!/usr/bin/env python3
"""공고레이더 수집 소스 관리.

작업 폴더의 sources.json을 다룬다. 파이썬 표준 라이브러리만 쓴다.

  init     기본 소스를 작업 폴더에 복사 (--merge: 스킬에 새로 생긴 기본 소스만 추가)
  list     소스 목록 (--tier N, --all, --json)
  plan     이번 스캔의 조회 순서
  mark     조회 결과 기록 (--result ok|fail)
  check    목록 URL HTTP 접속 점검
  add      소스 추가 (--origin auto 이면 자동 추가)
  remove   소스 삭제 (되돌릴 수 있게 removed 상태로 보관)
  restore  삭제한 소스 되돌리기
  set      필드 수정
"""
import argparse
import datetime as dt
import json
import re
import shutil
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = SKILL_DIR / "data" / "sources.json"
PRIORITIES = ["필수", "상", "중", "하"]
METHODS = ["api>websearch", "webfetch>websearch", "websearch>webfetch", "webfetch", "websearch", "iris"]
VERIFIED = ["F", "F*", "S", "미확인", "API"]
FAIL_LIMIT = 3
LOW_PRIORITY_DAYS = 7


def today():
    return dt.date.today().isoformat()


def die(msg):
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(1)


def src_path(workdir):
    return Path(workdir) / "sources.json"


def load(workdir):
    p = src_path(workdir)
    if not p.exists():
        die(f"{p} 가 없습니다. 먼저 'sources.py init --workdir {workdir}' 를 실행하세요.")
    return json.loads(p.read_text(encoding="utf-8"))


def save(workdir, doc):
    p = src_path(workdir)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def norm_url(u):
    u = (u or "").strip()
    pr = urllib.parse.urlsplit(u)
    host = pr.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host + pr.path.rstrip("/") + ("?" + pr.query if pr.query else "")


def domain(u):
    host = urllib.parse.urlsplit((u or "").strip()).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def find(doc, key, include_removed=False):
    k = (key or "").strip().lower()
    hits = []
    for s in doc["sources"]:
        if not include_removed and s.get("status") == "removed":
            continue
        if k in (s["id"].lower(), (s.get("short") or "").lower(), s["name"].lower()):
            hits.append(s)
    if not hits:
        die(f"'{key}' 소스를 찾지 못했습니다. 'sources.py list --all' 로 id를 확인하세요.")
    if len(hits) > 1:
        die(f"'{key}' 에 해당하는 소스가 여러 개입니다: {', '.join(h['id'] for h in hits)}. id로 지정하세요.")
    return hits[0]


def state_label(s):
    if s.get("status") == "removed":
        return "삭제됨"
    if not s.get("enabled", True):
        return "비활성"
    if s.get("fail_count", 0) >= FAIL_LIMIT:
        return "점검 필요"
    return "사용"


def make_id(doc, name, short):
    base = re.sub(r"[^a-z0-9]+", "-", (short or "").lower()).strip("-")
    if not base:
        base = "src"
    ids = {s["id"] for s in doc["sources"]}
    cand, n = base, 2
    while cand in ids or cand == "src":
        cand = f"{base}-{n}"
        n += 1
    return cand


def parse_bool(v):
    if isinstance(v, bool):
        return v
    v = str(v).strip().lower()
    if v in ("true", "1", "yes", "y", "예", "on"):
        return True
    if v in ("false", "0", "no", "n", "아니오", "off"):
        return False
    die(f"true/false 값이 아닙니다: {v}")


# ---------- commands ----------

def cmd_init(a):
    wd = Path(a.workdir)
    wd.mkdir(parents=True, exist_ok=True)
    p = src_path(wd)
    default = json.loads(DEFAULT_SOURCES.read_text(encoding="utf-8"))
    if not p.exists():
        shutil.copyfile(DEFAULT_SOURCES, p)
        print(f"기본 소스 {len(default['sources'])}개를 {p} 에 복사했습니다.")
        return
    if not a.merge:
        doc = load(wd)
        active = sum(1 for s in doc["sources"] if s.get("status") != "removed")
        print(f"{p} 가 이미 있습니다 (소스 {active}개). 스킬의 새 기본 소스를 더하려면 --merge.")
        return
    doc = load(wd)
    have = {s["id"] for s in doc["sources"]}  # 삭제한 소스도 id가 남아 있으므로 되살아나지 않는다
    added = [s for s in default["sources"] if s["id"] not in have]
    doc["sources"].extend(added)
    save(wd, doc)
    print(f"새 기본 소스 {len(added)}개 추가: {', '.join(s['short'] for s in added) or '없음'}")


def cmd_list(a):
    doc = load(a.workdir)
    rows = [s for s in doc["sources"] if a.all or (s.get("status") != "removed" and s.get("enabled", True))]
    if a.tier:
        rows = [s for s in rows if s["tier"] == a.tier]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    rows.sort(key=lambda s: (s["tier"], PRIORITIES.index(s["priority"]) if s["priority"] in PRIORITIES else 9, s["name"]))
    print("| id | 기관 | Tier | 우선 | 조회 방법 | 검증 | 사전조사 | 최근 결과 | 상태 | 출처 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for s in rows:
        last = "-"
        if s.get("last_checked"):
            r = "성공" if s.get("last_result") == "ok" else "실패"
            found = f" {s['last_found']}건" if s.get("last_found") not in (None, "") and s.get("last_result") == "ok" else ""
            fails = f" (연속 {s['fail_count']}회)" if s.get("fail_count") else ""
            last = f"{s['last_checked']} {r}{found}{fails}"
        origin = {"default": "기본", "user": "사용자", "auto": "자동"}.get(s.get("origin"), s.get("origin", ""))
        print(f"| {s['id']} | {s['name']} ({s.get('short','')}) | {s['tier']} | {s['priority']} | {s['method']} | "
              f"{s['verified']} | {'O' if s.get('presurvey') else ''} | {last} | {state_label(s)} | {origin} |")
    total = len(rows)
    warn = [s["id"] for s in rows if state_label(s) == "점검 필요"]
    print(f"\n총 {total}개" + (f" · 점검 필요: {', '.join(warn)}" if warn else ""))


def cmd_plan(a):
    doc = load(a.workdir)
    ref = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    active = [s for s in doc["sources"] if s.get("status") != "removed" and s.get("enabled", True)]
    groups = {"필수": [], "상": [], "중": [], "하": []}
    skipped = []
    for s in active:
        p = s["priority"] if s["priority"] in groups else "중"
        if p == "하":
            lc = s.get("last_checked")
            if lc and (ref - dt.date.fromisoformat(lc)).days < LOW_PRIORITY_DAYS:
                skipped.append(s)
                continue
        groups[p].append(s)
    budget = {"필수": "소스당 2회 (상한 12)", "상": "소스당 1회, 실패 시 검색 1회 (상한 18)",
              "중": "남은 예산 안에서 소스당 1회", "하": "7일 경과분만, 예산이 남을 때"}
    n = 0
    print(f"# 조회 계획 ({ref.isoformat()}) — 총 50회 이내, 사전조사 검색 6회 별도 확보\n")
    for g in ["필수", "상", "중", "하"]:
        if not groups[g]:
            continue
        print(f"## {g} — {budget[g]}")
        for s in sorted(groups[g], key=lambda x: (x["tier"], x["name"])):
            n += 1
            tags = []
            if s["method"] == "iris":
                tags.append("IRIS로 대체" + (" · 사전조사 확인만" if s.get("presurvey") else " · 자체 조회 안 함"))
            if s["verified"] == "F*":
                tags.append("JS 렌더링 → 검색 우선")
            if s.get("monitor_only"):
                tags.append("모니터링 전용 · 채점 안 함")
            if s.get("api"):
                tags.append("API 가능(키 필요)")
            if s.get("presurvey"):
                tags.append("사전조사 게시")
            if s.get("fail_count", 0) >= FAIL_LIMIT:
                tags.append(f"연속 실패 {s['fail_count']}회")
            print(f"{n}. [{s['id']}] {s['name']} — {s['method']} — {s['url']}" + (f"  ({'; '.join(tags)})" if tags else ""))
        print()
    if skipped:
        print("## 이번에 건너뜀 (하, 최근 7일 내 조회)")
        print(", ".join(f"{s['id']}({s['last_checked']})" for s in skipped))


def cmd_mark(a):
    doc = load(a.workdir)
    s = find(doc, a.id)
    s["last_checked"] = a.date or today()
    s["last_result"] = a.result
    if a.result == "ok":
        s["fail_count"] = 0
        s["last_found"] = a.found
    else:
        s["fail_count"] = s.get("fail_count", 0) + 1
        s["last_found"] = None
    if a.note:
        s["last_note"] = a.note
    msg = f"[{s['id']}] {s['name']}: {'성공' if a.result == 'ok' else '실패'}"
    if a.result == "fail":
        msg += f" (연속 {s['fail_count']}회)"
        if s["fail_count"] >= FAIL_LIMIT:
            if s.get("origin") == "auto":
                s["enabled"] = False
                s["status"] = "disabled"
                msg += " → 자동 추가 소스라 비활성화했습니다"
            else:
                msg += " → 점검 필요 (URL 재확인)"
    save(a.workdir, doc)
    print(msg)


def cmd_check(a):
    doc = load(a.workdir)
    targets = [find(doc, a.id)] if a.id else [s for s in doc["sources"] if s.get("status") != "removed" and s.get("enabled", True)]
    ctx = ssl.create_default_context()
    print("| id | 기관 | HTTP | 비고 |")
    print("| --- | --- | --- | --- |")
    bad = 0
    for s in targets:
        url = s["url"]
        code, note = None, ""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (announcement-radar source check)"})
            with urllib.request.urlopen(req, timeout=a.timeout, context=ctx) as r:
                code = r.status
                final = r.geturl()
                if norm_url(final) != norm_url(url):
                    note = f"리다이렉트 → {final}"
        except urllib.error.HTTPError as e:
            code, note = e.code, "HTTP 오류"
        except ssl.SSLError as e:
            note = "SSL 오류 (WebFetch로 확인)"
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            note = "SSL 오류 (WebFetch로 확인)" if isinstance(reason, ssl.SSLError) else f"접속 실패: {reason}"
        except Exception as e:  # timeout 등
            note = f"접속 실패: {type(e).__name__}"
        ok = code is not None and 200 <= code < 400
        if not ok:
            bad += 1
        s["http_status"] = code
        s["http_checked"] = today()
        if s.get("verified") == "F*" and ok:
            note = (note + " · " if note else "") + "열리지만 목록은 JS 렌더링"
        print(f"| {s['id']} | {s['name']} | {code if code else '-'} | {note} |")
    save(a.workdir, doc)
    print(f"\n점검 {len(targets)}개 · 응답 이상 {bad}개. HTTP 응답은 '페이지가 열리는가'만 보여줍니다. "
          "게시물이 실제로 보이는지는 WebFetch로 확인하세요.")


def cmd_add(a):
    doc = load(a.workdir)
    if not re.match(r"^https?://", a.url or ""):
        die("URL은 http:// 또는 https:// 로 시작해야 합니다.")
    nu, dom = norm_url(a.url), domain(a.url)
    for s in doc["sources"]:
        if norm_url(s["url"]) == nu:
            die(f"같은 URL이 이미 있습니다: [{s['id']}] {s['name']} ({state_label(s)})"
                + (" — 'restore' 로 되살리세요." if s.get("status") == "removed" else ""))
        if s["name"].strip() == a.name.strip() and s.get("status") != "removed":
            die(f"같은 이름의 소스가 이미 있습니다: [{s['id']}]")
    same_dom = [s for s in doc["sources"] if domain(s["url"]) == dom and s.get("status") != "removed"]
    if same_dom and (a.origin == "auto" or not a.allow_same_domain):
        die(f"같은 도메인({dom})의 소스가 이미 있습니다: {', '.join(s['id'] for s in same_dom)}. "
            "다른 게시판을 따로 등록하려면 --allow-same-domain (자동 추가에는 허용 안 됨).")
    priority = a.priority or ("하" if a.origin == "auto" else "중")
    if priority not in PRIORITIES:
        die(f"우선순위는 {', '.join(PRIORITIES)} 중 하나")
    if a.method not in METHODS:
        die(f"조회 방법은 {', '.join(METHODS)} 중 하나")
    if a.verified not in VERIFIED:
        die(f"검증 표기는 {', '.join(VERIFIED)} 중 하나")
    short = a.short or a.name
    sid = a.id or make_id(doc, a.name, a.short)
    if any(s["id"] == sid for s in doc["sources"]):
        die(f"id '{sid}' 가 이미 있습니다.")
    src = dict(id=sid, name=a.name, short=short, tier=a.tier, ministry=a.ministry or "", url=a.url.strip(), api="",
               method=a.method, iris=a.iris, fields=a.fields or "", priority=priority, verified=a.verified,
               presurvey=bool(a.presurvey), monitor_only=False, enabled=True, status="active", origin=a.origin,
               added=today(), last_checked=None, last_result=None, last_found=None, fail_count=0, note=a.note or "")
    doc["sources"].append(src)
    save(a.workdir, doc)
    kind = "자동 추가" if a.origin == "auto" else "추가"
    print(f"{kind}: [{sid}] {a.name} — Tier {a.tier} · 우선 {priority} · {a.url}")


def cmd_remove(a):
    doc = load(a.workdir)
    s = find(doc, a.id)
    s["status"] = "removed"
    s["enabled"] = False
    s["removed"] = today()
    save(a.workdir, doc)
    print(f"삭제: [{s['id']}] {s['name']} — {s['url']}\n되돌리려면: sources.py restore --workdir {a.workdir} --id {s['id']}")


def cmd_restore(a):
    doc = load(a.workdir)
    s = find(doc, a.id, include_removed=True)
    s["status"] = "active"
    s["enabled"] = True
    s["fail_count"] = 0
    s.pop("removed", None)
    save(a.workdir, doc)
    print(f"복원: [{s['id']}] {s['name']}")


def cmd_set(a):
    doc = load(a.workdir)
    s = find(doc, a.id, include_removed=True)
    changes = []
    for field in ["name", "short", "url", "ministry", "fields", "note", "iris", "api"]:
        v = getattr(a, field)
        if v is not None:
            if field == "url" and not re.match(r"^https?://", v):
                die("URL은 http:// 또는 https:// 로 시작해야 합니다.")
            s[field] = v
            changes.append(field)
    if a.tier is not None:
        s["tier"] = a.tier; changes.append("tier")
    if a.priority is not None:
        if a.priority not in PRIORITIES:
            die(f"우선순위는 {', '.join(PRIORITIES)} 중 하나")
        s["priority"] = a.priority; changes.append("priority")
    if a.method is not None:
        if a.method not in METHODS:
            die(f"조회 방법은 {', '.join(METHODS)} 중 하나")
        s["method"] = a.method; changes.append("method")
    if a.verified is not None:
        if a.verified not in VERIFIED:
            die(f"검증 표기는 {', '.join(VERIFIED)} 중 하나")
        s["verified"] = a.verified; changes.append("verified")
    if a.presurvey is not None:
        s["presurvey"] = parse_bool(a.presurvey); changes.append("presurvey")
    if a.enabled is not None:
        s["enabled"] = parse_bool(a.enabled)
        s["status"] = "active" if s["enabled"] else "disabled"
        if s["enabled"]:
            s["fail_count"] = 0
        changes.append("enabled")
    if "url" in changes:
        s["fail_count"] = 0
    if not changes:
        die("바꿀 값을 하나 이상 지정하세요.")
    save(a.workdir, doc)
    print(f"수정: [{s['id']}] {s['name']} — {', '.join(changes)}")


def main():
    ap = argparse.ArgumentParser(description="공고레이더 수집 소스 관리")
    ap.add_argument("--workdir", default="공고레이더", help="작업 폴더 (기본: ./공고레이더)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def wd(p):
        p.add_argument("--workdir", default=argparse.SUPPRESS)
        return p

    p = wd(sub.add_parser("init")); p.add_argument("--merge", action="store_true"); p.set_defaults(fn=cmd_init)
    p = wd(sub.add_parser("list")); p.add_argument("--tier", type=int); p.add_argument("--all", action="store_true")
    p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_list)
    p = wd(sub.add_parser("plan")); p.add_argument("--date"); p.set_defaults(fn=cmd_plan)
    p = wd(sub.add_parser("mark")); p.add_argument("--id", required=True)
    p.add_argument("--result", required=True, choices=["ok", "fail"]); p.add_argument("--found", type=int)
    p.add_argument("--note"); p.add_argument("--date"); p.set_defaults(fn=cmd_mark)
    p = wd(sub.add_parser("check")); p.add_argument("--id"); p.add_argument("--timeout", type=float, default=10)
    p.set_defaults(fn=cmd_check)
    p = wd(sub.add_parser("add"))
    p.add_argument("--name", required=True); p.add_argument("--url", required=True)
    p.add_argument("--tier", type=int, required=True, choices=[1, 2, 3])
    p.add_argument("--short"); p.add_argument("--id"); p.add_argument("--priority"); p.add_argument("--ministry")
    p.add_argument("--method", default="webfetch>websearch"); p.add_argument("--iris", default="?")
    p.add_argument("--fields"); p.add_argument("--verified", default="미확인"); p.add_argument("--presurvey", action="store_true")
    p.add_argument("--origin", default="user", choices=["user", "auto"]); p.add_argument("--note")
    p.add_argument("--allow-same-domain", action="store_true"); p.set_defaults(fn=cmd_add)
    p = wd(sub.add_parser("remove")); p.add_argument("--id", required=True); p.set_defaults(fn=cmd_remove)
    p = wd(sub.add_parser("restore")); p.add_argument("--id", required=True); p.set_defaults(fn=cmd_restore)
    p = wd(sub.add_parser("set")); p.add_argument("--id", required=True)
    for f in ["name", "short", "url", "ministry", "fields", "note", "iris", "api", "priority", "method", "verified",
              "presurvey", "enabled"]:
        p.add_argument(f"--{f}")
    p.add_argument("--tier", type=int, choices=[1, 2, 3]); p.set_defaults(fn=cmd_set)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
