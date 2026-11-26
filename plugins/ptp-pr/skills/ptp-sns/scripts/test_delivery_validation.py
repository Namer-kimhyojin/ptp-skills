#!/usr/bin/env python3
"""Delivery regressions for explicit shared cards and independent channel files."""

import contextlib
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import validate_delivery as delivery


def png(path, width=2, height=3, color=2):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    channels = 4 if color == 6 else 3
    pixels = (b"\0" + b"\xff" * width * channels) * height
    data = delivery.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class SharedDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ptp-delivery-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "out"
        self.out.mkdir()
        self.cards = [self.out / "cards" / f"{i:02}.png" for i in (1, 2)]
        for path in self.cards:
            png(path)
        self.job = {
            "job_id": "SYNTHETIC-DELIVERY-TEST", "requested_outputs": ["png"],
            "output": {"color_mode": "RGB", "shared_across_platforms": True},
            "platform_targets": [
                {
                    "platform": platform, "placement": "feed", "width_px": 2, "height_px": 3,
                    "content_variant_id": "shared-main", "target_count": 2,
                    "requested_outputs": ["png"], "format_counts": {"png": 2},
                    "file_naming": "{platform}/{job_id}_{placement}_{page_no:02}.png",
                    "shared_output_paths": [str(path) for path in self.cards],
                } for platform in ("instagram", "facebook")
            ],
        }

    def run_delivery(self):
        job_path = self.root / "job.json"
        manifest = self.root / "manifest.json"
        job_path.write_text(json.dumps(self.job), encoding="utf-8")
        args = ["validate_delivery.py", str(job_path), str(self.out), "--write-manifest", str(manifest)]
        # Isolate the file-delivery contract; the live job separately runs full structural validation.
        with patch.object(sys, "argv", args), patch.object(delivery, "validate_job_request", return_value=([], [])):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = delivery.main()
        return code, json.loads(manifest.read_text(encoding="utf-8"))

    def test_shared_cards_checked_for_each_target_with_real_hash_and_order(self):
        self.job["platform_targets"][1]["shared_output_paths"] = ["cards/01.png", "cards/02.png"]
        code, result = self.run_delivery()
        self.assertEqual(code, 0, result["errors"])
        self.assertEqual(len(result["files"]), 4)
        for index, record in enumerate(result["files"]):
            source = self.cards[index % 2]
            self.assertEqual(record["sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual((record["width_px"], record["height_px"], record["color_mode"]), (2, 3, "RGB"))
            self.assertEqual(record["page_no"], index % 2 + 1)
            self.assertTrue(record["shared_across_platforms"])

    def test_missing_card_fails(self):
        self.cards[1].unlink()
        code, result = self.run_delivery()
        self.assertEqual(code, 1)
        self.assertTrue(any("파일이 없습니다" in e for e in result["errors"]))

    def test_each_target_dimensions_and_color_are_checked(self):
        self.job["platform_targets"][1]["width_px"] = 9
        png(self.cards[0], color=6)
        code, result = self.run_delivery()
        self.assertEqual(code, 1)
        self.assertTrue(any("width_px 2 != 9" in e for e in result["errors"]))
        self.assertTrue(any("color_mode RGBA != RGB" in e for e in result["errors"]))

    def test_count_and_duplicate_paths_fail(self):
        for paths in ([str(self.cards[0])], [str(self.cards[0]), str(self.cards[0])]):
            with self.subTest(paths=paths):
                self.job["platform_targets"][0]["shared_output_paths"] = paths
                self.assertEqual(self.run_delivery()[0], 1)

    def test_shared_flag_requires_a_valid_explicit_list_for_each_target(self):
        for value in (None, [], "cards/01.png", [None, str(self.cards[1])]):
            with self.subTest(value=value):
                self.job["platform_targets"][1]["shared_output_paths"] = value
                self.assertEqual(self.run_delivery()[0], 1)

    def test_outside_output_path_is_rejected_without_reading(self):
        outside = self.root / "outside.png"
        png(outside)
        self.job["platform_targets"][0]["shared_output_paths"] = [str(outside), str(self.cards[1])]
        original = delivery.sha256
        def checked_hash(path):
            self.assertNotEqual(path, outside)
            return original(path)
        with patch.object(delivery, "sha256", side_effect=checked_hash):
            code, result = self.run_delivery()
        self.assertEqual(code, 1)
        self.assertTrue(any("출력 폴더 밖" in e for e in result["errors"]))

    def test_unrequested_extension_and_invalid_png_fail(self):
        wrong = self.out / "wrong.txt"
        wrong.write_text("not a card", encoding="utf-8")
        self.job["platform_targets"][0]["shared_output_paths"] = [str(wrong), str(self.cards[1])]
        self.cards[1].write_bytes(b"not PNG")
        code, result = self.run_delivery()
        self.assertEqual(code, 1)
        self.assertTrue(any("요청하지 않은 형식" in e for e in result["errors"]))
        self.assertTrue(any("PNG IHDR" in e for e in result["errors"]))

    def test_independent_channel_naming_remains_unchanged(self):
        self.job["output"]["shared_across_platforms"] = False
        for target in self.job["platform_targets"]:
            for i in (1, 2):
                path = self.out / delivery.expected_relative_path(
                    target["file_naming"], self.job["job_id"], target["platform"], target["placement"], i, "png"
                )
                png(path)
        code, result = self.run_delivery()
        self.assertEqual(code, 0, result["errors"])
        self.assertEqual(len(result["files"]), 4)
        self.assertTrue(all("shared_across_platforms" not in row for row in result["files"]))
        self.assertTrue(all("cards" not in row["file"] for row in result["files"]))

    def test_independent_mode_still_rejects_cross_target_reuse(self):
        self.job["output"]["shared_across_platforms"] = False
        for target in self.job["platform_targets"]:
            target["file_naming"] = "cards/{page_no:02}.png"
        code, result = self.run_delivery()
        self.assertEqual(code, 1)
        self.assertTrue(any("중복 배정" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
