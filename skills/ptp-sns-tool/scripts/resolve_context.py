#!/usr/bin/env python3
"""Return the minimum PTP skill references and assets for one request."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from character_sets import select_set, snapshot


ROOT = Path(__file__).resolve().parent.parent
COMIC_TYPES = {"social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic"}


def load_json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def add_paths(target: set[str], values: object) -> None:
    if isinstance(values, list):
        target.update(str(value) for value in values if isinstance(value, str) and value)


def existing_size(relative_paths: set[str]) -> int:
    total = 0
    for relative in relative_paths:
        path = ROOT / relative
        if path.is_file():
            total += path.stat().st_size
    return total


def resolve(args: argparse.Namespace) -> dict[str, object]:
    character_set = select_set(getattr(args, 'character_set', None), getattr(args, 'character', None),
                               render_style=args.render_style, publication=args.production_mode == 'publication')
    render_style = args.render_style or ('3d' if '3d' in character_set.get('render_styles', ['3d']) else '2d')
    delivery_form = getattr(args, 'delivery_form', None)
    generation_method = getattr(args, 'generation_method', None) or ('whole-image' if delivery_form == 'single-image' or args.content_type in COMIC_TYPES else 'separate-lettering')
    content_type = 'social-post' if delivery_form == 'single-image' else args.content_type
    if delivery_form == 'card-news' and content_type not in COMIC_TYPES:
        content_type = 'card-news'
    routing = load_json("assets/context-routing.json")
    active = load_json("assets/active-assets.json")
    references: set[str] = set()
    references.add('references/qr-code-workflow.md')
    add_paths(references, routing.get("always"))
    for section, key in (
        ("workflows", getattr(args, "workflow", "creative")),
        ("production_modes", args.production_mode),
        ("content_types", content_type),
        ("render_styles", render_style),
        ("platforms", args.platform),
    ):
        table = routing.get(section)
        if isinstance(table, dict):
            add_paths(references, table.get(key))
    format_table = routing.get("formats")
    if isinstance(format_table, dict):
        for output_format in args.formats:
            add_paths(references, format_table.get(output_format))
    flag_table = routing.get("flags")
    if isinstance(flag_table, dict):
        if args.photoreal:
            add_paths(references, flag_table.get("photoreal"))
        if args.print_output:
            add_paths(references, flag_table.get("print"))

    assets: list[str] = [] if generation_method == 'whole-image' else [str(active["font_css"])]
    characters = active.get("characters") if isinstance(active.get("characters"), dict) else {}
    selected = [m.get('legacy_key') for m in character_set['members'] if m.get('legacy_key')] if character_set.get('legacy_family') else []
    has_characters = bool(character_set['members'])
    if args.pose and has_characters and not character_set.get('legacy_family'):
        raise ValueError('기본 테오·피오 포즈를 다른 세트에 적용할 수 없습니다. 해당 세트 기준으로 동작을 제작하세요')
    character_refs = {"references/character-identity.md", "references/character-asset-system.md", "references/3d-character-style.md", "references/3d-generation-prompts.md"}
    if not character_set.get('legacy_family'):
        references.difference_update(character_refs)
    if has_characters:
        assets.append(character_set['identity_spec'])
        add_paths(references, character_set.get('references'))
        manifest = load_json('assets/asset-manifest.json')
        catalog = {a['id']: a for a in manifest['assets']}
        for member in character_set['members']:
            assets.extend('assets/' + catalog[a]['path'] for a in member['anchor_ids'])
            assets.extend(member.get('style_assets', {}).get(render_style, []))
    if selected:
        assets.append(str(active["identity_spec"]))
    else:
        references.difference_update({"references/character-identity.md", "references/character-asset-system.md", "references/3d-character-style.md", "references/3d-generation-prompts.md"})
    for name in selected:
        character = characters.get(name)
        if not isinstance(character, dict):
            continue
        assets.extend([str(character["guide"]), str(character["anchor_2d"])])
        if render_style == "3d":
            assets.append(str(character["style_3d"]))
    if render_style == "3d" and selected:
        assets.append(str(active["style_3d_spec"]))
        pose_library_path = str(active["pose_library_3d"])
        assets.append(pose_library_path)
        if args.pose:
            pose_library = load_json(pose_library_path)
            pose_characters = pose_library.get("characters") if isinstance(pose_library.get("characters"), dict) else {}
            for name in selected:
                pose_character = pose_characters.get(name)
                if not isinstance(pose_character, dict):
                    continue
                poses = pose_character.get("poses") if isinstance(pose_character.get("poses"), list) else []
                match = next((pose for pose in poses if isinstance(pose, dict) and pose.get("id") == args.pose), None)
                if isinstance(match, dict):
                    assets.append(str(Path(pose_library_path).parent / str(match["path"])).replace("\\", "/"))
        if len(selected) == 2:
            assets.append(str(active["family_3d"]))
    if args.platform != "custom":
        assets.extend([str(active["platform_presets"]), str(active["output_size_profiles"])])
    if content_type in COMIC_TYPES:
        assets.append(str(active["webtoon_template"]))
    if args.production_mode == "quick-draft":
        assets.append(str(active["quick_job_template"]))
    else:
        assets.extend([str(active["job_template"]), str(active["visual_concepts"])])
        if delivery_form == 'single-image':
            assets.remove(str(active['job_template']))
            assets.append('assets/single-image-job-template.json')
    if delivery_form == 'single-image':
        references.add('references/single-image-social.md')
    if getattr(args, 'workflow', 'creative') == 'notice-to-social':
        references.add('references/brand-identities.md')
        assets.append('assets/brand-identities/registry.json')

    validators = ["scripts/validate_job.py"]
    if args.production_mode in {"standard", "publication"}:
        validators.append("scripts/validate_assets.py")
        if render_style == "3d" and selected:
            validators.append("scripts/validate_pose_library.py")
    if args.production_mode == "publication":
        validators.extend(["scripts/validate_delivery.py", "scripts/validate_publication.py"])
        references.add('references/content-review.md')
    if getattr(args,'automated',False):
        references.add('references/automated-operation.md')
    if content_type in COMIC_TYPES:
        validators.append("scripts/validate_webtoon_mode.py")
    level = "fast" if args.production_mode == "quick-draft" else ("publication" if args.production_mode == "publication" else "standard")
    result = {
        "schema_version": "1.0",
        "request": {
            "workflow": getattr(args, "workflow", "creative"),
            "production_mode": args.production_mode,
            "content_type": content_type,
            "delivery_form": delivery_form,
            "generation_method": generation_method,
            "character": getattr(args, 'character', None),
            "character_set": character_set['id'],
            "render_style": render_style,
            "platform": args.platform,
            "formats": args.formats,
            "photoreal": args.photoreal,
            "print": args.print_output,
            "pose": args.pose,
        },
        "validation_level": level,
        "runtime_contract_version": 1 if args.production_mode=='publication' else None,
        "runtime_tools": ['scripts/social_runtime.py','scripts/content_preflight.py'] if getattr(args,'automated',False) else [],
        "character_set": snapshot(character_set),
        "link_policy": load_json('config/link-policy.json'),
        "link_preflight": "For any QR, resolve official_url -> verified short URL before image generation. Include link_policy_version, short_link_report, final decode report and visible short URL review. Institution URLs use shorten_notice_url.py --purpose institution. Never use a long URL silently when short-preferred is active.",
        "character_mode": 'set' if has_characters else 'none',
        "resolved_characters": [{k: m[k] for k in ('id', 'name', 'role', 'anchor_ids')} for m in character_set['members']],
        "validator_levels": {
            "scripts/validate_job.py": level,
            "scripts/validate_assets.py": "standard" if args.production_mode == "publication" else level,
        },
        "publication_gate": "scripts/validate_publication.py --job <job.json>" if args.production_mode == "publication" else None,
        "references": sorted(references),
        "assets": sorted(set(assets)),
        "validators": sorted(set(validators)),
        "reference_bytes": existing_size(references),
        "rules": [
            "whole-image: generate scene and exact text together, visually compare all text, decode the final QR; never claim glyph measurement. separate-lettering: measure the actual rendered font.",
            "Load returned references plus their linked references needed for the current stage.",
            "Use only the selected set identity spec and anchors. Do not mix character sets or inject Theo/Pio into no-character jobs.",
            "Copy character_set snapshot into job and delivery manifest; include its definition and asset hashes in character cache dependencies.",
            "In 3D mode, reuse the selected approved pose reference before generating a new pose.",
            "Do not read the full asset manifest during generation; reserve it for standard or publication validation.",
        ],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", choices=["creative", "notice-to-social"], default="creative")
    parser.add_argument("--delivery-form", choices=['single-image','card-news'], help="10초 형식 선택이 끝난 후 확정값 전달")
    parser.add_argument('--generation-method', choices=['whole-image','separate-lettering'], help='단일 홍보 이미지 기본은 전체 이미지 생성')
    parser.add_argument("--production-mode", choices=["quick-draft", "standard", "publication"], default="standard")
    parser.add_argument("--content-type", choices=[
        "card-news", "poster", "signage", "web-banner", "social-post", "social-story", "channel-message",
        "social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic",
    ], default="card-news")
    parser.add_argument("--character", choices=["teo", "pio", "both", "none"], help="기존 호출 호환 옵션. --character-set과 충돌하면 차단")
    parser.add_argument('--character-set', help='저장된 세트 ID·이름·별칭 또는 none')
    parser.add_argument('--list-character-sets', action='store_true')
    parser.add_argument("--render-style", choices=["2d", "3d"], help='미지정이면 선택 세트의 지원 스타일 사용. 기존 테오·피오는 3d')
    parser.add_argument("--pose", choices=[
        "neutral", "open-hand-guide", "index-explain", "thumbs-up",
        "action-step", "concerned-kind", "tablet", "wave",
    ])
    parser.add_argument("--platform", choices=["instagram", "facebook", "kakaotalk", "custom"], default="instagram")
    parser.add_argument("--format", dest="formats", action="append", choices=["png", "pdf", "html"], default=[])
    parser.add_argument("--photoreal", action="store_true")
    parser.add_argument("--print", dest="print_output", action="store_true")
    parser.add_argument("--guide", action="store_true")
    parser.add_argument('--automated', action='store_true', help='예약/자동 실행: 계정 작업 점유·실행 근거 절차 추가')
    args = parser.parse_args()
    if args.list_character_sets:
        from character_sets import main as character_main
        sys.argv = [sys.argv[0], 'list']
        return character_main()
    if args.guide:
        print("Examples:")
        print('  resolve_context.py --list-character-sets')
        print('  resolve_context.py --character-set none --delivery-form single-image')
        print('  resolve_context.py --character-set teo-pio --content-type social-toon')
        print("  resolve_context.py --workflow notice-to-social --delivery-form single-image --production-mode publication --platform instagram --format png")
        print("  resolve_context.py --workflow notice-to-social --production-mode publication --content-type card-news --platform instagram --format png")
        print("  resolve_context.py --production-mode quick-draft --content-type social-post --character both --render-style 3d --platform instagram --format png")
        print("  resolve_context.py --production-mode standard --content-type four-panel --character both --render-style 3d --platform instagram --format png")
        print("  resolve_context.py --production-mode publication --content-type poster --character teo --render-style 3d --platform custom --format pdf --print")
        return 0
    if not args.formats:
        args.formats = ["png"]
    try:
        result = resolve(args)
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        print(f"ERROR: 컨텍스트 라우팅 데이터를 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
