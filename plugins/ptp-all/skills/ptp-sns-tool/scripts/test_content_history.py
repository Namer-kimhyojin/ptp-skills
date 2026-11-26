#!/usr/bin/env python3
"""Isolated production-registry tests. Never touch shared state or remote accounts."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

import content_history as content

SCRIPT = Path(__file__).with_name("content_history.py")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1cAAAAASUVORK5CYII=")


class ContentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "content.jsonl"
        self.pub = self.root / "publication.jsonl"
        self.manifest = self.root / "package-manifest.json"
        self.image = self.root / "01.png"
        self.image.write_bytes(PNG)
        self.document = {"schema_version": "1.0", "source_key": "ptp:15:123", "files": [
            {"file": "01.png", "sha256": hashlib.sha256(PNG).hexdigest(), "bytes": len(PNG)}]}
        self.save_manifest()

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.document), encoding="utf-8")

    def command(self, command, *extra, source="ptp:15:123"):
        return [sys.executable, str(SCRIPT), command, "--ledger", str(self.ledger),
                "--publication-ledger", str(self.pub), "--source-key", source, *extra]

    def call(self, command, *extra, expected=0, **kwargs):
        result = subprocess.run(self.command(command, *extra, **kwargs), capture_output=True,
                                text=True, encoding="utf-8")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def start(self):
        return self.call("start")["event"]["production_id"]

    def finish(self, production_id, **kwargs):
        return self.call("finish", "--production-id", production_id, "--status", "produced",
                         "--manifest", str(self.manifest), "--evidence", "Five-page package reviewed", **kwargs)

    def import_package(self, **kwargs):
        return self.call("import-produced", "--manifest", str(self.manifest),
                         "--evidence", "Existing package checked", "--provenance", "Prior completed production", **kwargs)

    def revision_fixture(self):
        previous = self.import_package()["event"]
        directory = self.root / "publish-variant"
        directory.mkdir()
        (directory / "01.png").write_bytes(PNG)
        caption = b"Find the notice through the official website menu."
        (directory / "facebook-caption.txt").write_bytes(caption)
        document = {"source_key": "ptp:15:123", "files": [
            {"file": "01.png", "sha256": hashlib.sha256(PNG).hexdigest()},
            {"file": "facebook-caption.txt", "sha256": hashlib.sha256(caption).hexdigest()}]}
        manifest = directory / "package-manifest.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        return previous, manifest

    def revise(self, previous, manifest, *extra, **kwargs):
        return self.call("revise-produced", "--previous-event-id", previous["event_id"],
                         "--original-manifest-sha256", previous["manifest_sha256"],
                         "--manifest", str(manifest), "--reason", "Platform link quota requires a caption path",
                         "--evidence", "No submission attempted; original QR and cards retained", *extra, **kwargs)

    def test_revision_appends_linked_event_and_preserves_original(self):
        previous, manifest = self.revision_fixture()
        before = self.ledger.read_bytes()
        original = self.manifest.read_bytes()
        revised = self.revise(previous, manifest)["event"]
        self.assertTrue(self.ledger.read_bytes().startswith(before))
        self.assertEqual(len(self.ledger.read_text().splitlines()), 2)
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertEqual(self.image.read_bytes(), PNG)
        self.assertEqual(revised["production_id"], previous["production_id"])
        self.assertEqual(revised["revision"]["previous_event_id"], previous["event_id"])
        self.assertEqual(content.read_latest(self.ledger)["ptp:15:123"], revised)
        self.assertEqual(self.call("check", expected=2)["integrity"]["manifest_path"], str(manifest))
        after = self.ledger.read_bytes()
        self.revise(previous, manifest, expected=2)
        self.assertEqual(self.ledger.read_bytes(), after)

    def test_revision_requires_original_event_hash_and_intact_files(self):
        previous, manifest = self.revision_fixture()
        before = self.ledger.read_bytes()
        self.revise(previous, manifest, "--previous-event-id", str(uuid.uuid4()), expected=2)
        self.revise(previous, manifest, "--original-manifest-sha256", "0" * 64, expected=2)
        original_manifest = self.manifest.read_bytes()
        self.manifest.write_bytes(original_manifest + b" ")
        self.revise(previous, manifest, expected=2)
        self.manifest.write_bytes(original_manifest)
        self.image.write_bytes(PNG + b"changed")
        self.revise(previous, manifest, expected=2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_revision_blocks_successful_or_unresolved_attempts_on_every_channel(self):
        previous, manifest = self.revision_fixture()
        before = self.ledger.read_bytes()
        for channel in ("instagram", "facebook"):
            for state in ("submitting", "unknown", "published", "scheduled"):
                with self.subTest(channel=channel, state=state):
                    self.publication(state)
                    event = json.loads(self.pub.read_text())
                    event["platform"] = channel
                    if channel == "facebook" and state == "published":
                        event["remote_url"] = "https://www.facebook.com/test/posts/test123"
                    self.pub.write_text(json.dumps(event) + "\n", encoding="utf-8")
                    self.revise(previous, manifest, expected=2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_revision_requires_separate_same_source_package_and_unchanged_images(self):
        previous, manifest = self.revision_fixture()
        before = self.ledger.read_bytes()
        self.revise(previous, self.manifest, expected=2)
        document = json.loads(manifest.read_text())
        document["source_key"] = "ptp:15:999"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        self.revise(previous, manifest, expected=1)
        document["source_key"] = "ptp:15:123"
        changed_image = PNG + b"different-art"
        (manifest.parent / "01.png").write_bytes(changed_image)
        document["files"][0]["sha256"] = hashlib.sha256(changed_image).hexdigest()
        manifest.write_text(json.dumps(document), encoding="utf-8")
        self.revise(previous, manifest, expected=2)
        self.assertEqual(self.ledger.read_bytes(), before)

    def test_revision_requires_reason_and_rejects_unlinked_ledger_event(self):
        previous, manifest = self.revision_fixture()
        before = self.ledger.read_bytes()
        self.revise(previous, manifest, "--reason", " ", expected=1)
        self.assertEqual(self.ledger.read_bytes(), before)
        event = self.revise(previous, manifest)["event"]
        event["revision"]["previous_event_id"] = str(uuid.uuid4())
        self.ledger.write_bytes(before + (json.dumps(event) + "\n").encode())
        with self.assertRaises(content.HistoryError):
            content.read_latest(self.ledger)

    def publication(self, status="published", source="ptp:15:123"):
        event = {"schema_version": 1, "event_id": str(uuid.uuid4()), "attempt_id": str(uuid.uuid4()),
                 "source_key": source, "platform": "instagram", "account": "handle:ptp_public",
                 "manifest_sha256": hashlib.sha256(self.manifest.read_bytes()).hexdigest(), "status": status,
                 "recorded_at": "2026-10-22T12:00:00+09:00", "evidence": "Verified result",
                 "remote_url": "https://www.instagram.com/p/test123/" if status == "published" else None,
                 "post_id": "test123" if status == "published" else None,
                 "published_at": "2026-10-22T12:00:00+09:00" if status == "published" else None,
                 "scheduled_at": "2026-10-23T12:00:00+09:00" if status == "scheduled" else None,
                 "definitive_failure": status == "failed"}
        if status == "scheduled":
            event["post_id"] = "test123"
        self.pub.write_text(json.dumps(event) + "\n", encoding="utf-8")

    def test_producing_blocks_recreation_until_same_id_finishes(self):
        self.assertEqual(self.call("check")["status"], "not_recorded")
        production_id = self.start()
        report = self.call("check", expected=2)
        self.assertEqual(report["status"], "producing")
        self.assertTrue(report["requires_recovery"])
        self.call("start", expected=2)
        self.finish(str(uuid.uuid4()), expected=1)
        self.finish(production_id)
        latest = content.read_latest(self.ledger)
        self.assertEqual(latest["ptp:15:123"]["production_id"], production_id)
        self.assertEqual(latest["ptp:15:123"]["manifest_path"], str(self.manifest))
        report = self.call("check", expected=2)
        self.assertEqual(report["status"], "produced")
        self.assertFalse(report["requires_recovery"])
        self.assertEqual(report["integrity"]["image_count"], 1)
        original = self.ledger.read_bytes()
        self.finish(production_id, expected=2)
        self.import_package(expected=2)
        self.call("start", expected=2)
        self.assertEqual(self.ledger.read_bytes(), original)

    def test_definitive_failed_production_can_retry_with_new_id(self):
        production_id = self.start()
        args = ("--production-id", production_id, "--status", "failed", "--evidence", "No usable package exists")
        self.call("finish", *args, expected=1)
        self.call("check", expected=2)
        self.call("finish", *args, "--definitive-failure")
        self.assertEqual(self.call("check")["status"], "failed")
        self.assertNotEqual(production_id, self.start())

    def test_import_requires_provenance_and_accepts_published_existing_package(self):
        self.publication()
        self.assertTrue(self.call("check", expected=2)["requires_recovery"])
        self.call("start", expected=2)
        result = self.import_package()
        self.assertTrue(result["event"]["imported"])
        self.assertIn("Prior completed", result["event"]["provenance"])
        report = self.call("check", expected=2)
        self.assertEqual(report["status"], "produced")
        self.assertEqual(len(report["publication_blockers"]), 1)
        self.assertFalse(report["requires_recovery"])

    def test_import_cannot_take_over_an_active_production(self):
        self.start()
        self.import_package(expected=2)

    def test_all_successful_and_unresolved_publication_states_block_new_production(self):
        for state in ("published", "scheduled", "submitting", "unknown"):
            with self.subTest(state=state):
                self.publication(state)
                report = self.call("start", expected=2)
                self.assertEqual(report["status"], "not_recorded")
                self.assertEqual(report["publication_blockers"][0]["status"], state)
                self.assertFalse(self.ledger.exists())
        self.publication("failed")
        self.assertTrue(self.call("check")["allowed"])
        self.publication("published", source="ptp:15:999")
        self.assertTrue(self.call("check")["allowed"])

    def test_missing_or_modified_produced_files_require_recovery_not_recreation(self):
        self.import_package()
        self.image.unlink()
        report = self.call("check", expected=2)
        self.assertEqual(report["status"], "produced")
        self.assertTrue(report["requires_recovery"])
        self.call("start", expected=2)
        self.image.write_bytes(PNG + b"changed")
        self.assertTrue(self.call("check", expected=2)["requires_recovery"])
        self.image.write_bytes(PNG)
        self.assertFalse(self.call("check", expected=2)["requires_recovery"])
        self.document["revision"] = 2
        self.save_manifest()
        self.assertTrue(self.call("check", expected=2)["requires_recovery"])
        self.call("start", expected=2)

    def test_invalid_manifests_never_mark_content_produced(self):
        production_id = self.start()
        self.document["source_key"] = "ptp:15:456"
        self.save_manifest()
        self.finish(production_id, expected=1)
        self.document["source_key"] = "ptp:15:123"
        self.document["files"][0]["sha256"] = "0" * 64
        self.save_manifest()
        self.finish(production_id, expected=2)
        self.document["files"] = []
        self.save_manifest()
        self.finish(production_id, expected=1)
        self.assertEqual(self.call("check", expected=2)["status"], "producing")

    def test_manifest_cannot_escape_package_or_use_fake_image(self):
        self.document["files"][0]["file"] = "../01.png"
        self.save_manifest()
        self.import_package(expected=1)
        self.document["files"][0]["file"] = "C:/outside.png"
        self.save_manifest()
        self.import_package(expected=1)
        self.image.write_bytes(b"this is not a png")
        self.document["files"] = [{"file": "01.png", "sha256": hashlib.sha256(self.image.read_bytes()).hexdigest()}]
        self.save_manifest()
        self.import_package(expected=2)
        self.assertFalse(self.ledger.exists())

    def test_missing_text_file_blocks_package_completion_too(self):
        self.document["files"].append({"file": "caption.txt", "sha256": "a" * 64})
        self.save_manifest()
        self.import_package(expected=2)
        self.assertFalse(self.ledger.exists())

    def test_concurrent_start_only_creates_one_production(self):
        processes = [subprocess.Popen(self.command("start"), stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        results = [process.communicate(timeout=20) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 2], results)
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 1)

    def test_existing_locks_are_never_removed_automatically(self):
        for ledger in (self.ledger, self.pub):
            lock = ledger.with_name(ledger.name + ".lock")
            lock.write_text("another interrupted run", encoding="utf-8")
            self.call("start", expected=2)
            self.assertEqual(lock.read_text(encoding="utf-8"), "another interrupted run")
            lock.unlink()
        self.assertFalse(self.ledger.exists())

    def test_torn_or_malformed_content_and_publication_ledgers_fail_closed(self):
        self.start()
        original = self.ledger.read_bytes()
        self.ledger.write_bytes(original.rstrip(b"\n"))
        self.call("check", expected=1)
        self.ledger.write_bytes(original + b"broken\n")
        self.call("check", expected=1)
        self.ledger.write_bytes(original)
        self.publication()
        self.pub.write_bytes(self.pub.read_bytes().rstrip(b"\n"))
        self.call("check", expected=1)

    def test_terminal_overwrite_in_ledger_is_rejected(self):
        self.import_package()
        event = json.loads(self.ledger.read_text(encoding="utf-8"))
        event["event_id"] = str(uuid.uuid4())
        with self.ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")
        self.call("check", expected=1)

    def test_source_keys_are_canonical(self):
        self.call("check", source="ptp:15:00123", expected=1)
        self.call("check", source="ptp:16:123", expected=1)


if __name__ == "__main__":
    unittest.main()
