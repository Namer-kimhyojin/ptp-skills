#!/usr/bin/env python3
"""Check that a publication's QR follows the saved link policy and actual image hash."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
POLICY=ROOT/'config/link-policy.json'

def validate(data, job_path):
    qr=data.get('qr')
    if not isinstance(qr,dict):
        if data.get('link_policy') and not data.get('qr_exclusion_evidence'):
            return ['단축주소 정책: QR이 필요한 작업에 qr 객체가 없습니다']
        return []
    errors=[]
    def report(key):
        raw=qr.get(key)
        if not isinstance(raw,str) or not raw.strip():raise ValueError(f'qr.{key}가 필요합니다')
        path=Path(raw)
        return json.loads((path if path.is_absolute() else job_path.parent/path).read_text('utf-8'))
    try:
        policy=json.loads(POLICY.read_text('utf-8'))
        if qr.get('link_policy_version')!=policy['version']:
            raise ValueError('현재 단축주소 정책 버전이 작업에 적용되지 않았습니다')
        official=qr.get('official_url')
        if not isinstance(official,str) or not official.startswith('https://'):
            raise ValueError('원래 공식 주소 official_url이 필요합니다')
        short_report=report('short_link_report')
        if short_report.get('official_url')!=official:
            raise ValueError('단축주소 보고서의 공식 목적지가 다릅니다')
        selected=short_report.get('selected')
        if selected:
            passed=[a for a in short_report.get('attempts',[]) if a.get('passed') is True and a.get('short_url')==selected and a.get('redirect',{}).get('location')==official]
            if not passed or qr.get('target_url')!=selected:
                raise ValueError('QR에 검증된 단축주소가 반영되지 않았습니다')
            if not qr.get('visible_short_url_review') or qr.get('visible_short_url')!=selected:
                raise ValueError('이미지에 표시된 단축주소와 실제 QR 주소의 대조 근거가 필요합니다')
        else:
            if not short_report.get('attempts') or not qr.get('fallback_reason') or qr.get('target_url')!=official:
                raise ValueError('단축 실패 시 원문 사용에는 실제 실패 기록과 사유가 필요합니다')
        decoded=report('report_path')
        check=decoded.get('image_verification',{})
        if decoded.get('passed') is not True or decoded.get('expected_url')!=qr.get('target_url'):
            raise ValueError('최종 QR 해독 주소가 정책·단축주소와 다릅니다')
        checks=check.get('checks',[])
        if not {1.0,0.5}.issubset({c.get('scale') for c in checks if c.get('passed') is True}):
            raise ValueError('최종 QR 원본·0.5배 검사가 필요합니다')
        raw=check.get('image')
        path=Path(raw) if isinstance(raw,str) else None
        if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=check.get('sha256'):
            raise ValueError('QR 검증 후 최종 이미지가 바뀌었거나 파일을 찾을 수 없습니다')
    except (OSError,ValueError,KeyError,TypeError) as exc:
        errors.append(f'단축주소 정책: {exc}')
    return errors
