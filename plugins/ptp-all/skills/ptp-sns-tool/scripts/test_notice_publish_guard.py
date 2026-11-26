#!/usr/bin/env python3
"""Isolated pre-submission integration tests; never touch the shared state files."""
from __future__ import annotations

import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import content_history
import notice_publish_guard
import run_hooks
from notice_publish_guard import check_job, check_start


KEY = "ptp:15:123"
CONTENT_SCRIPT = Path(__file__).with_name("content_history.py")
PUBLICATION_SCRIPT = Path(__file__).with_name("publication_history.py")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aG1cAAAAASUVORK5CYII=")


class NoticePublishGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.content_ledger = self.root / "content.jsonl"
        self.publication_ledger = self.root / "state" / "publication-history.jsonl"
        self.manifest = self.root / "package-manifest.json"
        self.image = self.root / "01.png"
        self.image.write_bytes(PNG)
        self.document = {"schema_version": "1.0", "source_key": KEY, "files": [
            {"file": "01.png", "sha256": hashlib.sha256(PNG).hexdigest(), "bytes": len(PNG)}]}
        self.manifest.write_text(json.dumps(self.document), encoding="utf-8")
        self.now = datetime.now(timezone.utc)
        self.eligibility = self.root / "eligibility.json"
        self.evidence = {
            "schema_version": 1, "source_key": KEY,
            "source_url": "https://www.ptp.or.kr/main/board/view.do?menu_idx=116&manage_idx=15&board_idx=123",
            "checked_at": self.now.isoformat(), "source_status": "open",
            "source_status_evidence": {"path": "source/detail.html", "location": "접수 상태", "raw_text": "접수중"},
            "application_period": {
                "purpose": "application", "verified": True, "kind": "bounded",
                "start": (self.now - timedelta(days=1)).isoformat(),
                "end": (self.now + timedelta(days=1)).isoformat(),
                "evidence": {"path": "source/notice.pdf", "location": "접수기간 항목", "raw_text": "격리된 테스트 접수기간 근거"},
            },
        }
        self.save_evidence()

    def save_evidence(self):
        self.eligibility.write_text(json.dumps(self.evidence), encoding="utf-8")

    def run_json(self, command, expected=0):
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def content(self, command, *extra, expected=0):
        return self.run_json([sys.executable, str(CONTENT_SCRIPT), command,
                             "--ledger", str(self.content_ledger), "--publication-ledger", str(self.publication_ledger),
                             "--source-key", KEY, *extra], expected)

    def import_produced(self):
        return self.content("import-produced", "--manifest", str(self.manifest),
                            "--evidence", "Offline test package inspected", "--provenance", "Isolated test fixture")

    def submit(self, *extra, expected=0, eligibility=True, manifest=None,
               platform="instagram", account="ptp_test"):
        args = [sys.executable, str(PUBLICATION_SCRIPT), "record", "--ledger", str(self.publication_ledger),
                "--source-key", KEY, "--platform", platform, "--account", account,
                "--manifest", str(manifest or self.manifest), "--content-ledger", str(self.content_ledger)]
        if eligibility:
            args.extend(["--eligibility", str(self.eligibility)])
        args.extend(extra or ("--status", "submitting"))
        return self.run_json(args, expected)

    def gate(self, manifest=None, eligibility=True):
        return check_start(KEY, manifest or self.manifest, self.eligibility if eligibility else None,
                           self.content_ledger)

    def job_fixture(self):
        return {"workflow": "notice-to-social", "production_mode": "publication",
                "source_notice": {"source_key": KEY, "eligibility_path": "eligibility.json"},
                "publication": {"authorized": True, "package_manifest": "package-manifest.json",
                                "targets": [{"platform": "instagram", "account_id": "ptp_test"}]}}

    def job_gate(self, job):
        # Patch the two production defaults, never replace validation functions.
        # Both the content registry and the fixed publication path stay in temp.
        with patch.object(content_history, "DEFAULT_LEDGER", self.content_ledger), \
             patch.object(notice_publish_guard, "__file__", str(self.root / "scripts" / "notice_publish_guard.py")):
            return check_job(job, self.root / "job.json")

    def before_publish_hook(self, job, authorized_flag=True):
        job_path = self.root / "job.json"
        job_path.write_text(json.dumps(job), encoding="utf-8")
        argv = ["run_hooks.py", "before_publish", str(job_path)]
        if authorized_flag:
            argv.append("--authorized")
        output = io.StringIO()
        with patch.object(content_history, "DEFAULT_LEDGER", self.content_ledger), \
             patch.object(notice_publish_guard, "__file__", str(self.root / "scripts" / "notice_publish_guard.py")), \
             patch.object(sys, "argv", argv), redirect_stdout(output):
            code = run_hooks.main()
        return code, json.loads(output.getvalue())

    def snapshot(self):
        return {p.name: p.read_bytes() if p.exists() else None
                for p in (self.content_ledger, self.publication_ledger)}

    def rejected_without_events(self, reason, **kwargs):
        before = self.snapshot()
        result = self.submit(expected=2, **kwargs)
        self.assertFalse(result["ok"], result)
        self.assertFalse(result["notice_gate"]["allowed"], result)
        self.assertIn(reason, result["notice_gate"]["reasons"], result)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.publication_ledger.with_name(self.publication_ledger.name + ".lock").exists())
        return result

    def test_new_submission_requires_fresh_eligibility_file(self):
        self.import_produced()
        self.rejected_without_events("fresh_application_period_evidence_required", eligibility=False)

    def test_new_submission_requires_registered_produced_cards(self):
        self.rejected_without_events("completed_card_package_not_registered")

    def test_producing_cards_are_not_treated_as_completed(self):
        self.content("start")
        result = self.rejected_without_events("completed_card_package_not_registered")
        self.assertIn("registered_card_package_requires_recovery", result["notice_gate"]["reasons"])

    def test_expired_application_window_blocks_without_writing_event(self):
        self.import_produced()
        self.evidence["application_period"]["end"] = (self.now - timedelta(seconds=10)).isoformat()
        self.save_evidence()
        self.rejected_without_events("application_closed")

    def test_stale_evidence_blocks_without_writing_event(self):
        self.import_produced()
        self.evidence["checked_at"] = (self.now - timedelta(minutes=31)).isoformat()
        self.save_evidence()
        self.rejected_without_events("evidence_stale")

    def test_cancelled_notice_blocks_even_with_current_dates(self):
        self.import_produced()
        self.evidence["source_status"] = "cancelled"
        self.save_evidence()
        self.rejected_without_events("source_status_cancelled")

    def test_changed_card_file_blocks_without_writing_event(self):
        self.import_produced()
        self.image.write_bytes(PNG + b"modified")
        result = self.rejected_without_events("notice_guard_input_or_history_error")
        self.assertIn("hash mismatch", result["notice_gate"]["error"])

    def test_missing_card_file_blocks_without_writing_event(self):
        self.import_produced()
        self.image.unlink()
        result = self.rejected_without_events("notice_guard_input_or_history_error")
        self.assertIn("missing or unreadable", result["notice_gate"]["error"])

    def test_changed_package_manifest_blocks_without_writing_event(self):
        self.import_produced()
        self.document["revision"] = "changed"
        self.manifest.write_text(json.dumps(self.document), encoding="utf-8")
        result = self.rejected_without_events("registered_package_fingerprint_mismatch")
        self.assertIn("registered_card_package_requires_recovery", result["notice_gate"]["reasons"])

    def test_fresh_eligible_produced_package_records_submitting(self):
        produced = self.import_produced()["event"]
        content_before = self.content_ledger.read_bytes()
        result = self.submit()
        self.assertTrue(result["ok"])
        event = result["event"]
        self.assertEqual("submitting", event["status"])
        self.assertTrue(event["notice_gate"]["allowed"])
        self.assertEqual(produced["production_id"], event["notice_gate"]["production_id"])
        self.assertEqual(hashlib.sha256(self.eligibility.read_bytes()).hexdigest(), event["notice_gate"]["eligibility_sha256"])
        self.assertEqual(content_before, self.content_ledger.read_bytes())
        self.assertEqual(1, len(self.publication_ledger.read_text().splitlines()))

    def test_identical_submission_cannot_create_duplicate_attempt(self):
        self.import_produced()
        self.submit()
        before = self.snapshot()
        result = self.submit(expected=2)
        self.assertFalse(result["allowed"])
        self.assertEqual(1, len(result["blocking_attempts"]))
        self.assertEqual(before, self.snapshot())

    def test_second_channel_reuses_same_produced_package(self):
        self.import_produced()
        first = self.submit()["event"]
        second = self.submit(platform="facebook", account="ptp_page_test")["event"]
        self.assertNotEqual(first["attempt_id"], second["attempt_id"])
        self.assertEqual(first["notice_gate"]["production_id"], second["notice_gate"]["production_id"])
        self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
        self.assertEqual(2, len(self.publication_ledger.read_text().splitlines()))

    def test_planned_release_after_deadline_blocks_new_attempt(self):
        self.import_produced()
        before = self.snapshot()
        result = self.submit("--status", "submitting", "--planned-publish-at",
                             (self.now + timedelta(days=2)).isoformat(), expected=2)
        self.assertIn("schedule_after_application_end", result["notice_gate"]["reasons"])
        self.assertEqual(before, self.snapshot())

    def test_expired_notice_still_allows_reconciling_existing_real_post(self):
        self.import_produced()
        initial = self.submit()["event"]
        self.evidence["application_period"]["end"] = (self.now - timedelta(seconds=10)).isoformat()
        self.save_evidence()
        self.assertFalse(self.gate()["allowed"])
        result = self.submit("--status", "published", "--attempt-id", initial["attempt_id"],
                             "--remote-url", "https://www.instagram.com/p/isolatedTest123/",
                             "--published-at", self.now.isoformat(), "--evidence", "Confirmed original submission result")
        self.assertEqual(initial["attempt_id"], result["event"]["attempt_id"])
        self.assertEqual("published", result["event"]["status"])
        self.assertEqual(2, len(self.publication_ledger.read_text().splitlines()))

    def test_unreadable_eligibility_and_corrupt_content_history_fail_closed(self):
        self.import_produced()
        self.eligibility.write_text("{broken", encoding="utf-8")
        self.rejected_without_events("notice_guard_input_or_history_error")
        self.save_evidence()
        self.content_ledger.write_text("{broken\n", encoding="utf-8")
        self.rejected_without_events("notice_guard_input_or_history_error")

    def test_supplied_manifest_copy_requires_its_own_intact_card_files(self):
        self.import_produced()
        alternate = self.root / "alternate"
        alternate.mkdir()
        copied_manifest = alternate / "package-manifest.json"
        copied_manifest.write_bytes(self.manifest.read_bytes())
        # The registry's original package is intact, but the submitted package
        # points to a missing card. Matching JSON fingerprints are insufficient.
        before = self.snapshot()
        result = self.gate(manifest=copied_manifest)
        self.assertFalse(result["allowed"], result)
        self.rejected_without_events("notice_guard_input_or_history_error", manifest=copied_manifest)
        (alternate / "01.png").write_bytes(PNG)
        self.assertTrue(self.gate(manifest=copied_manifest)["allowed"])
        self.assertEqual(before, self.snapshot())
        (alternate / "01.png").write_bytes(PNG + b"modified")
        result = self.gate(manifest=copied_manifest)
        self.assertFalse(result["allowed"], result)

    def test_unrelated_creative_job_does_not_read_shared_registry(self):
        self.assertIsNone(check_job({"workflow": "creative"}, self.root / "job.json"))
        result = check_job({"workflow": "notice-to-social"}, self.root / "job.json")
        self.assertFalse(result["allowed"])
        self.assertEqual(["notice_source_key_required"], result["reasons"])

    def test_job_relative_paths_resolve_against_job_directory(self):
        self.import_produced()
        before = self.snapshot()
        result = self.job_gate(self.job_fixture())
        self.assertTrue(result["allowed"], result)
        self.assertEqual(hashlib.sha256(self.manifest.read_bytes()).hexdigest(), result["manifest_sha256"])
        self.assertEqual(before, self.snapshot())

    def test_job_requires_nonempty_publication_targets(self):
        self.import_produced()
        for targets in (None, [], "instagram"):
            with self.subTest(targets=targets):
                job = self.job_fixture()
                if targets is None:
                    del job["publication"]["targets"]
                else:
                    job["publication"]["targets"] = targets
                result = self.job_gate(job)
                self.assertFalse(result["allowed"], result)
                self.assertEqual(["publication_targets_required"], result["reasons"])

    def test_job_blocks_an_already_published_target_channel(self):
        self.import_produced()
        attempt = self.submit()["event"]["attempt_id"]
        self.submit("--status", "published", "--attempt-id", attempt,
                    "--remote-url", "https://www.instagram.com/p/isolatedTest123/",
                    "--published-at", self.now.isoformat(), "--evidence", "Existing result verified")
        before = self.snapshot()
        result = self.job_gate(self.job_fixture())
        self.assertFalse(result["allowed"], result)
        self.assertEqual(["existing_or_unresolved_publication"], result["reasons"])
        self.assertEqual("published", result["history"]["blocking_attempts"][0]["status"])
        self.assertEqual(before, self.snapshot())

    def test_job_malformed_publication_is_blocked(self):
        for publication in (None, [], "malformed"):
            with self.subTest(publication=publication):
                job = self.job_fixture()
                job["publication"] = publication
                result = self.job_gate(job)
                self.assertFalse(result["allowed"])
                self.assertEqual(["publication_object_required"], result["reasons"])

    def test_before_publish_hook_checks_eligible_job_and_does_not_append(self):
        self.import_produced()
        before = self.snapshot()
        code, report = self.before_publish_hook(self.job_fixture())
        self.assertEqual(0, code, report)
        self.assertEqual("pass", report["status"])
        self.assertEqual(before, self.snapshot())

    def test_before_publish_hook_blocks_expired_job(self):
        self.import_produced()
        self.evidence["application_period"]["end"] = (self.now - timedelta(seconds=10)).isoformat()
        self.save_evidence()
        before = self.snapshot()
        code, report = self.before_publish_hook(self.job_fixture())
        self.assertEqual(3, code, report)
        self.assertEqual("block", report["status"])
        self.assertIn("application_closed", report["notice_gate"]["reasons"])
        self.assertEqual(before, self.snapshot())

    def test_before_publish_hook_does_not_require_notice_data_for_creative_job(self):
        code, report = self.before_publish_hook({"workflow": "creative", "publication": {"authorized": True}})
        self.assertEqual(0, code, report)
        self.assertEqual("pass", report["status"])
        self.assertFalse(self.content_ledger.exists())
        self.assertFalse(self.publication_ledger.exists())

    def test_before_publish_hook_blocks_malformed_publication(self):
        job = self.job_fixture()
        job["publication"] = []
        code, report = self.before_publish_hook(job)
        self.assertEqual(3, code, report)
        self.assertEqual("block", report["status"])

    def test_partial_publication_ledger_line_blocks_job_without_rewrite(self):
        self.import_produced()
        self.submit()
        self.publication_ledger.write_bytes(self.publication_ledger.read_bytes().rstrip(b"\n"))
        before = self.snapshot()
        result = self.job_gate(self.job_fixture())
        self.assertFalse(result["allowed"], result)
        self.assertEqual(["publication_history_or_targets_invalid"], result["reasons"])
        self.assertIn("incomplete final line", result["error"])
        self.assertEqual(before, self.snapshot())


class RuntimeContractIntegration(NoticePublishGuardTests):
    # Reuse the isolated base harness and also check legacy compatibility.
    def test_interactive_submission_validates_files_without_a_schedule(self):
        import content_preflight as quality
        import social_runtime as runtime
        from test_runtime_upgrade import spec_fixture

        spec = spec_fixture(self.root)
        spec['source_key'] = KEY
        spec_path = self.root / 'quality-spec.json'
        runtime.atomic_json(spec_path, spec)
        report = quality.review_quality(spec, self.root)
        self.assertTrue(report['passed'], report)
        report.update(spec_path=str(spec_path), spec_sha256=runtime.sha(spec_path))
        report_path = self.root / 'quality-report.json'
        runtime.atomic_json(report_path, report)
        reviewed_path = Path(report['images'][0]['path'])
        self.document['files'].extend(
            {'file': path.name, 'sha256': runtime.sha(path), 'bytes': path.stat().st_size}
            for path in (report_path, reviewed_path)
        )
        self.document.update(
            runtime_contract_version=1,
            runtime={'mode': 'interactive', 'quality_review_path': report_path.name},
            final_image_paths=[reviewed_path.name],
        )
        self.manifest.write_text(json.dumps(self.document), encoding='utf-8')
        self.import_produced()
        self.assertTrue(self.submit()['ok'])
        self.assertTrue(self.submit(platform='facebook', account='pohangtpoffcial')['ok'])
        self.assertFalse(self.submit(expected=2)['allowed'])

        bad_path = self.root / 'unregistered-report-manifest.json'
        bad_manifest = dict(self.document, runtime={'mode': 'interactive', 'quality_review_path': spec_path.name})
        runtime.atomic_json(bad_path, bad_manifest)
        blocked = check_start(KEY, bad_path, self.eligibility, self.content_ledger)
        self.assertIn('interactive_quality_report_must_be_registered', blocked['reasons'])

    def test_runtime_reserves_two_channels_under_same_owner(self):
        import social_runtime as runtime
        import content_preflight as quality
        from test_runtime_upgrade import fixture, spec_fixture, observation
        now=runtime.current_time()
        plan,state=fixture();row=plan['schedule'][0]
        row.update(board_id='123',source_key=KEY,publish_date=now.date().isoformat(),publish_time='00:00')
        plan.update(start_date=now.date().isoformat(),end_date=now.date().isoformat())
        state['allowed_notice_ids']=['123'];state['end_date']=plan['end_date']
        state['entries']={KEY:state['entries'].pop('ptp:15:7814')};state['entries'][KEY]['scheduled_date']=plan['start_date']
        pp=self.root/'plan.json';ep=self.root/'execution.json';runtime.atomic_json(pp,plan);runtime.atomic_json(ep,state)
        contract={'plan_path':str(pp),'execution_path':str(ep),'runtime_dir':str(self.root/'runtime')}
        initial_spec=spec_fixture(self.root)
        final_path=Path(initial_spec['images'][0]['path'])
        self.document['files'].append({'file':final_path.name,'sha256':runtime.sha(final_path),'bytes':final_path.stat().st_size})
        self.document.update(runtime_contract_version=1,runtime=contract,final_image_paths=[final_path.name])
        self.manifest.write_text(json.dumps(self.document),encoding='utf-8');self.import_produced()
        denied=self.submit(expected=2,account='pohangtp_official')
        self.assertFalse(denied['notice_gate']['allowed'])
        owner=runtime.claim(contract['runtime_dir'],'foundation-meta',KEY,'publish',now.isoformat(),'automation',plan_sha256=runtime.sha(pp))
        obs=observation();obs['checked_at']=now.isoformat()
        pf=runtime.evaluate_preflight(obs,{'instagram':'pohangtp_official','facebook':'pohangtpoffcial'},'automation')
        pfpath=self.root/'preflight.json';runtime.atomic_json(pfpath,pf)
        runtime.change_run(contract['runtime_dir'],'foundation-meta',owner['run_id'],stage='preflight',evidence=pfpath)
        spec=spec_fixture(self.root);spec['source_key']=KEY;sp=self.root/'quality-spec.json';runtime.atomic_json(sp,spec)
        report=quality.review_quality(spec,self.root);report.update(spec_path=str(sp),spec_sha256=runtime.sha(sp));qp=self.root/'quality-report.json';runtime.atomic_json(qp,report)
        runtime.change_run(contract['runtime_dir'],'foundation-meta',owner['run_id'],stage='ready',evidence=qp)
        bad=self.root/'unreviewed-manifest.json';bad_doc=dict(self.document,final_image_paths=['01.png']);runtime.atomic_json(bad,bad_doc)
        blocked=check_start(KEY,bad,self.eligibility,self.content_ledger,publication_ledger=self.publication_ledger)
        self.assertIn('runtime_reviewed_images_differ_from_submitted_manifest',blocked['reasons'])
        wrong=self.submit(expected=2,account='other_account');self.assertFalse(wrong['allowed'])
        a=self.submit(account='pohangtp_official');b=self.submit(platform='facebook',account='pohangtpoffcial')
        self.assertEqual(a['event']['runtime_run_id'],owner['run_id']);self.assertEqual(b['event']['runtime_run_id'],owner['run_id'])


if __name__ == "__main__":
    unittest.main()
