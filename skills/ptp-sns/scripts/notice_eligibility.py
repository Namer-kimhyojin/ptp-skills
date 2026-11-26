#!/usr/bin/env python3
"""Fail-closed application-window gate for PTP notice publication.

This validates declarations and time bounds, not their truth: the caller must
read the live official notice, resolve corrections, and retain source evidence.
Only application periods count; project performance periods are not substitutes.
Python 3.10+ standard library only. Production CLI always uses the real clock.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

KST = timezone(timedelta(hours=9))
MAX_EVIDENCE_AGE = timedelta(minutes=30)
MAX_FUTURE_SKEW = timedelta(seconds=60)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
DATETIME_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})\Z"
)
SOURCE_KEY_RE = re.compile(r"ptp:15:([1-9]\d*)\Z")
STATUSES = {"open", "upcoming", "closed", "cancelled", "unknown"}


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not DATETIME_RE.fullmatch(value):
        raise ValueError("ISO datetime with explicit timezone required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(KST)


def _bound(value: object, *, end: bool) -> tuple[datetime, str]:
    if isinstance(value, str) and DATE_RE.fullmatch(value):
        day = date.fromisoformat(value)
        # A date-only deadline includes the full Korean calendar day. Do not
        # invent a business-hour deadline when the source does not state one.
        return datetime.combine(day, time.max if end else time.min, KST), "day"
    return _timestamp(value), "datetime"


def _provenance(value: object) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(key), str) and bool(value[key].strip())
        for key in ("path", "location", "raw_text")
    )


def _official_source(url: object, source_key: str) -> bool:
    match = SOURCE_KEY_RE.fullmatch(source_key)
    if match is None or not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        return (
            parsed.scheme == "https"
            and parsed.hostname == "www.ptp.or.kr"
            and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and parsed.path == "/main/board/view.do"
            and not parsed.fragment
            and params.get("menu_idx") == ["116"]
            and params.get("manage_idx") == ["15"]
            and params.get("board_idx") == [match.group(1)]
        )
    except (TypeError, ValueError):
        return False


def evaluate(evidence: dict, source_key: str, now: datetime | None = None,
             scheduled_at: str | None = None) -> dict:
    """Return deterministic eligibility; ``now`` injection is for unit tests.

    Both exact deadlines and date-only deadlines are inclusive. Evidence must
    be refreshed immediately before submission even after this check passes.
    A scheduled post needs a fresh check again before its actual release.
    Open-ended notices may be posted now but cannot be scheduled in the future.
    """
    result = {
        "schema_version": 1, "source_key": source_key, "allowed": False,
        "state": "unknown", "reasons": [], "evaluated_at": None,
        "evidence_validation_only": True,
        "requires_live_official_check": True,
        "max_evidence_age_seconds": int(MAX_EVIDENCE_AGE.total_seconds()),
    }
    reasons = result["reasons"]
    current = datetime.now(KST) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None or current.utcoffset() is None:
        reasons.append("evaluation_time_requires_timezone")
        return result
    current = current.astimezone(KST)
    result["evaluated_at"] = current.isoformat()
    if not isinstance(evidence, dict):
        reasons.append("evidence_object_required")
        return result
    if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != 1:
        reasons.append("unsupported_schema_version")
    if not isinstance(source_key, str) or SOURCE_KEY_RE.fullmatch(source_key) is None:
        reasons.append("invalid_source_key")
    if evidence.get("source_key") != source_key:
        reasons.append("source_key_mismatch")
    if not isinstance(source_key, str) or not _official_source(evidence.get("source_url"), source_key):
        reasons.append("official_source_url_mismatch")

    checked = None
    try:
        checked = _timestamp(evidence.get("checked_at"))
        result["checked_at"] = checked.isoformat()
        age = current - checked
        if age > MAX_EVIDENCE_AGE:
            reasons.append("evidence_stale")
        if age < -MAX_FUTURE_SKEW:
            reasons.append("evidence_from_future")
    except (ValueError, TypeError, OverflowError):
        reasons.append("invalid_checked_at")

    source_status = evidence.get("source_status")
    if not isinstance(source_status, str) or source_status not in STATUSES:
        source_status = "unknown"
        reasons.append("invalid_source_status")
    if source_status != "open":
        reasons.append("source_status_" + source_status)
    if not _provenance(evidence.get("source_status_evidence")):
        reasons.append("source_status_evidence_required")

    period = evidence.get("application_period")
    if not isinstance(period, dict):
        period = {}
        reasons.append("application_period_required")
    if period.get("purpose") != "application":
        reasons.append("application_period_purpose_required")
    if period.get("verified") is not True:
        reasons.append("application_period_not_verified")
    if not _provenance(period.get("evidence")):
        reasons.append("application_period_evidence_required")
    kind = period.get("kind")
    if kind not in ("bounded", "open-ended"):
        reasons.append("invalid_application_period_kind")
    start = end = None
    try:
        start, start_precision = _bound(period.get("start"), end=False)
        result["application_start"] = start.isoformat()
        result["start_precision"] = start_precision
    except (ValueError, TypeError, OverflowError):
        reasons.append("invalid_application_start")
    if kind == "bounded":
        try:
            end, end_precision = _bound(period.get("end"), end=True)
            result["application_end"] = end.isoformat()
            result["end_precision"] = end_precision
        except (ValueError, TypeError, OverflowError):
            reasons.append("invalid_application_end")
        if start is not None and end is not None and end < start:
            reasons.append("application_end_before_start")
    elif kind == "open-ended":
        if not isinstance(period.get("condition"), str) or not period["condition"].strip():
            reasons.append("open_ended_official_condition_required")
        elif not _provenance(period.get("evidence")) or period["condition"].strip() not in period["evidence"]["raw_text"]:
            reasons.append("open_ended_condition_not_in_evidence")
        if period.get("end") is not None:
            reasons.append("open_ended_period_must_not_have_end")

    if start is not None and current < start:
        reasons.append("application_not_started")
    if end is not None and current > end:
        reasons.append("application_closed")

    scheduled = None
    if scheduled_at is not None:
        try:
            scheduled = _timestamp(scheduled_at)
            result["scheduled_at"] = scheduled.isoformat()
            result["requires_recheck_at_release"] = True
            if scheduled < current:
                reasons.append("schedule_in_past")
            if start is not None and scheduled < start:
                reasons.append("schedule_before_application_start")
            if end is not None and scheduled > end:
                reasons.append("schedule_after_application_end")
            if kind == "open-ended" and scheduled > current:
                reasons.append("open_ended_future_schedule_not_allowed")
        except (ValueError, TypeError, OverflowError):
            reasons.append("invalid_scheduled_at")

    # Terminal source states prevail; contradictions and missing evidence never
    # turn an uncertain notice into a publishable one.
    if source_status == "cancelled":
        result["state"] = "cancelled"
    elif source_status == "closed" or "application_closed" in reasons:
        result["state"] = "closed"
    elif source_status == "upcoming" or "application_not_started" in reasons:
        result["state"] = "upcoming"
    elif not reasons:
        result["state"] = "open"
        result["allowed"] = True
    if checked is not None:
        try:
            expires = checked + MAX_EVIDENCE_AGE
            result["recheck_no_later_than"] = min(expires, end).isoformat() if end is not None else expires.isoformat()
        except OverflowError:
            # Extreme but valid ISO years must fail closed instead of crashing
            # a caller that is evaluating an untrusted evidence document.
            reasons.append("invalid_checked_at")
            result["allowed"] = False
            result["state"] = "unknown"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--source-key", required=True)
    parser.add_argument("--scheduled-at", help="Scheduled release ISO datetime with explicit timezone")
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(json.dumps({"allowed": False, "state": "unknown", "reasons": ["evidence_file_unreadable"],
                          "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    result = evaluate(evidence, args.source_key, scheduled_at=args.scheduled_at)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
