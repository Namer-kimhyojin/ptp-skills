#!/usr/bin/env python3
"""Suggest diverse PTP content concepts from input signals using only stdlib."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


PHOTO_VALUES = {"available", "preferred", "none"}
ROOT = Path(__file__).resolve().parent.parent


def recent_designs(ledger: Path, lookback: int = 6, exclude_source: str | None = None) -> tuple[list[dict], list[str]]:
    """Read completed packages once per notice; never rewrite production history."""
    from content_history import read_latest
    events = read_latest(ledger)
    completed = sorted((e for e in events.values() if e['status'] == 'produced'
                        and e['source_key'] != exclude_source), key=lambda e:datetime.fromisoformat(e['recorded_at'].replace('Z','+00:00')), reverse=True)[:lookback]
    recent, warnings = [], []
    for event in completed:
        manifest_path = Path(event['manifest_path'])
        try:
            raw = manifest_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != event['manifest_sha256']:
                raise ValueError('manifest fingerprint mismatch')
            manifest = json.loads(raw.decode('utf-8-sig'))
            job_path = manifest_path.parent / 'job.json'
            job = json.loads(job_path.read_text('utf-8-sig')) if job_path.exists() else {}
            signature = manifest.get('creative_signature') or job.get('creative_signature') or {}
            sidecar = manifest_path.parent / 'creative-signature.json'
            if not signature and sidecar.exists():
                note = json.loads(sidecar.read_text('utf-8-sig'))
                if note.get('manifest_sha256') != event['manifest_sha256']:
                    raise ValueError('creative signature belongs to a different package')
                signature = note.get('creative_signature', {})
            concept = signature.get('concept_id') or job.get('concept_strategy',{}).get('selected_concept_id')
            recent.append({**signature,'concept_id':concept,'source_key':event['source_key'],
                           'recorded_at':event['recorded_at'],'manifest_path':str(manifest_path),
                           'preview_path':str(manifest_path.parent/'preview.png')})
            if not signature.get('layout_family'):
                warnings.append(f"{event['source_key']}: layout history incomplete; inspect its actual preview")
        except (OSError,UnicodeError,ValueError,TypeError,AttributeError) as exc:
            warnings.append(f"{event['source_key']}: cannot inspect prior design: {exc}")
    return recent, warnings


def presentation_choices(signals: set[str], recent: list[dict]) -> list[dict]:
    catalog=json.loads((ROOT/'assets'/'creative-formats.json').read_text('utf-8'))['formats']
    ranked=[]
    for item in catalog:
        score=3*len(signals & set(item['signal_tags']))
        # Change narrative AND structure; a new medium with the same frame is insufficient.
        for index, old in enumerate(recent):
            if old.get('format_id')==item['id']: score-=12 if index==0 else 3
            if old.get('layout_family')==item['layout_family']: score-=10 if index==0 else 2
        ranked.append((score,item))
    ranked.sort(key=lambda pair:(-pair[0],pair[1]['id']))
    return [{**item,'score':score} for score,item in ranked[:3]]


def load_catalog() -> list[dict[str, object]]:
    path = Path(__file__).resolve().parent.parent / "assets" / "visual-concept-presets.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    concepts = data.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        raise ValueError("visual concept catalog is empty")
    return [item for item in concepts if isinstance(item, dict)]


def score_concept(concept: dict[str, object], signals: set[str], tones: set[str], photo: str) -> tuple[int, list[str]]:
    concept_signals = set(concept.get("signal_tags", []))
    concept_tones = set(concept.get("tone_tags", []))
    signal_hits = sorted(signals & concept_signals)
    tone_hits = sorted(tones & concept_tones)
    score = len(signal_hits) * 3 + len(tone_hits) * 2 + int(concept.get("commercial_rank", 0))
    reasons: list[str] = []
    if signal_hits:
        reasons.append("입력 신호: " + ", ".join(signal_hits))
    if tone_hits:
        reasons.append("톤 적합: " + ", ".join(tone_hits))

    dependency = concept.get("photo_dependency")
    if photo == "available":
        if dependency == "preferred":
            score += 3
            reasons.append("사용 가능한 실사 자산 활용")
        elif dependency == "optional":
            score += 2
    elif photo == "preferred":
        if dependency == "preferred":
            score += 2
    elif photo == "none":
        if dependency == "none":
            score += 3
            reasons.append("사진 없이 제작 가능")
        elif dependency == "preferred":
            score -= 2
    if not reasons:
        reasons.append("상업 완성도와 범용성")
    return score, reasons


def resolve(concepts: list[dict[str, object]], signals: set[str], tones: set[str], photo: str, count: int, recent: list[dict] | None = None) -> list[dict[str, object]]:
    ranked = []
    for concept in concepts:
        score, reasons = score_concept(concept, signals, tones, photo)
        for index, old in enumerate(recent or []):
            if old.get('concept_id') == concept.get('id'):
                score -= 10 if index == 0 else 3
                reasons.append('최근 제작 콘셉트 반복 감점: ' + str(old.get('source_key','previous')))
            elif old.get('medium_family') == concept.get('medium_family'):
                score -= 5 if index == 0 else 1
                reasons.append('최근 매체군 반복 감점')
        ranked.append((score, int(concept.get("commercial_rank", 0)), str(concept.get("id", "")), concept, reasons))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))

    selected: list[dict[str, object]] = []
    families: set[str] = set()
    for score, _rank, _id, concept, reasons in ranked:
        family = str(concept.get("medium_family", ""))
        if not family or family in families:
            continue
        selected.append({
            "rank": len(selected) + 1,
            "id": concept.get("id"),
            "name_ko": concept.get("name_ko"),
            "medium_family": family,
            "score": score,
            "selection_basis": reasons,
            "scene_recipe": concept.get("scene_recipe"),
            "character_treatment": concept.get("character_treatment"),
        })
        families.add(family)
        if len(selected) == count:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signal", action="append", default=[], help="benefit, deadline, event, technology, place, process, achievement 등")
    parser.add_argument("--tone", action="append", default=[], help="professional, premium, friendly, clear 등")
    parser.add_argument("--photo", choices=sorted(PHOTO_VALUES), default="preferred")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--list", action="store_true", help="콘셉트 카탈로그만 출력")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--history", type=Path, default=ROOT/'state'/'content-history.jsonl', help="기본은 공유 제작 이력; 별도 경로는 격리 시험용")
    parser.add_argument("--lookback", type=int, default=6)
    parser.add_argument("--source-key", help="현재 공고는 이전 디자인 비교에서 제외")
    args = parser.parse_args()
    if not 1 <= args.count <= 5:
        print("ERROR: --count는 1~5여야 합니다", file=sys.stderr)
        return 2
    if not 1 <= args.lookback <= 30:
        print("ERROR: --lookback은 1~30이어야 합니다", file=sys.stderr)
        return 2
    try:
        concepts = load_catalog()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: 콘셉트 카탈로그를 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1

    if args.list:
        result: object = [{"id": item.get("id"), "name_ko": item.get("name_ko"), "medium_family": item.get("medium_family")} for item in concepts]
    else:
        try:
            recent, warnings = recent_designs(args.history,args.lookback,args.source_key)
        except Exception as exc:
            print(f"ERROR: 이전 제작 이력을 읽을 수 없습니다. 기록을 보존하고 확인하세요: {exc}",file=sys.stderr)
            return 1
        proposals = resolve(concepts, set(args.signal), set(args.tone), args.photo, args.count,recent)
        if len(proposals) < args.count:
            print("ERROR: 서로 다른 매체군의 콘셉트를 요청 수만큼 찾을 수 없습니다", file=sys.stderr)
            return 1
        result = {
            "input": {"signals": args.signal, "tones": args.tone, "photo": args.photo},
            "selection_mode": "propose-diverse-concepts",
            "default_selected_id": proposals[0]["id"],
            "proposals": proposals,
            "presentation_proposals": presentation_choices(set(args.signal),recent),
            "recent_designs": recent,
            "history_warnings": warnings,
            "variation_policy": "Compare actual previous previews; change narrative and layout, not only color. Explicit user design choices override automatic recency penalties with a recorded reason.",
        }
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
