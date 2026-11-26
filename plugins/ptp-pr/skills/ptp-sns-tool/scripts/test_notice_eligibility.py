#!/usr/bin/env python3
"""Offline regression tests for application-period publication eligibility."""
from __future__ import annotations

import copy
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notice_eligibility import KST, evaluate

KEY = "ptp:15:8190"
NOW = datetime(2026, 10, 22, 13, 45, 0, tzinfo=KST)


def fixture() -> dict:
    return {
        "schema_version": 1, "source_key": KEY,
        "source_url": "https://www.ptp.or.kr/main/board/view.do?menu_idx=116&manage_idx=15&board_idx=8190",
        "checked_at": NOW.isoformat(), "source_status": "open",
        "source_status_evidence": {"path": "source/detail.html", "location": "접수 상태", "raw_text": "접수중"},
        "application_period": {
            "purpose": "application", "verified": True, "kind": "bounded",
            "start": "2026-10-21", "end": "2026-10-30T15:00:00+09:00",
            "evidence": {"path": "source/notice.pdf", "location": "2쪽 접수기간", "raw_text": "2026.10.21 ~ 10.30 15:00"},
        },
    }


class EligibilityTests(unittest.TestCase):
    def check(self, evidence=None, now=NOW, scheduled_at=None):
        return evaluate(fixture() if evidence is None else evidence, KEY, now, scheduled_at)

    def denied(self, evidence, reason, **kwargs):
        result = self.check(evidence, **kwargs)
        self.assertFalse(result["allowed"], result)
        self.assertIn(reason, result["reasons"], result)
        return result

    def at(self, timestamp, end="2026-10-30T15:00:00+09:00"):
        value = fixture()
        current = datetime.fromisoformat(timestamp)
        value["checked_at"] = current.isoformat()
        value["application_period"]["end"] = end
        return self.check(value, current)

    def test_verified_current_window_is_allowed(self):
        result = self.check()
        self.assertTrue(result["allowed"], result)
        self.assertEqual("open", result["state"])
        self.assertTrue(result["evidence_validation_only"])
        self.assertEqual("2026-10-22T14:15:00+09:00", result["recheck_no_later_than"])

    def test_exact_deadline_is_inclusive_then_closes(self):
        self.assertTrue(self.at("2026-10-30T15:00:00+09:00")["allowed"])
        result = self.at("2026-10-30T15:00:00.000001+09:00")
        self.assertFalse(result["allowed"])
        self.assertEqual("closed", result["state"])

    def test_date_only_deadline_includes_entire_korean_day(self):
        result = self.at("2026-10-30T23:59:59.999999+09:00", "2026-10-30")
        self.assertTrue(result["allowed"], result)
        self.assertEqual("day", result["end_precision"])
        self.assertFalse(self.at("2026-10-31T00:00:00+09:00", "2026-10-30")["allowed"])

    def test_date_only_deadline_uses_kst_when_clock_is_utc(self):
        self.assertTrue(self.at("2026-10-30T14:59:59+00:00", "2026-10-30")["allowed"])
        self.assertFalse(self.at("2026-10-30T15:00:00+00:00", "2026-10-30")["allowed"])

    def test_datetime_deadline_different_offset_is_same_instant(self):
        result = self.at("2026-10-30T15:00:00+09:00", "2026-10-30T06:00:00Z")
        self.assertTrue(result["allowed"], result)

    def test_start_date_is_midnight_kst_and_inclusive(self):
        self.assertTrue(self.at("2026-10-20T15:00:00+00:00")["allowed"])
        result = self.at("2026-10-20T14:59:59+00:00")
        self.assertFalse(result["allowed"])
        self.assertEqual("upcoming", result["state"])

    def test_current_status_overrides_calendar(self):
        for state in ("upcoming", "closed", "cancelled", "unknown"):
            with self.subTest(state=state):
                value = fixture()
                value["source_status"] = state
                result = self.denied(value, "source_status_" + state)
                self.assertEqual(state, result["state"])

    def test_invalid_status_is_fail_closed(self):
        for state in ("접수중", "OPEN", [], None):
            with self.subTest(state=state):
                value = fixture()
                value["source_status"] = state
                self.denied(value, "invalid_source_status")

    def test_live_status_without_verified_dates_is_insufficient(self):
        value = fixture()
        value["application_period"]["verified"] = False
        self.denied(value, "application_period_not_verified")

    def test_project_performance_dates_are_not_application_dates(self):
        value = fixture()
        value["application_period"]["purpose"] = "project-operation"
        self.denied(value, "application_period_purpose_required")

    def test_missing_period_is_blocked(self):
        value = fixture()
        del value["application_period"]
        self.denied(value, "application_period_required")

    def test_unknown_or_missing_end_is_blocked(self):
        value = fixture()
        for end in (None, "추후 공지", "2026-02-30", "2026-10-30T15:00:00", "2026-10-30T15:00:00+99:00"):
            with self.subTest(end=end):
                value["application_period"]["end"] = end
                self.denied(value, "invalid_application_end")

    def test_naive_or_invalid_start_is_blocked(self):
        value = fixture()
        for start in (None, "2026-10-21T09:00:00", "2026-10-00"):
            with self.subTest(start=start):
                value["application_period"]["start"] = start
                self.denied(value, "invalid_application_start")

    def test_end_before_start_is_blocked(self):
        value = fixture()
        value["application_period"]["end"] = "2026-10-20"
        self.denied(value, "application_end_before_start")

    def test_freshness_has_a_fixed_thirty_minute_limit(self):
        value = fixture()
        value["checked_at"] = (NOW - timedelta(minutes=30)).isoformat()
        self.assertTrue(self.check(value)["allowed"])
        value["checked_at"] = (NOW - timedelta(minutes=30, microseconds=1)).isoformat()
        self.denied(value, "evidence_stale")

    def test_future_check_time_allows_only_small_clock_skew(self):
        value = fixture()
        value["checked_at"] = (NOW + timedelta(seconds=60)).isoformat()
        self.assertTrue(self.check(value)["allowed"])
        value["checked_at"] = (NOW + timedelta(seconds=61)).isoformat()
        self.denied(value, "evidence_from_future")

    def test_checked_at_requires_timezone(self):
        value = fixture()
        value["checked_at"] = "2026-10-22T13:45:00"
        self.denied(value, "invalid_checked_at")

    def test_extreme_iso_year_does_not_crash_gate(self):
        value = fixture()
        value["checked_at"] = "9999-12-31T23:59:59+09:00"
        self.denied(value, "evidence_from_future")

    def test_test_clock_requires_timezone(self):
        self.denied(fixture(), "evaluation_time_requires_timezone", now=NOW.replace(tzinfo=None))

    def test_source_key_and_official_url_must_agree(self):
        value = fixture()
        value["source_key"] = "ptp:15:8191"
        self.denied(value, "source_key_mismatch")
        value = fixture()
        for url in (
            value["source_url"].replace("8190", "8191"),
            value["source_url"].replace("manage_idx=15", "manage_idx=14"),
            value["source_url"].replace("menu_idx=116", "menu_idx=115"),
            value["source_url"].replace("https:", "http:"),
            value["source_url"].replace("www.ptp.or.kr", "www.ptp.or.kr.evil.invalid"),
            value["source_url"].replace("www.ptp.or.kr", "spoof@www.ptp.or.kr"),
            value["source_url"] + "&board_idx=8190",
        ):
            with self.subTest(url=url):
                candidate = copy.deepcopy(value)
                candidate["source_url"] = url
                self.denied(candidate, "official_source_url_mismatch")

    def test_provenance_requires_path_location_and_raw_text(self):
        for container in ("source_status_evidence", "application_period"):
            for field in ("path", "location", "raw_text"):
                with self.subTest(container=container, field=field):
                    value = fixture()
                    proof = value[container] if container == "source_status_evidence" else value[container]["evidence"]
                    proof[field] = " "
                    self.denied(value, "source_status_evidence_required" if container == "source_status_evidence" else "application_period_evidence_required")

    def test_valid_future_schedule_still_requires_release_recheck(self):
        result = self.check(scheduled_at="2026-10-30T15:00:00+09:00")
        self.assertTrue(result["allowed"], result)
        self.assertTrue(result["requires_recheck_at_release"])

    def test_schedule_after_deadline_is_blocked(self):
        self.denied(fixture(), "schedule_after_application_end", scheduled_at="2026-10-30T15:00:01+09:00")

    def test_schedule_in_past_or_without_timezone_is_blocked(self):
        self.denied(fixture(), "schedule_in_past", scheduled_at="2026-10-22T13:44:59+09:00")
        self.denied(fixture(), "invalid_scheduled_at", scheduled_at="2026-10-23")
        self.denied(fixture(), "invalid_scheduled_at", scheduled_at="2026-10-23T15:00:00")

    def test_future_schedule_cannot_bypass_current_upcoming_status(self):
        value = fixture()
        value["application_period"]["start"] = "2026-10-23"
        self.denied(value, "application_not_started", scheduled_at="2026-10-24T12:00:00+09:00")

    def open_ended(self):
        value = fixture()
        period = value["application_period"]
        period["kind"] = "open-ended"
        period.pop("end")
        period["condition"] = "예산 소진 시까지"
        period["evidence"]["raw_text"] = "2026. 10. 21.부터 예산 소진 시까지 접수"
        return value

    def test_open_ended_accepts_explicit_condition_and_current_status(self):
        self.assertTrue(self.check(self.open_ended())["allowed"])

    def test_open_ended_rejects_future_scheduling(self):
        self.denied(self.open_ended(), "open_ended_future_schedule_not_allowed", scheduled_at="2026-10-22T13:45:01+09:00")
        self.assertTrue(self.check(self.open_ended(), scheduled_at=NOW.isoformat())["allowed"])

    def test_open_ended_requires_condition_present_in_source(self):
        value = self.open_ended()
        del value["application_period"]["condition"]
        self.denied(value, "open_ended_official_condition_required")
        value = self.open_ended()
        value["application_period"]["condition"] = "상시 접수"
        self.denied(value, "open_ended_condition_not_in_evidence")

    def test_open_ended_closed_source_and_stale_check_still_block(self):
        value = self.open_ended()
        value["source_status"] = "closed"
        self.denied(value, "source_status_closed")
        value = self.open_ended()
        value["checked_at"] = (NOW - timedelta(hours=1)).isoformat()
        self.denied(value, "evidence_stale")

    def test_schema_bool_and_non_object_evidence_are_rejected(self):
        value = fixture()
        value["schema_version"] = True
        self.denied(value, "unsupported_schema_version")
        self.denied([], "evidence_object_required")

    def test_production_cli_has_no_clock_override(self):
        script = Path(__file__).with_name("notice_eligibility.py")
        result = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode)
        self.assertNotIn("--now", result.stdout)
        result = subprocess.run([sys.executable, str(script), "--evidence", "unused.json", "--source-key", KEY,
                                 "--now", NOW.isoformat()], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
