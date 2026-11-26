#!/usr/bin/env python3
"""Validate a PTP character-content job request using only stdlib."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MODES = {
    "card-news", "poster", "signage", "web-banner", "social-post", "social-story", "channel-message",
    "webtoon", "social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic",
}
MEDIUMS = {"digital", "print", "physical"}
CAPABILITIES = {"direct", "tool-dependent", "specification-only"}
SPEC_SOURCES = {"user-provided", "platform-provided", "vendor-provided", "project-custom"}
CHARACTER_IDS = {"CHR-BLUE", "CHR-ORANGE"}
OUTFIT_SLOTS = {"default", "field", "research"}
APPROVALS = {"pending", "approved", "not-applicable"}
APPROVAL_KEYS = {"character", "brand", "claims", "publication_spec", "final_human_review"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DENSITIES = {"low", "medium", "high"}
PRODUCTION_MODES = {"quick-draft", "standard", "publication"}
AUTHORING_MODES = {"individual", "integrated"}
OUTPUT_FORMATS = {"png", "pdf", "html"}
SOURCE_STRENGTHS = {"official-platform", "mixed", "project-default", "user-provided", "vendor-provided"}
TARGET_CONTENT_TYPES = {
    "social-post", "social-story", "channel-message", "web-banner", "poster", "signage",
    "social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic",
}
CONCEPT_SELECTION_MODES = {"propose-3-then-select", "auto-select-highest-fit", "user-selected"}
COMMERCIAL_QUALITY_TARGETS = {"campaign-ready", "commercial-ready"}
LAYER_ROLES = {"background", "atmosphere", "context", "character", "information", "typography", "brand-legal"}
REQUIRED_LAYER_ROLES = {"background", "atmosphere", "context", "character", "information", "typography"}
PHOTO_REVIEW_KEYS = {
    "perspective_match", "lighting_match", "contact_shadow", "edge_integration",
    "color_grade_match", "depth_occlusion_review",
}
COMMERCIAL_REVIEW_KEYS = {
    "concept_fit_review", "distinctiveness_review", "platform_crop_review", "campaign_consistency_review",
}
COMIC_MODES = {"social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic"}
READING_DIRECTIONS = {"left-to-right", "right-to-left", "vertical-scroll"}
FRAME_DIVERSITY = {"uniform", "controlled", "expressive"}
RESOLUTION_SELECTION_MODES = {"user-selected", "auto-recommended"}
RESOLUTION_ADAPTATIONS = {"preserve", "recompose", "crop", "letterbox"}


def positive_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_preset_catalog() -> dict[str, dict[str, object]]:
    path = Path(__file__).resolve().parent.parent / "assets" / "platform-presets.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    presets = data.get("presets") if isinstance(data, dict) else None
    if not isinstance(presets, list):
        return {}
    return {item.get("id"): item for item in presets if isinstance(item, dict) and nonempty(item.get("id"))}


def load_concept_catalog() -> dict[str, dict[str, object]]:
    path = Path(__file__).resolve().parent.parent / "assets" / "visual-concept-presets.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    concepts = data.get("concepts") if isinstance(data, dict) else None
    if not isinstance(concepts, list):
        return {}
    return {item.get("id"): item for item in concepts if isinstance(item, dict) and nonempty(item.get("id"))}


def load_resolution_profiles() -> dict[str, dict[str, object]]:
    path = Path(__file__).resolve().parent.parent / "assets" / "output-size-profiles.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, list):
        return {}
    return {item.get("id"): item for item in profiles if isinstance(item, dict) and nonempty(item.get("id"))}


def validate_resolution_policy(data: dict[str, object], errors: list[str], production_mode: str | None) -> None:
    policy = data.get("resolution_policy")
    if not isinstance(policy, dict):
        errors.append("schema 1.3에는 resolution_policy 객체가 필요합니다")
        return
    if policy.get("selection_mode") not in RESOLUTION_SELECTION_MODES:
        errors.append("resolution_policy.selection_mode이 올바르지 않습니다")
    if policy.get("render_strategy") != "render-from-source-at-primary-size":
        errors.append("resolution_policy.render_strategy는 render-from-source-at-primary-size여야 합니다")
    if policy.get("upscale_existing_raster") is not False:
        errors.append("완성된 저해상도 래스터의 확대는 금지됩니다")
    if policy.get("preserve_aspect_ratio") is not True:
        errors.append("resolution_policy.preserve_aspect_ratio는 true여야 합니다")
    if policy.get("adaptation_strategy") not in RESOLUTION_ADAPTATIONS:
        errors.append("resolution_policy.adaptation_strategy는 preserve, recompose, crop, letterbox 중 하나여야 합니다")
    for key in ("deliver_upload_copy", "deliver_master_copy"):
        if not isinstance(policy.get(key), bool):
            errors.append(f"resolution_policy.{key}는 불리언이어야 합니다")

    profiles = load_resolution_profiles()
    if not profiles:
        errors.append("assets/output-size-profiles.json을 읽을 수 없습니다")
        return
    profile_id = policy.get("profile_id")
    profile = profiles.get(profile_id)
    if profile is None:
        errors.append(f"등록되지 않은 해상도 프로필입니다: {profile_id}")
        return
    if policy.get("deliver_upload_copy") is not profile.get("deliver_upload_copy"):
        errors.append("resolution_policy.deliver_upload_copy가 선택 프로필과 다릅니다")
    if policy.get("deliver_master_copy") is not profile.get("deliver_master_copy"):
        errors.append("resolution_policy.deliver_master_copy가 선택 프로필과 다릅니다")
    if profile.get("final_eligible") is False and production_mode != "quick-draft":
        errors.append("draft-preview-0.5x는 빠른 초안 전용이며 최종 결과물로 사용할 수 없습니다")
    if profile_id == "draft-preview-0.5x" and production_mode != "quick-draft":
        errors.append("draft-preview-0.5x는 production_mode=quick-draft에서만 사용할 수 있습니다")
    if profile_id == "print-production":
        for key in ("print_width_mm", "print_height_mm", "print_dpi"):
            if not positive_number(policy.get(key)):
                errors.append(f"resolution_policy.{key}는 인쇄 제작에서 양수여야 합니다")
        dpi = policy.get("print_dpi")
        if positive_number(dpi) and not 72 <= float(dpi) <= 1200:
            errors.append("resolution_policy.print_dpi는 72~1200 범위여야 합니다")
    elif profile_id == "custom-pixel":
        for key in ("custom_width_px", "custom_height_px"):
            value = policy.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"resolution_policy.{key}는 사용자 지정 픽셀에서 양의 정수여야 합니다")


def validate_resolution_output_match(data: dict[str, object], output: dict[str, object], errors: list[str]) -> None:
    policy = data.get("resolution_policy")
    targets = data.get("platform_targets")
    if not isinstance(policy, dict) or not isinstance(targets, list) or not targets or not isinstance(targets[0], dict):
        return
    profile_id = policy.get("profile_id")
    base_width = targets[0].get("width_px")
    base_height = targets[0].get("height_px")
    if not positive_number(base_width) or not positive_number(base_height):
        return
    expected: tuple[int, int] | None = None
    if profile_id == "channel-native-1x":
        expected = (int(base_width), int(base_height))
    elif profile_id == "high-resolution-master-2x":
        expected = (int(base_width) * 2, int(base_height) * 2)
    elif profile_id == "custom-pixel":
        custom_width = policy.get("custom_width_px")
        custom_height = policy.get("custom_height_px")
        if isinstance(custom_width, int) and isinstance(custom_height, int):
            expected = (custom_width, custom_height)
            base_ratio = float(base_width) / float(base_height)
            custom_ratio = custom_width / custom_height
            if abs(base_ratio - custom_ratio) / base_ratio > 0.005 and policy.get("adaptation_strategy") == "preserve":
                errors.append("사용자 지정 종횡비가 달라 재구성·크롭·레터박스 전략이 필요합니다")
    elif profile_id == "print-production":
        if output.get("medium") != "print":
            errors.append("print-production 프로필의 output.medium은 print여야 합니다")
        for output_key, policy_key in (("width_mm", "print_width_mm"), ("height_mm", "print_height_mm"), ("dpi", "print_dpi")):
            if output.get(output_key) != policy.get(policy_key):
                errors.append(f"output.{output_key}가 resolution_policy.{policy_key}와 다릅니다")
    if expected is not None and (output.get("width_px"), output.get("height_px")) != expected:
        errors.append(f"output 픽셀 크기는 선택 프로필 기준 {expected[0]}x{expected[1]}이어야 합니다")


def validate_concept_strategy(data: dict[str, object], errors: list[str]) -> None:
    strategy = data.get("concept_strategy")
    if not isinstance(strategy, dict):
        errors.append("schema 1.2 이상에는 concept_strategy 객체가 필요합니다")
        return
    if strategy.get("selection_mode") not in CONCEPT_SELECTION_MODES:
        errors.append("concept_strategy.selection_mode이 올바르지 않습니다")
    signals = strategy.get("input_signals")
    if not isinstance(signals, list) or not signals or any(not nonempty(item) for item in signals):
        errors.append("concept_strategy.input_signals는 비어 있지 않은 문자열 배열이어야 합니다")
    proposals = strategy.get("proposed_concept_ids")
    if (
        not isinstance(proposals, list)
        or len(proposals) != 3
        or any(not nonempty(item) for item in proposals)
        or len(set(proposals)) != 3
    ):
        errors.append("concept_strategy.proposed_concept_ids는 서로 다른 콘셉트 ID 3개여야 합니다")
        proposals = []
    catalog = load_concept_catalog()
    if not catalog:
        errors.append("assets/visual-concept-presets.json을 읽을 수 없습니다")
    families: list[str] = []
    for concept_id in proposals:
        concept = catalog.get(concept_id)
        if concept is None:
            errors.append(f"등록되지 않은 콘셉트 ID입니다: {concept_id}")
        else:
            families.append(str(concept.get("medium_family", "")))
    if families and len(families) != len(set(families)):
        errors.append("제안 콘셉트 3안은 서로 다른 medium_family여야 합니다")
    selected = strategy.get("selected_concept_id")
    if selected not in proposals:
        errors.append("concept_strategy.selected_concept_id는 proposed_concept_ids 중 하나여야 합니다")
    if not nonempty(strategy.get("selection_basis")):
        errors.append("concept_strategy.selection_basis가 필요합니다")
    mode = strategy.get("composition_mode")
    if mode not in {"multi-layer", "whole-image"}:
        errors.append("concept_strategy.composition_mode은 multi-layer 또는 whole-image여야 합니다")
    if mode == "whole-image" and data.get("generation_method") != "whole-image":
        errors.append("전체 이미지 구성은 generation_method=whole-image로 실제 방식을 기록해야 합니다")
    if strategy.get("allow_flat_geometric_only") is not False:
        errors.append("concept_strategy.allow_flat_geometric_only는 false여야 합니다")
    if strategy.get("commercial_quality_target") not in COMMERCIAL_QUALITY_TARGETS:
        errors.append("concept_strategy.commercial_quality_target이 올바르지 않습니다")


def validate_comic(comic: object, errors: list[str], character_ids=None) -> None:
    if not isinstance(comic, dict):
        errors.append("웹툰·만화 출력에는 comic 객체가 필요합니다")
        return
    allowed_characters = CHARACTER_IDS if character_ids is None else character_ids
    if comic.get('cast_revision_required') is True:
        errors.append('캐릭터 세트 변경 후 컷·대사·화자 검토를 완료하고 cast_revision_required=false로 기록하세요')
    if comic.get("enabled") is not True:
        errors.append("comic.enabled는 true여야 합니다")
    if comic.get("content_mode") not in COMIC_MODES:
        errors.append("comic.content_mode이 올바르지 않습니다")
    if comic.get("reading_direction") not in READING_DIRECTIONS:
        errors.append("comic.reading_direction이 올바르지 않습니다")
    if comic.get("frame_diversity") not in FRAME_DIVERSITY:
        errors.append("comic.frame_diversity가 올바르지 않습니다")
    if comic.get("lettering_mode") == "native-integrated":
        if comic.get("art_and_lettering_separate") is not False:
            errors.append("통합 생성은 comic.art_and_lettering_separate=false로 실제 방식을 기록해야 합니다")
        if not isinstance(comic.get("integrated_lettering_review"), str) or not comic["integrated_lettering_review"].strip():
            errors.append("통합 생성에는 실제 문구·화자·넘침 검수 근거 integrated_lettering_review가 필요합니다")
    elif comic.get("art_and_lettering_separate") is not True:
        errors.append("별도 조판은 comic.art_and_lettering_separate=true여야 합니다")
    if comic.get("character_continuity_required") is not True:
        errors.append("comic.character_continuity_required는 true여야 합니다")
    panel_count = comic.get("panel_count")
    if not isinstance(panel_count, int) or isinstance(panel_count, bool) or panel_count <= 0:
        errors.append("comic.panel_count는 양의 정수여야 합니다")
        panel_count = 0
    beats = comic.get("story_beats")
    if not isinstance(beats, list) or len(beats) < 3 or any(not nonempty(item) for item in beats):
        errors.append("comic.story_beats는 3개 이상의 문자열 배열이어야 합니다")
    panels = comic.get("panel_contract")
    if not isinstance(panels, list) or len(panels) != panel_count:
        errors.append("comic.panel_contract 수는 panel_count와 같아야 합니다")
        panels = []
    seen: set[int] = set()
    for index, panel in enumerate(panels):
        label = f"comic.panel_contract[{index}]"
        if not isinstance(panel, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        number = panel.get("panel")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0 or number in seen:
            errors.append(f"{label}.panel은 중복 없는 양의 정수여야 합니다")
        else:
            seen.add(number)
        for key in ("function", "visual_action", "core_information", "lettering_safe_area", "state_before", "state_after"):
            if not nonempty(panel.get(key)):
                errors.append(f"{label}.{key}가 필요합니다")
        source_refs = panel.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs or any(not nonempty(item) for item in source_refs):
            errors.append(f"{label}.source_refs는 비어 있지 않은 문자열 배열이어야 합니다")
        characters = panel.get("characters")
        if not isinstance(characters, list) or any(item not in allowed_characters for item in characters):
            errors.append(f"{label}.characters에는 등록된 캐릭터 ID만 사용할 수 있습니다")
    if panels and seen != set(range(1, panel_count + 1)):
        errors.append("comic.panel_contract[].panel은 1부터 panel_count까지 연속되어야 합니다")


def load_asset_approvals() -> dict[str, str]:
    path = Path(__file__).resolve().parent.parent / "assets" / "asset-manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    assets = data.get("assets") if isinstance(data, dict) else None
    if not isinstance(assets, list):
        return {}
    return {
        item.get("id"): item.get("approval")
        for item in assets
        if isinstance(item, dict) and nonempty(item.get("id")) and nonempty(item.get("approval"))
    }


def validate_v12_fields(data: dict[str, object], errors: list[str]) -> str | None:
    production_mode = data.get("production_mode")
    if production_mode not in PRODUCTION_MODES:
        errors.append("production_mode은 quick-draft, standard, publication 중 하나여야 합니다")

    authoring_mode = data.get("authoring_mode")
    if authoring_mode not in AUTHORING_MODES:
        errors.append("authoring_mode은 individual 또는 integrated여야 합니다")

    requested = data.get("requested_outputs")
    if (
        not isinstance(requested, list)
        or not requested
        or any(item not in OUTPUT_FORMATS for item in requested)
        or len(set(requested)) != len(requested)
    ):
        errors.append("requested_outputs는 png, pdf, html의 중복 없는 배열이어야 합니다")

    requested_set = set(requested) if isinstance(requested, list) else set()
    catalog = load_preset_catalog()
    if not catalog:
        errors.append("assets/platform-presets.json을 읽을 수 없습니다")

    targets = data.get("platform_targets")
    if not isinstance(targets, list) or not targets:
        errors.append("platform_targets는 하나 이상의 항목을 가진 배열이어야 합니다")
        targets = []
    seen_target_keys: set[tuple[str, str]] = set()
    content_variant_ids: list[str] = []
    for index, target in enumerate(targets):
        label = f"platform_targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        for key in ("preset_id", "platform", "placement", "content_variant_id"):
            if not nonempty(target.get(key)):
                errors.append(f"{label}.{key}가 필요합니다")
        if nonempty(target.get("content_variant_id")):
            content_variant_ids.append(str(target["content_variant_id"]))
        target_key = (str(target.get("platform", "")), str(target.get("placement", "")))
        if all(target_key):
            if target_key in seen_target_keys:
                errors.append(
                    f"중복 플랫폼 대상입니다: {target_key[0]}/{target_key[1]}. "
                    "한 지면은 platform_targets에서 한 번만 정의하세요"
                )
            seen_target_keys.add(target_key)
        if target.get("content_type") not in TARGET_CONTENT_TYPES:
            errors.append(f"{label}.content_type이 올바르지 않습니다")
        if not positive_number(target.get("width_px")) or not positive_number(target.get("height_px")):
            errors.append(f"{label}에는 양의 width_px와 height_px가 필요합니다")
        if not positive_number(target.get("target_count")):
            errors.append(f"{label}.target_count는 양수여야 합니다")
        target_outputs = target.get("requested_outputs")
        if (
            not isinstance(target_outputs, list)
            or not target_outputs
            or any(item not in OUTPUT_FORMATS for item in target_outputs)
            or len(set(target_outputs)) != len(target_outputs)
        ):
            errors.append(f"{label}.requested_outputs가 올바르지 않습니다")
            target_outputs = []
        elif requested_set and set(target_outputs) != requested_set:
            errors.append(
                f"{label}.requested_outputs는 상위 requested_outputs와 같아야 합니다. "
                "채널별로 다른 형식이 필요하면 작업을 분리하세요"
            )
        counts = target.get("format_counts")
        if not isinstance(counts, dict):
            errors.append(f"{label}.format_counts 객체가 필요합니다")
            counts = {}
        for fmt in target_outputs:
            count = counts.get(fmt)
            if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                errors.append(f"{label}.format_counts.{fmt}는 양의 정수여야 합니다")
        unexpected_count_keys = set(counts) - set(target_outputs)
        if unexpected_count_keys:
            errors.append(
                f"{label}.format_counts에 요청하지 않은 형식이 있습니다: "
                f"{', '.join(sorted(unexpected_count_keys))}"
            )
        if isinstance(target.get("target_count"), (int, float)) and counts.get("png") is not None:
            if counts.get("png") != int(target["target_count"]):
                errors.append(f"{label}.format_counts.png는 target_count와 같아야 합니다")
        naming = target.get("file_naming")
        if not nonempty(naming) or any(
            token not in naming for token in ("{job_id}", "{platform}", "{placement}", "{page_no")
        ):
            errors.append(f"{label}.file_naming에는 job_id, platform, placement, page_no 토큰이 필요합니다")
        strength = target.get("source_strength")
        if strength is not None and strength not in SOURCE_STRENGTHS:
            errors.append(f"{label}.source_strength가 올바르지 않습니다")
        checked = target.get("spec_checked_at")
        if checked is not None and (not isinstance(checked, str) or not DATE_RE.match(checked)):
            errors.append(f"{label}.spec_checked_at은 YYYY-MM-DD 형식이어야 합니다")

        preset_id = target.get("preset_id")
        if nonempty(preset_id):
            preset = catalog.get(preset_id)
            if preset is None:
                if not preset_id.startswith("custom-") or strength not in {"user-provided", "vendor-provided"}:
                    errors.append(f"{label}.preset_id가 프리셋 카탈로그에 없습니다: {preset_id}")
            else:
                for key in ("platform", "placement", "width_px", "height_px"):
                    if target.get(key) != preset.get(key):
                        errors.append(f"{label}.{key}가 프리셋 {preset_id}와 다릅니다")

    if authoring_mode == "individual" and len(content_variant_ids) != len(set(content_variant_ids)):
        errors.append("개별 작성에서는 platform_targets[].content_variant_id가 모두 달라야 합니다")
    if authoring_mode == "integrated":
        if len(targets) < 2:
            errors.append("통합 작성에는 두 개 이상의 platform_targets가 필요합니다")
        if content_variant_ids and any(variant_id != "shared-main" for variant_id in content_variant_ids):
            errors.append("통합 작성에서는 모든 content_variant_id가 shared-main이어야 합니다")

    publication = data.get("publication")
    if not isinstance(publication, dict):
        errors.append("publication 객체가 필요합니다")
        publication = {}
    for key in ("requested", "authorized"):
        if not isinstance(publication.get(key), bool):
            errors.append(f"publication.{key}는 불리언이어야 합니다")
    if publication.get("authorized") is True and publication.get("requested") is not True:
        errors.append("publication.authorized=true에는 publication.requested=true가 필요합니다")
    if production_mode == "quick-draft" and (publication.get("requested") is True or publication.get("authorized") is True):
        errors.append("quick-draft에서는 외부 게시를 요청하거나 승인할 수 없습니다")
    return production_mode if isinstance(production_mode, str) else None


def validate(job_path: Path, require_locked: bool) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"작업 요청서를 읽을 수 없습니다: {exc}"], warnings

    schema_version = data.get("schema_version")
    from character_sets import validate_selection
    selection_errors, selected_set = validate_selection(data, publication=require_locked or data.get('production_mode') == 'publication')
    errors.extend(selection_errors)
    selected_ids = {m['id'] for m in selected_set['members']} if selected_set else (set() if data.get('character_mode') == 'none' else CHARACTER_IDS)
    from resolve_delivery_form import validate_form
    errors.extend(validate_form(data))
    if schema_version not in {"1.0", "1.1", "1.2", "1.3"}:
        errors.append("schema_version은 '1.0', '1.1', '1.2' 또는 '1.3'이어야 합니다")
    status = data.get("status")
    if status not in {"review-draft", "draft", "locked", "delivered"}:
        errors.append("status는 review-draft, draft, locked, delivered 중 하나여야 합니다")
    for key in ("job_id", "purpose", "audience", "channel"):
        if not nonempty(data.get(key)):
            errors.append(f"{key}가 필요합니다")

    production_mode = None
    if schema_version in {"1.2", "1.3"}:
        validate_concept_strategy(data, errors)
        production_mode = validate_v12_fields(data, errors)
        if schema_version == "1.3":
            validate_resolution_policy(data, errors, production_mode)
        if production_mode == "quick-draft":
            if data.get("comic") is not None:
                validate_comic(data.get("comic"), errors, selected_ids)
            brief = data.get("quick_brief")
            if not isinstance(brief, dict):
                errors.append("quick-draft에는 quick_brief 객체가 필요합니다")
                brief = {}
            for key in ("headline", "call_to_action", "source_ref"):
                if not nonempty(brief.get(key)):
                    errors.append(f"quick_brief.{key}가 필요합니다")
            if status not in {"review-draft", "draft"}:
                errors.append("quick-draft status는 review-draft 또는 draft여야 합니다")
            if require_locked:
                errors.append("quick-draft는 최종 승인 검사 대상이 아닙니다")
            warnings.append("빠른 초안 모드입니다. 전체 검증과 외부 게시를 수행하지 않습니다")
            return errors, warnings

    output = data.get("output")
    if not isinstance(output, dict):
        errors.append("output 객체가 필요합니다")
        output = {}
    medium = output.get("medium")
    if output.get("mode") not in MODES:
        errors.append("output.mode가 허용 목록에 없습니다")
    if output.get("mode") in {"webtoon", *COMIC_MODES} or data.get("comic") is not None:
        validate_comic(data.get("comic"), errors, selected_ids)
    if medium not in MEDIUMS:
        errors.append("output.medium이 허용 목록에 없습니다")
    if output.get("capability") not in CAPABILITIES:
        errors.append("output.capability가 허용 목록에 없습니다")
    if output.get("spec_source") not in SPEC_SOURCES:
        errors.append("output.spec_source가 허용 목록에 없습니다")
    if not nonempty(output.get("spec_reference")):
        errors.append("output.spec_reference가 필요합니다")
    if not isinstance(output.get("spec_checked_at"), str) or not DATE_RE.match(output["spec_checked_at"]):
        errors.append("output.spec_checked_at은 YYYY-MM-DD 형식이어야 합니다")

    if medium == "digital" and (
        not positive_number(output.get("width_px")) or not positive_number(output.get("height_px"))
    ):
        errors.append("디지털 결과물에는 양의 width_px와 height_px가 필요합니다")
    if medium in {"print", "physical"} and (
        not positive_number(output.get("width_mm")) or not positive_number(output.get("height_mm"))
    ):
        errors.append("인쇄·실물 결과물에는 양의 width_mm와 height_mm가 필요합니다")
    if medium == "print":
        if not positive_number(output.get("dpi")):
            errors.append("인쇄 결과물에는 양의 dpi가 필요합니다")
        bleed = output.get("bleed_mm")
        if not isinstance(bleed, (int, float)) or isinstance(bleed, bool) or bleed < 0:
            errors.append("인쇄 결과물의 bleed_mm는 0 이상의 수여야 합니다")
    if not nonempty(output.get("color_mode")):
        errors.append("output.color_mode가 필요합니다")
    extension = output.get("extension")
    if not nonempty(extension) or not extension.startswith("."):
        errors.append("output.extension은 점(.)으로 시작해야 합니다")
    target_count = output.get("target_count")
    if not positive_number(target_count):
        errors.append("output.target_count는 양수여야 합니다")
    if not nonempty(output.get("file_naming")):
        errors.append("output.file_naming이 필요합니다")
    if schema_version == "1.3":
        validate_resolution_output_match(data, output, errors)

    characters = data.get("characters")
    no_characters = data.get("character_mode") == "none"
    if no_characters and (characters != [] or not nonempty(data.get("character_exclusion_evidence"))):
        errors.append("character_mode=none은 빈 characters 배열과 사용자 제외 요청 근거가 필요합니다")
    if not isinstance(characters, list) or (not characters and not no_characters):
        errors.append("characters는 하나 이상의 항목을 가진 배열이어야 합니다")
        characters = []
    seen: set[str] = set()
    asset_approvals = load_asset_approvals()
    for index, character in enumerate(characters):
        label = f"characters[{index}]"
        if not isinstance(character, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        char_id = character.get("id")
        if char_id not in selected_ids:
            errors.append(f"{label}.id가 허용 목록에 없습니다")
        elif char_id in seen:
            errors.append(f"중복 캐릭터 ID입니다: {char_id}")
        else:
            seen.add(char_id)
        if not nonempty(character.get("role")):
            errors.append(f"{label}.role이 필요합니다")
        if character.get("outfit_slot") not in OUTFIT_SLOTS:
            errors.append(f"{label}.outfit_slot이 허용 목록에 없습니다")
        anchors = character.get("anchor_ids")
        if not isinstance(anchors, list) or any(not nonempty(item) for item in anchors):
            errors.append(f"{label}.anchor_ids는 문자열 배열이어야 합니다")
        if character.get("approval") not in {"pending", "approved"}:
            errors.append(f"{label}.approval이 올바르지 않습니다")
        for anchor_id in anchors if isinstance(anchors, list) else []:
            if anchor_id not in asset_approvals:
                errors.append(f"{label}.anchor_ids에 없는 자산 ID가 있습니다: {anchor_id}")
            elif asset_approvals[anchor_id] != "approved":
                warnings.append(f"{label} 앵커가 아직 승인되지 않았습니다: {anchor_id}")

    design = data.get("design")
    if schema_version in {"1.1", "1.2", "1.3"}:
        if not isinstance(design, dict):
            errors.append("schema 1.1 작업에는 design 객체가 필요합니다")
            design = {}
        for key in ("direction", "hero_message", "hero_metric"):
            if not nonempty(design.get(key)):
                errors.append(f"design.{key}이 필요합니다")
        reading_order = design.get("reading_order")
        if (
            not isinstance(reading_order, list)
            or len(reading_order) < 3
            or any(not nonempty(item) for item in reading_order)
            or len(set(reading_order)) != len(reading_order)
        ):
            errors.append("design.reading_order는 중복 없는 문자열 3개 이상의 배열이어야 합니다")

        budget = design.get("content_budget")
        if not isinstance(budget, dict):
            errors.append("design.content_budget 객체가 필요합니다")
            budget = {}
        if budget.get("max_primary_messages") != 1:
            errors.append("design.content_budget.max_primary_messages는 1이어야 합니다")
        blocks = budget.get("max_supporting_blocks")
        if not isinstance(blocks, int) or isinstance(blocks, bool) or not 1 <= blocks <= 3:
            errors.append("design.content_budget.max_supporting_blocks는 1~3의 정수여야 합니다")
        characters_limit = budget.get("max_body_characters")
        if (
            not isinstance(characters_limit, int)
            or isinstance(characters_limit, bool)
            or not 80 <= characters_limit <= 300
        ):
            errors.append("design.content_budget.max_body_characters는 80~300의 정수여야 합니다")

        visual = design.get("visual_system")
        if not isinstance(visual, dict):
            errors.append("design.visual_system 객체가 필요합니다")
            visual = {}
        for key in ("grid", "motif"):
            if not nonempty(visual.get(key)):
                errors.append(f"design.visual_system.{key}이 필요합니다")
        if visual.get("density") not in DENSITIES:
            errors.append("design.visual_system.density는 low, medium, high 중 하나여야 합니다")
        palette = visual.get("palette")
        if (
            not isinstance(palette, list)
            or not 2 <= len(palette) <= 6
            or any(not isinstance(color, str) or not HEX_RE.match(color) for color in palette)
        ):
            errors.append("design.visual_system.palette는 2~6개의 #RRGGBB 색상 배열이어야 합니다")
        if schema_version in {"1.2", "1.3"}:
            layers = visual.get("layer_plan")
            if not isinstance(layers, list) or not layers:
                errors.append("design.visual_system.layer_plan이 필요합니다")
                layers = []
            layer_ids: set[str] = set()
            roles: set[str] = set()
            for index, layer in enumerate(layers):
                label = f"design.visual_system.layer_plan[{index}]"
                if not isinstance(layer, dict):
                    errors.append(f"{label}는 객체여야 합니다")
                    continue
                layer_id = layer.get("id")
                role = layer.get("role")
                if not nonempty(layer_id) or layer_id in layer_ids:
                    errors.append(f"{label}.id는 중복 없는 문자열이어야 합니다")
                else:
                    layer_ids.add(str(layer_id))
                if role not in LAYER_ROLES or role in roles:
                    errors.append(f"{label}.role은 중복 없는 허용 레이어 역할이어야 합니다")
                else:
                    roles.add(str(role))
                if not nonempty(layer.get("source_type")):
                    errors.append(f"{label}.source_type이 필요합니다")
                if role == "background" and layer.get("source_type") == "flat-shapes":
                    errors.append("background 레이어를 평면 도형만으로 구성할 수 없습니다")
            required_roles = REQUIRED_LAYER_ROLES - {"character"} if no_characters else REQUIRED_LAYER_ROLES
            missing_roles = required_roles - roles
            if missing_roles:
                errors.append("필수 레이어 역할이 없습니다: " + ", ".join(sorted(missing_roles)))

            photo = visual.get("photoreal_composite")
            if not isinstance(photo, dict):
                errors.append("design.visual_system.photoreal_composite 객체가 필요합니다")
            elif photo.get("enabled") is True:
                if not nonempty(photo.get("base_source")):
                    errors.append("photoreal_composite.base_source가 필요합니다")
                for key in PHOTO_REVIEW_KEYS:
                    if photo.get(key) is not True:
                        errors.append(f"photoreal_composite.{key}는 true여야 합니다")
                if not nonempty(photo.get("rights_status")):
                    errors.append("photoreal_composite.rights_status가 필요합니다")

            commercial = visual.get("commercial_quality")
            if not isinstance(commercial, dict):
                errors.append("design.visual_system.commercial_quality 객체가 필요합니다")
            else:
                for key in COMMERCIAL_REVIEW_KEYS:
                    if commercial.get(key) is not True:
                        errors.append(f"commercial_quality.{key}는 true여야 합니다")

        integration = design.get("character_integration")
        if not isinstance(integration, dict) and not no_characters:
            errors.append("design.character_integration 객체가 필요합니다")
            integration = {}
        if selected_set and not no_characters:
            actions = integration.get('actions') if isinstance(integration, dict) else None
            if not isinstance(actions, dict) or set(actions) != selected_ids or any(not nonempty(v) for v in actions.values()):
                errors.append('design.character_integration.actions에는 선택한 각 캐릭터 ID의 행동만 필요합니다')
            elif require_locked and any('【' in v or '】' in v for v in actions.values()):
                errors.append('선택한 캐릭터의 행동에 미확정 표기가 남아 있습니다')
        for key in (() if no_characters else (("functional_target",) if selected_set else ("teo_action", "pio_action", "functional_target"))):
            if not nonempty(integration.get(key)):
                errors.append(f"design.character_integration.{key}이 필요합니다")
        avoid = design.get("avoid")
        if not isinstance(avoid, list) or not avoid or any(not nonempty(item) for item in avoid):
            errors.append("design.avoid는 비어 있지 않은 문자열 배열이어야 합니다")
    elif design is None:
        warnings.append("schema 1.0 호환 요청입니다. 새 작업은 정보 위계 검증을 위해 schema 1.1을 권장합니다")

    copy = data.get("copy")
    if not isinstance(copy, dict):
        errors.append("copy 객체가 필요합니다")
        copy = {}
    for key in ("title", "call_to_action"):
        if not nonempty(copy.get(key)):
            errors.append(f"copy.{key}이 필요합니다")
    body = copy.get("body")
    if not isinstance(body, list) or not body or any(not nonempty(item) for item in body):
        errors.append("copy.body는 비어 있지 않은 문자열 배열이어야 합니다")
    claims = copy.get("claims")
    if not isinstance(claims, list):
        errors.append("copy.claims는 배열이어야 합니다")
        claims = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"copy.claims[{index}]는 객체여야 합니다")
            continue
        for key in ("id", "statement", "source_ref", "source_checked_at", "reviewer", "status"):
            if not nonempty(claim.get(key)):
                errors.append(f"copy.claims[{index}].{key}가 필요합니다")
        checked = claim.get("source_checked_at")
        if nonempty(checked) and not DATE_RE.match(checked):
            errors.append(f"copy.claims[{index}].source_checked_at은 YYYY-MM-DD 형식이어야 합니다")

    if schema_version in {"1.1", "1.2", "1.3"}:
        cards = copy.get("cards")
        if not isinstance(cards, list) or not cards:
            errors.append("schema 1.1 작업에는 copy.cards 배열이 필요합니다")
            cards = []
        if positive_number(target_count) and len(cards) != int(target_count):
            errors.append("copy.cards 수는 output.target_count와 같아야 합니다")
        seen_pages: set[int] = set()
        max_support = 3
        max_body_characters = 180
        if isinstance(design, dict):
            budget = design.get("content_budget")
            if isinstance(budget, dict) and isinstance(budget.get("max_supporting_blocks"), int):
                max_support = budget["max_supporting_blocks"]
            if isinstance(budget, dict) and isinstance(budget.get("max_body_characters"), int):
                max_body_characters = budget["max_body_characters"]
        for index, card in enumerate(cards):
            label = f"copy.cards[{index}]"
            if not isinstance(card, dict):
                errors.append(f"{label}는 객체여야 합니다")
                continue
            page = card.get("page")
            if not isinstance(page, int) or isinstance(page, bool) or page <= 0:
                errors.append(f"{label}.page는 양의 정수여야 합니다")
            elif page in seen_pages:
                errors.append(f"중복 카드 페이지 번호입니다: {page}")
            else:
                seen_pages.add(page)
            for key in ("purpose", "headline", "hero_metric", "cta"):
                if not nonempty(card.get(key)):
                    errors.append(f"{label}.{key}이 필요합니다")
            supporting = card.get("supporting_points")
            if (
                not isinstance(supporting, list)
                or any(not nonempty(item) for item in supporting)
                or len(supporting) > max_support
            ):
                errors.append(f"{label}.supporting_points는 최대 {max_support}개의 문자열 배열이어야 합니다")
            source_refs = card.get("source_refs")
            if not isinstance(source_refs, list) or not source_refs or any(not nonempty(item) for item in source_refs):
                errors.append(f"{label}.source_refs는 비어 있지 않은 문자열 배열이어야 합니다")
            text_parts = [card.get("headline", ""), card.get("hero_metric", ""), card.get("cta", "")]
            if isinstance(supporting, list):
                text_parts.extend(item for item in supporting if isinstance(item, str))
            text_length = sum(len(item) for item in text_parts if isinstance(item, str))
            if text_length > max_body_characters:
                warnings.append(
                    f"{label} 문구가 {text_length}자로 예산 {max_body_characters}자를 초과합니다. "
                    "글자 축소보다 카드 분리·요약을 검토하세요"
                )
        if cards and seen_pages != set(range(1, len(cards) + 1)):
            errors.append("copy.cards[].page는 1부터 카드 수까지 빠짐없이 연속되어야 합니다")

    accessibility = data.get("accessibility")
    if not isinstance(accessibility, dict):
        errors.append("accessibility 객체가 필요합니다")
    else:
        for key in ("alt_text_required", "contrast_review", "reading_order_required"):
            if accessibility.get(key) is not True:
                errors.append(f"accessibility.{key}는 true여야 합니다")

    approvals = data.get("approvals")
    if not isinstance(approvals, dict):
        errors.append("approvals 객체가 필요합니다")
        approvals = {}
    for key in APPROVAL_KEYS:
        if approvals.get(key) not in APPROVALS:
            errors.append(f"approvals.{key}가 올바르지 않습니다")

    if require_locked:
        if status not in {"locked", "delivered"}:
            errors.append("최종 승인 검사에서는 status가 locked 또는 delivered여야 합니다")
        for character in characters:
            if not isinstance(character, dict):
                continue
            if character.get("approval") != "approved":
                errors.append(f"캐릭터 승인이 필요합니다: {character.get('id', '(unknown)')}")
            if not character.get("anchor_ids"):
                errors.append(f"앵커 자산 연결이 필요합니다: {character.get('id', '(unknown)')}")
            for anchor_id in character.get("anchor_ids", []):
                if asset_approvals.get(anchor_id) != "approved":
                    errors.append(f"승인된 앵커 자산이 필요합니다: {anchor_id}")
        for key in APPROVAL_KEYS:
            if approvals.get(key) not in {"approved", "not-applicable"}:
                errors.append(f"최종 승인 전 확인이 필요합니다: {key}")
        if "【" in json.dumps(copy, ensure_ascii=False) or "】" in json.dumps(copy, ensure_ascii=False):
            errors.append("최종 승인 문안에 미확정 표기 【 】가 남아 있습니다")
    elif status in {"review-draft", "draft"}:
        warnings.append("현재 작업 요청서는 초안입니다. 승인 잠금 전에는 검토용 결과물만 만드세요")

    return errors, warnings


def validate_fast(job_path: Path) -> tuple[list[str], list[str]]:
    """Validate only the fields needed to safely create a review draft."""
    errors: list[str] = []
    warnings = ["fast 검증입니다. 사실·권리·상세 디자인·최종 승인 검사를 생략합니다"]
    try:
        data = json.loads(job_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"작업 요청서를 읽을 수 없습니다: {exc}"], warnings
    from character_sets import validate_selection
    errors.extend(validate_selection(data)[0])
    schema_version = data.get("schema_version")
    if schema_version not in {"1.2", "1.3"}:
        errors.append("fast 검증은 schema_version 1.2 또는 1.3을 지원합니다")
    for key in ("job_id", "purpose", "audience", "channel"):
        if not nonempty(data.get(key)):
            errors.append(f"{key}가 필요합니다")
    production_mode = data.get("production_mode")
    if production_mode not in PRODUCTION_MODES:
        errors.append("production_mode이 올바르지 않습니다")
    if data.get("authoring_mode") not in AUTHORING_MODES:
        errors.append("authoring_mode이 올바르지 않습니다")
    requested = data.get("requested_outputs")
    if not isinstance(requested, list) or not requested or any(item not in OUTPUT_FORMATS for item in requested):
        errors.append("requested_outputs에는 png, pdf, html 중 하나 이상이 필요합니다")
    targets = data.get("platform_targets")
    if not isinstance(targets, list) or not targets:
        errors.append("platform_targets는 하나 이상의 항목이 필요합니다")
        targets = []
    for index, target in enumerate(targets):
        label = f"platform_targets[{index}]"
        if not isinstance(target, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        for key in ("preset_id", "platform", "placement", "content_type"):
            if not nonempty(target.get(key)):
                errors.append(f"{label}.{key}가 필요합니다")
        if not positive_number(target.get("width_px")) or not positive_number(target.get("height_px")):
            errors.append(f"{label}의 픽셀 크기가 필요합니다")
        if not positive_number(target.get("target_count")):
            errors.append(f"{label}.target_count가 필요합니다")
    if schema_version == "1.3":
        validate_resolution_policy(data, errors, production_mode if isinstance(production_mode, str) else None)
    if production_mode == "quick-draft":
        brief = data.get("quick_brief")
        if not isinstance(brief, dict):
            errors.append("quick-draft에는 quick_brief 객체가 필요합니다")
        else:
            for key in ("headline", "call_to_action", "source_ref"):
                if not nonempty(brief.get(key)):
                    errors.append(f"quick_brief.{key}가 필요합니다")
        publication = data.get("publication")
        if isinstance(publication, dict) and (publication.get("requested") is True or publication.get("authorized") is True):
            errors.append("quick-draft에서는 외부 게시를 요청하거나 승인할 수 없습니다")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--require-locked", action="store_true")
    parser.add_argument("--level", choices=["fast", "standard", "publication"], default="standard")
    args = parser.parse_args()
    if args.level == "fast" and not args.require_locked:
        errors, warnings = validate_fast(args.job.resolve())
    else:
        errors, warnings = validate(args.job.resolve(), args.require_locked or args.level == "publication")
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK: job request is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
