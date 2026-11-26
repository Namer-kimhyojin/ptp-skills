#!/usr/bin/env python3
"""Measure routed-context reduction and local validation/cache performance."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from resolve_context import resolve
from validate_assets import validate as validate_assets
from validate_job import validate as validate_job, validate_fast


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "asset-manifest.json"


def timed(callable_obj, repeats: int = 3) -> tuple[object, float]:
    samples: list[float] = []
    result: object = None
    for _ in range(repeats):
        started = time.perf_counter()
        result = callable_obj()
        samples.append((time.perf_counter() - started) * 1000)
    return result, round(statistics.median(samples), 3)


def route(production_mode: str, content_type: str, pose: str | None) -> dict[str, object]:
    return resolve(argparse.Namespace(
        production_mode=production_mode, content_type=content_type, character="both", render_style="3d",
        pose=pose, platform="instagram", formats=["png"], photoreal=False, print_output=False,
    ))


def check_result(result: object, label: str) -> None:
    errors = result[0] if isinstance(result, tuple) and result else ["unexpected result"]
    if errors:
        raise RuntimeError(f"{label}: {'; '.join(str(item) for item in errors)}")


def main() -> int:
    reference_dir = ROOT / "references"
    full_reference_bytes = sum(path.stat().st_size for path in reference_dir.glob("*.md"))
    quick_route, quick_route_ms = timed(lambda: route("quick-draft", "social-post", "open-hand-guide"))
    standard_route, standard_route_ms = timed(lambda: route("standard", "four-panel", "tablet"))

    quick_validation, fast_ms = timed(lambda: validate_fast(ROOT / "assets" / "quick-job-template.json"))
    standard_validation, standard_job_ms = timed(lambda: validate_job(ROOT / "assets" / "job-template.json", False))
    check_result(quick_validation, "fast job validation")
    check_result(standard_validation, "standard job validation")

    with tempfile.TemporaryDirectory(prefix="ptp-benchmark-") as raw:
        cache_dir = Path(raw) / "asset-cache"
        cold, asset_cold_ms = timed(lambda: validate_assets(MANIFEST, False, "standard", cache_dir), repeats=1)
        hot, asset_hot_ms = timed(lambda: validate_assets(MANIFEST, False, "standard", cache_dir), repeats=3)
        check_result(cold, "cold asset validation")
        check_result(hot, "hot asset validation")

        dependency = Path(raw) / "source.txt"
        output = Path(raw) / "output.png"
        layer_cache = Path(raw) / "layers"
        dependency.write_text("source", encoding="utf-8")
        output.write_text("output", encoding="utf-8")
        base = [sys.executable, str(ROOT / "scripts" / "layer_cache.py"), "record", "--cache-dir", str(layer_cache),
                "--layer", "character", "--dependency", f"source={dependency}", "--value", "pose=tablet", "--output", str(output)]
        subprocess.run(base, check=True, capture_output=True)
        check = base.copy()
        check[2] = "check"
        del check[check.index("--output"):]
        layer_result, layer_check_ms = timed(lambda: subprocess.run(check, capture_output=True), repeats=3)
        layer_reuse = getattr(layer_result, "returncode", 1) == 0

    def reduction(routed: dict[str, object]) -> float:
        return round((1 - int(routed["reference_bytes"]) / full_reference_bytes) * 100, 1)

    report = {
        "schema_version": "1.0",
        "baseline": {"all_reference_bytes": full_reference_bytes},
        "routing": {
            "quick_social_3d": {"reference_bytes": quick_route["reference_bytes"], "reduction_percent": reduction(quick_route), "median_ms": quick_route_ms},
            "standard_four_panel_3d": {"reference_bytes": standard_route["reference_bytes"], "reduction_percent": reduction(standard_route), "median_ms": standard_route_ms},
        },
        "validation": {
            "quick_job_median_ms": fast_ms,
            "standard_job_median_ms": standard_job_ms,
            "assets_cold_ms": asset_cold_ms,
            "assets_hot_median_ms": asset_hot_ms,
        },
        "layer_cache": {"reuse": layer_reuse, "check_median_ms": layer_check_ms},
        "image_generation_policy": {
            "approved_pose_count": 16,
            "character_generation_calls_when_pose_fits": 0,
            "new_character_generation": "only when no approved pose communicates the required action"
        }
    }
    if not layer_reuse or reduction(quick_route) <= 0 or reduction(standard_route) <= 0:
        raise RuntimeError("optimization benchmark did not demonstrate reuse and context reduction")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
