#!/usr/bin/env python3
"""Read-only PTP notice inventory and provisional SNS candidate screening.

The catalog covers every observed ongoing/upcoming page (bounded by --max-pages)
and the first recently closed page. It does not claim to inventory all historical
notices or posts created outside the shared skill ledgers. No SNS post, credential
access, attachment download, or ledger mutation is performed.
"""

from __future__ import annotations

import argparse
import csv
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, parse_qs, urlsplit

from collect_ptp_notice import (BASE, LIST_URL, Document, PublicClient, first_class,
                               parse_detail, parse_listing, save_evidence, validate_detail_url)
import publication_history


SKILL_ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
STATUS_LABELS = {"접수중": "open", "접수전": "upcoming", "접수마감": "closed",
                 "접수종료": "closed", "취소": "cancelled", "공고취소": "cancelled"}
PLATFORM_LABELS = {"published": "게시 완료", "scheduled": "예약 완료", "submitting": "게시 처리 중",
                   "unknown": "확인 필요", "failed": "실패 확인", "not_recorded": "게시 기록 없음"}
CONTENT_LABELS = {"produced": "제작 완료", "producing": "제작 중", "not_recorded": "제작 기록 없음",
                  "failed": "확인 필요", "unknown": "확인 필요"}


def parse_inventory_listing(html: str, listing_url: str) -> dict:
    """Full inventory can sort after collecting all pages; latest-only cannot.

    Preserve the collector's structure/date/order-request validation. The one
    relaxed constraint is observed row date ordering: PTP can put an older
    unpinned row group before a newer ordinary row even with add_date DESC.
    """
    doc = Document(html).root
    values = {n.attrs.get("name"): n.attrs.get("value") for n in doc.walk() if n.tag == "input"}
    requested = parse_qs(urlsplit(listing_url).query).get("viewPage")
    if requested and values.get("viewPage") != requested[0]:
        raise ValueError("Returned listing page does not match the requested page")
    try:
        result = parse_listing(html, listing_url)
        result["regular_date_order_confirmed"] = True
        return result
    except ValueError as exc:
        if str(exc) != "Regular rows are not registration-date descending; cannot establish latest notice":
            raise
    # parse_listing validated all rows before its date-order-only rejection.
    # Rebuild those same validated fields without changing the original HTML.
    rows = []
    for row in first_class(doc, "board-list").walk():
        if row.tag != "tr":
            continue
        link = next((n for n in row.walk() if n.tag == "a" and re.search(r"viewBoard\(\s*\d+", n.attrs.get("onclick", ""))), None)
        if link is None:
            continue
        board_id = re.search(r"viewBoard\(\s*(\d+)", link.attrs["onclick"]).group(1)
        registered = datetime.strptime(first_class(row, "date").text(), "%Y.%m.%d").date().isoformat()
        rows.append({"board_id": board_id, "title": (row.attrs.get("title") or link.text()).strip(),
                     "registration_date": registered, "date_precision": "day",
                     "pinned": first_class(row, "ico-notice") is not None, "listing_url": listing_url,
                     "detail_url": f"{BASE}/main/board/view.do?menu_idx=116&manage_idx=15&board_idx={board_id}"})
    pages = [int(n.attrs["keyvalue"]) for n in doc.walk() if n.tag == "a" and n.attrs.get("keyvalue", "").isdigit()]
    return {"rows": rows, "regular_rows": [row for row in rows if not row["pinned"]],
            "has_next": max(pages, default=1) > int(values.get("viewPage") or 1),
            "regular_date_order_confirmed": False}


def enrich_listing(html: str, listing_url: str, evidence_path: str) -> dict:
    """Get status from each actual row, including pinned rows bypassing filters."""
    parsed = parse_inventory_listing(html, listing_url)
    board = first_class(Document(html).root, "board-list")
    metadata = {}
    for row in board.walk():
        if row.tag != "tr":
            continue
        link = next((n for n in row.walk() if n.tag == "a" and re.search(r"viewBoard\(\s*\d+", n.attrs.get("onclick", ""))), None)
        if link is None:
            continue
        board_id = re.search(r"viewBoard\(\s*(\d+)", link.attrs["onclick"]).group(1)
        badges = [n for n in row.walk() if n.has_class("tag-d")]
        labels = [n.text() for n in badges]
        states = {STATUS_LABELS.get(label, "unknown") for label in labels}
        state = next(iter(states)) if len(states) == 1 else "unknown"
        # Existing PTP colors with a contrary label indicate a changed/conflicting UI.
        if any((n.has_class("tag-off") and state not in {"closed", "cancelled"}) or
               (n.has_class("tag-orange") and state != "open") for n in badges):
            state = "unknown"
        item = {"listing_status": state, "listing_status_raw": " / ".join(labels),
                "listing_status_classes": [n.attrs.get("class", "") for n in badges],
                "source_status_evidence": {"path": evidence_path,
                    "location": f"board-list tr viewBoard({board_id}) .tag-d", "raw_text": " / ".join(labels)}}
        if board_id in metadata and metadata[board_id] != item:
            raise ValueError(f"Conflicting duplicate row status for board {board_id}")
        metadata[board_id] = item
    for row in parsed["rows"]:
        row.update(metadata[row["board_id"]])
    return parsed


def parse_application_period(fields: dict, evidence_path: str) -> dict:
    """Parse only explicit labeled application dates; do not infer from titles."""
    matches = [(key, value) for key, value in fields.items() if key.replace(" ", "") in {"접수기간", "신청기간"}]
    raw = " | ".join(f"{key}: {value}" for key, value in matches)
    result = {"purpose": "application", "verified": False, "kind": "unknown", "start": None, "end": None,
              "evidence": {"path": evidence_path, "location": "view-cont-biz dl dt/dd application-period", "raw_text": raw}}
    if not matches:
        result["parse_error"] = "접수기간 또는 신청기간 필드 없음"
        return result
    if len({re.sub(r"\s+", "", value) for _, value in matches}) != 1:
        result["parse_error"] = "접수기간과 신청기간 필드가 서로 다름"
        return result
    value = matches[0][1].strip()
    result["evidence"]["raw_text"] = value
    result["evidence"]["location"] = "view-cont-biz dl dt=" + matches[0][0]
    date_part = r"(?P<{p}date>\d{{4}}[-.]\d{{1,2}}[-.]\d{{1,2}})(?:\s*\([월화수목금토일]\))?"
    time_part = r"(?:\s+(?P<{p}hour>\d{{1,2}})(?:시(?:\s*(?P<{p}km>\d{{1,2}})분)?|:(?P<{p}cm>\d{{2}})))?"
    endpoint = date_part + time_part
    pattern = endpoint.format(p="s") + r"\s*[~∼～]\s*" + endpoint.format(p="e")
    match = re.fullmatch(pattern, value)
    if not match:
        result["parse_error"] = "단일 명시적 시작·마감 일시로 해석할 수 없음; 원문 검토 필요"
        return result
    try:
        for prefix, key in (("s", "start"), ("e", "end")):
            year, month, day = map(int, re.split(r"[-.]", match[prefix + "date"]))
            hour = match[prefix + "hour"]
            minute = match[prefix + "km"] or match[prefix + "cm"] or "0"
            value_dt = datetime(year, month, day, int(hour or 0), int(minute), tzinfo=KST)
            result[key] = value_dt.isoformat() if hour is not None else value_dt.date().isoformat()
        if result["start"][:10] > result["end"][:10] or (len(result["start"]) > 10 and len(result["end"]) > 10 and result["start"] > result["end"]):
            raise ValueError("마감이 시작보다 빠름")
    except ValueError as exc:
        result.update(start=None, end=None, parse_error="유효하지 않은 접수일시: " + str(exc))
        return result
    result.update(verified=True, kind="bounded")
    return result


def _read_local_state(content_latest, publication_latest, accounts):
    """Validated readers are fail-closed; no malformed ledger is treated as empty."""
    import content_history
    # Match the registry writer's fixed content -> publication lock order.
    # Hold locks only for the local snapshot, never while fetching web pages.
    with ExitStack() as locks:
        if content_latest is None:
            locks.enter_context(publication_history.ledger_lock(content_history.DEFAULT_LEDGER))
        if publication_latest is None:
            locks.enter_context(publication_history.ledger_lock(content_history.DEFAULT_PUBLICATION_LEDGER))
        if content_latest is None:
            content_latest = content_history.read_latest(content_history.DEFAULT_LEDGER)
        if publication_latest is None:
            content_history.complete_lines(content_history.DEFAULT_PUBLICATION_LEDGER)
            publication_latest = publication_history.read_latest(content_history.DEFAULT_PUBLICATION_LEDGER)
    if accounts is None:
        config = json.loads((SKILL_ROOT / "config" / "social-accounts.json").read_text(encoding="utf-8-sig"))
        accounts = {platform: config[platform]["account_id"] for platform in ("instagram", "facebook")}
    for platform in ("instagram", "facebook"):
        publication_history.canonical_account(accounts[platform], platform)
    return content_latest, publication_latest, accounts


def merge_history(notice: dict, content_latest: dict, publication_latest: dict, accounts: dict) -> dict:
    import content_history
    source_key = notice["source_key"]
    result = content_history.inspect(content_latest, source_key, publication_latest=publication_latest, verify_files=True)
    status = result.get("status", "unknown")
    if status == "producing":
        label = "제작 중"
    elif result.get("requires_recovery"):
        label = "확인 필요"
    else:
        label = CONTENT_LABELS.get(status, "확인 필요")
    platform_states = {}
    for platform, account in accounts.items():
        target = (source_key, platform, publication_history.canonical_account(account, platform))
        check = publication_history.inspect(publication_latest, target, None)
        matching = [event for event in publication_latest.values() if publication_history.key(event) == target]
        blockers = check["blocking_attempts"]
        # A successful/unresolved earlier attempt must never be hidden by a failed one.
        priority = {"published": 5, "scheduled": 4, "unknown": 3, "submitting": 2, "failed": 1}
        chosen = max(blockers or matching, key=lambda item: (priority.get(item["status"], 0), item.get("recorded_at", "")), default=None)
        state = chosen["status"] if chosen else "not_recorded"
        platform_states[platform] = {"status": state, "label": PLATFORM_LABELS[state], "account": target[2],
                                     "allowed": check["allowed"], "remote_url": (chosen or {}).get("remote_url"),
                                     "blocking_attempt_count": len(blockers)}
    return {"content_status": status, "content_label": label, "content_requires_recovery": bool(result.get("requires_recovery")),
            "can_create": bool(result.get("can_create", result.get("allowed", False))), "platforms": platform_states}


def _write_outputs(output_dir: Path, report: dict):
    (output_dir / "inventory.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    columns = ["공고번호", "공고명", "등록일", "접수상태", "원문접수기간", "카드뉴스", "인스타그램", "페이스북", "후보", "공고URL", "인스타그램URL", "페이스북URL"]
    with (output_dir / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for notice in report["notices"]:
            channels = notice.get("platforms", {})
            values = [notice["board_id"], notice["title"], notice.get("registration_date", ""), notice.get("listing_status_raw", "확인 필요"),
                      notice.get("application_period_raw", ""), notice.get("content_label", "확인 필요"), channels.get("instagram", {}).get("label", "확인 필요"),
                      channels.get("facebook", {}).get("label", "확인 필요"), "신규 제작 후보" if notice.get("candidate_for_creation") else "기존 제작물 재사용 후보" if notice.get("candidate_for_reuse") else "제외",
                      notice["detail_url"], channels.get("instagram", {}).get("remote_url") or "", channels.get("facebook", {}).get("remote_url") or ""]
            # Avoid spreadsheet formulas in source-controlled public text.
            writer.writerow([("'" + str(v)) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
    def cell(value):
        return str(value or "—").replace("|", "\\|").replace("\n", " ")
    lines = ["# 사업공고 제작·게시 현황", "", f"확인시각: {report['collected_at']}", "",
             "범위: 접수중·접수전 전체 페이지(설정 상한 이내), 최근 접수마감 첫 페이지, 공통 이력에 남은 공고.",
             "‘제작 기록 없음’은 이 스킬 공통 장부에 기록이 없다는 뜻입니다. 다른 경로에서 제작·게시한 이력은 별도 대조가 필요합니다.",
             "후보는 홈페이지 접수기간에 따른 1차 선별입니다. 첨부 공고문과 정정·취소 여부를 대조한 최종 게시 검증이 별도로 필요합니다.", "",
             f"수집 완전성: {'설정 범위 수집 완료' if report['complete'] else '일부 확인 필요 — 자동 후보 선택 중지'}", "",
             "| 번호 | 공고명 | 접수상태 / 기간 | 카드뉴스 | Instagram | Facebook | 선별 |", "|---|---|---|---|---|---|---|"]
    for notice in report["notices"]:
        channels = notice.get("platforms", {})
        def channel(platform):
            value = channels.get(platform, {})
            label = cell(value.get("label", "확인 필요"))
            return f"[{label}]({value['remote_url']})" if value.get("remote_url") else label
        lines.append("| " + " | ".join([notice["board_id"], f"[{cell(notice['title'])}]({notice['detail_url']})",
            cell(notice.get("listing_status_raw")) + " / " + cell(notice.get("application_period_raw")), cell(notice.get("content_label", "확인 필요")),
            channel("instagram"), channel("facebook"), "신규 제작 후보" if notice.get("candidate_for_creation") else "기존 제작물 재사용 후보" if notice.get("candidate_for_reuse") else cell(notice.get("exclusion_reason", "확인 필요"))]) + " |")
    if report["errors"]:
        lines += ["", "## 확인이 필요한 항목", ""] + ["- " + cell(error) for error in report["errors"]]
    lines += ["", "이 목록 작성으로 새 카드뉴스나 SNS 게시물이 생성되지는 않습니다.", ""]
    (output_dir / "status.md").write_text("\n".join(lines), encoding="utf-8")


def collect_inventory(output_dir: Path, timeout: int = 30, max_bytes: int = 5 * 1024 * 1024,
                      max_pages: int = 100, max_details: int = 50, *, fetch=None, now=None,
                      content_latest=None, publication_latest=None, accounts=None, evaluate_fn=None) -> dict:
    if not 1 <= max_pages <= 100 or not 1 <= max_details <= 500 or timeout < 1:
        raise ValueError("max-pages must be 1..100; max-details 1..500; timeout positive")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty to preserve collection evidence")
    now = now or datetime.now(KST)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires explicit timezone")
    if evaluate_fn is None:
        from notice_eligibility import evaluate
        evaluate_fn = evaluate
    client = PublicClient(timeout, max_bytes) if fetch is None else None
    fetch = fetch or client.fetch
    report = {"schema_version": 1, "collected_at": now.isoformat(), "source_url": LIST_URL, "complete": True,
              "publication_ready": False, "errors": [], "warnings": [], "listing_evidence": [], "notices": [],
              "scope": {"open_and_upcoming": "all pages within configured bounds", "closed": "first recent page only",
                        "max_pages_per_partition": max_pages, "max_detail_pages": max_details,
                        "history": "shared skill ledgers only; absence is not proof of never created externally",
                        "attachment_review": "not performed; candidate screening only"}, "partitions": {}, "candidate_source_keys": []}
    try:
        content_latest, publication_latest, accounts = _read_local_state(content_latest, publication_latest, accounts)
        history_ok = True
    except Exception as exc:
        report["errors"].append("Shared history unavailable: " + str(exc))
        content_latest, publication_latest, accounts, history_ok = {}, {}, {}, False
    unique = {}
    for status in ("ongoing", "before", "after"):
        previous_tail = None
        seen_regular = set()
        partition = {"pages": 0, "complete": False, "limited_to_recent_first_page": status == "after"}
        report["partitions"][status] = partition
        for page in range(1, (1 if status == "after" else max_pages) + 1):
            query = {"menu_idx": "116", "manage_idx": "15", "bid_search": status, "order_name": "add_date", "order_type": "DESC", "viewPage": str(page)}
            url = BASE + "/main/board/index.do?" + urlencode(query)
            try:
                data, metadata = fetch(url)
                evidence = save_evidence(output_dir, f"listing-{status}-{page}.html", data)
                evidence["path"] = str((output_dir / evidence["path"]).resolve())
                listing_record = {"status_filter": status, "page": page, "url": url,
                                  "parse_status": "pending", **metadata, **evidence}
                report["listing_evidence"].append(listing_record)
                listing = enrich_listing(data.decode("utf-8-sig"), url, evidence["path"])
                regular = listing["regular_rows"]
                if not listing["regular_date_order_confirmed"] or (previous_tail and regular and regular[0]["registration_date"] > previous_tail):
                    report["warnings"].append(f"Listing {status} page {page} is not date-descending; inventory collects every page and sorts the complete observed set locally.")
                ids = {row["board_id"] for row in regular}
                if page > 1 and ids & seen_regular:
                    raise ValueError("Pagination repeats prior rows; cannot establish complete inventory")
                seen_regular.update(ids)
                for row in listing["rows"]:
                    old = unique.get(row["board_id"])
                    if old and any(old[key] != row[key] for key in ("title", "registration_date", "listing_status")):
                        old["listing_conflict"] = True
                        old["listing_status"] = "unknown"
                        report["errors"].append(f"Conflicting listing metadata for board {row['board_id']}")
                    else:
                        unique.setdefault(row["board_id"], dict(row, observed_in=[]))
                    unique[row["board_id"]]["observed_in"].append({"status_filter": status, "page": page})
                listing_record.update(row_count=len(listing["rows"]), parse_status="parsed",
                                      regular_date_order_confirmed=listing["regular_date_order_confirmed"])
                partition["pages"] += 1
                if status == "after" or not listing["has_next"]:
                    partition["complete"] = True
                    break
                if not regular:
                    raise ValueError("Next page advertised but no regular rows are present")
                previous_tail = regular[-1]["registration_date"]
            except Exception as exc:
                report["errors"].append(f"Listing {status} page {page}: {exc}")
                break
        if not partition["complete"]:
            report["errors"].append(f"Incomplete {status} partition; automatic candidate selection disabled")
    ordered = sorted(unique.values(), key=lambda item: (item["registration_date"], int(item["board_id"])), reverse=True)
    for index, row in enumerate(ordered):
        notice = dict(row, source_key="ptp:15:" + row["board_id"], publication_ready=False,
                      candidate_for_creation=False, candidate_for_reuse=False, candidate_action=None)
        report["notices"].append(notice)
        if history_ok:
            try:
                notice.update(merge_history(notice, content_latest, publication_latest, accounts))
            except Exception as exc:
                report["errors"].append(f"History {notice['source_key']}: {exc}")
                notice.update(content_status="unknown", content_label="확인 필요", can_create=False)
        else:
            notice.update(content_status="unknown", content_label="확인 필요", can_create=False)
        if index >= max_details:
            notice["exclusion_reason"] = "상세 확인 상한 도달"
            report["errors"].append(f"Detail limit reached for {notice['source_key']}")
            continue
        try:
            data, metadata = fetch(row["detail_url"])
            evidence = save_evidence(output_dir, f"detail-{row['board_id']}.html", data)
            evidence["path"] = str((output_dir / evidence["path"]).resolve())
            notice["detail_evidence"] = {**metadata, **evidence}
            validate_detail_url(metadata.get("final_url", ""), row["board_id"])
            detail = parse_detail(data.decode("utf-8-sig"), row)
            period = parse_application_period(detail["fields"], evidence["path"])
            notice.update(detail_evidence={**metadata, **evidence}, detail_fields=detail["fields"],
                          application_period_raw=period["evidence"]["raw_text"], application_period=period,
                          attachment_count=len(detail["attachments"]), attachment_reviewed=False)
            eligibility_evidence = {"schema_version": 1, "source_key": notice["source_key"], "source_url": row["detail_url"],
                "checked_at": now.isoformat(), "source_status": row["listing_status"],
                "source_status_evidence": row["source_status_evidence"], "application_period": period}
            notice["period_evidence"] = eligibility_evidence
            notice["period_screening"] = evaluate_fn(eligibility_evidence, notice["source_key"], now=now)
            eligible = bool(notice["period_screening"].get("eligible", notice["period_screening"].get("allowed", False)))
            notice["period_screening_provisional"] = True
            duplicate_free = all(notice.get("platforms", {}).get(platform, {}).get("allowed") for platform in ("instagram", "facebook"))
            notice["candidate_for_creation"] = bool(eligible and row["listing_status"] == "open" and
                notice.get("content_status") == "not_recorded" and notice.get("can_create") and duplicate_free)
            notice["available_platforms"] = [platform for platform in ("instagram", "facebook")
                                            if notice.get("platforms", {}).get(platform, {}).get("allowed")]
            notice["candidate_for_reuse"] = bool(eligible and row["listing_status"] == "open" and
                notice.get("content_status") == "produced" and not notice.get("content_requires_recovery") and
                notice["available_platforms"])
            notice["candidate_action"] = "create" if notice["candidate_for_creation"] else "reuse" if notice["candidate_for_reuse"] else None
            if not notice["candidate_action"]:
                if notice.get("content_status") != "not_recorded":
                    reason = notice.get("content_label", "제작 이력 확인 필요")
                elif not duplicate_free:
                    reason = "게시 완료·처리 중 이력 또는 확인 필요"
                else:
                    reason = "접수기간 또는 원문 상태 확인 필요" if row["listing_status"] == "open" else "접수중 아님"
                notice["exclusion_reason"] = reason
        except Exception as exc:
            notice["exclusion_reason"] = "상세 정보 확인 실패"
            notice["detail_error"] = str(exc)
            report["errors"].append(f"Detail {notice['source_key']}: {exc}")
    # Preserve evidence of already known work even when outside this listing scope.
    known_keys = set(content_latest) | {event["source_key"] for event in publication_latest.values()}
    observed_keys = {notice["source_key"] for notice in report["notices"]}
    for source_key in sorted(known_keys - observed_keys):
        match = re.fullmatch(r"ptp:15:(\d+)", source_key)
        if not match:
            continue
        notice = {"source_key": source_key, "board_id": match[1], "title": "공통 이력에 있는 공고 (이번 목록 범위 밖)",
                  "detail_url": f"{BASE}/main/board/view.do?menu_idx=116&manage_idx=15&board_idx={match[1]}",
                  "listing_status": "unknown", "listing_status_raw": "이번 목록 미관측", "publication_ready": False,
                  "candidate_for_creation": False, "candidate_for_reuse": False, "candidate_action": None,
                  "exclusion_reason": "현재 접수기간 재확인 필요", "observed_in": []}
        try:
            notice.update(merge_history(notice, content_latest, publication_latest, accounts))
        except Exception as exc:
            report["errors"].append(f"History {source_key}: {exc}")
        report["notices"].append(notice)
    report["complete"] = not report["errors"]
    if not report["complete"]:
        for notice in report["notices"]:
            if notice.get("candidate_action"):
                notice.update(candidate_for_creation=False, candidate_for_reuse=False, candidate_action=None, exclusion_reason="수집·이력 확인 미완료")
    report["candidate_source_keys"] = [notice["source_key"] for notice in report["notices"] if notice.get("candidate_action")]
    report["creation_candidate_source_keys"] = [notice["source_key"] for notice in report["notices"] if notice["candidate_for_creation"]]
    report["reuse_candidate_source_keys"] = [notice["source_key"] for notice in report["notices"] if notice.get("candidate_for_reuse")]
    report["summary"] = {"notices": len(report["notices"]), "observed_notices": len(unique),
                         "creation_candidates": len(report["creation_candidate_source_keys"]),
                         "reuse_candidates": len(report["reuse_candidate_source_keys"]),
                         "made": sum(notice.get("content_status") == "produced" for notice in report["notices"]),
                         "no_creation_record": sum(notice.get("content_status") == "not_recorded" for notice in report["notices"])}
    if client:
        report["warnings"].extend(client.warnings)
    _write_outputs(output_dir, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-pages", default=100, type=int)
    parser.add_argument("--max-details", default=50, type=int)
    parser.add_argument("--timeout", default=30, type=int)
    args = parser.parse_args(argv)
    try:
        report = collect_inventory(args.output_dir, timeout=args.timeout, max_pages=args.max_pages, max_details=args.max_details)
        print(json.dumps({"complete": report["complete"], **report["summary"], "candidate_source_keys": report["candidate_source_keys"],
            "inventory": str((args.output_dir / "inventory.json").resolve()), "errors": report["errors"]}, ensure_ascii=False))
        return 0 if report["complete"] else 2
    except Exception as exc:
        print(json.dumps({"complete": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
