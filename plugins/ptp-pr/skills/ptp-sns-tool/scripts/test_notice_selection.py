#!/usr/bin/env python3
"""Offline explicit-inventory selection tests; no network or shared-state access."""
import json
import io
from contextlib import redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import collect_ptp_notice as collector
from test_notice_collector import listing, row


def detail(board_id="20", title="Notice 20", identity=True):
    fields = (f'<input name="board_idx" value="{board_id}"><input name="manage_idx" value="15">'
              if identity else "")
    return fields + f'<div class="board-view"><div class="view-cont-biz"><p class="subject">{title}</p></div></div>'


def url(board_id):
    return f"{collector.BASE}/main/board/view.do?menu_idx=116&manage_idx=15&board_idx={board_id}"


class NoticeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = self.root / "inventory.json"
        self.candidate = {"board_id": "20", "title": "Notice 20", "registration_date": "2026-10-20",
                          "detail_url": url("20"), "source_key": "ptp:15:20"}
        self.notices = [self.candidate]
        self.listing_html = listing(row(21, "2026.10.21") + row(20, "2026.10.20"))
        self.detail_html = None
        self.final_url = None
        self.requests = []

    def fetch(self, request_url):
        self.requests.append(request_url)
        if "/index.do?" in request_url:
            return self.listing_html.encode("utf-8"), {"final_url": request_url, "http_status": 200}
        self.assertIn("/view.do?", request_url)
        selected = "21" if "board_idx=21" in request_url else self.candidate["board_id"]
        html = self.detail_html if self.detail_html is not None else detail(selected, "Notice " + selected)
        return html.encode("utf-8"), {"final_url": self.final_url or request_url, "http_status": 200}

    def collect(self, board_id="20", inventory_data=None):
        self.inventory.write_text(json.dumps({"notices": self.notices} if inventory_data is None else inventory_data), encoding="utf-8")
        with patch.object(collector, "PublicClient") as client:
            client.return_value.fetch.side_effect = self.fetch
            client.return_value.warnings = []
            return collector.collect(self.root / "evidence", board_id=board_id,
                                     inventory_path=self.inventory if board_id is not None else None)

    def test_default_still_collects_latest_across_status_partitions(self):
        report = self.collect(board_id=None)
        self.assertEqual(report["selected"]["board_id"], "21")
        self.assertEqual(len(report["listing_evidence"]), 4)
        self.assertIn("registration_date descending", report["selection"]["rule"])
        self.assertFalse(report["publication_ready"])

    def test_explicit_inventory_selects_older_candidate_and_rechecks_original(self):
        report = self.collect()
        self.assertEqual(report["selected"]["board_id"], "20")
        self.assertEqual(report["selection"]["latest_overall_board_id"], "21")
        self.assertEqual(report["detail_identity_fields"], {"board_idx": "20", "manage_idx": "15"})
        self.assertFalse(report["selection"]["publication_eligibility_verified"])
        self.assertFalse(report["publication_ready"])
        self.assertEqual(self.requests[-1], url("20"))

    def test_selected_id_must_exist_exactly_once_in_inventory(self):
        self.notices = []
        with self.assertRaises(ValueError):
            self.collect()
        self.assertFalse((self.root / "evidence" / "source.json").exists())

    def test_duplicated_inventory_candidate_is_rejected(self):
        self.notices.append(dict(self.candidate))
        with self.assertRaises(ValueError):
            self.collect()

    def test_canonical_detail_url_must_identify_selected_board(self):
        self.candidate["detail_url"] = url("21")
        with self.assertRaises(ValueError):
            self.collect()

    def test_source_key_must_identify_selected_board(self):
        self.candidate["source_key"] = "ptp:15:21"
        with self.assertRaises(ValueError):
            self.collect()

    def test_invalid_calendar_date_is_rejected(self):
        self.candidate["registration_date"] = "2026-02-30"
        with self.assertRaises(ValueError):
            self.collect()

    def test_date_requires_canonical_iso_format(self):
        self.candidate["registration_date"] = "2026-1-1"
        with self.assertRaises(ValueError):
            self.collect()

    def test_inventory_date_must_match_current_listing_when_observed(self):
        self.candidate["registration_date"] = "2026-10-19"
        with self.assertRaises(ValueError):
            self.collect()

    def test_older_candidate_records_when_date_only_comes_from_inventory(self):
        self.listing_html = listing(row(21, "2026.10.21"))
        report = self.collect()
        self.assertEqual(report["selected"]["board_id"], "20")
        self.assertFalse(report["selection"]["registration_date_current_listing_verified"])
        self.assertIn("inventory snapshot", report["registration_date_verified_from"])

    def test_blank_inventory_and_detail_titles_are_rejected(self):
        self.candidate["title"] = ""
        self.detail_html = detail("20", "")
        with self.assertRaises(ValueError):
            self.collect()

    def test_changed_original_title_is_rejected(self):
        self.detail_html = detail("20", "Amended notice")
        with self.assertRaises(ValueError):
            self.collect()

    def test_original_hidden_identity_mismatch_is_rejected(self):
        self.detail_html = detail("21", "Notice 20")
        with self.assertRaises(ValueError):
            self.collect()

    def test_redirect_to_other_board_is_rejected_even_with_identical_title(self):
        self.detail_html = detail("21", "Notice 20", identity=False)
        self.final_url = url("21")
        with self.assertRaises(ValueError):
            self.collect()

    def test_conflicting_final_url_and_hidden_identity_are_rejected(self):
        self.detail_html = detail("20", "Notice 20")
        self.final_url = url("21")
        with self.assertRaises(ValueError):
            self.collect()

    def test_reordered_response_query_keeps_the_same_identity(self):
        self.final_url = collector.BASE + "/main/board/view.do?board_idx=20&manage_idx=15&menu_idx=116"
        self.assertEqual(self.collect()["selected"]["board_id"], "20")

    def test_duplicate_response_identity_parameters_are_rejected(self):
        self.final_url = url("20") + "&board_idx=21"
        with self.assertRaises(ValueError):
            self.collect()

    def test_noncanonical_board_id_is_rejected(self):
        self.candidate.update(board_id="020", title="Notice 020", detail_url=url("020"), source_key="ptp:15:020")
        with self.assertRaises(ValueError):
            self.collect(board_id="020")

    def test_malformed_inventory_is_reported_as_validation_error(self):
        with self.assertRaises(ValueError):
            self.collect(inventory_data=[])

    def test_cli_requires_inventory_and_board_id_together(self):
        for extra in (["--board-id", "20"], ["--inventory", str(self.inventory)]):
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()), patch("sys.argv", ["collect_ptp_notice.py", "--output-dir", str(self.root / "evidence"), *extra]):
                with self.assertRaises(SystemExit) as error:
                    collector.main()
                self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
