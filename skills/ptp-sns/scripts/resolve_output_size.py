#!/usr/bin/env python3
"""Resolve final pixel or print dimensions from PTP output-size profiles."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_json(name: str) -> dict[str, object]:
    return json.loads((ROOT / "assets" / name).read_text(encoding="utf-8"))


def catalog(items: object) -> dict[str, dict[str, object]]:
    if not isinstance(items, list):
        return {}
    return {str(item["id"]): item for item in items if isinstance(item, dict) and item.get("id")}


def positive(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def pixel_size(width: int, height: int, scale: float) -> dict[str, int]:
    return {"width_px": max(1, round(width * scale)), "height_px": max(1, round(height * scale))}


def digital_target(
    preset: dict[str, object],
    profile: dict[str, object],
    custom_width: int | None,
    custom_height: int | None,
    adaptation: str,
) -> dict[str, object]:
    native_w = int(preset["width_px"])
    native_h = int(preset["height_px"])
    profile_id = str(profile["id"])
    native = {"width_px": native_w, "height_px": native_h}
    derivatives: list[dict[str, object]] = []

    if profile_id == "custom-pixel":
        if not positive(custom_width) or not positive(custom_height):
            raise ValueError("custom-pixel에는 --width-px와 --height-px가 필요합니다")
        primary = {"width_px": int(custom_width), "height_px": int(custom_height)}
        native_ratio = native_w / native_h
        custom_ratio = int(custom_width) / int(custom_height)
        ratio_changed = not math.isclose(native_ratio, custom_ratio, rel_tol=0.005)
        if ratio_changed and adaptation == "none":
            raise ValueError("사용자 지정 비율이 채널 프리셋과 다릅니다. --adaptation recompose|crop|letterbox를 선택하세요")
    else:
        scale = float(profile["scale_factor"])
        primary = pixel_size(native_w, native_h, scale)
        ratio_changed = False

    if profile.get("deliver_upload_copy") and primary != native:
        derivatives.append({"role": "channel-upload", **native, "source": "downsample-from-master"})

    return {
        "preset_id": preset["id"],
        "platform": preset.get("platform"),
        "placement": preset.get("placement"),
        "profile_id": profile_id,
        "primary": {"role": "master" if profile.get("deliver_master_copy") else "channel-upload", **primary},
        "derivatives": derivatives,
        "native_channel_size": native,
        "aspect_ratio_changed": ratio_changed,
        "adaptation_strategy": adaptation if ratio_changed else "preserve",
        "render_strategy": "render-from-source-at-primary-size",
        "upscale_existing_raster": False,
    }


def print_target(profile: dict[str, object], width_mm: float | None, height_mm: float | None, dpi: int | None) -> dict[str, object]:
    if not positive(width_mm) or not positive(height_mm) or not positive(dpi):
        raise ValueError("print-production에는 --width-mm, --height-mm, --dpi가 필요합니다")
    width_px = round(float(width_mm) / 25.4 * int(dpi))
    height_px = round(float(height_mm) / 25.4 * int(dpi))
    return {
        "profile_id": profile["id"],
        "primary": {
            "role": "print-master",
            "width_mm": float(width_mm),
            "height_mm": float(height_mm),
            "dpi": int(dpi),
            "width_px": width_px,
            "height_px": height_px,
        },
        "render_strategy": "render-from-source-at-print-pixels",
        "upscale_existing_raster": False,
        "preflight_required": ["bleed", "trim", "safe-area", "color-profile", "vendor-spec"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guide", action="store_true")
    parser.add_argument("--profile", default="channel-native-1x")
    parser.add_argument("--preset", action="append", default=[])
    parser.add_argument("--width-px", type=int)
    parser.add_argument("--height-px", type=int)
    parser.add_argument("--width-mm", type=float)
    parser.add_argument("--height-mm", type=float)
    parser.add_argument("--dpi", type=int)
    parser.add_argument("--adaptation", choices=["none", "recompose", "crop", "letterbox"], default="recompose")
    args = parser.parse_args()

    try:
        profiles = catalog(load_json("output-size-profiles.json").get("profiles"))
        presets = catalog(load_json("platform-presets.json").get("presets"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: 크기 카탈로그를 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1

    if args.guide:
        print(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2))
        return 0
    profile = profiles.get(args.profile)
    if profile is None:
        print(f"ERROR: 등록되지 않은 해상도 프로필입니다: {args.profile}", file=sys.stderr)
        return 2

    try:
        if profile.get("medium") == "print":
            result: object = print_target(profile, args.width_mm, args.height_mm, args.dpi)
        else:
            if not args.preset:
                raise ValueError("디지털 출력에는 하나 이상의 --preset이 필요합니다")
            targets = []
            for preset_id in args.preset:
                preset = presets.get(preset_id)
                if preset is None:
                    raise ValueError(f"등록되지 않은 채널 프리셋입니다: {preset_id}")
                targets.append(digital_target(preset, profile, args.width_px, args.height_px, args.adaptation))
            result = {"profile": profile, "targets": targets}
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
