#!/usr/bin/env python3
"""Resolve one or more SNS presets into a quick production plan."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ALLOWED_FORMATS = {"png", "pdf", "html"}
SOURCE_LABELS = {
    "official-platform": "공식",
    "mixed": "혼합",
    "project-default": "제작 기본",
    "user-provided": "사용자 제공",
    "vendor-provided": "업체 제공",
}


def load_catalog() -> dict[str, object]:
    path = Path(__file__).resolve().parent.parent / "assets" / "platform-presets.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="프리셋 목록 출력")
    parser.add_argument("--guide", action="store_true", help="플랫폼별 유형·크기·비율 안내")
    parser.add_argument("--platform", help="목록을 플랫폼으로 필터")
    parser.add_argument("--preset", action="append", default=[], help="프리셋 ID, 여러 번 사용 가능")
    parser.add_argument("--formats", default="png", help="쉼표 구분: png,pdf,html")
    parser.add_argument("--count", type=int, default=1, help="프리셋별 산출물 수")
    parser.add_argument("--mode", choices=["quick-draft", "standard", "publication"], default="quick-draft")
    parser.add_argument(
        "--authoring-mode",
        choices=["auto", "individual", "integrated"],
        default="auto",
        help="개별 작성, 통합 작성 또는 선택 수에 따른 자동 결정",
    )
    parser.add_argument("--out", type=Path, help="생성 계획 JSON 경로")
    args = parser.parse_args()

    try:
        catalog = load_catalog()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: 프리셋을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1

    presets = catalog.get("presets", [])
    if not isinstance(presets, list):
        print("ERROR: presets 배열이 없습니다", file=sys.stderr)
        return 1
    ids = [item.get("id") for item in presets if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        print("ERROR: 중복 프리셋 ID가 있습니다", file=sys.stderr)
        return 1
    for item in presets:
        if not isinstance(item, dict):
            print("ERROR: 프리셋 항목은 객체여야 합니다", file=sys.stderr)
            return 1
        if not isinstance(item.get("width_px"), int) or not isinstance(item.get("height_px"), int):
            print(f"ERROR: 프리셋 크기가 올바르지 않습니다: {item.get('id')}", file=sys.stderr)
            return 1
        if item["width_px"] <= 0 or item["height_px"] <= 0:
            print(f"ERROR: 프리셋 크기는 양수여야 합니다: {item.get('id')}", file=sys.stderr)
            return 1

    if args.list:
        rows = [p for p in presets if isinstance(p, dict) and (not args.platform or p.get("platform") == args.platform)]
        for item in rows:
            print(f"{item.get('id')}\t{item.get('width_px')}x{item.get('height_px')}\t{item.get('source_strength')}")
        return 0

    if args.guide:
        rows = [p for p in presets if isinstance(p, dict) and (not args.platform or p.get("platform") == args.platform)]
        grouped: dict[str, list[dict[str, object]]] = {}
        for item in rows:
            grouped.setdefault(str(item.get("platform")), []).append(item)
        for platform, items in grouped.items():
            print(f"[{platform}]")
            for item in items:
                source_label = SOURCE_LABELS.get(str(item.get("source_strength")), str(item.get("source_strength")))
                print(
                    f"- {item.get('id')}: {item.get('width_px')}x{item.get('height_px')} "
                    f"({item.get('aspect_ratio')}) [{source_label}]"
                )
            print()
        print("작성 방식: individual=유형별 독립 문구·레이아웃, integrated=공통 원고를 규격별 재배치")
        return 0

    if not args.preset:
        print("ERROR: --preset, --list 또는 --guide가 필요합니다", file=sys.stderr)
        return 2
    if args.count <= 0:
        print("ERROR: --count는 양수여야 합니다", file=sys.stderr)
        return 2

    formats = [item.strip().lower() for item in args.formats.split(",") if item.strip()]
    unknown_formats = sorted(set(formats) - ALLOWED_FORMATS)
    if not formats or unknown_formats:
        print(f"ERROR: 지원하지 않는 형식: {', '.join(unknown_formats) or '(empty)'}", file=sys.stderr)
        return 2

    by_id = {item.get("id"): item for item in presets if isinstance(item, dict)}
    missing = [preset_id for preset_id in args.preset if preset_id not in by_id]
    if missing:
        print(f"ERROR: 없는 프리셋: {', '.join(missing)}", file=sys.stderr)
        return 2
    if len(args.preset) != len(set(args.preset)):
        print("ERROR: 같은 프리셋을 중복 선택할 수 없습니다", file=sys.stderr)
        return 2

    authoring_mode = args.authoring_mode
    if authoring_mode == "auto":
        authoring_mode = "integrated" if len(args.preset) > 1 else "individual"
    if authoring_mode == "integrated" and len(args.preset) < 2:
        print("ERROR: 통합 작성에는 두 개 이상의 프리셋이 필요합니다", file=sys.stderr)
        return 2

    targets = []
    for preset_id in args.preset:
        item = dict(by_id[preset_id])
        item["preset_id"] = item.pop("id")
        item["content_variant_id"] = "shared-main" if authoring_mode == "integrated" else preset_id
        if item.get("platform") == "kakao-channel":
            item["content_type"] = "channel-message"
        elif item.get("placement") in {"story", "reels-cover", "reels-vertical"}:
            item["content_type"] = "social-story"
        else:
            item["content_type"] = "social-post"
        item["target_count"] = args.count
        item["requested_outputs"] = formats
        item["format_counts"] = {fmt: args.count if fmt == "png" else 1 for fmt in formats}
        item["file_naming"] = "{job_id}_{platform}_{placement}_{page_no:02d}"
        item["spec_checked_at"] = catalog.get("checked_at")
        targets.append(item)

    plan = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_mode": args.mode,
        "authoring_mode": authoring_mode,
        "catalog_checked_at": catalog.get("checked_at"),
        "requested_outputs": formats,
        "platform_targets": targets,
        "publication": {"requested": False, "authorized": False},
    }
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.out.resolve().write_text(rendered, encoding="utf-8")
        print(f"PLAN: {args.out.resolve()}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
