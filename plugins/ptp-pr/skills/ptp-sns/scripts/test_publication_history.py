#!/usr/bin/env python3
"""Generic ledger regression tests; PTP submission gates have separate integration tests."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("publication_history.py")


class PublicationHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "history.jsonl"
        self.manifest = self.root / "package.json"
        self.manifest.write_text('{"source_key":"fixture:15:123","assets":["one.png"]}', encoding="utf-8")

    def call(self, command, *extra, platform="instagram", account="ptp_public", expected=0):
        result = subprocess.run([
            sys.executable, str(SCRIPT), command,
            "--ledger", str(self.ledger), "--source-key", "fixture:15:123",
            "--platform", platform, "--account", account,
            "--manifest", str(self.manifest), *extra,
        ], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def start(self, **kwargs):
        return self.call("record", "--status", "submitting", **kwargs)["event"]["attempt_id"]

    def publish(self, attempt, **kwargs):
        return self.call("record", "--status", "published", "--attempt-id", attempt,
                         "--post-id", "123456", "--evidence", "Operator inspected account permalink after posting",
                         "--published-at", "2026-10-22T10:00:00+09:00", **kwargs)

    def test_submitting_and_changed_manifest_block_duplicates(self):
        self.assertTrue(self.call("check")["allowed"])
        attempt = self.start()
        report = self.call("check", expected=2)
        self.assertEqual(report["blocking_attempts"][0]["attempt_id"], attempt)
        original = self.ledger.read_bytes()
        self.manifest.write_text('{"revision":2}', encoding="utf-8")
        report = self.call("record", "--status", "submitting", expected=2)
        self.assertTrue(report["fingerprint_changed"])
        self.assertEqual(original, self.ledger.read_bytes())

    def test_unknown_reconciles_and_success_is_immutable(self):
        attempt = self.start()
        self.call("record", "--status", "unknown", "--attempt-id", attempt,
                  "--evidence", "Browser response lost after submit")
        self.call("check", expected=2)
        self.publish(attempt)
        original = self.ledger.read_bytes()
        self.publish(attempt, expected=2)
        self.call("record", "--status", "submitting", expected=2)
        self.assertEqual(original, self.ledger.read_bytes())
        self.assertEqual(len(original.splitlines()), 3)

    def test_definitive_failure_allows_only_failed_channel_retry(self):
        instagram = self.start()
        self.publish(instagram)
        facebook = self.start(platform="facebook")
        self.call("record", "--status", "failed", "--attempt-id", facebook,
                  "--evidence", "Request outcome unknown", platform="facebook", expected=1)
        self.call("check", platform="facebook", expected=2)
        self.call("record", "--status", "failed", "--attempt-id", facebook,
                  "--definitive-failure", "--evidence", "Meta rejected before creation; operator confirmed no post exists",
                  platform="facebook")
        self.assertTrue(self.call("check", platform="facebook")["allowed"])
        retry = self.start(platform="facebook")
        self.assertNotEqual(retry, facebook)
        self.call("check", expected=2)
        self.assertTrue(self.call("check", account="second_public_account")["allowed"])

    def test_scheduled_requires_evidence_and_aware_timestamp(self):
        attempt = self.start()
        base = ("record", "--status", "scheduled", "--attempt-id", attempt,
                "--remote-url", "https://www.instagram.com/p/abcdef/", "--scheduled-at")
        self.call(*base, "2026-10-25T09:00:00+09:00", expected=1)
        self.call(*base, "2026-10-25T09:00:00", "--evidence", "Scheduled item inspected", expected=1)
        self.call(*base, "2026-10-25T09:00:00+09:00", "--evidence", "Scheduled item inspected")
        self.call("check", expected=2)

    def test_lock_collision_and_torn_ledger_fail_closed(self):
        lock = self.ledger.with_name(self.ledger.name + ".lock")
        lock.write_text("another process", encoding="utf-8")
        self.call("record", "--status", "submitting", expected=2)
        self.assertEqual(lock.read_text(encoding="utf-8"), "another process")
        lock.unlink()
        self.start()
        with self.ledger.open("ab") as stream:
            stream.write(b'{"broken":')
        original = self.ledger.read_bytes()
        self.call("check", expected=1)
        self.call("record", "--status", "submitting", expected=1)
        self.assertEqual(original, self.ledger.read_bytes())

    def test_wrong_attempt_identity_or_package_cannot_be_reconciled(self):
        attempt = self.start()
        self.publish(attempt, account="other", expected=1)
        self.manifest.write_text('{"different":true}', encoding="utf-8")
        self.publish(attempt, expected=1)

    def test_instagram_aliases_block_and_reconcile_the_same_account(self):
        attempt = self.start(account="https://www.instagram.com/PTP_Test/")
        aliases = ("https://instagram.com/ptp_test", "https://www.instagram.com/ptp_test/",
                   "PTP_TEST", "@ptp_test", "handle:ptp_test")
        for alias in aliases:
            with self.subTest(alias=alias):
                report = self.call("check", account=alias, expected=2)
                self.assertEqual(report["account"], "handle:ptp_test")
                self.call("record", "--status", "submitting", account=alias, expected=2)
        self.publish(attempt, account="@PTP_TEST")
        self.call("check", account="https://instagram.com/PTP_Test/", expected=2)

    def test_facebook_vanity_and_numeric_url_aliases(self):
        vanity = self.start(platform="facebook", account="https://www.facebook.com/PTPTest/")
        for alias in ("https://m.facebook.com/ptptest", "https://facebook.com/ptptest/",
                      "https://www.facebook.com/pg/PTPTest/", "@PTPTEST", "ptptest"):
            with self.subTest(alias=alias):
                self.call("check", platform="facebook", account=alias, expected=2)
        self.publish(vanity, platform="facebook", account="@ptptest")
        numeric = self.start(platform="facebook", account="https://m.facebook.com/profile.php?id=123456")
        for alias in ("123456", "id:123456", "https://www.facebook.com/123456/",
                      "https://facebook.com/profile.php?id=123456",
                      "https://www.facebook.com/pages/PTP-Test/123456/"):
            with self.subTest(alias=alias):
                self.call("check", platform="facebook", account=alias, expected=2)
        self.publish(numeric, platform="facebook", account="123456")

    def test_legacy_ledger_aliases_normalize_without_rewriting(self):
        attempt = self.start(account="ptp_test")
        event = json.loads(self.ledger.read_text(encoding="utf-8"))
        event["account"] = "https://www.instagram.com/PTP_TEST/"
        self.ledger.write_text(json.dumps(event) + "\n", encoding="utf-8")
        original = self.ledger.read_bytes()
        self.call("check", account="@ptp_test", expected=2)
        self.assertEqual(original, self.ledger.read_bytes())
        self.publish(attempt, account="https://instagram.com/ptp_test")
        self.assertTrue(self.ledger.read_bytes().startswith(original))
        self.call("check", account="PTP_TEST", expected=2)

    def test_instagram_numeric_id_is_not_guessed_from_a_handle(self):
        self.start(account="123456")
        self.call("check", account="id:123456", expected=2)
        # Even a numeric-looking handle is a separate identity; account configuration
        # must retain one verified stable ID instead of alternating IDs and handles.
        self.assertTrue(self.call("check", account="@123456")["allowed"])
        self.assertTrue(self.call("check", account="https://instagram.com/123456/")["allowed"])
        self.assertTrue(self.call("check", account="ptp_test")["allowed"])

    def test_credentials_in_url_and_ambiguous_cli_are_rejected(self):
        self.call("record", "--status", "published", "--remote-url",
                  "https://www.instagram.com/p/abc/?access_token=do-not-record",
                  "--evidence", "Example", "--published-at", "2026-10-22T10:00:00+09:00", expected=1)
        self.assertFalse(self.ledger.exists())
        self.call("record", expected=1)

    def test_concurrent_starts_create_only_one_attempt(self):
        command = [sys.executable, str(SCRIPT), "record", "--ledger", str(self.ledger),
                   "--source-key", "fixture:15:123", "--platform", "instagram", "--account", "ptp_public",
                   "--manifest", str(self.manifest), "--status", "submitting"]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        outcomes = [process.communicate(timeout=30) for process in processes]
        self.assertEqual(sum(process.returncode == 0 for process in processes), 1, outcomes)
        self.assertTrue(all(process.returncode in {0, 2} for process in processes), outcomes)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
