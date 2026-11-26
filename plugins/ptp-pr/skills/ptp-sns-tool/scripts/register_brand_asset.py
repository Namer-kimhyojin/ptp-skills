#!/usr/bin/env python3
"""Register a user-provided logo as a new version without replacing old files."""
import argparse, datetime, hashlib, json, os, shutil, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / 'assets' / 'brand-identities'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file', required=True, type=Path)
    p.add_argument('--organization', required=True)
    p.add_argument('--variant', required=True)
    p.add_argument('--source', required=True, help='Source or user-provided provenance')
    p.add_argument('--usage', required=True, help='Known terms or unverified status')
    a = p.parse_args()
    if a.file.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.svg', '.webp'} or not a.file.is_file():
        p.error('A real PNG/JPEG/SVG/WebP file is required')
    data = a.file.read_bytes()
    if not data or len(data) > 20_000_000:
        p.error('File must be nonempty and no larger than 20 MB')
    digest = hashlib.sha256(data).hexdigest()
    path = ROOT / 'user-updates' / (digest + a.file.suffix.lower())
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open('xb') as output:
            output.write(data)
    registry = ROOT / 'registry.json'
    doc = json.loads(registry.read_text(encoding='utf-8'))
    if any(x.get('sha256') == digest and x.get('organization') == a.organization and x.get('variant') == a.variant for x in doc['entries']):
        print(json.dumps({'status':'already-registered','sha256':digest}, ensure_ascii=False)); return
    record = {'organization':a.organization,'variant':a.variant,'file':path.relative_to(ROOT).as_posix(),
              'sha256':digest,'source_page':None,'origin':a.source,'usage':a.usage,
              'checked_at':datetime.date.today().isoformat(),'status':'available-reference',
              'supersedes':'manual-selection-required'}
    doc['entries'].append(record)
    tmp = registry.with_name(registry.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(tmp,registry)
    finally:
        if tmp.exists(): tmp.unlink()
    print(json.dumps({'status':'registered','entry':record},ensure_ascii=False))

if __name__ == '__main__': main()
