#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

from check_headline_options import (
    ENDING_DIVERSITY_MESSAGE,
    OPENING_DIVERSITY_MESSAGE,
    RECOMMENDATION_MESSAGE,
    TYPE_DIVERSITY_MESSAGE,
    check_options,
)
from check_press_release import (
    CLICHE_TITLE_MESSAGE,
    HEADLINE_NEWS_MESSAGE,
    MIN_BODY_PARAGRAPHS_MESSAGE,
    OVERLOADED_SENTENCE_MESSAGE,
    REPEATED_CONNECTOR_MESSAGE,
    REPEATED_OPENING_MESSAGE,
    TRAILING_SUBTITLE_DASH_MESSAGE,
    check,
)
from fill_press_release_hwpx import validate_package


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
NS = {"hp": HP, "hh": HH}


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    filler = skill_root / "scripts" / "fill_press_release_hwpx.py"
    headline_checker = (
        skill_root / "scripts" / "check_headline_options.py"
    )
    headline_framework = (
        skill_root / "references" / "headline-subtitle-framework.md"
    )
    template = (
        skill_root
        / "assets"
        / "pohang-tp-press-release-template-v2.hwpx"
    )
    for required in (
        skill_root / "SKILL.md",
        filler,
        headline_checker,
        headline_framework,
        template,
    ):
        if not required.is_file():
            raise FileNotFoundError(f"필수 파일이 없습니다: {required}")

    skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    output_template_text = (
        skill_root / "references" / "output-template.md"
    ).read_text(encoding="utf-8")
    headline_framework_text = headline_framework.read_text(encoding="utf-8")
    required_selection_rules = (
        "## 제목·부제목 선택 단계",
        "사용자가 선택하기 전에는 보도자료 본문이나 HWPX 파일을 작성하지 말고",
        "제목은 2안, 부제목은 1안처럼 조합",
    )
    required_hwpx_followup_rules = (
        "## HWPX 후속 제안",
        "## HWPX 후속 확인",
        "보도자료 작성이 완료되었습니다. 배포양식에 맞춘 HWPX 파일도 작성할까요?",
        "사용자가 처음부터 HWPX",
        "확정된 제목·부제목·본문·원장명·담당자 정보·기관 역할을 다시 묻지",
    )
    required_body_length_rules = (
        "완성형 본문은 `❍` 문단 6개 이상",
        "HWPX 본문도 6~8개의 독립된 `❍` 문단",
        "`body`는 선행 `❍` 없이 6~8개 문단",
    )
    required_headline_framework_rules = (
        "서로 다른 관점군 5개 이상",
        "제목·부제목 조합을 내부적으로 7개 이상",
        "14점 만점에 11점 이상",
        "scripts/check_headline_options.py",
        "국립국어원",
        "인사혁신처",
        "문장 끝에는 ` -`를 붙이지",
    )
    combined_rules = (
        f"{skill_text}\n{output_template_text}\n{headline_framework_text}"
    )
    for rule in required_selection_rules:
        if rule not in combined_rules:
            raise ValueError(f"제목·부제목 선택 규칙이 없습니다: {rule}")
    for rule in required_hwpx_followup_rules:
        if rule not in combined_rules:
            raise ValueError(f"HWPX 후속 확인 규칙이 없습니다: {rule}")
    for rule in required_body_length_rules:
        if rule not in combined_rules:
            raise ValueError(f"본문 6문단 규칙이 없습니다: {rule}")
    for rule in required_headline_framework_rules:
        if rule not in combined_rules:
            raise ValueError(f"제목 고도화 규칙이 없습니다: {rule}")

    payload = {
        "release_date": "[확인 필요: 배포일시]",
        "press_time": "배포 후 즉시",
        "department": "테스트본부",
        "attachments": "[확인 필요: 붙임자료]",
        "director_name": "테스트원장",
        "roles": {
            "host": "테스트기관",
            "organizer": "테스트기관",
            "sponsor": "없음",
            "cooperation": "없음",
            "operator": "없음",
        },
        "contact": {
            "team": "테스트본부 테스트팀",
            "name": "테스트담당자",
            "title": "",
            "phone": "054-000-0000",
            "email": "test@example.org",
        },
        "title": "포항TP, 배포 환경 자체 점검",
        "subtitle": [
            "HWPX 생성과 문단 구조 확인",
            "확인 필요 문구의 빨간색 표시 확인",
        ],
        "body": [
            "포항테크노파크(원장 테스트원장, 이하 포항TP)가 자체 점검 문서를 생성했다고 밝혔다.",
            "이번 문서는 설치 환경과 HWPX 생성 기능을 확인하기 위해 마련됐다.",
            "각 본문 항목은 독립된 문단과 동일한 내어쓰기를 사용한다.",
            "생성된 문서는 본문 분량과 구조 검수에도 사용한다.",
            "테스트원장 포항TP 원장은 “설치 환경을 확인하기 위한 문서”라고 말했다.",
            "한편, 이 문서는 설치 확인 후 자동으로 삭제된다.",
        ],
    }

    with tempfile.TemporaryDirectory(prefix="pohang-tp-skill-test-") as temp:
        temp_dir = Path(temp)
        payload_path = temp_dir / "input.json"
        output_path = temp_dir / "output.hwpx"
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        subprocess.run(
            [
                sys.executable,
                str(filler),
                "--template",
                str(template),
                "--input",
                str(payload_path),
                "--output",
                str(output_path),
            ],
            check=True,
        )
        validate_package(output_path)

        with zipfile.ZipFile(output_path) as archive:
            section = etree.fromstring(archive.read("Contents/section0.xml"))
            header = etree.fromstring(archive.read("Contents/header.xml"))

        body = []
        for paragraph in section.xpath("./hp:p", namespaces=NS):
            text = "".join(
                paragraph.xpath(".//hp:t/text()", namespaces=NS)
            ).strip()
            if text.startswith("❍"):
                body.append(paragraph)
        if len(body) != 6:
            raise ValueError(f"본문 문단 수가 6개가 아닙니다: {len(body)}")
        if any(paragraph.get("paraPrIDRef") != "24" for paragraph in body):
            raise ValueError("본문 내어쓰기 문단 서식이 일관되지 않습니다.")

        paragraph_texts = [
            "".join(paragraph.xpath(".//hp:t/text()", namespaces=NS)).strip()
            for paragraph in section.xpath(".//hp:p", namespaces=NS)
        ]
        generated_subtitles = [
            text for text in paragraph_texts if text.startswith("- ")
        ]
        if len(generated_subtitles) != 2:
            raise ValueError(
                f"생성된 부제목이 2개가 아닙니다: {generated_subtitles}"
            )
        if any(text.endswith("-") for text in generated_subtitles):
            raise ValueError("HWPX 부제목 끝에 불필요한 `-`가 남았습니다.")

        confirm_nodes = section.xpath(
            ".//hp:t[contains(text(), '[확인 필요:')]",
            namespaces=NS,
        )
        if len(confirm_nodes) != 2:
            raise ValueError(
                f"확인 필요 문구가 2개가 아닙니다: {len(confirm_nodes)}"
            )
        for node in confirm_nodes:
            style_id = node.getparent().get("charPrIDRef")
            styles = header.xpath(
                ".//hh:charPr[@id=$style_id]",
                namespaces=NS,
                style_id=style_id,
            )
            if len(styles) != 1 or styles[0].get("textColor") != "#FF0000":
                raise ValueError("확인 필요 문구의 빨간색 서식이 없습니다.")

        short_payload = dict(payload)
        short_payload["body"] = payload["body"][:5]
        short_payload_path = temp_dir / "short-input.json"
        short_output_path = temp_dir / "short-output.hwpx"
        short_payload_path.write_text(
            json.dumps(short_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        short_result = subprocess.run(
            [
                sys.executable,
                str(filler),
                "--template",
                str(template),
                "--input",
                str(short_payload_path),
                "--output",
                str(short_output_path),
            ],
            check=False,
            capture_output=True,
        )
        if short_result.returncode == 0 or b"6~8" not in short_result.stderr:
            raise ValueError("HWPX 생성기가 5개 본문 문단을 거부하지 않았습니다.")

    absent_sponsor_message = (
        "후원기관이 없다는 사실은 본문에 쓰지 말고 후원 관련 문구를 생략하세요."
    )
    bad_sponsor_issues = check(
        "❍ 이번 세미나는 포항시가 주최하고 포항TP가 주관하며, "
        "후원 없이 추진됐다.",
        final=True,
    )
    if not any(
        level == "ERROR" and message == absent_sponsor_message
        for level, message in bad_sponsor_issues
    ):
        raise ValueError("본문의 `후원 없이` 표현을 검출하지 못했습니다.")

    clean_sponsor_issues = check(
        "❍ 이번 세미나는 포항시가 주최하고 포항TP가 주관했다.",
        final=True,
    )
    if any(message == absent_sponsor_message for _, message in clean_sponsor_issues):
        raise ValueError("후원 문구를 생략한 정상 문장을 잘못 검출했습니다.")

    repeated_connector_issues = check(
        "❍ 행사에서는 기술 세미나를 운영하며 기업 상담을 진행하며 "
        "시험분석 장비를 소개한다.",
        final=False,
    )
    if not any(
        message == REPEATED_CONNECTOR_MESSAGE
        for _, message in repeated_connector_issues
    ):
        raise ValueError("반복 연결어를 검출하지 못했습니다.")

    clean_flow_issues = check(
        "❍ 행사에서는 최신 기술 동향을 공유하는 세미나와 기업별 상담을 "
        "운영한다. 시험분석 장비와 지원 절차도 함께 소개한다.",
        final=False,
    )
    if any(
        message == REPEATED_CONNECTOR_MESSAGE
        for _, message in clean_flow_issues
    ):
        raise ValueError("자연스럽게 나눈 문장을 반복 연결어로 잘못 검출했습니다.")

    overloaded_issues = check(
        "❍ " + ("기업 지원 내용을 구체적으로 안내하고, " * 10)
        + "참여 기업의 사업화 준비를 돕는다.",
        final=False,
    )
    if not any(
        message == OVERLOADED_SENTENCE_MESSAGE
        for _, message in overloaded_issues
    ):
        raise ValueError("쉼표가 많은 장문을 검출하지 못했습니다.")

    repeated_opening_issues = check(
        "❍ 이번 행사는 기업의 기술 애로를 해소하기 위해 마련됐다.\n"
        "❍ 이번 행사는 전문기관 상담과 시험분석 지원을 제공한다.",
        final=False,
    )
    if not any(
        message == REPEATED_OPENING_MESSAGE
        for _, message in repeated_opening_issues
    ):
        raise ValueError("연속 문단의 같은 시작 표현을 검출하지 못했습니다.")

    short_body_issues = check(
        "\n".join(f"❍ 테스트 본문 {index}" for index in range(1, 6)),
        final=False,
    )
    if not any(
        MIN_BODY_PARAGRAPHS_MESSAGE in message
        for _, message in short_body_issues
    ):
        raise ValueError("5개 이하 본문 문단을 검출하지 못했습니다.")

    six_body_issues = check(
        "\n".join(f"❍ 테스트 본문 {index}" for index in range(1, 7)),
        final=False,
    )
    if any(
        MIN_BODY_PARAGRAPHS_MESSAGE in message
        for _, message in six_body_issues
    ):
        raise ValueError("6개 본문 문단을 부족한 분량으로 잘못 검출했습니다.")

    direct_title_issues = check(
        "포항TP, KOLAS 연료전지 시험범위 확대\n"
        "- 7월 16일 연료전지 시험 분야 3종 추가 인정",
        final=False,
    )
    if any(message == HEADLINE_NEWS_MESSAGE for _, message in direct_title_issues):
        raise ValueError("구체적인 사실형 제목을 잘못 경고했습니다.")
    if any(
        "제목에 산업·기업·시민·지역에 주는 의미" in message
        for _, message in direct_title_issues
    ):
        raise ValueError("사실형 제목에 의미 표현을 잘못 강제했습니다.")

    scene_title_issues = check(
        "배터리 기술, 산업을 넘어 시민의 일상으로\n"
        "- 11월 13일 포항종합운동장서 국제 배터리 엑스포 개최",
        final=False,
    )
    if any(message == HEADLINE_NEWS_MESSAGE for _, message in scene_title_issues):
        raise ValueError("부제목이 뉴스를 보완한 현장형 제목을 잘못 경고했습니다.")

    vague_title_issues = check(
        "포항TP, 미래를 향한 새로운 도약\n"
        "- 지역과 함께 만드는 더 나은 내일",
        final=False,
    )
    if not any(message == HEADLINE_NEWS_MESSAGE for _, message in vague_title_issues):
        raise ValueError("구체적 보도내용이 없는 제목·부제목을 검출하지 못했습니다.")
    if not any(message == CLICHE_TITLE_MESSAGE for _, message in vague_title_issues):
        raise ValueError("제목의 상투적 표현을 검출하지 못했습니다.")

    clean_subtitle_issues = check(
        "포항TP, 이차전지 기술사업화 참여기업 모집\n"
        "- 9월 1~18일 경북 소재 기업 접수…20개사 선정\n"
        "- 시제품 제작·시험분석·인증·투자상담 연계",
        final=False,
    )
    if any(
        message == TRAILING_SUBTITLE_DASH_MESSAGE
        for _, message in clean_subtitle_issues
    ):
        raise ValueError("끝 대시가 없는 부제목을 잘못 경고했습니다.")

    old_subtitle_issues = check(
        "포항TP, 이차전지 기술사업화 참여기업 모집\n"
        "- 9월 1~18일 경북 소재 기업 접수…20개사 선정 -",
        final=False,
    )
    if not any(
        message == TRAILING_SUBTITLE_DASH_MESSAGE
        for _, message in old_subtitle_issues
    ):
        raise ValueError("부제목 끝의 불필요한 대시를 검출하지 못했습니다.")

    diverse_options = [
        {
            "id": 1,
            "type": "공식 행동·사실",
            "title": "포항TP, 이차전지 시험분석 지원창구 가동",
            "subtitle": [
                "6월 10일부터 지역 소재 기업 대상 상담 운영",
                "장비 연계와 인증 절차 안내를 한곳에서 제공",
            ],
            "recommended": True,
        },
        {
            "id": 2,
            "type": "대상·독자 효익",
            "title": "기업별 시험분석 상담, 한곳에서 받는다",
            "subtitle": [
                "포항TP 이차전지 지원창구 6월 10일 운영 시작",
                "장비 선택부터 인증 절차까지 기업별 안내",
            ],
            "recommended": False,
        },
        {
            "id": 3,
            "type": "시점·기회",
            "title": "6월 10일 문 여는 배터리 기업 지원창구",
            "subtitle": [
                "지역 소재 기업 대상 시험분석·인증 상담 운영",
                "포항TP 보유 장비와 전문기관 연계 지원",
            ],
            "recommended": False,
        },
    ]
    diverse_issues = check_options(diverse_options)
    if any(level == "ERROR" for level, _ in diverse_issues):
        raise ValueError(
            "서로 다른 관점의 정상 제목 제안안을 잘못 거부했습니다: "
            f"{diverse_issues}"
        )

    repetitive_options = [
        {
            "id": 1,
            "type": "기관행동형",
            "title": "포항TP, 배터리 기업 지원 강화",
            "subtitle": ["배터리 기업 지원 프로그램 운영"],
            "recommended": False,
        },
        {
            "id": 2,
            "type": "기관행동형",
            "title": "포항TP, 배터리 기업 상담 강화",
            "subtitle": ["배터리 기업 상담 프로그램 운영"],
            "recommended": False,
        },
        {
            "id": 3,
            "type": "기관행동형",
            "title": "포항TP, 배터리 기업 인증 강화",
            "subtitle": ["배터리 기업 인증 프로그램 운영"],
            "recommended": False,
        },
    ]
    repetitive_issues = check_options(repetitive_options)
    repetitive_messages = {
        message for _, message in repetitive_issues
    }
    for expected in (
        TYPE_DIVERSITY_MESSAGE,
        OPENING_DIVERSITY_MESSAGE,
        ENDING_DIVERSITY_MESSAGE,
        RECOMMENDATION_MESSAGE,
    ):
        if expected not in repetitive_messages:
            raise ValueError(
                f"획일적 제목 제안안의 문제를 검출하지 못했습니다: {expected}"
            )

    print("SELF-TEST PASSED")
    print(f"Python: {sys.executable}")
    print(f"lxml: {etree.LXML_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
