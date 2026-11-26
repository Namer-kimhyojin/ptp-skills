#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


METADATA_LABELS = ("배포일시", "보도일시", "담당부서", "붙임자료", "담 당 자")
PLACEHOLDER_PATTERNS = (
    r"\[확인 필요(?::[^\]]*)?\]",
    r"\b(?:TBD|TODO)\b",
    r"○○",
    r"OOO",
    r"00기업",
)
ATTRIBUTION_PATTERN = re.compile(
    r"(?:고|라고)\s*(?:말했다|밝혔다|전했다|강조했다|설명했다)"
)
PHONE_PATTERN = re.compile(r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)")
EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
HEADLINE_NEWS_PATTERN = re.compile(
    r"개최|성료|모집|개소|오픈|출범|선정|인증|확대|구축|지원|협약|"
    r"엑스포|경진대회|수료|투자|개발|운영|달성|돌파|개막|공개|"
    r"가동|선발|착공|준공|체결|교육|상담|전시|체험|시험"
)
TITLE_CLICHE_PATTERN = re.compile(
    r"새로운\s+도약|힘찬\s+출발|미래를\s+향한|새\s+지평|"
    r"혁신\s+생태계|한\s+단계\s+도약|미래를\s+연다"
)
SUBTITLE_DETAIL_PATTERN = re.compile(
    r"개최|운영|지원|참여|모집|전시|체험|상담|교육|세션|기업|"
    r"장소|센터|체육관|공원|본부|성과|대상|규모|프로그램"
)
ABSENT_SPONSOR_PATTERN = re.compile(
    r"후원\s*(?:없이|없음|기관(?:은|이)?\s*없|을\s*받지)"
    r"|후원사(?:는|가)?\s*없"
)
REPEATED_CONNECTOR_MESSAGE = (
    "같은 연결어가 반복됩니다. 핵심 동작을 나누고 문장 관계에 맞는 "
    "연결어를 사용하세요."
)
OVERLOADED_SENTENCE_MESSAGE = (
    "문장이 길고 쉼표가 많습니다. 핵심 메시지와 부연 설명을 "
    "두 문장으로 나누세요."
)
REPEATED_OPENING_MESSAGE = (
    "연속 문단이 같은 표현으로 시작합니다. 주체 반복을 줄이고 "
    "앞 문단과의 관계가 드러나게 연결하세요."
)
HEADLINE_NEWS_MESSAGE = (
    "제목과 부제목 조합에서 무엇을 발표·추진·달성하는지 "
    "구체적인 보도내용을 더 분명히 하세요."
)
CLICHE_TITLE_MESSAGE = (
    "제목에 어느 사업에도 적용될 수 있는 상투적 표현이 있습니다. "
    "확인된 행동·수치·대상·변화로 구체화하세요."
)
MIN_BODY_PARAGRAPHS_MESSAGE = (
    "기본 보도자료는 `❍` 본문 문단을 6개 이상으로 구성하세요."
)
TRAILING_SUBTITLE_DASH_MESSAGE = (
    "부제목은 앞에만 `- `를 붙이고 문장 끝의 `-` 표시는 삭제하세요."
)
PARAGRAPH_OPENING_PATTERNS = (
    (re.compile(r"^이번\s+(?:행사|사업|세미나|교육|과정)(?:은|는)"), "이번 행사"),
    (re.compile(r"^포항TP(?:가|는)"), "포항TP"),
    (
        re.compile(r"^포항테크노파크\([^)]*\)(?:가|는)"),
        "포항테크노파크",
    ),
    (re.compile(r"^행사에서는"), "행사에서는"),
)


def add_issue(
    issues: list[tuple[str, str]], level: str, message: str
) -> None:
    issues.append((level, message))


def contact_value(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        match = re.search(r"담\s*당\s*자", line)
        if not match:
            continue
        value = line[match.end():].strip(" :")
        if value:
            return value
        if index + 1 < len(lines):
            return lines[index + 1]
    return ""


def headline_parts(lines: list[str]) -> tuple[str, list[str]]:
    subtitle_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^-\s*.+", line)
    ]
    if not subtitle_indexes:
        return "", []
    first = subtitle_indexes[0]
    title = lines[first - 1] if first > 0 else ""
    subtitles = []
    for index in range(first, len(lines)):
        match = re.match(r"^-\s*(.+?)(?:\s+-)?$", lines[index])
        if not match:
            break
        subtitles.append(match.group(1).strip())
    return title, subtitles


def paragraph_opening(line: str) -> str:
    body = re.sub(r"^❍\s*", "", line).strip()
    for pattern, opening in PARAGRAPH_OPENING_PATTERNS:
        if pattern.search(body):
            return opening
    return ""


def check(
    text: str,
    final: bool,
    director_name: str | None = None,
    require_organizers: bool = False,
) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if "보 도 자 료" not in text:
        add_issue(issues, "ERROR" if final else "WARN", "`보 도 자 료` 표제가 없습니다.")

    for label in METADATA_LABELS:
        if label not in text:
            add_issue(
                issues,
                "ERROR" if final else "WARN",
                f"메타데이터 항목 `{label}`이 없습니다.",
            )

    contact = contact_value(lines)
    contact_level = "ERROR" if final else "WARN"
    if "담 당 자" in text:
        if not PHONE_PATTERN.search(contact):
            add_issue(issues, contact_level, "담당자 전화번호가 없거나 형식이 올바르지 않습니다.")
        if not EMAIL_PATTERN.search(contact):
            add_issue(issues, contact_level, "담당자 이메일이 없거나 형식이 올바르지 않습니다.")
        contact_words = re.findall(r"[가-힣]{2,}", contact)
        if len(contact_words) < 2:
            add_issue(
                issues,
                contact_level,
                "담당자 성명과 소속 부서·팀을 모두 포함했는지 확인하세요.",
            )

    bullet_lines = [line for line in lines if line.startswith("❍")]
    for line in bullet_lines:
        if ABSENT_SPONSOR_PATTERN.search(line):
            add_issue(
                issues,
                "ERROR",
                "후원기관이 없다는 사실은 본문에 쓰지 말고 후원 관련 문구를 생략하세요.",
            )
        if line.count("하며") >= 2 or line.count("하고") >= 3:
            add_issue(issues, "WARN", REPEATED_CONNECTOR_MESSAGE)
        sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"^❍\s*", "", line))
        if any(
            len(sentence) >= 180 and sentence.count(",") >= 3
            for sentence in sentences
        ):
            add_issue(issues, "WARN", OVERLOADED_SENTENCE_MESSAGE)
    for previous, current in zip(bullet_lines, bullet_lines[1:]):
        previous_opening = paragraph_opening(previous)
        current_opening = paragraph_opening(current)
        if previous_opening and previous_opening == current_opening:
            add_issue(issues, "WARN", REPEATED_OPENING_MESSAGE)
    if len(bullet_lines) < 6:
        add_issue(
            issues,
            "ERROR" if final else "WARN",
            f"`❍` 본문 문단이 {len(bullet_lines)}개입니다. "
            + MIN_BODY_PARAGRAPHS_MESSAGE,
        )

    title, subtitles = headline_parts(lines)
    if not subtitles:
        add_issue(issues, "WARN", "`- 부제` 형식의 부제가 없습니다.")
    else:
        if any(re.match(r"^-\s*.+?\s+-$", line) for line in lines):
            add_issue(issues, "WARN", TRAILING_SUBTITLE_DASH_MESSAGE)
        if len(subtitles) > 2:
            add_issue(
                issues,
                "WARN",
                f"부제목이 {len(subtitles)}줄입니다. 핵심 세부정보 1~2줄로 압축하세요.",
            )
        subtitle_text = " ".join(subtitles)
        if not re.search(r"\d", subtitle_text):
            add_issue(
                issues,
                "WARN",
                "부제목에 일정·규모·성과를 보여주는 숫자 정보가 없습니다.",
            )
        if not SUBTITLE_DETAIL_PATTERN.search(subtitle_text):
            add_issue(
                issues,
                "WARN",
                "부제목에 장소·대상·프로그램 등 구체적인 세부정보를 보강하세요.",
            )

    if title:
        if len(title) > 50:
            add_issue(
                issues,
                "WARN",
                f"제목이 {len(title)}자입니다. 가장 강한 뉴스 요소만 남겨 압축하세요.",
            )
        headline_text = " ".join([title, *subtitles])
        if not HEADLINE_NEWS_PATTERN.search(headline_text):
            add_issue(
                issues,
                "WARN",
                HEADLINE_NEWS_MESSAGE,
            )
        if TITLE_CLICHE_PATTERN.search(title):
            add_issue(
                issues,
                "WARN",
                CLICHE_TITLE_MESSAGE,
            )
        if subtitles:
            title_words = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", title))
            subtitle_words = set(
                re.findall(r"[가-힣A-Za-z0-9]{2,}", " ".join(subtitles))
            )
            if title_words and subtitle_words:
                overlap = len(title_words & subtitle_words) / min(
                    len(title_words), len(subtitle_words)
                )
                if overlap >= 0.7:
                    add_issue(
                        issues,
                        "WARN",
                        "제목과 부제목의 표현이 많이 겹칩니다. 부제목에 새로운 세부 사실을 넣으세요.",
                    )

    if "포항TP" not in text and "포항테크노파크" not in text:
        add_issue(issues, "WARN", "포항TP 또는 포항테크노파크 기관 표기가 없습니다.")

    if bullet_lines:
        lead = bullet_lines[0]
        if re.search(
            r"^❍\s*포항테크노파크\([^)]*\)(?:은|는)",
            lead,
        ):
            add_issue(
                issues,
                "ERROR" if final else "WARN",
                "첫 리드의 행위 주체는 `포항테크노파크(… )가`로 연결하세요. "
                "`은/는`은 대조·화제 전환이 필요한 경우에만 사용합니다.",
            )
        lead_verbs = (
            "밝혔다",
            "개최했다",
            "진행했다",
            "마련했다",
            "오픈했다",
            "개소했다",
            "모집한다",
            "인정받았다",
            "완료했다",
            "마무리됐다",
        )
        if not any(verb in lead for verb in lead_verbs):
            add_issue(
                issues,
                "WARN",
                "첫 `❍` 문단에서 핵심 발표·행동을 분명한 동사로 끝내는지 확인하세요.",
            )

    quote_level = "ERROR" if final else "WARN"
    if "“" not in text or "”" not in text:
        add_issue(issues, quote_level, "원장 직접 인용문이 없습니다.")
    elif not ATTRIBUTION_PATTERN.search(text):
        add_issue(issues, quote_level, "인용문 뒤의 발언자 귀속 표현을 확인하세요.")

    if director_name:
        confirmed_director = " ".join(director_name.split())
        if confirmed_director not in text:
            add_issue(
                issues,
                "ERROR" if final else "WARN",
                f"확인된 원장명 `{confirmed_director}`이 본문에 없습니다.",
            )

    if require_organizers:
        role_level = "ERROR" if final else "WARN"
        for role in ("주최", "주관", "후원"):
            if role not in text:
                add_issue(
                    issues,
                    role_level,
                    f"행사·사업의 `{role}` 기관 또는 `{role} 없음` 확인 내용이 없습니다.",
                )

    placeholders = []
    for pattern in PLACEHOLDER_PATTERNS:
        placeholders.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    if placeholders:
        level = "ERROR" if final else "WARN"
        add_issue(
            issues,
            level,
            f"확인용 자리표시자가 {len(placeholders)}개 남아 있습니다.",
        )

    fixed_redundancies = (
        "지역 산업의 지역산업의",
        "제공도 함께 제공",
        "계획할 계획",
        "수행하고 있으며 수행",
    )
    for phrase in fixed_redundancies:
        if phrase in text:
            add_issue(issues, "ERROR" if final else "WARN", f"중복 표현 `{phrase}`을 수정하세요.")

    repeated_word = re.search(r"([가-힣A-Za-z]{2,})\s+\1(?:\s|[,.])", text)
    if repeated_word:
        add_issue(
            issues,
            "WARN",
            f"연속 중복 단어 `{repeated_word.group(1)}`을 확인하세요.",
        )

    if re.search(r"다\.”(?:라며|라고)|\.”(?:라며|라고)", text):
        add_issue(
            issues,
            "WARN",
            "인용문 마침표 뒤에 `라며/라고`가 붙었습니다. 마침표를 제거하세요.",
        )

    if "부터~" in text:
        add_issue(
            issues,
            "WARN",
            "`부터~`는 중복 범위 표기입니다. `부터` 또는 물결표 하나만 사용하세요.",
        )

    if final and "배포 후 즉시" not in text and "보도일시" in text:
        if not re.search(r"보도일시.{0,40}\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.", text, re.DOTALL):
            add_issue(
                issues,
                "WARN",
                "보도일시가 `배포 후 즉시`도 아니고 명확한 날짜 형식도 아닙니다.",
            )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(
        description="포항TP 보도자료의 구조와 흔한 문체 오류를 점검합니다."
    )
    parser.add_argument("file", type=Path, help="UTF-8 텍스트 또는 Markdown 파일")
    parser.add_argument(
        "--final",
        action="store_true",
        help="배포용 최종본으로 검사하여 자리표시자와 누락 메타데이터를 오류로 처리",
    )
    parser.add_argument(
        "--director-name",
        help="확인된 현재 원장명. 지정하면 본문 포함 여부를 검사합니다.",
    )
    parser.add_argument(
        "--require-organizers",
        action="store_true",
        help="행사·사업의 주최·주관·후원 표기 여부를 검사합니다.",
    )
    args = parser.parse_args()

    text = args.file.read_text(encoding="utf-8")
    issues = check(
        text,
        args.final,
        args.director_name,
        args.require_organizers,
    )
    if not issues:
        print("[OK] 구조 및 기본 문체 점검을 통과했습니다.")
        return 0

    for level, message in issues:
        print(f"[{level}] {message}")

    errors = sum(level == "ERROR" for level, _ in issues)
    warnings = sum(level == "WARN" for level, _ in issues)
    print(f"요약: 오류 {errors}개, 경고 {warnings}개")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
