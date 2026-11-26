#!/usr/bin/env python3
"""Track new public PTP board rows and enforce the monitored publication gap."""
from __future__ import annotations

import argparse
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode

from collect_ptp_notice import BASE, PublicClient
from notice_inventory import parse_inventory_listing
from publication_history import ledger_lock, read_latest
from social_runtime import ROOT, atomic_json, current_time, load, stamp

BOARDS = {"2": "113", "15": "116"}
INTERVAL = timedelta(hours=2)


def is_board_notice(key):
    parts = key.split(":")
    return len(parts) == 3 and parts[0] == "ptp" and parts[1] in BOARDS and parts[2].isdigit()


def next_slot(source_key, history):
    latest = None
    for event in history.values():
        key = event["source_key"]
        if not is_board_notice(key) or key == source_key:
            continue
        status = event["status"]
        if status in {"submitting", "unknown", "scheduled"}:
            raise ValueError("other_notice_submission_requires_reconciliation:" + key)
        if status == "published":
            when = stamp(event.get("published_at") or event["recorded_at"])
            latest = when if latest is None else max(when, latest)
    return latest + INTERVAL if latest is not None else None


def check_window(plan, source_key, history, now):
    """Called by the shared runtime before work and immediately before submitting."""
    policy = load(plan["board_monitor"])
    if policy["schema_version"] != 1 or policy["interval_minutes"] != 120:
        raise ValueError("invalid_board_monitor_policy")
    state = load(policy["state_path"])
    if source_key in policy.get("held_keys", []):
        raise ValueError("notice_on_hold")
    board = source_key.split(":")[1]
    if board in state.get("errors", {}) or not timedelta(0) <= now - stamp(state["boards"][board]) <= timedelta(hours=1):
        raise ValueError("recent_board_scan_required")
    row = state["notices"][source_key]
    if row["kind"] not in {"backlog", "new"}:
        raise ValueError("notice_not_in_monitored_queue")
    not_before = max(stamp(policy["start_at"]), stamp(row["eligible_at"]))
    slot = next_slot(source_key, history)
    if slot is not None:
        not_before = max(not_before, slot)
    if now < not_before:
        raise ValueError("two_hour_wait_not_elapsed")


def announcement_evidence(evidence, source_key, planned_publish_at):
    now = current_time()
    expected = BASE + "/main/board/view.do?" + urlencode(
        dict(menu_idx=113, manage_idx=2, board_idx=source_key.split(":")[-1]))
    if (planned_publish_at or evidence["source_key"] != source_key or evidence["source_url"] != expected
            or evidence["status"] != "public-current"
            or not timedelta(0) <= now - stamp(evidence["checked_at"]) <= timedelta(minutes=30)):
        raise ValueError("fresh_public_announcement_evidence_required")
    path = Path(evidence["detail_path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["detail_sha256"]:
        raise ValueError("announcement_detail_evidence_changed")
    deadline = evidence["deadline"]
    if deadline is not None:
        stamp(deadline)
        if evidence.get("deadline_precision") not in {"day", "datetime"}:
            raise ValueError("announcement_deadline_precision_required")
    return {"allowed": True, "reasons": [], "evaluated_at": now.isoformat(),
            "application_end": deadline, "end_precision": evidence.get("deadline_precision")}


def collect_board(client, board, since):
    rows = {}
    for page in range(1, 21):
        url = BASE + "/main/board/index.do?" + urlencode(dict(menu_idx=BOARDS[board],
            manage_idx=board, order_name="add_date", order_type="DESC", viewPage=page))
        raw, _ = client.fetch(url)
        observed = current_time()
        result = parse_inventory_listing(raw.decode("utf-8"), url)
        for row in result["rows"]:
            ident = row["board_id"]
            rows.setdefault(f"ptp:{board}:{ident}", dict(
                title=row["title"], registration_date=row["registration_date"], listing_url=url,
                detail_url=BASE + "/main/board/view.do?" + urlencode(dict(menu_idx=BOARDS[board],
                    manage_idx=board, board_idx=ident)), listing_sha256=hashlib.sha256(raw).hexdigest(),
                first_seen_at=observed.isoformat()))
        # One extra page covers same-day rows even if the site reorders pinned groups.
        regular = result["regular_rows"]
        if not result["has_next"] or (page >= 2 and regular and all(r["registration_date"] < since for r in regular)):
            return rows
    raise ValueError("board_scan_page_limit_reached")


def scan(policy_path):
    policy = load(policy_path)
    path = Path(policy["state_path"])
    client = PublicClient(timeout=12, max_bytes=3_000_000)
    path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_lock(path):
        state = load(path) if path.exists() else {"boards": {}, "notices": {}}
        now = current_time()
        for key, record in policy["backlog"].items():
            state["notices"].setdefault(key, dict(record, kind="backlog", eligible_at=policy["start_at"]))
        errors = {}
        for board in BOARDS:
            previous = state["boards"].get(board)
            since = stamp(previous).date().isoformat() if previous else now.date().isoformat()
            try:
                rows = collect_board(client, board, since)
            except (OSError, ValueError) as exc:
                errors[board] = str(exc)
                continue
            for key, row in rows.items():
                if key in state["notices"]:
                    continue
                first_seen = stamp(row["first_seen_at"])
                day_start = stamp(row["registration_date"] + "T00:00:00+09:00")
                kind = "new" if previous and row["registration_date"] >= since else "baseline"
                state["notices"][key] = dict(row, kind=kind,
                    eligible_at=(max(first_seen, day_start) + INTERVAL).isoformat())
            state["boards"][board] = now.isoformat()
        state["errors"] = errors
        atomic_json(path, state)
    history = read_latest(ROOT / "state" / "publication-history.jsonl")
    statuses = {}
    for event in history.values():
        statuses.setdefault(event["source_key"], {}).setdefault(event["platform"], set()).add(event["status"])
    candidates = []
    for key, row in state["notices"].items():
        if row["kind"] == "baseline" or key.split(":")[1] in errors:
            continue
        if all(statuses.get(key, {}).get(channel, set()) & {"published", "scheduled"} for channel in ("instagram", "facebook")):
            continue
        try:
            check_window({"board_monitor": str(policy_path)}, key, history, current_time())
            reason = None
        except (OSError, ValueError, KeyError) as exc:
            reason = str(exc)
        candidates.append(dict(row, source_key=key, window_block=reason))
    candidates.sort(key=lambda row: (row["kind"] != "backlog", row.get("priority", 0), row.get("first_seen_at", ""), row["source_key"]))
    return {"checked_at": current_time().isoformat(), "errors": errors, "candidates": candidates}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(scan(args.policy), indent=2))
