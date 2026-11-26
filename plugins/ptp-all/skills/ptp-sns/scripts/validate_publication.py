#!/usr/bin/env python3
"""Validate one publication job and its declared assets; does not grant approval.

This declaration/integrity check cannot prove a human review, authorization,
undisclosed pixel sources, or external publication success. The library-wide
publication audit remains available separately in validate_assets.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import validate_assets
import validate_job


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "asset-manifest.json"
LIMITATION = "작업별 선언·자산 무결성 검사입니다. 검토·권한의 진실성, 미기재 이미지 출처 또는 외부 게시 성공을 증명하거나 새 승인을 부여하지 않습니다."


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def walk_values(value: object, path: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            if key != "publication_asset_ids":
                yield from walk_values(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_values(child, f"{path}[{i}]")
    else:
        yield path, value


def validate(job_path: Path) -> tuple[list[str], list[str]]:
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"작업 또는 자산 목록을 읽을 수 없습니다: {exc}"], [LIMITATION]
    if not isinstance(data, dict) or not isinstance(manifest, dict):
        return ["작업 및 자산 목록은 JSON 객체여야 합니다"], [LIMITATION]
    try:
        errors, warnings = validate_job.validate(job_path, require_locked=True)
        asset_errors, asset_warnings = validate_assets.validate(MANIFEST, require_locked=False, level="standard")
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        return [f"기존 스키마 검사에 실패했습니다: {exc}"], [LIMITATION]
    errors.extend(f"자산 무결성: {item}" for item in asset_errors)
    warnings.extend(asset_warnings)
    warnings.append(LIMITATION)
    if data.get("production_mode") != "publication":
        errors.append("production_mode은 publication이어야 합니다")
    from validate_link_policy import validate as validate_links
    errors.extend(validate_links(data,job_path))
    from content_preflight import validate_job_quality
    errors.extend(validate_job_quality(data, job_path))
    assets = {a["id"]: a for a in manifest.get("assets", []) if isinstance(a, dict) and isinstance(a.get("id"), str)}
    raw_ids = data.get("publication_asset_ids")
    selected = set()
    generated_only = data.get('generation_method') == 'whole-image' and raw_ids == [] and data.get('characters') == []
    if generated_only:
        generated = data.get('generated_assets')
        if not isinstance(generated, list) or not generated:
            errors.append('전체 이미지 생성의 라이브러리 미사용 작업에는 generated_assets의 실제 파일·해시·출처가 필요합니다')
        for item in generated if isinstance(generated,list) else []:
            if not isinstance(item,dict) or not all(nonempty(item.get(k)) for k in ('path','sha256','origin')):
                errors.append('전체 이미지 생성의 파일·해시·출처가 누락됐습니다')
                continue
            try:
                p=Path(item['path'])
                if not p.is_absolute(): p=job_path.parent/p
                if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
                    errors.append('전체 이미지 생성 파일 해시가 일치하지 않습니다')
            except OSError:
                errors.append('전체 이미지 생성 파일을 확인할 수 없습니다')
    if not isinstance(raw_ids, list) or (not raw_ids and not generated_only) or any(not nonempty(item) for item in raw_ids):
        errors.append("publication_asset_ids는 실제 사용한 라이브러리 자산 ID의 비어 있지 않은 문자열 배열이어야 합니다")
    else:
        selected = set(raw_ids)
        if len(selected) != len(raw_ids):
            errors.append("publication_asset_ids에 중복 ID가 있습니다")
        for asset_id in sorted(selected):
            if asset_id not in assets:
                errors.append(f"등록되지 않은 publication_asset_ids 자산: {asset_id}")
            elif assets[asset_id].get("approval") != "approved":
                errors.append(f"작업에 선택한 자산이 approved가 아닙니다: {asset_id}")

    # Inventory references already present anywhere in the job, including known
    # library paths, so omitting their IDs cannot hide review-only source assets.
    for location, value in walk_values(data):
        if not isinstance(value, str):
            continue
        normalized = value.replace("\\", "/").lower()
        used = set(re.findall(r"\bAST-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", value))
        for asset_id, asset in assets.items():
            relative = str(asset.get("path", "")).replace("\\", "/").lower()
            if relative and (normalized in {relative, "assets/" + relative} or normalized.endswith("/assets/" + relative)):
                used.add(asset_id)
        for asset_id in sorted(used):
            if asset_id not in selected:
                errors.append(f"{location} 사용 자산이 publication_asset_ids에 없습니다: {asset_id}")
            if asset_id not in assets:
                errors.append(f"{location}에 등록되지 않은 자산 참조가 있습니다: {asset_id}")
            elif assets[asset_id].get("approval") != "approved":
                errors.append(f"{location}에 미승인 원본 자산이 있습니다: {asset_id}")
        if location.endswith("rights_status") and value not in {"approved", "not-applicable"}:
            errors.append(f"{location}는 approved 또는 not-applicable이어야 합니다")

    authority = manifest.get("production_requirements", {}).get("character_anchor_set", {}).get("approved_assets", [])
    if data.get('character_set') is not None:
        from character_sets import validate_selection
        set_errors, selected_set = validate_selection(data, publication=True)
        errors.extend(set_errors)
        # Other saved sets carry their own anchor authority; old jobs retain v1.2.
        if selected_set is not None:
            authority = [a for m in selected_set['members'] for a in m['anchor_ids']]
    characters = data.get("characters")
    for character in characters if isinstance(characters, list) else []:
        if not isinstance(character, dict):
            continue
        char_id = character.get("id")
        anchors = character.get("anchor_ids", [])
        if not isinstance(anchors, list):
            continue
        valid_identity = False
        for asset_id in anchors:
            if not isinstance(asset_id, str):
                continue
            asset = assets.get(asset_id, {})
            if asset_id not in selected:
                errors.append(f"{char_id}의 anchor_ids를 publication_asset_ids에 모두 포함해야 합니다: {asset_id}")
            if asset.get("character_id") not in {None, char_id}:
                errors.append(f"{char_id}에 다른 캐릭터의 앵커를 사용할 수 없습니다: {asset_id}")
            if asset_id in authority and asset.get("kind") == "character-anchor" and asset.get("character_id") == char_id:
                valid_identity = True
        if not valid_identity:
            errors.append(f"{char_id}의 승인된 2D 정체성 앵커가 anchor_ids에 필요합니다")

    review = data.get("publication_review")
    if not isinstance(review, dict):
        review = {}
        errors.append("publication_review 객체가 필요합니다")
    for key in ("brand_evidence", "rights_evidence", "final_review_evidence", "reviewer", "checked_at"):
        value = review.get(key)
        if not nonempty(value) or value.strip().lower() in {"pending", "tbd", "unknown"} or "【" in value or "】" in value:
            errors.append(f"publication_review.{key}에 이번 작업의 구체적인 확인 근거가 필요합니다")
    if nonempty(review.get("checked_at")):
        try:
            checked_at = datetime.fromisoformat(review["checked_at"].replace("Z", "+00:00"))
            if checked_at.tzinfo is None or checked_at.utcoffset() is None:
                raise ValueError("timezone required")
        except ValueError:
            errors.append("publication_review.checked_at은 시간대가 포함된 유효한 ISO 일시여야 합니다 (예: 2026-10-22T12:00:00+09:00)")
    approvals = data.get("approvals")
    final_review = approvals.get("final_human_review") if isinstance(approvals, dict) else None
    if final_review == "not-applicable":
        if review.get("review_mode") != "delegated" or not nonempty(review.get("delegation_evidence")):
            errors.append("final_human_review=not-applicable은 review_mode=delegated와 사용자의 제작·검토·게시 위임 근거 delegation_evidence가 필요합니다")
    elif final_review == "approved":
        if review.get("review_mode") != "human":
            errors.append("final_human_review=approved는 review_mode=human과 실제 사람의 검토 근거가 필요합니다")
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    args = parser.parse_args()
    errors, warnings = validate(args.job.resolve())
    print(json.dumps({"status": "failed" if errors else "passed", "scope": "job-declarations-and-asset-integrity",
                      "job": str(args.job.resolve()), "errors": errors, "warnings": warnings,
                      "authorization_granted": False, "external_publication_verified": False}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
