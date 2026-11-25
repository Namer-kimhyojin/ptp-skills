#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HH = "http://www.hancom.co.kr/hwpml/2011/head"
OPF = "http://www.idpf.org/2007/opf/"
NS = {"hp": HP, "hh": HH, "opf": OPF}
REQUIRED_PACKAGE_FILES = (
    "mimetype",
    "Contents/header.xml",
    "Contents/section0.xml",
    "Contents/content.hpf",
    "META-INF/container.xml",
)
PHONE_PATTERN = re.compile(r"^0\d{1,2}-\d{3,4}-\d{4}$")
EMAIL_PATTERN = re.compile(
    r"^[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}$",
    re.IGNORECASE,
)
CONFIRM_PATTERN = re.compile(r"(\[확인 필요:[^\]\r\n]+\])")


def plain_text(value: object, field: str, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise ValueError(f"필수 입력값이 없습니다: {field}")
    return text


def load_payload(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("입력 JSON의 최상위 값은 객체여야 합니다.")
    return payload


def subtitle_lines(value: object) -> list[str]:
    if isinstance(value, str):
        raw_lines = [value]
    elif isinstance(value, list):
        raw_lines = value
    else:
        raise ValueError("`subtitle`은 문자열 또는 문자열 배열이어야 합니다.")
    if not 1 <= len(raw_lines) <= 2:
        raise ValueError("부제목은 1~2줄이어야 합니다.")
    return [
        plain_text(line, f"subtitle[{index}]")
        for index, line in enumerate(raw_lines)
    ]


def replace_placeholder(
    root: etree._Element, placeholder: str, value: str
) -> None:
    nodes = root.xpath(
        ".//hp:t[text()=$placeholder]",
        namespaces=NS,
        placeholder=placeholder,
    )
    if len(nodes) != 1:
        raise ValueError(
            f"양식 자리표시자 `{placeholder}`의 개수가 1개가 아닙니다: {len(nodes)}"
        )
    nodes[0].text = value


def set_subtitles(root: etree._Element, lines: list[str]) -> None:
    nodes = root.xpath(
        ".//hp:t[text()='{{부제목}}']",
        namespaces=NS,
    )
    if len(nodes) != 1:
        raise ValueError(
            f"양식 자리표시자 `{{{{부제목}}}}`의 개수가 1개가 아닙니다: {len(nodes)}"
        )
    placeholder = nodes[0]
    placeholder.text = lines[0]
    following_text_node = placeholder.getnext()
    if (
        following_text_node is not None
        and following_text_node.tag == f"{{{HP}}}t"
        and (following_text_node.text or "").strip() == "-"
    ):
        following_text_node.text = ""
    subtitle_paragraphs = placeholder.xpath("ancestor::hp:p[1]", namespaces=NS)
    if len(subtitle_paragraphs) != 1:
        raise ValueError("부제목 문단을 찾지 못했습니다.")
    subtitle_paragraph = subtitle_paragraphs[0]
    parent = subtitle_paragraph.getparent()

    reserved_second = None
    following = subtitle_paragraph.getnext()
    if following is not None and following.tag == f"{{{HP}}}p":
        following_text = "".join(
            following.xpath(".//hp:t/text()", namespaces=NS)
        ).strip()
        if following_text == "{{부제목2}}":
            reserved_second = following

    if reserved_second is not None:
        runs = reserved_second.xpath("./hp:run", namespaces=NS)
        if not runs:
            raise ValueError("두 번째 부제목 문단에 텍스트 런이 없습니다.")
        primary = runs[0]
        for run in runs[1:]:
            reserved_second.remove(run)
        for child in list(primary):
            primary.remove(child)
        text_node = etree.SubElement(primary, f"{{{HP}}}t")
        text_node.text = f"- {lines[1]}" if len(lines) == 2 else ""
        return

    next_id = next_paragraph_id(root)
    insert_index = parent.index(subtitle_paragraph) + 1
    for line in lines[1:]:
        cloned = copy.deepcopy(subtitle_paragraph)
        cloned.set("id", str(next_id))
        next_id += 1
        runs = cloned.xpath("./hp:run", namespaces=NS)
        if not runs:
            raise ValueError("부제목 문단에 텍스트 런이 없습니다.")
        primary = runs[0]
        for run in runs[1:]:
            cloned.remove(run)
        for child in list(primary):
            primary.remove(child)
        text_node = etree.SubElement(primary, f"{{{HP}}}t")
        text_node.text = f"- {line}"
        for cache in cloned.xpath("./hp:linesegarray", namespaces=NS):
            cloned.remove(cache)
        parent.insert(insert_index, cloned)
        insert_index += 1


def set_cell_after_label(
    root: etree._Element, label: str, value: str
) -> None:
    label_cells = []
    for cell in root.xpath(".//hp:tc", namespaces=NS):
        text = "".join(cell.xpath(".//hp:t/text()", namespaces=NS)).strip()
        if text == label:
            label_cells.append(cell)
    if len(label_cells) != 1:
        raise ValueError(
            f"표 라벨 `{label}`의 개수가 1개가 아닙니다: {len(label_cells)}"
        )

    label_cell = label_cells[0]
    row = label_cell.getparent()
    cells = row.xpath("./hp:tc", namespaces=NS)
    index = cells.index(label_cell)
    if index + 1 >= len(cells):
        raise ValueError(f"표 라벨 `{label}` 다음에 입력 셀이 없습니다.")
    value_cell = cells[index + 1]

    text_nodes = value_cell.xpath(".//hp:t", namespaces=NS)
    if text_nodes:
        text_nodes[0].text = value
        for node in text_nodes[1:]:
            node.text = ""
        return

    runs = value_cell.xpath(".//hp:run", namespaces=NS)
    if not runs:
        raise ValueError(f"표 라벨 `{label}`의 입력 셀에 텍스트 런이 없습니다.")
    text_node = etree.SubElement(runs[0], f"{{{HP}}}t")
    text_node.text = value


def body_paragraphs(root: etree._Element) -> list[etree._Element]:
    paragraphs = []
    for paragraph in root.xpath("./hp:p", namespaces=NS):
        text = "".join(paragraph.xpath(".//hp:t/text()", namespaces=NS)).strip()
        if text.startswith("❍"):
            paragraphs.append(paragraph)
    if len(paragraphs) < 2:
        raise ValueError(
            f"본문 입력용 `❍` 문단이 2개보다 적습니다: {len(paragraphs)}"
        )
    return paragraphs


def next_paragraph_id(root: etree._Element) -> int:
    ids = []
    for paragraph in root.xpath(".//hp:p[@id]", namespaces=NS):
        try:
            ids.append(int(paragraph.get("id", "0")))
        except ValueError:
            continue
    return max(ids, default=1000000000) + 1


def set_body_text(paragraph: etree._Element, item: str) -> None:
    runs = paragraph.xpath("./hp:run", namespaces=NS)
    if not runs:
        raise ValueError("본문 입력 문단에 텍스트 런이 없습니다.")

    primary = runs[0]
    for run in runs[1:]:
        paragraph.remove(run)
    for child in list(primary):
        primary.remove(child)
    text_node = etree.SubElement(primary, f"{{{HP}}}t")
    text_node.text = f"❍ {item}"
    for cache in paragraph.xpath("./hp:linesegarray", namespaces=NS):
        paragraph.remove(cache)


def set_body_blocks(root: etree._Element, items: list[str]) -> None:
    anchors = body_paragraphs(root)
    first, second = anchors[0], anchors[-1]
    if first.getparent() is not root or second.getparent() is not root:
        raise ValueError("본문 입력 문단이 섹션 최상위에 있지 않습니다.")

    children = list(root)
    first_index = children.index(first)
    second_index = children.index(second)
    if first_index >= second_index:
        raise ValueError("본문 입력 문단의 순서가 올바르지 않습니다.")

    for child in children[first_index : second_index + 1]:
        root.remove(child)

    next_id = next_paragraph_id(root)
    for index, item in enumerate(items):
        paragraph = copy.deepcopy(second)
        paragraph.set("id", str(next_id))
        next_id += 1
        set_body_text(paragraph, item)
        root.insert(first_index + index, paragraph)


def clear_layout_cache(root: etree._Element) -> None:
    for cache in root.xpath(".//hp:linesegarray", namespaces=NS):
        cache.getparent().remove(cache)


def ensure_red_char_pr(
    header_root: etree._Element,
    base_id: str,
    red_ids: dict[str, str],
) -> str:
    if base_id in red_ids:
        return red_ids[base_id]

    properties = header_root.xpath(".//hh:charProperties", namespaces=NS)
    if len(properties) != 1:
        raise ValueError(
            f"글자 속성 그룹의 개수가 1개가 아닙니다: {len(properties)}"
        )
    char_properties = properties[0]
    base_nodes = char_properties.xpath(
        "./hh:charPr[@id=$base_id]",
        namespaces=NS,
        base_id=base_id,
    )
    if len(base_nodes) != 1:
        raise ValueError(
            f"기준 글자 속성 ID `{base_id}`의 개수가 1개가 아닙니다: "
            f"{len(base_nodes)}"
        )

    existing_ids = [
        int(node.get("id", "0"))
        for node in char_properties.xpath("./hh:charPr", namespaces=NS)
        if node.get("id", "0").isdigit()
    ]
    new_id = str(max(existing_ids, default=0) + 1)
    cloned = copy.deepcopy(base_nodes[0])
    cloned.set("id", new_id)
    cloned.set("textColor", "#FF0000")
    char_properties.append(cloned)
    char_properties.set(
        "itemCnt",
        str(len(char_properties.xpath("./hh:charPr", namespaces=NS))),
    )
    red_ids[base_id] = new_id
    return new_id


def apply_confirmation_red(
    section_root: etree._Element,
    header_root: etree._Element,
) -> None:
    red_ids: dict[str, str] = {}
    targets = list(
        section_root.xpath(
            ".//hp:t[contains(text(), '[확인 필요:')]",
            namespaces=NS,
        )
    )
    for text_node in targets:
        text = text_node.text or ""
        parts = [part for part in CONFIRM_PATTERN.split(text) if part]
        if not any(CONFIRM_PATTERN.fullmatch(part) for part in parts):
            continue

        run = text_node.getparent()
        base_id = run.get("charPrIDRef", "0")
        if len(parts) == 1 and CONFIRM_PATTERN.fullmatch(parts[0]):
            run.set(
                "charPrIDRef",
                ensure_red_char_pr(header_root, base_id, red_ids),
            )
            continue

        text_nodes = run.xpath("./hp:t", namespaces=NS)
        controls = run.xpath("./hp:ctrl", namespaces=NS)
        if len(text_nodes) != 1 or controls:
            raise ValueError(
                "확인 필요 문구가 다른 필드 제어와 섞여 있어 색상 분리가 어렵습니다."
            )
        paragraph = run.getparent()
        insert_index = paragraph.index(run)
        paragraph.remove(run)
        for part in parts:
            split_run = etree.Element(f"{{{HP}}}run", **run.attrib)
            if CONFIRM_PATTERN.fullmatch(part):
                split_run.set(
                    "charPrIDRef",
                    ensure_red_char_pr(header_root, base_id, red_ids),
                )
            split_text = etree.SubElement(split_run, f"{{{HP}}}t")
            split_text.text = part
            paragraph.insert(insert_index, split_run)
            insert_index += 1


def preview_text(
    payload: dict[str, object],
    body: list[str],
    subtitles: list[str],
) -> str:
    contact = payload["contact"]
    assert isinstance(contact, dict)
    contact_title = plain_text(contact.get("title"), "contact.title", required=False)
    contact_parts = [
        plain_text(contact.get("team"), "contact.team"),
        plain_text(contact.get("name"), "contact.name"),
    ]
    if contact_title:
        contact_parts.append(contact_title)
    contact_line = " ".join(contact_parts)
    contact_line += (
        f" ({plain_text(contact.get('phone'), 'contact.phone')}, "
        f"{plain_text(contact.get('email'), 'contact.email')})"
    )

    lines = [
        "보 도 자 료",
        f"배포일시  {plain_text(payload.get('release_date'), 'release_date')}",
        f"보도일시  {plain_text(payload.get('press_time'), 'press_time')}",
        f"담당부서  {plain_text(payload.get('department'), 'department')}",
        f"붙임자료  {plain_text(payload.get('attachments'), 'attachments')}",
        f"담 당 자  {contact_line}",
        "",
        plain_text(payload.get("title"), "title"),
    ]
    lines.extend(f"- {subtitle}" for subtitle in subtitles)
    lines.append("")
    lines.extend(f"❍ {item}" for item in body)
    return "\r\n".join(lines) + "\r\n"


def validate_package(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if not infos or infos[0].filename != "mimetype":
            raise ValueError("mimetype이 ZIP의 첫 엔트리가 아닙니다.")
        if infos[0].compress_type != zipfile.ZIP_STORED:
            raise ValueError("mimetype이 비압축 방식이 아닙니다.")
        if archive.read("mimetype") != b"application/hwp+zip":
            raise ValueError("mimetype 내용이 올바르지 않습니다.")
        names = set(archive.namelist())
        for required in REQUIRED_PACKAGE_FILES:
            if required not in names:
                raise ValueError(f"HWPX 필수 파일이 없습니다: {required}")
        for name in names:
            if name.lower().endswith((".xml", ".hpf")):
                etree.fromstring(archive.read(name))
        section = archive.read("Contents/section0.xml").decode("utf-8")
        if "{{" in section or "}}" in section:
            raise ValueError("결과 HWPX에 양식 자리표시자가 남아 있습니다.")
        if "Preview/PrvText.txt" in names:
            preview = archive.read("Preview/PrvText.txt").decode("utf-8")
            if "{{" in preview or "}}" in preview:
                raise ValueError("결과 HWPX의 미리보기 텍스트에 자리표시자가 남아 있습니다.")


def build(template: Path, payload_path: Path, output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"출력 파일이 이미 존재합니다: {output}")

    payload = load_payload(payload_path)
    contact = payload.get("contact")
    if not isinstance(contact, dict):
        raise ValueError("`contact`는 객체여야 합니다.")

    director_name = plain_text(payload.get("director_name"), "director_name")
    contact_phone = plain_text(contact.get("phone"), "contact.phone")
    contact_email = plain_text(contact.get("email"), "contact.email")
    contact_team = plain_text(contact.get("team"), "contact.team")
    contact_name = plain_text(contact.get("name"), "contact.name")
    contact_title = plain_text(
        contact.get("title"), "contact.title", required=False
    )
    if not PHONE_PATTERN.fullmatch(contact_phone):
        raise ValueError(
            "담당자 전화번호 형식이 올바르지 않습니다. 예: 054-000-0000"
        )
    if not EMAIL_PATTERN.fullmatch(contact_email):
        raise ValueError(
            "담당자 이메일 형식이 올바르지 않습니다. 예: name@example.org"
        )
    body_raw = payload.get("body")
    if not isinstance(body_raw, list):
        raise ValueError("`body`는 문자열 배열이어야 합니다.")
    body = [
        re.sub(r"^\s*❍\s*", "", plain_text(item, f"body[{index}]"))
        for index, item in enumerate(body_raw)
    ]
    if not 6 <= len(body) <= 8:
        raise ValueError("본문 문단은 6~8개여야 합니다.")
    if director_name not in "\n".join(body):
        raise ValueError("본문에 확인된 원장명과 원장 인용문을 포함해야 합니다.")
    subtitles = subtitle_lines(payload.get("subtitle"))

    replacements = {
        "{{배포일시}}": plain_text(payload.get("release_date"), "release_date"),
        "{{부서명}}": plain_text(payload.get("department"), "department"),
        "{{팀명}}": contact_team,
        "{{이름}}": contact_name,
        "{{직급}}": f" {contact_title}" if contact_title else "",
        "{{전화}}": contact_phone,
        "{{이메일}}": contact_email,
        "{{제목}}": plain_text(payload.get("title"), "title"),
    }

    with zipfile.ZipFile(template, "r") as source:
        section_root = etree.fromstring(source.read("Contents/section0.xml"))
        header_root = etree.fromstring(source.read("Contents/header.xml"))
        content_root = etree.fromstring(source.read("Contents/content.hpf"))
        for placeholder, value in replacements.items():
            replace_placeholder(section_root, placeholder, value)
        set_subtitles(section_root, subtitles)
        set_cell_after_label(
            section_root,
            "보도일시",
            plain_text(payload.get("press_time"), "press_time"),
        )
        set_cell_after_label(
            section_root,
            "붙임자료",
            plain_text(payload.get("attachments"), "attachments"),
        )

        set_body_blocks(section_root, body)
        apply_confirmation_red(section_root, header_root)
        clear_layout_cache(section_root)

        section_bytes = etree.tostring(
            section_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        header_bytes = etree.tostring(
            header_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        title_nodes = content_root.xpath("./opf:metadata/opf:title", namespaces=NS)
        if len(title_nodes) != 1:
            raise ValueError(
                f"문서 제목 메타데이터의 개수가 1개가 아닙니다: {len(title_nodes)}"
            )
        title_nodes[0].text = replacements["{{제목}}"]
        for metadata_name in ("creator", "lastsaveby"):
            metadata_nodes = content_root.xpath(
                "./opf:metadata/opf:meta[@name=$name]",
                namespaces=NS,
                name=metadata_name,
            )
            if len(metadata_nodes) == 1:
                metadata_nodes[0].set("content", contact_name)
        content_bytes = etree.tostring(
            content_root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
        preview_bytes = preview_text(payload, body, subtitles).encode("utf-8")

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w") as destination:
            for info in source.infolist():
                # The template preview image contains placeholder text. Omitting
                # it prevents a stale thumbnail; Hancom regenerates it on save.
                if info.filename == "Preview/PrvImage.png":
                    continue
                copied = copy.copy(info)
                if info.filename == "mimetype":
                    copied.compress_type = zipfile.ZIP_STORED
                if info.filename == "Contents/section0.xml":
                    data = section_bytes
                elif info.filename == "Contents/header.xml":
                    data = header_bytes
                elif info.filename == "Contents/content.hpf":
                    data = content_bytes
                elif info.filename == "Preview/PrvText.txt":
                    data = preview_bytes
                else:
                    data = source.read(info.filename)
                destination.writestr(copied, data)

    validate_package(output)

    long_paragraphs = [
        index + 1 for index, text in enumerate(body) if len(text) > 240
    ]
    print(f"CREATED: {output}")
    print(f"BODY_PARAGRAPHS: {len(body)}")
    print(f"SUBTITLES: {len(subtitles)}")
    if long_paragraphs:
        print(
            "WARNING: 240자를 넘는 본문 문단이 있습니다: "
            + ", ".join(map(str, long_paragraphs))
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="포항TP 보도자료 HWPX 양식에 JSON 내용을 채웁니다."
    )
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        build(args.template, args.input, args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
