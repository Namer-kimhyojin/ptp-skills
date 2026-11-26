#!/usr/bin/env python3
"""Validate delivered PNG, PDF, and HTML files and write a delivery manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_job import validate as validate_job_request


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_COLOR_MODES = {0: "GRAYSCALE", 2: "RGB", 3: "INDEXED", 4: "GRAYSCALE_ALPHA", 6: "RGBA"}
SUPPORTED_FORMATS = {"png", "pdf", "html"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_png(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        header = handle.read(26)
    if len(header) < 26 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("유효한 PNG IHDR을 찾을 수 없습니다")
    width, height = struct.unpack(">II", header[16:24])
    return {
        "width_px": width,
        "height_px": height,
        "bit_depth": header[24],
        "color_mode": PNG_COLOR_MODES.get(header[25], f"UNKNOWN_{header[25]}"),
    }


def inspect_pdf(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("PDF 서명이 없습니다")
    page_markers = len(re.findall(rb"/Type\s*/Page\b", data))
    return {"pdf_signature": data[:8].decode("ascii", errors="replace"), "page_markers": page_markers}


def inspect_html(path: Path) -> tuple[dict[str, object], list[str]]:
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"UTF-8 HTML이 아닙니다: {exc}") from exc
    lowered = text.lower()
    if "<html" not in lowered and "<!doctype html" not in lowered:
        raise ValueError("HTML 문서 루트가 없습니다")
    if "paperlogy" not in lowered:
        warnings.append(f"{path.name}: Paperlogy 참조를 찾지 못했습니다")
    image_tags = re.findall(r"<img\b[^>]*>", lowered)
    missing_alt = sum(1 for tag in image_tags if not re.search(r"\balt\s*=", tag))
    if missing_alt:
        warnings.append(f"{path.name}: alt 속성이 없는 이미지가 {missing_alt}개 있습니다")
    page_tokens = [int(value) for value in re.findall(r"\bdata-card-page\s*=\s*[\"'](\d+)[\"']", lowered)]
    return {
        "html_chars": len(text),
        "paperlogy_reference": "paperlogy" in lowered,
        "image_count": len(image_tags),
        "missing_alt_count": missing_alt,
        "card_pages": page_tokens,
    }, warnings


def expected_relative_path(
    naming: str,
    job_id: str,
    platform: str,
    placement: str,
    page_no: int,
    extension: str,
) -> Path:
    rendered = naming.format(
        job_id=job_id,
        platform=platform,
        placement=placement,
        page_no=page_no,
        extension=extension,
        ext=extension,
    )
    path = Path(rendered)
    if path.suffix.lower() != f".{extension}":
        path = path.with_name(f"{path.name}.{extension}")
    return path


def expected_formats(job: dict[str, object], output: dict[str, object]) -> list[str]:
    requested = job.get("requested_outputs")
    if isinstance(requested, list) and requested:
        return [str(item).lower() for item in requested]
    extension = str(output.get("extension", ".png")).lower().lstrip(".")
    return [extension]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--write-manifest", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    try:
        job = json.loads(args.job.resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ERROR: 작업 요청서를 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1

    job_errors, job_warnings = validate_job_request(args.job.resolve(), require_locked=False)
    errors.extend(f"작업 요청서: {message}" for message in job_errors)
    warnings.extend(f"작업 요청서: {message}" for message in job_warnings)

    output = job.get("output") if isinstance(job.get("output"), dict) else {}
    formats = expected_formats(job, output)
    unknown = sorted(set(formats) - SUPPORTED_FORMATS)
    if unknown:
        print(f"ERROR: 지원하지 않는 납품 형식: {', '.join(unknown)}", file=sys.stderr)
        return 1

    output_dir = args.output_dir.resolve()
    if not output_dir.is_dir():
        print(f"ERROR: 산출물 폴더가 없습니다: {output_dir}", file=sys.stderr)
        return 1

    expected_mode = str(output.get("color_mode", "")).upper()
    platform_targets = job.get("platform_targets") if isinstance(job.get("platform_targets"), list) else []
    shared_outputs = output.get("shared_across_platforms") is True
    records: list[dict[str, object]] = []
    assigned: set[Path] = set()

    if platform_targets:
        for index, target in enumerate(platform_targets):
            if not isinstance(target, dict):
                continue
            platform = str(target.get("platform", ""))
            placement = str(target.get("placement", ""))
            job_id = str(job.get("job_id", ""))
            prefix = f"{job_id}_{platform}_{placement}_"
            target_formats = target.get("requested_outputs") if isinstance(target.get("requested_outputs"), list) else formats
            counts = target.get("format_counts") if isinstance(target.get("format_counts"), dict) else {}
            width = target.get("width_px")
            height = target.get("height_px")
            target_pages = target.get("target_count")
            naming = str(target.get("file_naming", "{job_id}_{platform}_{placement}_{page_no:02d}"))
            shared_paths: list[Path] = []
            if shared_outputs:
                declared = target.get("shared_output_paths")
                if not isinstance(declared, list) or not declared:
                    errors.append(f"platform_targets[{index}].shared_output_paths는 비어 있지 않은 경로 배열이어야 합니다")
                    declared = []
                for item in declared:
                    if not isinstance(item, str) or not item.strip():
                        errors.append(f"platform_targets[{index}].shared_output_paths에 유효하지 않은 경로가 있습니다")
                        continue
                    path = (output_dir / item).resolve()
                    try:
                        path.relative_to(output_dir)
                    except ValueError:
                        errors.append(f"platform_targets[{index}].shared_output_paths가 출력 폴더 밖을 가리킵니다: {path}")
                        continue
                    if path.suffix.lower().lstrip(".") not in target_formats:
                        errors.append(f"platform_targets[{index}].shared_output_paths에 요청하지 않은 형식이 있습니다: {path.name}")
                        continue
                    shared_paths.append(path)
            for extension in target_formats:
                expected_count = counts.get(extension, target_pages if extension == "png" else 1)
                expected_count = int(expected_count) if isinstance(expected_count, (int, float)) else 0
                if shared_outputs:
                    expected_paths = [path for path in shared_paths if path.suffix.lower() == f".{extension}"]
                    if len(expected_paths) != expected_count:
                        errors.append(
                            f"platform_targets[{index}].shared_output_paths {extension.upper()} 개수가 다릅니다: "
                            f"예상 {expected_count}, 실제 {len(expected_paths)}"
                        )
                else:
                    try:
                        expected_paths = [
                            (output_dir / expected_relative_path(naming, job_id, platform, placement, page_no, extension)).resolve()
                            for page_no in range(1, expected_count + 1)
                        ]
                    except (KeyError, ValueError) as exc:
                        errors.append(f"platform_targets[{index}].file_naming을 해석할 수 없습니다: {exc}")
                        expected_paths = []
                if len(set(expected_paths)) != len(expected_paths):
                    errors.append(f"platform_targets[{index}] 파일명이 page_no별로 고유하지 않습니다")
                files = [path for path in expected_paths if path.is_file()]
                for expected_path in expected_paths:
                    try:
                        expected_path.relative_to(output_dir)
                    except ValueError:
                        errors.append(f"platform_targets[{index}] 파일명이 출력 폴더 밖을 가리킵니다: {expected_path}")
                    if not expected_path.is_file():
                        errors.append(
                            f"platform_targets[{index}] {extension.upper()} 파일이 없습니다: "
                            f"{expected_path.name}"
                        )
                unexpected = sorted(
                    path.resolve()
                    for path in output_dir.rglob(f"{prefix}*.{extension}")
                    if path.is_file() and path.resolve() not in set(expected_paths)
                )
                for path in unexpected:
                    errors.append(f"platform_targets[{index}] 연속 번호 규칙에 맞지 않는 파일입니다: {path.name}")
                for path in files:
                    if path in assigned and not shared_outputs:
                        errors.append(f"한 파일이 둘 이상의 채널 대상에 중복 배정되었습니다: {path.name}")
                    assigned.add(path.resolve())
                    record: dict[str, object] = {
                        "file": str(path.relative_to(output_dir)),
                        "format": extension,
                        "platform": platform,
                        "placement": placement,
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                    if shared_outputs:
                        record["shared_across_platforms"] = True
                        record["page_no"] = expected_paths.index(path) + 1
                    try:
                        if extension == "png":
                            details = inspect_png(path)
                            record.update(details)
                            if isinstance(width, (int, float)) and details["width_px"] != int(width):
                                errors.append(f"{path.name}: width_px {details['width_px']} != {int(width)}")
                            if isinstance(height, (int, float)) and details["height_px"] != int(height):
                                errors.append(f"{path.name}: height_px {details['height_px']} != {int(height)}")
                            if expected_mode and details["color_mode"] != expected_mode:
                                errors.append(f"{path.name}: color_mode {details['color_mode']} != {expected_mode}")
                        elif extension == "pdf":
                            record.update(inspect_pdf(path))
                            markers = record.get("page_markers")
                            if markers == 0:
                                errors.append(
                                    f"{path.name}: PDF 페이지 수를 확인할 수 없습니다. "
                                    "실제 PDF 파서 또는 렌더러로 확인 가능한 파일을 다시 내보내세요"
                                )
                            elif isinstance(target_pages, (int, float)):
                                expected_pdf_pages = int(target_pages) if expected_count == 1 else 1
                                if markers != expected_pdf_pages:
                                    errors.append(
                                        f"{path.name}: PDF 페이지 {markers}쪽이 목표 {expected_pdf_pages}쪽과 다릅니다"
                                    )
                        elif extension == "html":
                            details, html_warnings = inspect_html(path)
                            record.update(details)
                            warnings.extend(html_warnings)
                            if isinstance(target_pages, (int, float)):
                                file_number = expected_paths.index(path) + 1 if path in expected_paths else 0
                                expected_html_pages = (
                                    list(range(1, int(target_pages) + 1)) if expected_count == 1 else [file_number]
                                )
                                if details.get("card_pages") != expected_html_pages:
                                    errors.append(
                                        f"{path.name}: data-card-page 순서 {details.get('card_pages')}가 "
                                        f"목표 {expected_html_pages}와 다릅니다"
                                    )
                    except (OSError, ValueError) as exc:
                        errors.append(f"{path.name}: {exc}")
                    records.append(record)
        for extension in formats:
            for path in output_dir.rglob(f"*.{extension}"):
                if path.is_file() and path.resolve() not in assigned:
                    warnings.append(f"채널 대상에 연결되지 않은 파일입니다: {path.relative_to(output_dir)}")
    else:
        target_count = output.get("target_count")
        width = output.get("width_px")
        height = output.get("height_px")
        for extension in formats:
            files = sorted(path for path in output_dir.rglob(f"*.{extension}") if path.is_file())
            expected_count = int(target_count) if extension == "png" and isinstance(target_count, (int, float)) else 1
            if len(files) != expected_count:
                errors.append(f"{extension.upper()} 산출물 수가 다릅니다: 예상 {expected_count}, 실제 {len(files)}")
            for path in files:
                record = {"file": str(path.relative_to(output_dir)), "format": extension, "bytes": path.stat().st_size, "sha256": sha256(path)}
                try:
                    if extension == "png":
                        details = inspect_png(path)
                        record.update(details)
                        if isinstance(width, (int, float)) and details["width_px"] != int(width):
                            errors.append(f"{path.name}: width_px {details['width_px']} != {int(width)}")
                        if isinstance(height, (int, float)) and details["height_px"] != int(height):
                            errors.append(f"{path.name}: height_px {details['height_px']} != {int(height)}")
                    elif extension == "pdf":
                        record.update(inspect_pdf(path))
                    elif extension == "html":
                        details, html_warnings = inspect_html(path)
                        record.update(details)
                        warnings.extend(html_warnings)
                except (OSError, ValueError) as exc:
                    errors.append(f"{path.name}: {exc}")
                records.append(record)

    manifest = {
        "schema_version": "1.1",
        "job_id": job.get("job_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "expected_formats": formats,
        "files": records,
        "warnings": warnings,
        "errors": errors,
    }
    if 'character_set' in job:
        manifest['character_set'] = job['character_set']
        manifest['character_mode'] = job.get('character_mode')
    if args.write_manifest:
        manifest_path = args.write_manifest.resolve()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"MANIFEST: {manifest_path}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"OK: {len(records)} file(s) validated across {', '.join(formats)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
