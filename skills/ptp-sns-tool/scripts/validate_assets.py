#!/usr/bin/env python3
"""Validate a PTP character-content asset manifest using only stdlib."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


ALLOWED_KINDS = {"character-guide", "brand-reference", "character-anchor", "3d-style-reference", "logo", "font", "other"}
ALLOWED_APPROVALS = {"review_only", "approved", "rejected"}
PNG_MODES = {0: "L", 2: "RGB", 3: "P", 4: "LA", 6: "RGBA"}
REQUIREMENT_KEYS = {
    "identity_rule_set",
    "character_guide_set",
    "character_anchor_set",
    "three_d_style_set",
    "pose_library_set",
    "context_routing_set",
    "typography_set",
    "channel_preset_set",
    "output_size_profile_set",
    "output_format_set",
    "visual_concept_set",
    "webtoon_mode_set",
    "brand_guide",
    "rights_and_ai_policy",
}
FONT_SUFFIXES = {".ttf", ".otf"}
DOCUMENT_SUFFIXES = {".json", ".css", ".html", ".md", ".txt"}


def read_png_header(path: Path) -> tuple[int, int, str]:
    with path.open("rb") as handle:
        header = handle.read(33)
    if len(header) < 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("유효한 PNG IHDR을 읽을 수 없습니다")
    width, height, _bit_depth, color_type = struct.unpack(">IIBB", header[16:26])
    if color_type not in PNG_MODES:
        raise ValueError(f"지원하지 않는 PNG 색상 유형입니다: {color_type}")
    return width, height, PNG_MODES[color_type]


def read_jpeg_header(path: Path) -> tuple[int, int, str]:
    data = path.read_bytes()
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ValueError("유효한 JPEG 시작 표식을 읽을 수 없습니다")
    position = 2
    sof_markers = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while position + 3 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[position : position + 2])[0]
        if segment_length < 2 or position + segment_length > len(data):
            break
        if marker in sof_markers:
            if segment_length < 8:
                break
            height, width = struct.unpack(">HH", data[position + 3 : position + 7])
            components = data[position + 7]
            modes = {1: "L", 3: "RGB", 4: "CMYK"}
            return width, height, modes.get(components, f"JPEG-{components}-component")
        position += segment_length
    raise ValueError("JPEG 크기 정보를 읽을 수 없습니다")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_validation_cache(cache_dir: Path | None) -> tuple[Path | None, dict[str, object]]:
    if cache_dir is None:
        return None, {}
    path = cache_dir.resolve() / "asset-validation-cache.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        data = {}
    items = data.get("items") if isinstance(data, dict) else None
    return path, items if isinstance(items, dict) else {}


def write_validation_cache(path: Path | None, items: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"schema_version": "1.0", "items": items}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validate(
    manifest_path: Path,
    require_locked: bool,
    level: str = "standard",
    cache_dir: Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"매니페스트를 읽을 수 없습니다: {exc}"], warnings

    if require_locked:
        level = "publication"
    fast = level == "fast"
    cache_path, cached_items = load_validation_cache(cache_dir if level == "standard" else None)
    updated_cache = dict(cached_items)

    if data.get("schema_version") not in {"1.0", "1.2"}:
        errors.append("schema_version은 '1.0' 또는 '1.2'여야 합니다")
    status = data.get("status")
    if status not in {"review_only", "identity_locked", "locked"}:
        errors.append("status는 review_only, identity_locked 또는 locked여야 합니다")
    if not isinstance(data.get("project_id"), str) or not data["project_id"].strip():
        errors.append("project_id가 필요합니다")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        errors.append("assets는 하나 이상의 항목을 가진 배열이어야 합니다")
        assets = []

    base = manifest_path.parent.resolve()
    seen_ids: set[str] = set()
    for index, asset in enumerate(assets):
        label = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        asset_id = asset.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            errors.append(f"{label}.id가 필요합니다")
        elif asset_id in seen_ids:
            errors.append(f"중복 자산 ID입니다: {asset_id}")
        else:
            seen_ids.add(asset_id)
        if asset.get("kind") not in ALLOWED_KINDS:
            errors.append(f"{label}.kind가 허용 목록에 없습니다")
        if asset.get("approval") not in ALLOWED_APPROVALS:
            errors.append(f"{label}.approval이 올바르지 않습니다")

        relative = asset.get("path")
        if not isinstance(relative, str) or not relative.strip():
            errors.append(f"{label}.path가 필요합니다")
            continue
        file_path = (base / relative).resolve()
        try:
            file_path.relative_to(base)
        except ValueError:
            errors.append(f"{label}.path가 assets 폴더 밖을 가리킵니다")
            continue
        if not file_path.is_file():
            errors.append(f"자산 파일이 없습니다: {relative}")
            continue

        if fast:
            continue

        stat = file_path.stat()
        contract = hashlib.sha256(
            json.dumps(asset, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        signature = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "contract": contract,
        }
        if level == "standard" and cached_items.get(relative) == signature:
            continue
        error_count_before_asset_checks = len(errors)

        expected_hash = asset.get("sha256")
        if not isinstance(expected_hash, str) or len(expected_hash) != 64 or expected_hash.lower() != expected_hash:
            errors.append(f"{label}.sha256은 소문자 64자리여야 합니다")
        elif sha256(file_path) != expected_hash:
            errors.append(f"해시가 일치하지 않습니다: {relative}")

        suffix = file_path.suffix.lower()
        kind = asset.get("kind")
        if suffix == ".png":
            try:
                width, height, mode = read_png_header(file_path)
            except ValueError as exc:
                errors.append(f"{relative}: {exc}")
                continue
            if asset.get("width_px") != width or asset.get("height_px") != height:
                errors.append(f"크기가 매니페스트와 다릅니다: {relative} ({width}x{height})")
            if asset.get("color_mode") != mode:
                errors.append(f"색상 모드가 매니페스트와 다릅니다: {relative} ({mode})")
        elif suffix in {".jpg", ".jpeg"}:
            try:
                width, height, mode = read_jpeg_header(file_path)
            except ValueError as exc:
                errors.append(f"{relative}: {exc}")
                continue
            if asset.get("width_px") != width or asset.get("height_px") != height:
                errors.append(f"크기가 매니페스트와 다릅니다: {relative} ({width}x{height})")
            if asset.get("color_mode") != mode:
                errors.append(f"색상 모드가 매니페스트와 다릅니다: {relative} ({mode})")
        elif kind == "font":
            if suffix not in FONT_SUFFIXES:
                errors.append(f"{label} font 자산은 TTF 또는 OTF여야 합니다")
            if not isinstance(asset.get("font_family"), str) or not asset["font_family"].strip():
                errors.append(f"{label}.font_family가 필요합니다")
            weight = asset.get("font_weight")
            if not isinstance(weight, int) or weight < 100 or weight > 900 or weight % 100:
                errors.append(f"{label}.font_weight는 100~900 사이의 100 단위 정수여야 합니다")
            license_path = asset.get("license_path")
            if not isinstance(license_path, str) or not license_path.strip():
                errors.append(f"{label}.license_path가 필요합니다")
            else:
                license_file = (base / license_path).resolve()
                try:
                    license_file.relative_to(base)
                except ValueError:
                    errors.append(f"{label}.license_path가 assets 폴더 밖을 가리킵니다")
                else:
                    if not license_file.is_file():
                        errors.append(f"폰트 라이선스 파일이 없습니다: {license_path}")
        elif suffix in DOCUMENT_SUFFIXES:
            if not isinstance(asset.get("media_type"), str) or not asset["media_type"].strip():
                errors.append(f"{label}.media_type이 필요합니다")
        else:
            if not isinstance(asset.get("width_px"), int) or asset["width_px"] <= 0:
                errors.append(f"{label}.width_px는 양의 정수여야 합니다")
            if not isinstance(asset.get("height_px"), int) or asset["height_px"] <= 0:
                errors.append(f"{label}.height_px는 양의 정수여야 합니다")
        if level == "standard" and len(errors) == error_count_before_asset_checks:
            updated_cache[relative] = signature

    requirements = data.get("production_requirements")
    if not isinstance(requirements, dict):
        errors.append("production_requirements 객체가 필요합니다")
        requirements = {}
    for key in REQUIREMENT_KEYS:
        item = requirements.get(key)
        if not isinstance(item, dict) or item.get("status") not in {"pending", "locked"}:
            errors.append(f"production_requirements.{key}.status가 필요합니다")

    style_set = requirements.get("three_d_style_set")
    if isinstance(style_set, dict):
        spec_asset = style_set.get("spec_asset")
        candidates = style_set.get("candidate_assets")
        if spec_asset not in seen_ids:
            errors.append("three_d_style_set.spec_asset이 등록 자산을 가리켜야 합니다")
        if (
            not isinstance(candidates, list)
            or len(candidates) != 3
            or any(item not in seen_ids for item in candidates)
            or len(set(candidates)) != 3
        ):
            errors.append("three_d_style_set.candidate_assets는 등록된 서로 다른 3D 자산 3개여야 합니다")
        if style_set.get("identity_authority") != "character_anchor_set":
            errors.append("three_d_style_set.identity_authority는 character_anchor_set이어야 합니다")
        if style_set.get("status") == "locked":
            asset_approvals = {
                item.get("id"): item.get("approval") for item in assets if isinstance(item, dict)
            }
            for asset_id in [spec_asset, *(candidates if isinstance(candidates, list) else [])]:
                if asset_approvals.get(asset_id) != "approved":
                    errors.append(f"잠긴 3D 스타일 자산은 approved여야 합니다: {asset_id}")

    if require_locked:
        if status != "locked":
            errors.append("최종 승인 검사에서는 매니페스트 status가 locked여야 합니다")
        for asset in assets:
            if isinstance(asset, dict) and asset.get("approval") != "approved":
                errors.append(f"승인되지 않은 자산입니다: {asset.get('id', '(unknown)')}")
        for key in REQUIREMENT_KEYS:
            item = requirements.get(key, {})
            if not isinstance(item, dict) or item.get("status") != "locked":
                errors.append(f"최종 승인 전 잠금이 필요합니다: {key}")
    else:
        if fast:
            warnings.append("fast 검증은 자산 해시·이미지 헤더·폰트 세부 검사를 생략합니다")
        if status == "review_only":
            warnings.append("현재 자산은 검토용입니다. 외부 공개 결과물에 사용하지 마세요")
        elif status == "identity_locked":
            warnings.append("캐릭터 정체성은 확정됐지만 브랜드·권리·제작 사양은 작업별 확인이 필요합니다")
        for key in REQUIREMENT_KEYS:
            item = requirements.get(key, {})
            if isinstance(item, dict) and item.get("status") == "pending":
                warnings.append(f"미확정 생산 요건: {key}")

    if level == "standard" and not errors:
        write_validation_cache(cache_path, updated_cache)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent / "assets" / "asset-manifest.json")
    parser.add_argument("--require-locked", action="store_true")
    parser.add_argument("--level", choices=["fast", "standard", "publication"], default="standard")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    require_locked = args.require_locked or args.level == "publication"
    errors, warnings = validate(args.manifest.resolve(), require_locked, args.level, args.cache_dir)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK: asset manifest is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
