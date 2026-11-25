#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


NEWS_PATTERN = re.compile(
    r"개최|성료|모집|개소|오픈|출범|선정|인증|확대|구축|지원|협약|"
    r"엑스포|경진대회|수료|투자|개발|운영|달성|돌파|개막|공개|"
    r"가동|선발|착공|준공|체결|교육|상담|전시|체험|시험|마감|"
    r"배포|발간|도입|개선|해소|단축|줄인다|낮춘다|돕는다|논의"
)
CLICHE_PATTERN = re.compile(
    r"새로운\s+도약|힘찬\s+출발|미래를\s+향한|새\s+지평|"
    r"혁신\s+생태계|한\s+단계\s+도약|미래를\s+연다|경쟁력\s+강화"
)
SUPERLATIVE_PATTERN = re.compile(r"최초|최고|유일|1위")
TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
ENDING_PARTICLES = re.compile(
    r"(?:했다|한다|된다|됐다|나선다|밝혔다|예정이다|계획이다)$"
)

DUPLICATE_MESSAGE = "제목 후보가 같거나 어순만 바꾼 수준으로 중복됩니다."
TYPE_DIVERSITY_MESSAGE = "제안안은 최소 3개의 서로 다른 관점군으로 구성하세요."
OPENING_DIVERSITY_MESSAGE = (
    "같은 기관명·주어로 시작하는 제목이 2개를 넘습니다."
)
ENDING_DIVERSITY_MESSAGE = (
    "같은 끝맺음을 사용하는 제목이 2개를 넘습니다."
)
COMPLEMENT_MESSAGE = (
    "제목과 부제목의 핵심어가 과도하게 겹칩니다. "
    "부제목에 일정·대상·규모·근거 등 새로운 정보를 넣으세요."
)
RECOMMENDATION_MESSAGE = "추천안은 정확히 1개여야 합니다."


def add_issue(
    issues: list[tuple[str, str]], level: str, message: str
) -> None:
    issues.append((level, message))


def normalize_text(value: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]", "", value).lower()


def title_tokens(value: str) -> set[str]:
    stopwords = {
        "포항tp",
        "포항테크노파크",
        "위한",
        "통한",
        "관련",
        "이번",
        "본격",
    }
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(value)
        if token.lower() not in stopwords
    }


def semantic_signature(value: str) -> frozenset[str]:
    particles = (
        "에서",
        "으로",
        "에게",
        "부터",
        "까지",
        "하고",
        "하며",
        "한다",
        "했다",
        "가",
        "이",
        "은",
        "는",
        "을",
        "를",
    )
    signature = set()
    for token in title_tokens(value):
        stem = token
        for particle in particles:
            if stem.endswith(particle) and len(stem) > len(particle) + 1:
                stem = stem[: -len(particle)]
                break
        if len(stem) >= 2:
            signature.add(stem)
    return frozenset(signature)


def opening_key(value: str) -> str:
    title = value.strip()
    comma_match = re.match(r"^([^,，]{2,20})[,，]", title)
    if comma_match:
        return normalize_text(comma_match.group(1))
    tokens = TOKEN_PATTERN.findall(title)
    if not tokens:
        return ""
    return normalize_text(" ".join(tokens[:2]))


def ending_key(value: str) -> str:
    title = re.sub(r"[.!?…·\-–—]+$", "", value.strip())
    tokens = TOKEN_PATTERN.findall(title)
    if not tokens:
        return ""
    ending = ENDING_PARTICLES.sub("", tokens[-1])
    return normalize_text(ending or tokens[-1])


def normalize_subtitles(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
    return []


def option_label(option: dict[str, Any], index: int) -> str:
    return str(option.get("id") or index + 1)


def check_options(
    options: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    count = len(options)
    if count < 3 or count > 5:
        add_issue(
            issues,
            "ERROR",
            f"사용자 제안안은 3~5개여야 합니다. 현재 {count}개입니다.",
        )
    if not options:
        return issues

    types = [
        str(option.get("type", "")).strip()
        for option in options
        if str(option.get("type", "")).strip()
    ]
    if len(set(types)) < 3:
        add_issue(issues, "ERROR", TYPE_DIVERSITY_MESSAGE)

    recommendation_count = sum(
        bool(option.get("recommended")) for option in options
    )
    if recommendation_count != 1:
        add_issue(issues, "ERROR", RECOMMENDATION_MESSAGE)

    titles: list[str] = []
    openings: list[str] = []
    endings: list[str] = []
    for index, option in enumerate(options):
        label = option_label(option, index)
        title = str(option.get("title", "")).strip()
        subtitles = normalize_subtitles(option.get("subtitle"))
        if not title:
            add_issue(issues, "ERROR", f"{label}안 제목이 비어 있습니다.")
            continue
        titles.append(title)
        openings.append(opening_key(title))
        endings.append(ending_key(title))

        if not subtitles or len(subtitles) > 2:
            add_issue(
                issues,
                "ERROR",
                f"{label}안 부제목은 1~2줄이어야 합니다.",
            )
        headline_text = " ".join([title, *subtitles])
        if not NEWS_PATTERN.search(headline_text):
            add_issue(
                issues,
                "WARN",
                f"{label}안에서 구체적인 발표·행동·결과가 드러나지 않습니다.",
            )
        if CLICHE_PATTERN.search(title):
            add_issue(
                issues,
                "WARN",
                f"{label}안 제목에 구체적 사실 없이 쓰기 쉬운 상투어가 있습니다.",
            )
        if SUPERLATIVE_PATTERN.search(title):
            add_issue(
                issues,
                "WARN",
                f"{label}안의 최상급 표현은 객관적 근거를 확인하세요.",
            )
        if len(title) > 50:
            add_issue(
                issues,
                "WARN",
                f"{label}안 제목이 {len(title)}자입니다. 핵심어를 남겨 압축하세요.",
            )
        if len(re.findall(r"[!?…]", title)) > 1:
            add_issue(
                issues,
                "WARN",
                f"{label}안 제목의 물음표·느낌표·말줄임표 사용을 줄이세요.",
            )

        subtitle_text = " ".join(subtitles)
        title_words = title_tokens(title)
        subtitle_words = title_tokens(subtitle_text)
        if title_words and subtitle_words:
            overlap = len(title_words & subtitle_words) / min(
                len(title_words), len(subtitle_words)
            )
            if overlap >= 0.7:
                add_issue(
                    issues,
                    "WARN",
                    f"{label}안: {COMPLEMENT_MESSAGE}",
                )

    normalized_titles = [normalize_text(title) for title in titles]
    if len(set(normalized_titles)) != len(normalized_titles):
        add_issue(issues, "ERROR", DUPLICATE_MESSAGE)

    signatures = [semantic_signature(title) for title in titles]
    for left in range(len(signatures)):
        for right in range(left + 1, len(signatures)):
            a = signatures[left]
            b = signatures[right]
            if not a or not b:
                continue
            similarity = len(a & b) / min(len(a), len(b))
            if similarity >= 0.8:
                add_issue(
                    issues,
                    "WARN",
                    f"{left + 1}안과 {right + 1}안: {DUPLICATE_MESSAGE}",
                )

    opening_counts = Counter(key for key in openings if key)
    if any(value > 2 for value in opening_counts.values()):
        add_issue(issues, "ERROR", OPENING_DIVERSITY_MESSAGE)

    ending_counts = Counter(key for key in endings if key)
    if any(value > 2 for value in ending_counts.values()):
        add_issue(issues, "ERROR", ENDING_DIVERSITY_MESSAGE)

    if all(
        re.match(r"^(?:포항TP|포항테크노파크)", title)
        for title in titles
    ):
        add_issue(
            issues,
            "WARN",
            "모든 제목이 기관명으로 시작합니다. 사실이 허용하면 수치·대상·현장 관점도 포함하세요.",
        )

    return issues


def load_options(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("options")
    if not isinstance(data, list) or not all(
        isinstance(item, dict) for item in data
    ):
        raise ValueError(
            "JSON은 제목 안 객체의 배열 또는 `options` 배열을 가진 객체여야 합니다."
        )
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="포항TP 제목·부제목 제안안의 구조적 다양성과 중복을 점검합니다."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="제목 제안안 3~5개가 담긴 UTF-8 JSON 파일",
    )
    args = parser.parse_args()

    try:
        options = load_options(args.file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    issues = check_options(options)
    if not issues:
        print("[OK] 제목·부제목 제안안의 기본 다양성 점검을 통과했습니다.")
        return 0

    for level, message in issues:
        print(f"[{level}] {message}")
    errors = sum(level == "ERROR" for level, _ in issues)
    warnings = sum(level == "WARN" for level, _ in issues)
    print(f"요약: 오류 {errors}개, 경고 {warnings}개")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
