"""Verify measured glyph bounds against their parent boxes and final PNG hashes.

This cannot detect unreported text in pixels; inspect every exported card visually.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def validate(path: Path) -> list[str]:
    errors=[]
    try:
        data=json.loads(path.read_text('utf-8-sig'))
        image=Path(data['image'])
        if not image.is_absolute(): image=path.parent/image
        raw=image.read_bytes()
        if raw[:8]!=b'\x89PNG\r\n\x1a\n': raise ValueError('Final image is not a PNG')
        width,height=struct.unpack('>II',raw[16:24])
        if hashlib.sha256(raw).hexdigest()!=data['image_sha256']: errors.append('final_image_hash_changed')
        if data.get('engine')!='actual-canvas-glyph-metrics': errors.append('actual_glyph_metrics_required')
        blocks=data.get('text_blocks')
        if not isinstance(blocks,list) or not blocks: raise ValueError('Measured text blocks required')
        for index,block in enumerate(blocks):
            label=f'block[{index}]'
            b=block['box'];inner=block['inner']
            vals=[b[k] for k in ['x','y','width','height']]+[inner[k] for k in ['left','top','right','bottom']]
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in vals): raise ValueError('Invalid geometry')
            if not (0<=b['x']<b['x']+b['width']<=width and 0<=b['y']<b['y']+b['height']<=height): errors.append(label+': container_outside_image')
            if not (b['x']<=inner['left']<inner['right']<=b['x']+b['width'] and b['y']<=inner['top']<inner['bottom']<=b['y']+b['height']): errors.append(label+': unsafe_inner_bounds')
            if block['requiredHeight']>b['height']+.01: errors.append(label+': text_height_overflow')
            lines=block['lines']
            if not lines or not any(line.get('text','').strip() for line in lines): errors.append(label+': empty_measurements')
            for line in lines:
                if not line['text']: continue
                ink=line['ink']
                if any(not isinstance(ink[k],(int,float)) or not math.isfinite(ink[k]) for k in ['left','top','right','bottom']): raise ValueError('Invalid glyph bounds')
                if not (inner['left']-.01<=ink['left']<=ink['right']<=inner['right']+.01 and inner['top']-.01<=ink['top']<=ink['bottom']<=inner['bottom']+.01): errors.append(label+': glyph_outside_parent')
    except (OSError,ValueError,TypeError,KeyError,AttributeError,struct.error) as exc:
        errors.append('invalid_report: '+str(exc))
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',nargs='+',type=Path)
    args=p.parse_args()
    results=[{'report':str(path),'errors':validate(path)} for path in args.reports]
    passed=all(not r['errors'] for r in results)
    print(json.dumps({'status':'passed' if passed else 'failed','results':results,'scope':'Measured blocks and final-image integrity, not OCR or human visual approval'},ensure_ascii=False,indent=2))
    return 0 if passed else 1


if __name__=='__main__': raise SystemExit(main())
