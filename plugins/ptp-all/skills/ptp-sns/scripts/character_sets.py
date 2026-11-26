#!/usr/bin/env python3
"""List, register and resolve saved character sets without changing approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'assets/character-sets.json'
NONE_ALIASES = {'none', '없음', '캐릭터 없음', '캐릭터 없이', '캐릭터없이'}
LEGACY = {'both': 'teo-pio', 'teo': 'teo', 'pio': 'pio', 'none': 'none'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def local_file(relative, root=ROOT):
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError('캐릭터 자산 경로가 필요합니다')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'스킬 안의 실제 파일이 필요합니다: {relative}')
    return path


def validate_entry(entry, root=ROOT):
    if not isinstance(entry, dict) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', str(entry.get('id', ''))):
        raise ValueError('세트 ID는 소문자·숫자·하이픈으로 작성합니다')
    if entry['id'] in NONE_ALIASES:
        raise ValueError('none은 캐릭터 제외용 예약 ID입니다')
    for key in ('name', 'version'):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise ValueError(f'세트 {key}가 필요합니다')
    if entry.get('status') not in {'draft', 'ready', 'disabled'}:
        raise ValueError('세트 status는 draft/ready/disabled 중 하나입니다')
    aliases = entry.get('aliases', [])
    if not isinstance(aliases, list) or any(not isinstance(a, str) or not a.strip() for a in aliases):
        raise ValueError('aliases는 비어 있지 않은 문자열 배열입니다')
    styles = entry.get('render_styles')
    if not isinstance(styles, list) or not styles or any(s not in {'2d', '3d'} for s in styles):
        raise ValueError('render_styles에 2d 또는 3d가 필요합니다')
    local_file(entry.get('identity_spec'), root)
    refs = entry.get('references', [])
    if not isinstance(refs, list):
        raise ValueError('references는 배열입니다')
    for ref in refs:
        local_file(ref, root)
    assets = {a['id']: a for a in read(root / 'assets/asset-manifest.json')['assets']}
    members = entry.get('members')
    if not isinstance(members, list) or not members:
        raise ValueError('캐릭터 세트에 members가 필요합니다')
    seen = set()
    for member in members:
        if not isinstance(member, dict) or not re.fullmatch(r'CHR-[A-Z0-9]+(?:-[A-Z0-9]+)*', str(member.get('id', ''))):
            raise ValueError('멤버마다 CHR- 형식 ID가 필요합니다')
        if member['id'] in seen:
            raise ValueError('세트 안에 중복 캐릭터 ID가 있습니다')
        seen.add(member['id'])
        if entry.get('legacy_family'):
            legacy_ids = {'teo': 'CHR-BLUE', 'pio': 'CHR-ORANGE'}
            if legacy_ids.get(member.get('legacy_key')) != member['id'] or entry['identity_spec'] != 'assets/characters/character-spec-v1.2.json':
                raise ValueError('legacy_family는 기존 테오·피오 정체성과 일치해야 합니다')
        for key in ('name', 'role'):
            if not isinstance(member.get(key), str) or not member[key].strip():
                raise ValueError(f'캐릭터 {key}가 필요합니다')
        anchors = member.get('anchor_ids')
        if not isinstance(anchors, list) or not anchors or any(not isinstance(a, str) for a in anchors):
            raise ValueError('실제 자산 목록에 등록된 anchor_ids가 필요합니다')
        for asset_id in anchors:
            asset = assets.get(asset_id, {})
            if asset.get('kind') != 'character-anchor' or asset.get('character_id') != member['id']:
                raise ValueError(f'캐릭터와 일치하는 정체성 앵커가 필요합니다: {asset_id}')
            path = local_file('assets/' + asset['path'], root)
            if hashlib.sha256(path.read_bytes()).hexdigest() != asset.get('sha256'):
                raise ValueError(f'앵커 해시 불일치: {asset_id}')
            if entry['status'] == 'ready' and asset.get('approval') != 'approved':
                raise ValueError(f'ready 세트에는 승인 자산이 필요합니다: {asset_id}')
        style_assets = member.get('style_assets', {})
        if not isinstance(style_assets, dict):
            raise ValueError('style_assets는 스타일별 파일 배열 객체입니다')
        for style, paths in style_assets.items():
            if style not in styles or not isinstance(paths, list):
                raise ValueError('style_assets는 지원 스타일별 파일 배열입니다')
            for path in paths:
                local_file(path, root)
        if not entry.get('legacy_family') and '3d' in styles and not member.get('style_assets', {}).get('3d'):
            raise ValueError('3d 지원 세트에는 멤버별 3d 스타일 기준 파일이 필요합니다')


def load_registry(path=None, root=ROOT):
    registry = read(path or root / 'assets/character-sets.json')
    if not isinstance(registry, dict) or registry.get('schema_version') != '1.0' or not isinstance(registry.get('sets'), list):
        raise ValueError('캐릭터 세트 목록 형식이 잘못됐습니다')
    names = set(NONE_ALIASES)
    ids = set()
    for entry in registry['sets']:
        validate_entry(entry, root)
        tokens = {entry['id'], entry['name'], *entry.get('aliases', [])}
        if names.intersection(tokens):
            raise ValueError('캐릭터 세트 ID·이름·별칭이 충돌합니다')
        names.update(tokens)
        ids.add(entry['id'])
    if registry.get('default_set') not in ids:
        raise ValueError('default_set이 목록에 없습니다')
    return registry


def select_set(choice=None, legacy=None, *, registry=None, root=ROOT, render_style=None, publication=False):
    registry = registry if registry is not None else load_registry(root=root)
    def lookup(value):
        if value in NONE_ALIASES:
            return {'id': 'none', 'name': '캐릭터 없음', 'version': '1.0', 'status': 'ready', 'members': []}
        matches = [s for s in registry['sets'] if value in {s['id'], s['name'], *s.get('aliases', [])}]
        if len(matches) != 1:
            raise ValueError(f'알 수 없거나 모호한 캐릭터 세트: {value}')
        return matches[0]
    entry = lookup(choice if choice is not None else LEGACY.get(legacy, registry['default_set']))
    if legacy is not None and choice is not None and lookup(LEGACY[legacy])['id'] != entry['id']:
        raise ValueError('--character와 --character-set의 선택이 충돌합니다')
    if entry['status'] == 'disabled' or (publication and entry['status'] != 'ready'):
        raise ValueError('비활성 세트 또는 게시 준비가 안 된 세트입니다')
    if entry['members'] and render_style and render_style not in entry['render_styles']:
        raise ValueError(f"{entry['name']}은 {render_style} 스타일을 지원하지 않습니다")
    return deepcopy(entry)


def snapshot(entry, root=ROOT):
    paths = [entry['identity_spec']] if entry['members'] else []
    assets = {a['id']: a for a in read(root / 'assets/asset-manifest.json')['assets']}
    for member in entry['members']:
        paths.extend('assets/' + assets[a]['path'] for a in member['anchor_ids'])
        for style_paths in member.get('style_assets', {}).values():
            paths.extend(style_paths)
    return {'id': entry['id'], 'version': entry['version'], 'definition_sha256': fingerprint(entry),
            'member_ids': [m['id'] for m in entry['members']],
            'asset_hashes': {p: hashlib.sha256(local_file(p, root).read_bytes()).hexdigest() for p in sorted(set(paths))}}


def validate_selection(data, *, root=ROOT, publication=False):
    """Legacy jobs remain valid; new jobs bind set definition and actual assets."""
    if 'character_set' not in data:
        return [], None
    try:
        saved = data['character_set']
        if not isinstance(saved, dict):
            raise ValueError('character_set은 선택 스냅샷 객체입니다')
        entry = select_set(saved.get('id'), root=root, publication=publication)
        if saved != snapshot(entry, root):
            raise ValueError('캐릭터 세트 정의·버전·자산 해시가 선택 기록과 다릅니다')
        expected = [m['id'] for m in entry['members']]
        actual = [m.get('id') for m in data.get('characters', []) if isinstance(m, dict)]
        if actual != expected:
            raise ValueError('선택한 세트와 characters 멤버·순서가 다릅니다')
        if (entry['id'] == 'none') != (data.get('character_mode') == 'none'):
            raise ValueError('캐릭터 세트와 character_mode가 충돌합니다')
        if not isinstance(data.get('character_selection_evidence'), str) or not data['character_selection_evidence'].strip():
            raise ValueError('캐릭터 선택 근거가 필요합니다')
        if entry['id'] == 'none' and not data.get('character_exclusion_evidence'):
            raise ValueError('캐릭터 제외 선택 근거가 필요합니다')
        if entry['id'] == 'none':
            if data.get('approvals', {}).get('character') != 'not-applicable':
                raise ValueError('캐릭터 없음의 검토는 not-applicable로 기록합니다')
            if any(layer.get('role') == 'character' for layer in data.get('design', {}).get('visual_system', {}).get('layer_plan', [])):
                raise ValueError('캐릭터 없음 작업에 캐릭터 레이어가 남아 있습니다')
        comic = data.get('comic')
        for panel in comic.get('panel_contract', []) if isinstance(comic, dict) else []:
            if not isinstance(panel.get('characters'), list) or any(c not in expected for c in panel['characters']):
                raise ValueError('컷에 선택한 세트 밖의 캐릭터가 있습니다')
        for member, character in zip(entry['members'], data['characters']):
            if not set(member['anchor_ids']).issubset(character.get('anchor_ids', [])):
                raise ValueError('선택한 세트의 정체성 앵커가 작업에 누락됐습니다')
        return [], entry
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f'캐릭터 세트: {exc}'], None


def apply_to_job(data, entry, evidence, root=ROOT):
    if data.get('status') not in {'draft', 'review-draft'}:
        raise ValueError('확정·납품 작업은 변경하지 않습니다. 새 초안에서 선택하세요')
    if not isinstance(evidence, str) or not evidence.strip():
        raise ValueError('사용자 선택 또는 기존 작업 설정 근거가 필요합니다')
    job = deepcopy(data)
    job['character_set'] = snapshot(entry, root)
    job['character_selection_evidence'] = evidence
    job['character_mode'] = 'none' if not entry['members'] else 'set'
    job['characters'] = [{'id': m['id'], 'name': m['name'], 'role': m['role'], 'outfit_slot': 'default',
                          'anchor_ids': m['anchor_ids'], 'approval': 'approved' if entry['status'] == 'ready' else 'pending'} for m in entry['members']]
    if not entry['members']:
        job['character_exclusion_evidence'] = evidence
    else:
        job.pop('character_exclusion_evidence', None)
    job.setdefault('approvals', {})['character'] = 'pending' if entry['members'] else 'not-applicable'
    design = job.setdefault('design', {})
    if not isinstance(design, dict):
        raise ValueError('design은 객체여야 합니다')
    design['character_integration'] = {'actions': {m['id']: '【이번 콘텐츠에서 수행할 행동】' for m in entry['members']}, 'functional_target': '【정보 전달에 기여하는 역할】'} if entry['members'] else {}
    # A changed cast needs a new scene/lettering review, never silent speaker remapping.
    if isinstance(job.get('comic'), dict):
        for panel in job['comic'].get('panel_contract', []):
            panel['characters'] = []
        job['comic']['cast_revision_required'] = True
    if not entry['members']:
        layers = design.get('visual_system', {}).get('layer_plan', [])
        layers[:] = [layer for layer in layers if layer.get('role') != 'character']
    job.pop('publication_asset_ids', None)
    job.pop('publication_review', None)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    resolve = sub.add_parser('resolve')
    resolve.add_argument('--set', required=True)
    resolve.add_argument('--render-style', choices=['2d', '3d'])
    resolve.add_argument('--publication', action='store_true')
    register = sub.add_parser('register')
    register.add_argument('--file', required=True, type=Path)
    apply = sub.add_parser('apply')
    apply.add_argument('--job', type=Path, required=True)
    apply.add_argument('--set', required=True)
    apply.add_argument('--evidence', required=True)
    apply.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        registry = load_registry()
        if args.command == 'list':
            result = [{'id': 'none', 'name': '캐릭터 없음', 'status': 'ready'}] + [
                {k: s[k] for k in ('id', 'name', 'version', 'status', 'render_styles')} for s in registry['sets']]
        elif args.command == 'register':
            entry = read(args.file)
            if not isinstance(entry, dict):
                raise ValueError('세트 등록 파일은 JSON 객체입니다')
            if any(s['id'] == entry.get('id') for s in registry['sets']):
                raise ValueError('같은 ID는 덮어쓰지 않습니다. 새 버전 ID를 사용하세요')
            candidate = {**registry, 'sets': registry['sets'] + [entry]}
            # Validate all aliases and files before a single atomic replacement.
            temp = REGISTRY.with_suffix('.json.tmp')
            if temp.exists():
                raise ValueError('다른 등록 작업의 임시 파일이 있습니다')
            try:
                with temp.open('x', encoding='utf-8') as handle:
                    json.dump(candidate, handle, ensure_ascii=False, indent=2)
                load_registry(temp)
                temp.replace(REGISTRY)
            finally:
                temp.unlink(missing_ok=True)
            result = {'registered': entry['id'], 'publication_authorized': False}
        else:
            entry = select_set(args.set, registry=registry, render_style=getattr(args, 'render_style', None), publication=getattr(args, 'publication', False))
            if args.command == 'apply':
                if args.output.exists():
                    raise ValueError('출력 파일이 이미 있습니다. 새 초안 파일을 지정하세요')
                result = apply_to_job(read(args.job), entry, args.evidence)
                with args.output.open('x', encoding='utf-8') as handle:
                    json.dump(result, handle, ensure_ascii=False, indent=2)
                result = {'job': str(args.output), 'character_set': result['character_set']}
            else:
                result = {'set': entry, 'character_set': snapshot(entry)}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
