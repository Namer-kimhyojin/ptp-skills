#!/usr/bin/env python3
"""Regression checks for context routing, phased validation, pose reuse, and layer cache."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from resolve_context import resolve
from validate_job import validate_fast
from validate_pose_library import validate as validate_pose_library


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def context(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "production_mode": "standard", "content_type": "social-post", "character": "both",
        "render_style": "3d", "pose": None, "platform": "instagram", "formats": ["png"],
        "photoreal": False, "print_output": False,
    }
    values.update(overrides)
    return resolve(argparse.Namespace(**values))


def run_layer_cache(folder: Path) -> None:
    dependency = folder / "source.txt"
    output = folder / "character.png"
    cache_dir = folder / ".ptp-cache"
    dependency.write_text("source-v1", encoding="utf-8")
    output.write_text("render-v1", encoding="utf-8")
    common = [
        sys.executable, str(SCRIPTS / "layer_cache.py"),
        "record", "--cache-dir", str(cache_dir), "--layer", "character",
        "--dependency", f"source={dependency}", "--value", "pose=wave", "--output", str(output),
    ]
    require(subprocess.run(common, capture_output=True).returncode == 0, "layer record must pass")
    check = common.copy()
    check[2] = "check"
    output_index = check.index("--output")
    del check[output_index:output_index + 2]
    require(subprocess.run(check, capture_output=True).returncode == 0, "unchanged layer must be reusable")
    dependency.write_text("source-v2", encoding="utf-8")
    require(subprocess.run(check, capture_output=True).returncode == 3, "changed dependency must invalidate layer")


def main() -> int:
    quick = context(production_mode="quick-draft", pose="wave")
    require(quick["validation_level"] == "fast", "quick route must select fast validation")
    require("references/brand-rights.md" not in quick["references"], "quick route must not load publication policy")
    require(any(str(path).endswith("teo/08-wave.png") for path in quick["assets"]), "Teo wave pose must resolve")
    require(any(str(path).endswith("pio/08-wave.png") for path in quick["assets"]), "Pio wave pose must resolve")

    standard = context(content_type="four-panel", pose="tablet")
    require("references/webtoon-content-mode.md" in standard["references"], "comic route must load comic rules")
    require(standard["validation_level"] == "standard", "standard route must select standard validation")

    publication = context(production_mode="publication", content_type="poster", character="teo", platform="custom", formats=["pdf"], print_output=True)
    require("references/brand-rights.md" in publication["references"], "publication print route must load rights rules")
    require(publication["validation_level"] == "publication", "publication route must select full validation")

    all_paths = list(quick["references"]) + list(quick["assets"]) + list(quick["validators"])
    require(all((ROOT / str(path)).is_file() for path in all_paths), "all routed paths must exist")
    fast_errors, _ = validate_fast(ROOT / "assets" / "quick-job-template.json")
    require(not fast_errors, "quick template must pass fast validation: " + "; ".join(fast_errors))
    require(not validate_pose_library(), "pose library must pass validation")
    with tempfile.TemporaryDirectory(prefix="ptp-optimization-") as raw:
        run_layer_cache(Path(raw))
    print("OK: 10 optimization checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
