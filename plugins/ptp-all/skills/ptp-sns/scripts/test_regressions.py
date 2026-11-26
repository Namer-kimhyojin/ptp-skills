#!/usr/bin/env python3
"""Regression checks for concept, composite, and webtoon gates."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from validate_job import validate as validate_job
from validate_webtoon_mode import validate as validate_webtoon


ROOT = Path(__file__).resolve().parent.parent


def write_json(folder: Path, name: str, data: object) -> Path:
    path = folder / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    base = json.loads((ROOT / "assets" / "job-template.json").read_text(encoding="utf-8"))
    quick = json.loads((ROOT / "assets" / "quick-job-template.json").read_text(encoding="utf-8"))
    comic = json.loads((ROOT / "assets" / "webtoon-mode-template.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ptp-skill-regression-") as raw:
        folder = Path(raw)

        integrated = copy.deepcopy(base)
        integrated["output"]["mode"] = "four-panel"
        integrated["platform_targets"][0]["content_type"] = "four-panel"
        integrated["comic"] = comic
        errors, _ = validate_job(write_json(folder, "valid-webtoon.json", integrated), False)
        require(not errors, "valid webtoon-integrated job must pass: " + "; ".join(errors))

        quick_comic = copy.deepcopy(quick)
        quick_comic["comic"] = comic
        errors, _ = validate_job(write_json(folder, "valid-quick-webtoon.json", quick_comic), False)
        require(not errors, "valid quick webtoon job must pass: " + "; ".join(errors))

        duplicate = copy.deepcopy(base)
        duplicate["concept_strategy"]["proposed_concept_ids"] = [
            "data-led-photo-editorial", "data-led-photo-editorial", "photoreal-business-scene"
        ]
        errors, _ = validate_job(write_json(folder, "bad-duplicate.json", duplicate), False)
        require(errors, "duplicate concepts must fail")

        flat = copy.deepcopy(base)
        flat["design"]["visual_system"]["layer_plan"][0]["source_type"] = "flat-shapes"
        errors, _ = validate_job(write_json(folder, "bad-flat.json", flat), False)
        require(any("평면 도형" in item for item in errors), "flat-only background must fail")

        lighting = copy.deepcopy(base)
        lighting["design"]["visual_system"]["photoreal_composite"]["lighting_match"] = False
        errors, _ = validate_job(write_json(folder, "bad-lighting.json", lighting), False)
        require(any("lighting_match" in item for item in errors), "missing lighting review must fail")

        high_resolution = copy.deepcopy(base)
        high_resolution["resolution_policy"].update({
            "profile_id": "high-resolution-master-2x",
            "deliver_upload_copy": True,
            "deliver_master_copy": True,
        })
        high_resolution["output"]["width_px"] *= 2
        high_resolution["output"]["height_px"] *= 2
        errors, _ = validate_job(write_json(folder, "valid-high-resolution.json", high_resolution), False)
        require(not errors, "high-resolution master job must pass: " + "; ".join(errors))

        upscaled = copy.deepcopy(base)
        upscaled["resolution_policy"]["upscale_existing_raster"] = True
        errors, _ = validate_job(write_json(folder, "bad-upscale.json", upscaled), False)
        require(any("확대" in item for item in errors), "finished-raster upscaling must fail")

        custom_missing = copy.deepcopy(base)
        custom_missing["resolution_policy"]["profile_id"] = "custom-pixel"
        custom_missing["resolution_policy"]["deliver_upload_copy"] = False
        errors, _ = validate_job(write_json(folder, "bad-custom-missing.json", custom_missing), False)
        require(any("custom_width_px" in item for item in errors), "custom pixel profile without dimensions must fail")

        custom_stretched = copy.deepcopy(base)
        custom_stretched["resolution_policy"].update({
            "profile_id": "custom-pixel",
            "deliver_upload_copy": False,
            "deliver_master_copy": True,
            "custom_width_px": 1600,
            "custom_height_px": 900,
            "adaptation_strategy": "preserve",
        })
        custom_stretched["output"]["width_px"] = 1600
        custom_stretched["output"]["height_px"] = 900
        errors, _ = validate_job(write_json(folder, "bad-custom-stretched.json", custom_stretched), False)
        require(any("종횡비" in item for item in errors), "changed custom aspect ratio without adaptation must fail")

        preview_as_final = copy.deepcopy(base)
        preview_as_final["resolution_policy"]["profile_id"] = "draft-preview-0.5x"
        preview_as_final["resolution_policy"]["deliver_upload_copy"] = False
        errors, _ = validate_job(write_json(folder, "bad-preview-final.json", preview_as_final), False)
        require(any("빠른 초안" in item for item in errors), "preview profile in standard mode must fail")

        panel_gap = copy.deepcopy(comic)
        panel_gap["panel_contract"][3]["panel"] = 6
        errors = validate_webtoon(write_json(folder, "bad-panel-gap.json", panel_gap))
        require(errors, "non-contiguous panel numbers must fail")

    print("OK: 11 regression checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
