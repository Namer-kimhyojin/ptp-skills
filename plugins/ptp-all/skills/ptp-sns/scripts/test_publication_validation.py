#!/usr/bin/env python3
"""Isolated publication-job regressions. Fixtures declare synthetic test evidence."""

import json
import tempfile
import unittest
from pathlib import Path

import validate_publication as publication


def valid_fixture():
    text = (publication.ROOT / "assets" / "job-template.json").read_text(encoding="utf-8")
    job = json.loads(text.replace("【", "").replace("】", ""))
    job.update(status="locked", production_mode="publication")
    job["approvals"] = {key: "approved" for key in job["approvals"]}
    for character in job["characters"]:
        character["approval"] = "approved"
    for layer in job["design"]["visual_system"]["layer_plan"]:
        layer["rights_status"] = "approved"
    job["design"]["visual_system"]["photoreal_composite"]["rights_status"] = "approved"
    job["publication_asset_ids"] = [a for c in job["characters"] for a in c["anchor_ids"]]
    job["publication_review"] = {
        "brand_evidence": "SYNTHETIC TEST ONLY: approved character references, no CI usage",
        "rights_evidence": "SYNTHETIC TEST ONLY: rights checked for this fixture",
        "final_review_evidence": "SYNTHETIC TEST ONLY: layout and text inspection record",
        "reviewer": "Synthetic fixture reviewer; no real approval",
        "checked_at": "2026-10-22T12:00:00+09:00", "review_mode": "human",
    }
    return job


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ptp-publication-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "job.json"
        self.job = valid_fixture()

    def check(self):
        self.path.write_text(json.dumps(self.job, ensure_ascii=False), encoding="utf-8")
        return publication.validate(self.path)[0]

    def test_valid_selected_assets_pass_without_global_approval(self):
        before = publication.MANIFEST.read_bytes()
        self.assertEqual(self.check(), [])
        self.assertEqual(publication.MANIFEST.read_bytes(), before)

    def test_selected_review_only_ci_fails(self):
        self.job["publication_asset_ids"].append("AST-CI-USER")
        self.assertTrue(any("approved가 아닙니다" in e for e in self.check()))

    def test_undeclared_ci_source_path_fails(self):
        self.job["design"]["source_path"] = "assets/review/ptp-ci-user-provided.jpg"
        self.assertTrue(any("미승인 원본" in e for e in self.check()))

    def test_omitted_anchor_declaration_fails(self):
        self.job["publication_asset_ids"].remove("AST-ANCHOR-TEO-V12")
        self.assertTrue(any("모두 포함" in e for e in self.check()))

    def test_guide_cannot_replace_identity_anchor(self):
        self.job["characters"][0]["anchor_ids"] = ["AST-GUIDE-TEO-V10"]
        self.assertTrue(any("2D 정체성 앵커" in e for e in self.check()))

    def test_missing_policy_evidence_fails(self):
        self.job["publication_review"]["rights_evidence"] = ""
        self.assertTrue(any("rights_evidence" in e for e in self.check()))

    def test_delegated_review_requires_delegation(self):
        self.job["approvals"]["final_human_review"] = "not-applicable"
        self.job["publication_review"]["review_mode"] = "delegated"
        self.assertTrue(any("delegation_evidence" in e for e in self.check()))
        self.job["publication_review"]["delegation_evidence"] = "SYNTHETIC TEST ONLY: user explicitly delegated creation, review and publication"
        self.assertEqual(self.check(), [])

    def test_approved_human_review_cannot_be_delegated(self):
        self.job["publication_review"]["review_mode"] = "delegated"
        self.assertTrue(any("review_mode=human" in e for e in self.check()))

    def test_invalid_iso_date_fails(self):
        self.job["publication_review"]["checked_at"] = "2026-99-99"
        self.assertTrue(any("ISO" in e for e in self.check()))

    def test_date_and_naive_datetime_fail_but_zoned_values_pass(self):
        for value in ("2026-10-22", "2026-10-22T12:00:00"):
            with self.subTest(checked_at=value):
                self.job["publication_review"]["checked_at"] = value
                self.assertTrue(any("시간대가 포함된" in e for e in self.check()))
        for value in ("2026-10-22T12:00:00+09:00", "2026-10-22T03:00:00Z"):
            with self.subTest(checked_at=value):
                self.job["publication_review"]["checked_at"] = value
                self.assertEqual(self.check(), [])

    def test_pending_layer_rights_fails(self):
        self.job["design"]["visual_system"]["layer_plan"][0]["rights_status"] = "pending"
        self.assertTrue(any("rights_status" in e for e in self.check()))

    def test_duplicate_asset_ids_fail(self):
        self.job["publication_asset_ids"].append(self.job["publication_asset_ids"][0])
        self.assertTrue(any("중복 ID" in e for e in self.check()))


if __name__ == "__main__":
    unittest.main()
