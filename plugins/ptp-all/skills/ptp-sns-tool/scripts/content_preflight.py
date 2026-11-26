#!/usr/bin/env python3
"""Content change detection and file-bound publication review evidence.

These checks validate declared observations and file integrity. They do not
perform a human review, read a protected document, or prove visual quality.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from social_runtime import current_time, immutable_json, load, sha, stamp


def normalized(value):
    return re.sub(r'\s+', '', value) if isinstance(value, str) else value


def resolved(base, value):
    p=Path(value)
    return p if p.is_absolute() else Path(base)/p


def snapshot(source_path):
    source_path=Path(source_path).resolve();d=load(source_path)
    ident=str(d['selected']['board_id'])
    attachments={};errors=[]
    for item in d.get('attachments',[]):
        key=item.get('file_id',item.get('url',''))
        if not key or key in attachments:raise ValueError('invalid_or_duplicate_attachment_identity')
        if item.get('status')!='downloaded':
            errors.append('attachment_unavailable:'+str(key));continue
        path=resolved(source_path.parent,item['path']);digest=sha(path)
        if digest!=item.get('sha256'):errors.append('attachment_hash_mismatch:'+str(key))
        attachments[key]={'path':str(path.resolve()),'sha256':digest,'url':item.get('url'),'name':item.get('source_name')}
    detail=d.get('detail_evidence',{})
    detail_path=resolved(source_path.parent,detail['path'])
    if sha(detail_path)!=detail.get('sha256'):errors.append('detail_hash_mismatch')
    return {'schema_version':1,'source_key':'ptp:15:'+ident,'source_url':d['selected']['detail_url'],
            'checked_at':d.get('collected_at'),'snapshot_created_at':current_time().isoformat(),
            'source_path':str(source_path),'source_sha256':sha(source_path),
            'title':d['title'],'body_text':d.get('body_text',''),'fields':d.get('fields',{}),
            'attachments':attachments,'errors':errors,'complete':not errors,
            'document_reading_verified':False}


def compare_sources(before, after):
    if before.get('source_key')!=after.get('source_key') or before.get('source_url')!=after.get('source_url'):
        raise ValueError('cannot_compare_different_notices')
    changed=[]
    for name in ('title','body_text','fields'):
        if before.get(name)!=after.get(name):changed.append(name)
    old,new=before.get('attachments',{}),after.get('attachments',{})
    attachments=[k for k in sorted(set(old)|set(new)) if old.get(k,{}).get('sha256')!=new.get(k,{}).get('sha256')]
    changed_fields=[k for k in sorted(set(before.get('fields',{}))|set(after.get('fields',{})))
                    if before.get('fields',{}).get(k)!=after.get('fields',{}).get(k)]
    return {'source_key':after['source_key'],'checked_at':current_time().isoformat(),'changed':bool(changed or attachments),
            'changed_sections':changed,'changed_fields':changed_fields,'changed_attachment_ids':attachments,
            'requires_fact_review':bool(changed or attachments or not after.get('complete')),
            'after_source_sha256':after.get('source_sha256'),'after_complete':after.get('complete') is True,
            'publication_allowed_by_this_report':False,
            'next_action':'Read changed original sections/attachments and update affected copy/images; refresh eligibility immediately before submission.' if changed or attachments else 'Source unchanged; still recheck live acceptance/cancellation and eligibility.'}


def png_size(path):
    from PIL import Image
    with Image.open(path) as im:
        if im.format!='PNG':raise ValueError('PNG_required')
        im.verify()
    with Image.open(path) as im:
        im.load()
        return im.size


def review_education(spec, image_specs):
    key = spec.get('source_key')
    from spark_runtime import KEY_PATTERN
    episode = re.fullmatch(r'ptp:institution:support-guide-2026:ep(\d{2})', key) if isinstance(key, str) else None
    spark = isinstance(key, str) and re.fullmatch(KEY_PATTERN, key)
    if not spark and (not episode or (not 9 <= int(episode[1]) <= 34 and 'education_review' not in spec)):
        return []

    review = spec.get('education_review')
    if not isinstance(review, dict):
        return ['series_education_review_required']

    def has_text(record, field):
        value = record.get(field)
        return isinstance(value, str) and bool(value.strip())

    errors = []
    count = len(image_specs)
    level = review.get('level')
    expected_count = {'standard': 5, 'expanded': 6, 'complex': 7}
    if spark:
        if count < 5:
            errors.append('spark_requires_at_least_five_final_images')
        if (spec.get('forbidden_mascots_absent') is not True
                or not has_text(spec, 'mascot_exclusion_evidence')):
            errors.append('spark_requires_actual_mascot_exclusion_review')
        if not re.fullmatch(r'[a-f0-9]{64}', str(spec.get('industry_topic_sha256', ''))):
            errors.append('spark_topic_digest_required')
    elif not isinstance(level, str) or expected_count.get(level) != count:
        errors.append('series_requires_5_to_7_images_matching_education_level')
    hashes = [item.get('sha256') for item in image_specs if isinstance(item, dict)]
    if len(hashes) != count or any(not isinstance(h, str) for h in hashes) or len(set(hashes)) != count:
        errors.append('series_final_images_must_be_distinct')
    if not all(has_text(review, field) for field in ('page_count_reason', 'plain_language_evidence')):
        errors.append('series_page_count_and_plain_language_evidence_required')

    pages = review.get('pages')
    if not isinstance(pages, list) or len(pages) != count:
        errors.append('series_learning_steps_must_match_final_images')
    else:
        takeaways = set()
        roles_found = set()
        for number, page in enumerate(pages, 1):
            roles = ('question',) if number == 1 else ('apply',) if number == count else ('explain', 'example', 'compare', 'check')
            if (not isinstance(page, dict) or type(page.get('page')) is not int or page['page'] != number
                    or page.get('role') not in roles or not has_text(page, 'takeaway')):
                errors.append(f'series_learning_step_invalid:page_{number}')
                continue
            takeaway = normalized(page['takeaway'])
            if takeaway in takeaways:
                errors.append(f'series_learning_step_repeated:page_{number}')
            takeaways.add(takeaway)
            roles_found.add(page['role'])
        if (spark or int(episode[1]) >= 9) and not {'explain', 'example'}.issubset(roles_found):
            errors.append('series_requires_plain_explanation_and_concrete_example')

    checks = review.get('reader_checks')
    kinds = set()
    for check in checks if isinstance(checks, list) else []:
        if not isinstance(check, dict):
            continue
        kind, evidence_pages = check.get('kind'), check.get('pages')
        if (kind in ('explain', 'apply') and all(has_text(check, field) for field in ('question', 'answer'))
                and isinstance(evidence_pages, list) and evidence_pages
                and all(type(page) is int and 1 <= page <= count for page in evidence_pages)):
            kinds.add(kind)
    if kinds != {'explain', 'apply'}:
        errors.append('series_explanation_and_application_checks_required')
    return errors


def review_quality(spec, base):
    errors=[];warnings=[];images=[]
    if not isinstance(spec,dict):raise ValueError('quality_spec_required')
    if not spec.get('source_key') or not spec.get('reviewer'):errors.append('source_key_and_actual_reviewer_required')
    if spec.get('generation_method')!='whole-image' and spec.get('generation_method')!='separate-lettering':errors.append('generation_method_required')
    image_specs = spec.get('images')
    if not isinstance(image_specs, list) or not image_specs:
        errors.append('final_images_required')
        image_specs = []
    errors.extend(review_education(spec, image_specs))
    expected_size=tuple(spec.get('expected_size',[1080,1350]))
    presets = {}
    if any(isinstance(item, dict) and 'preset_id' in item for item in image_specs):
        presets = {preset['id']: preset for preset in load(
            Path(__file__).resolve().parents[1] / 'assets/platform-presets.json'
        )['presets']}
    for i,item in enumerate(image_specs):
        try:
            image=resolved(base,item['path']).resolve();mobile=resolved(base,item['mobile_path']).resolve()
            digest=sha(image);mobile_digest=sha(mobile)
            if digest!=item['sha256'] or mobile_digest!=item['mobile_sha256']:raise ValueError('reviewed_file_changed')
            size=png_size(image);msize=png_size(mobile)
            target_size = expected_size
            if presets:
                preset = presets[item['preset_id']]
                target_size = (preset['width_px'], preset['height_px'])
            if size != target_size:raise ValueError('final_dimensions_mismatch')
            if msize[0]!=360 or abs(msize[1]-size[1]*360/size[0])>1:raise ValueError('360px_mobile_preview_required')
            expected=item.get('expected_text');observed=item.get('observed_text')
            if not isinstance(expected,list) or not expected or not all(isinstance(t,str) and t.strip() for t in expected):raise ValueError('exact_expected_text_required')
            if not isinstance(observed,list) or [normalized(t) for t in expected]!=[normalized(t) for t in observed]:raise ValueError('observed_text_differs_from_confirmed_copy')
            reviews=item.get('reviews',{})
            for key in ('facts','text','mobile','layout','character','brand'):
                r=reviews.get(key,{})
                permitted={'passed'} if key not in {'character','brand'} else {'passed','not-applicable'}
                if r.get('status') not in permitted or not isinstance(r.get('evidence'),str) or not r['evidence'].strip():raise ValueError('actual_'+key+'_review_required')
                stamp(r['checked_at'])
            ocr=item.get('ocr')
            if ocr:
                if ocr.get('image_sha256')!=digest:raise ValueError('OCR_bound_to_other_image')
                if normalized(ocr.get('text',''))!=normalized(''.join(expected)):
                    warnings.append('OCR_difference_requires_actual_visual_comparison:image_'+str(i+1))
            images.append({'path':str(image),'sha256':digest,'width':size[0],'height':size[1],
                           'mobile_path':str(mobile),'mobile_sha256':mobile_digest,'text_compared':True})
            if presets:
                images[-1]['preset_id'] = item['preset_id']
        except (OSError,ValueError,KeyError,TypeError,ImportError) as exc:errors.append('image_'+str(i+1)+':'+str(exc))
    creative=spec.get('creative',{});signature=creative.get('signature',{})
    required=('format_id','layout_family','hook_device','character_acting')
    if not all(isinstance(signature.get(k),str) and signature[k].strip() for k in required):errors.append('actual_creative_signature_required')
    recent=creative.get('recent')
    if not isinstance(recent,list):errors.append('recent_actual_designs_required');recent=[]
    unique=[];seen=set()
    for r in recent:
        if r.get('source_key')==spec.get('source_key'):continue
        if r.get('source_key') in seen:continue
        seen.add(r.get('source_key'));unique.append(r)
    for r in unique[:6]:
        try:
            p=resolved(base,r['preview_path'])
            if sha(p)!=r['sha256'] or not r.get('review_evidence'):raise ValueError('previous_preview_not_reviewed_or_changed')
        except (OSError,ValueError,TypeError,KeyError) as exc:errors.append('recent_design:'+str(exc))
    if unique:
        last=unique[0].get('signature',{})
        if signature.get('format_id')==last.get('format_id') and signature.get('layout_family')==last.get('layout_family') and not creative.get('exception_evidence'):
            errors.append('consecutive_narrative_layout_repetition')
        if not creative.get('difference_evidence'):errors.append('actual_design_difference_evidence_required')
    elif not creative.get('no_history_evidence'):
        errors.append('empty_history_reason_required')
    result={'schema_version':1,'source_key':spec.get('source_key'),'checked_at':current_time().isoformat(),
            'passed':not errors,'images':images,'creative_signature':signature,'errors':errors,'warnings':warnings,
            'scope':'declared_visual_observations_and_file_integrity','human_review_performed':False,
            'limitation':'Visual observations must be made by the named reviewer. This report does not run OCR or perform a human review.'}
    return result


def validate_report(path, source_key):
    try:
        report=load(path)
        if report.get('passed') is not True:raise ValueError('quality_review_not_passed')
        if report.get('source_key')!=source_key:raise ValueError('quality_source_key_mismatch')
        specpath=Path(report['spec_path'])
        if sha(specpath)!=report['spec_sha256']:raise ValueError('quality_spec_changed')
        live=review_quality(load(specpath),specpath.parent)
        if live['errors']:raise ValueError('; '.join(live['errors']))
        if report.get('images')!=live['images'] or report.get('creative_signature')!=live['creative_signature']:
            raise ValueError('quality_report_binding_mismatch')
        return []
    except (OSError,ValueError,TypeError,KeyError) as exc:return [str(exc)]


def validate_job_quality(job, job_path):
    """New contract only; legacy immutable packages retain their old checks."""
    if job.get('runtime_contract_version') is None:return []
    errors=[]
    try:
        if job['runtime_contract_version']!=1:raise ValueError('unsupported_runtime_contract')
        path=resolved(Path(job_path).parent,job['quality_review_path'])
        key=job.get('source_key') or job.get('source_notice',{}).get('source_key')
        issues=validate_report(path,key)
        if issues:raise ValueError('; '.join(issues))
        report=load(path)
        if report.get('passed') is not True:raise ValueError('quality_review_not_passed')
        if report.get('source_key')!=key:raise ValueError('quality_source_key_mismatch')
        specpath=Path(report['spec_path'])
        if sha(specpath)!=report['spec_sha256']:raise ValueError('quality_spec_changed')
        live=review_quality(load(specpath),specpath.parent)
        if live['errors']:raise ValueError('; '.join(live['errors']))
        if report.get('images')!=live['images']:raise ValueError('quality_report_image_binding_mismatch')
        if job.get('ptp_ci_required') is True:
            brand_root = Path(__file__).resolve().parents[1] / 'assets/brand-identities'
            registered = {
                entry['file']: entry['sha256']
                for entry in load(brand_root / 'registry.json')['entries']
                if entry['organization'] == '포항테크노파크'
            }
            for image in load(specpath)['images']:
                review = image['reviews']['brand']
                source = review.get('asset_file')
                if (
                    review['status'] != 'passed'
                    or source not in registered
                    or review.get('asset_sha256') != registered[source]
                    or sha(brand_root / source) != registered[source]
                ):
                    raise ValueError('registered_ptp_ci_review_required')
        final_paths=job.get('final_image_paths')
        if not isinstance(final_paths,list) or not final_paths:raise ValueError('final_image_paths_required')
        declared={str(resolved(Path(job_path).parent,p).resolve()) for p in final_paths}
        if declared!={i['path'] for i in live['images']}:raise ValueError('delivered_images_differ_from_reviewed_images')
        if job.get('delivery_form') == 'single-image' and job.get('channel_image_policy') == 'shared-square-feed':
            if len(live['images']) != 1 or any(
                (image['width'], image['height']) != (1080, 1080) for image in live['images']
            ):
                raise ValueError('one_1080_square_image_required')
            if not job['platform_targets'] or any(
                target['preset_id'] not in {'instagram-feed-square', 'facebook-feed-square'}
                or (target['width_px'], target['height_px']) != (1080, 1080)
                for target in job['platform_targets']
            ):
                raise ValueError('square_feed_targets_required')
        if job.get('delivery_form') == 'single-image' and (
            job.get('channel_image_policy') == 'separate-feed-files'
            or any('preset_id' in image for image in live['images'])
        ):
            targets = sorted(target['preset_id'] for target in job['platform_targets'])
            reviewed = sorted(image.get('preset_id', '') for image in live['images'])
            if targets != reviewed or len(declared) != len(targets):
                raise ValueError('one_distinct_reviewed_image_required_per_target')
        if job.get('creative_signature')!=report.get('creative_signature'):raise ValueError('job_creative_signature_mismatch')
        if not report.get('images'):raise ValueError('reviewed_images_required')
    except (OSError,ValueError,TypeError,KeyError) as exc:errors.append('제작 검수: '+str(exc))
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('snapshot');s.add_argument('--source',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('compare');s.add_argument('--before',type=Path,required=True);s.add_argument('--after',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('review');s.add_argument('--spec',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        if a.command=='snapshot':result=snapshot(a.source)
        elif a.command=='compare':result=compare_sources(load(a.before),load(a.after))
        else:
            result=review_quality(load(a.spec),a.spec.resolve().parent)
            result.update(spec_path=str(a.spec.resolve()),spec_sha256=sha(a.spec))
        immutable_json(a.output,result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('errors') else 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False));return 2


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
