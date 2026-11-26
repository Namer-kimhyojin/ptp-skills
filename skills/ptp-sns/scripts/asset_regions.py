#!/usr/bin/env python3
"""Apply explicitly authorized QR/logo region replacement, preserving all other pixels.

Pillow is required for this operation. This utility does not generate posters or
replace their typography. A final QR decode remains mandatory after any patch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from social_runtime import immutable_json, load, sha


def grant_for(grants, source_key, kind, base_sha256):
    for g in grants.get('grants',[]):
        if (g.get('active') is True and kind in g.get('regions',[])
            and source_key in g.get('source_keys',[]) and g.get('user_request_evidence')
            and (not g.get('base_sha256') or g['base_sha256']==base_sha256)):
            return g
    raise ValueError('No existing user grant covers this source, region and image; retain the task-specific authorization evidence.')


def patch(base_path, source_key, regions, grants, output, report_path):
    from PIL import Image, ImageChops
    base_path,output,report_path=map(Path,(base_path,output,report_path))
    if output.exists() or report_path.exists():raise ValueError('output_and_report_must_be_new')
    if output.resolve()==base_path.resolve():raise ValueError('original_must_be_preserved')
    if output.suffix.lower()!='.png':raise ValueError('PNG_output_required')
    base_sha=sha(base_path)
    with Image.open(base_path) as im:
        if im.format!='PNG':raise ValueError('PNG_source_required')
        original=im.convert('RGBA')
    canvas=original.copy();mask=Image.new('L',original.size,0)
    evidence=[]
    if not regions:raise ValueError('regions_required')
    for r in regions:
        kind=r['kind']
        if kind not in {'qr','logo'}:raise ValueError('only_qr_and_logo_regions_allowed')
        grant=grant_for(grants,source_key,kind,base_sha)
        rect=r['rect']
        if len(rect)!=4 or any(type(v) is not int for v in rect):raise ValueError('integer_rectangle_required')
        x,y,w,h=rect
        if min(x,y)<0 or min(w,h)<=0 or x+w>canvas.width or y+h>canvas.height:raise ValueError('rectangle_outside_image')
        if mask.crop((x,y,x+w,y+h)).getbbox():raise ValueError('authorized_regions_must_not_overlap')
        asset=Path(r['asset_path'])
        if sha(asset)!=r['asset_sha256']:raise ValueError('original_asset_hash_mismatch')
        with Image.open(asset) as im:replacement=im.convert('RGBA')
        if kind=='qr' and (replacement.width!=replacement.height or w!=h):raise ValueError('square_QR_required')
        if kind=='logo':
            # A specific authorized asset is required, so an arbitrary recreated
            # wordmark cannot be accepted under a general patch grant.
            registered=grants.get('brand_assets',[])
            if r['asset_sha256'] not in {a.get('sha256') for a in registered}:raise ValueError('logo_must_match_registered_original')
        scale=min(w/replacement.width,h/replacement.height)
        size=(max(1,round(replacement.width*scale)),max(1,round(replacement.height*scale)))
        replacement=replacement.resize(size,Image.Resampling.NEAREST if kind=='qr' else Image.Resampling.LANCZOS)
        if 'background_rgba' in r:
            color=r['background_rgba']
            if len(color)!=4 or any(type(c) is not int or not 0<=c<=255 for c in color):raise ValueError('invalid_background_RGBA')
            canvas.paste(tuple(color),(x,y,x+w,y+h))
        canvas.alpha_composite(replacement,(x+(w-size[0])//2,y+(h-size[1])//2))
        mask.paste(255,(x,y,x+w,y+h))
        evidence.append({'kind':kind,'rect':rect,'asset_path':str(asset.resolve()),'asset_sha256':r['asset_sha256'],'grant_id':grant['id']})
    diff=ImageChops.difference(original,canvas)
    channels=diff.split()
    outside=ImageChops.invert(mask)
    if any(ImageChops.multiply(c,outside).getbbox() for c in channels):raise ValueError('pixels_changed_outside_authorized_regions')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation avoids overwriting an earlier immutable revision.
    with output.open('xb') as f:canvas.save(f,format='PNG')
    with Image.open(output) as reread:
        final=reread.convert('RGBA')
        if final.tobytes()!=canvas.tobytes():raise ValueError('saved_pixels_differ')
    report={'source_key':source_key,'base_path':str(base_path.resolve()),'base_sha256':base_sha,
            'output_path':str(output.resolve()),'output_sha256':sha(output),'regions':evidence,
            'outside_regions_unchanged':True,'width':canvas.width,'height':canvas.height,
            'final_qr_decode_verified':False,'next_action':'Decode the final whole image at required scales before publication.'}
    immutable_json(report_path,report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--source-key',required=True)
    p.add_argument('--regions',type=Path,required=True);p.add_argument('--grants',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    try:
        result=patch(a.base,a.source_key,load(a.regions)['regions'],load(a.grants),a.output,a.report)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError,ImportError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False));return 2


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
