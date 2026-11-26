#!/usr/bin/env python3
"""Validate the reusable PTP webtoon-mode overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


CHARACTERS = {"CHR-BLUE", "CHR-ORANGE"}
MODES = {"social-toon", "four-panel", "educational-comic", "vertical-webtoon", "page-comic"}
DIRECTIONS = {"left-to-right", "right-to-left", "vertical-scroll"}
FRAMES = {"uniform", "controlled", "expressive"}


def text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"웹툰 모드 파일을 읽을 수 없습니다: {exc}"]
    allowed_characters = CHARACTERS
    if 'character_set' in data:
        from character_sets import select_set, snapshot
        try:
            entry = select_set(data['character_set']['id'])
            if data['character_set'] != snapshot(entry):
                raise ValueError('선택 스냅샷과 현재 세트가 다릅니다')
            allowed_characters = {m['id'] for m in entry['members']}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'캐릭터 세트: {exc}')
            allowed_characters = set()
    if data.get('cast_revision_required') is True:
        errors.append('캐릭터 변경 후 컷·화자 재검수가 필요합니다')
    if data.get("schema_version") != "1.0":
        errors.append("schema_version은 1.0이어야 합니다")
    if data.get("enabled") is not True:
        errors.append("enabled는 true여야 합니다")
    if data.get("content_mode") not in MODES:
        errors.append("content_mode이 올바르지 않습니다")
    if data.get("reading_direction") not in DIRECTIONS:
        errors.append("reading_direction이 올바르지 않습니다")
    if data.get("frame_diversity") not in FRAMES:
        errors.append("frame_diversity가 올바르지 않습니다")
    for key in ("art_and_lettering_separate", "character_continuity_required"):
        if data.get(key) is not True:
            errors.append(f"{key}는 true여야 합니다")
    count = data.get("panel_count")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        errors.append("panel_count는 양의 정수여야 합니다")
        count = 0
    beats = data.get("story_beats")
    if not isinstance(beats, list) or len(beats) < 3 or any(not text(item) for item in beats):
        errors.append("story_beats는 3개 이상의 문자열 배열이어야 합니다")
    panels = data.get("panel_contract")
    if not isinstance(panels, list) or len(panels) != count:
        errors.append("panel_contract 수는 panel_count와 같아야 합니다")
        panels = []
    seen: set[int] = set()
    for index, panel in enumerate(panels):
        label = f"panel_contract[{index}]"
        if not isinstance(panel, dict):
            errors.append(f"{label}는 객체여야 합니다")
            continue
        number = panel.get("panel")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0 or number in seen:
            errors.append(f"{label}.panel은 중복 없는 양의 정수여야 합니다")
        else:
            seen.add(number)
        for key in ("function", "visual_action", "core_information", "lettering_safe_area", "state_before", "state_after"):
            if not text(panel.get(key)):
                errors.append(f"{label}.{key}가 필요합니다")
        refs = panel.get("source_refs")
        if not isinstance(refs, list) or not refs or any(not text(item) for item in refs):
            errors.append(f"{label}.source_refs가 필요합니다")
        characters = panel.get("characters")
        if not isinstance(characters, list) or any(item not in allowed_characters for item in characters):
            errors.append(f"{label}.characters가 올바르지 않습니다")
    if panels and seen != set(range(1, count + 1)):
        errors.append("panel 번호는 1부터 panel_count까지 연속되어야 합니다")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path.resolve())
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"FAIL: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK: webtoon mode is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
