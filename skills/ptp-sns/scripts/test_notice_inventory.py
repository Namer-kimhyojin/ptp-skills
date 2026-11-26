#!/usr/bin/env python3
"""Offline inventory regressions; no network, browser, or shared-ledger writes."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from contextlib import contextmanager

from notice_inventory import collect_inventory, enrich_listing, parse_application_period, merge_history, _read_local_state
import content_history as real_content_history
import publication_history
from collect_ptp_notice import parse_listing


NOW = datetime(2026, 10, 22, 16, tzinfo=timezone(timedelta(hours=9)))
ACCOUNTS = {"instagram": "pohangtp_official", "facebook": "pohangtpoffcial"}


def row(board_id, status="접수중", date="2026.10.21", pinned=False, cls=None):
    cls = cls or {"접수중": "tag-orange", "접수마감": "tag-off"}.get(status, "tag-blue")
    return (f'<tr title="Notice {board_id}"><td>' + ('<span class="ico-notice">공지</span>' if pinned else '') +
            f'</td><td><a onclick="viewBoard({board_id});">Notice {board_id}</a></td>' +
            (f'<td><span class="tag-d {cls}">{status}</span></td>' if status else '<td></td>') +
            f'<td class="date">{date}</td></tr>')


def listing(rows="", page=1, next_page=False):
    return ('<input name="order_name" value="add_date"><input name="order_type" value="DESC">' +
            f'<input name="viewPage" value="{page}"><div class="board-list"><table>{rows}</table></div>' +
            ('<p class="list_nodata">자료 없음</p>' if not rows else '') +
            (f'<a keyvalue="{page + 1}">다음</a>' if next_page else ''))


def detail(board_id, period="2026-10-21 18시 ~ 2026-10-30 15시"):
    return (f'<input name="board_idx" value="{board_id}"><input name="manage_idx" value="15">' +
            '<div class="board-view"><div class="view-cont-biz">' +
            f'<p class="subject">Notice {board_id}</p><dl><dt>접수기간</dt><dd>{period}</dd></dl></div></div>')


def evaluate(evidence, source_key, now=None):
    # Tests of the date boundary itself belong to notice_eligibility tests.
    period = evidence["application_period"]
    eligible = period["verified"] and evidence["source_status"] == "open"
    if eligible:
        eligible = datetime.fromisoformat(period["start"]) <= now < datetime.fromisoformat(period["end"])
    return {"eligible": eligible}


def content_inspect(latest, key, publication_latest=None, verify_files=True):
    value = latest.get(key, {})
    status = value.get("status", "not_recorded")
    return {"status": status, "can_create": status == "not_recorded", "requires_recovery": value.get("requires_recovery", False)}


CONTENT_MODULE = types.SimpleNamespace(inspect=content_inspect)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.mock = patch.dict("sys.modules", {"content_history": CONTENT_MODULE})
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def run_catalog(self, lists, details, **kwargs):
        calls = []
        def fetch(url):
            calls.append(url)
            query = parse_qs(urlsplit(url).query)
            if "board_idx" in query:
                value = details[query["board_idx"][0]]
            else:
                value = lists.get((query["bid_search"][0], int(query["viewPage"][0])), listing())
            if isinstance(value, Exception):
                raise value
            final_url = url
            if isinstance(value, tuple):
                value, final_url = value
            return value.encode("utf-8"), {"final_url": final_url, "http_status": 200, "content_type": "text/html"}
        with tempfile.TemporaryDirectory() as directory:
            report = collect_inventory(Path(directory), fetch=fetch, now=NOW, evaluate_fn=evaluate,
                content_latest=kwargs.pop("content_latest", {}), publication_latest=kwargs.pop("publication_latest", {}), accounts=ACCOUNTS, **kwargs)
            saved = json.loads((Path(directory) / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(report, saved)
            self.assertTrue((Path(directory) / "inventory.csv").read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertIn("공통 장부", (Path(directory) / "status.md").read_text(encoding="utf-8"))
            for evidence in report["listing_evidence"]:
                self.assertEqual(len(evidence["sha256"]), 64)
        return report, calls

    def test_real_row_status_overrides_filter_and_dedups_pinned(self):
        lists = {("ongoing", 1): listing(row(10, "접수마감", pinned=True) + row(20)),
                 ("after", 1): listing(row(10, "접수마감"))}
        report, calls = self.run_catalog(lists, {"10": detail(10), "20": detail(20)})
        self.assertTrue(report["complete"])
        self.assertEqual(report["candidate_source_keys"], ["ptp:15:20"])
        self.assertEqual(len(report["notices"]), 2)
        self.assertEqual(sum("board_idx=10" in url for url in calls), 1)
        self.assertEqual(report["notices"][1]["listing_status"], "closed")

    def test_full_ongoing_pagination_and_bounded_closed_scope(self):
        lists = {("ongoing", 1): listing(row(20), next_page=True),
                 ("ongoing", 2): listing(row(19, date="2026.10.20"), page=2),
                 ("after", 1): listing(row(10, "접수마감"), next_page=True)}
        report, calls = self.run_catalog(lists, {str(i): detail(i) for i in (10, 19, 20)})
        self.assertTrue(report["complete"])
        self.assertEqual(report["candidate_source_keys"], ["ptp:15:20", "ptp:15:19"])
        self.assertFalse(any("bid_search=after" in url and "viewPage=2" in url for url in calls))

    def test_max_pages_and_detail_failures_disable_all_candidates(self):
        for kwargs, details in (({"max_pages": 1}, {"20": detail(20)}), ({}, {"20": ValueError("network fixture failure")})):
            report, _ = self.run_catalog({("ongoing", 1): listing(row(20), next_page=True)}, details, **kwargs)
            self.assertFalse(report["complete"])
            self.assertEqual(report["candidate_source_keys"], [])
            self.assertTrue(report["errors"])

    def test_repeated_pagination_cannot_claim_complete(self):
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20), next_page=True),
                                     ("ongoing", 2): listing(row(20), page=2)}, {"20": detail(20)})
        self.assertFalse(report["complete"])
        self.assertIn("repeats", " ".join(report["errors"]))

    def test_unordered_rows_are_accepted_only_for_complete_inventory(self):
        html = listing(row(19, date="2025.10.31") + row(20, date="2026.07.20"))
        with self.assertRaises(ValueError):
            parse_listing(html, "https://www.ptp.or.kr/main/board/index.do")
        report, _ = self.run_catalog({("ongoing", 1): html}, {"20": detail(20), "19": detail(19)})
        self.assertTrue(report["complete"])
        self.assertEqual(report["candidate_source_keys"], ["ptp:15:20", "ptp:15:19"])
        self.assertTrue(report["warnings"])
        self.assertFalse(report["listing_evidence"][0]["regular_date_order_confirmed"])

    def test_cross_page_date_order_can_be_sorted_after_full_collection(self):
        report, _ = self.run_catalog({("ongoing", 1): listing(row(19, date="2025.10.31"), next_page=True),
                                     ("ongoing", 2): listing(row(20, date="2026.07.20"), page=2)},
                                    {"20": detail(20), "19": detail(19)})
        self.assertTrue(report["complete"])
        self.assertEqual(report["candidate_source_keys"], ["ptp:15:20", "ptp:15:19"])
        self.assertTrue(report["warnings"])

    def test_wrong_response_page_and_partial_overlap_cannot_claim_complete(self):
        for second in (listing(row(19), page=1), listing(row(20) + row(19), page=2)):
            report, _ = self.run_catalog({("ongoing", 1): listing(row(20), next_page=True), ("ongoing", 2): second},
                                        {"20": detail(20), "19": detail(19)})
            self.assertFalse(report["complete"])
            self.assertEqual(report["candidate_source_keys"], [])

    def test_detail_redirect_to_other_notice_blocks_catalog_candidate(self):
        redirected = "https://www.ptp.or.kr/main/board/view.do?menu_idx=116&manage_idx=15&board_idx=21"
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20))},
                                    {"20": (detail(20), redirected)})
        self.assertFalse(report["complete"])
        self.assertEqual(report["candidate_source_keys"], [])
        self.assertIn("detail_error", report["notices"][0])
        self.assertEqual(report["notices"][0]["detail_evidence"]["final_url"], redirected)
        self.assertEqual(len(report["notices"][0]["detail_evidence"]["sha256"]), 64)

    def test_missing_or_conflicting_badge_is_unknown(self):
        for html in (listing(row(20, "")), listing(row(20, "접수중", cls="tag-off"))):
            parsed = enrich_listing(html, "https://www.ptp.or.kr/main/board/index.do", "fixture.html")
            self.assertEqual(parsed["rows"][0]["listing_status"], "unknown")

    def test_period_precise_time_and_invalid_or_ambiguous_block(self):
        good = parse_application_period({"접수기간": "2026-10-21 18시 ~ 2026-10-30 15시 30분"}, "detail.html")
        self.assertEqual(good["start"], "2026-10-21T18:00:00+09:00")
        self.assertEqual(good["end"], "2026-10-30T15:30:00+09:00")
        for fields in ({}, {"접수기간": "상시"}, {"접수기간": "2026-10-21 ~ 2026-02-30"},
                       {"접수기간": "2026-10-30 18시 ~ 2026-10-21 15시"},
                       {"접수기간": "2026-10-21 ~ 2026-10-30", "신청기간": "2026-10-21 ~ 2026-11-01"},
                       {"사업기간": "2026-10-21 ~ 2026-10-30"}):
            self.assertFalse(parse_application_period(fields, "detail.html")["verified"])
        self.assertEqual(parse_application_period({"신청 기간": "2026-10-21 ~ 2026-10-30"}, "detail.html")["end"], "2026-10-30")

    def test_future_closed_and_unknown_period_not_candidates(self):
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20) + row(19)),
                                     ("before", 1): listing(row(21, "접수전"))},
            {"20": detail(20, "2026-10-21 18시 ~ 2026-10-22 15시"), "19": detail(19, "상시"), "21": detail(21)})
        self.assertTrue(report["complete"])
        self.assertEqual(report["candidate_source_keys"], [])

    def test_produced_reuse_and_producing_never_new_creation(self):
        content = {"ptp:15:20": {"status": "produced"}, "ptp:15:19": {"status": "producing"}}
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20) + row(19))},
                                    {"20": detail(20), "19": detail(19)}, content_latest=content)
        self.assertEqual(report["creation_candidate_source_keys"], [])
        self.assertEqual(report["reuse_candidate_source_keys"], ["ptp:15:20"])
        self.assertEqual(report["notices"][1]["content_label"], "제작 중")

    def test_produced_missing_files_requires_recovery_no_regeneration(self):
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20))}, {"20": detail(20)},
            content_latest={"ptp:15:20": {"status": "produced", "requires_recovery": True}})
        self.assertEqual(report["notices"][0]["content_label"], "확인 필요")
        self.assertEqual(report["candidate_source_keys"], [])

    def test_published_and_unresolved_block_new_candidate_and_keep_links(self):
        events = {platform: {"attempt_id": platform, "source_key": "ptp:15:20", "platform": platform,
            "account": publication_history.canonical_account(account, platform),
            "status": "published" if platform == "instagram" else "unknown", "recorded_at": NOW.isoformat(),
            "manifest_sha256": "0" * 64, "remote_url": "https://www.instagram.com/p/example/" if platform == "instagram" else None}
            for platform, account in ACCOUNTS.items()}
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20))}, {"20": detail(20)}, publication_latest=events)
        self.assertEqual(report["candidate_source_keys"], [])
        self.assertEqual(report["notices"][0]["platforms"]["instagram"]["label"], "게시 완료")
        self.assertEqual(report["notices"][0]["platforms"]["facebook"]["label"], "확인 필요")

    def test_known_history_outside_listing_is_not_lost(self):
        report, _ = self.run_catalog({}, {}, content_latest={"ptp:15:8190": {"status": "produced"}})
        self.assertEqual(report["notices"][0]["source_key"], "ptp:15:8190")
        self.assertEqual(report["notices"][0]["content_label"], "제작 완료")
        self.assertEqual(report["candidate_source_keys"], [])

    def test_detail_limit_and_unknown_structure_record_failure(self):
        report, _ = self.run_catalog({("ongoing", 1): listing(row(20) + row(19))}, {"20": detail(20)}, max_details=1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["candidate_source_keys"], [])
        report, _ = self.run_catalog({("ongoing", 1): "<html>Error page</html>"}, {})
        self.assertFalse(report["complete"])
        self.assertEqual(report["listing_evidence"][0]["parse_status"], "pending")

    def test_nonempty_directory_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "keep.txt").write_text("keep")
            with self.assertRaises(ValueError):
                collect_inventory(Path(directory), fetch=lambda url: None)

    def test_partial_publication_last_line_blocks_read_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory) / "content.jsonl"
            publication = Path(directory) / "publication.jsonl"
            publication.write_text('{"truncated":true}', encoding="utf-8")
            with patch.dict("sys.modules", {"content_history": real_content_history}), \
                 patch.object(real_content_history, "DEFAULT_LEDGER", content), \
                 patch.object(real_content_history, "DEFAULT_PUBLICATION_LEDGER", publication), \
                 patch.object(publication_history, "read_latest") as reader:
                with self.assertRaises(publication_history.HistoryError):
                    _read_local_state(None, None, ACCOUNTS)
                reader.assert_not_called()
            self.assertEqual(publication.read_text(), '{"truncated":true}')
            self.assertFalse(list(Path(directory).glob("*.lock")))

    def test_snapshot_lock_order_matches_production_writer(self):
        events = []
        @contextmanager
        def tracking_lock(path):
            events.append(("enter", path.name))
            yield
            events.append(("exit", path.name))
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory) / "content.jsonl"
            publication = Path(directory) / "publication.jsonl"
            with patch.dict("sys.modules", {"content_history": real_content_history}), \
                 patch.object(real_content_history, "DEFAULT_LEDGER", content), \
                 patch.object(real_content_history, "DEFAULT_PUBLICATION_LEDGER", publication), \
                 patch.object(publication_history, "ledger_lock", tracking_lock):
                self.assertEqual(_read_local_state(None, None, ACCOUNTS), ({}, {}, ACCOUNTS))
        self.assertEqual(events, [("enter", "content.jsonl"), ("enter", "publication.jsonl"),
                                  ("exit", "publication.jsonl"), ("exit", "content.jsonl")])


if __name__ == "__main__":
    unittest.main()
