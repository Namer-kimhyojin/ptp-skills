from __future__ import annotations

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS = {"hp": HP}


def mm_to_hwpunit(value: float) -> int:
    return int(round(value * 7200 / 25.4))


def update_hwpx(source_path: Path, output_path: Path, values: dict[str, int]) -> dict[str, object]:
    with zipfile.ZipFile(source_path, "r") as source:
        section_names = [name for name in source.namelist() if name.startswith("Contents/section") and name.endswith(".xml")]
        if not section_names:
            raise ValueError("HWPX section XML not found")

        replacements: dict[str, bytes] = {}
        before: list[dict[str, str]] = []
        after: list[dict[str, str]] = []
        for section_name in section_names:
            root = etree.fromstring(source.read(section_name))
            margins = root.xpath(".//hp:secPr/hp:pagePr/hp:margin", namespaces=NS)
            if not margins:
                raise ValueError(f"page margin not found: {section_name}")
            for margin in margins:
                before.append(dict(margin.attrib))
                for key, value in values.items():
                    margin.set(key, str(value))
                after.append(dict(margin.attrib))
            replacements[section_name] = etree.tostring(
                root,
                xml_declaration=True,
                encoding="UTF-8",
                standalone=True,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w") as target:
            for info in source.infolist():
                data = replacements.get(info.filename, source.read(info.filename))
                target.writestr(info, data)

    return {"before": before, "after": after, "output": str(output_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Set HWPX page margins without changing document content")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--top", type=float, default=15.0)
    parser.add_argument("--bottom", type=float, default=15.0)
    parser.add_argument("--left", type=float, default=15.0)
    parser.add_argument("--right", type=float, default=15.0)
    parser.add_argument("--header", type=float, default=10.0)
    parser.add_argument("--footer", type=float, default=10.0)
    parser.add_argument("--gutter", type=float, default=0.0)
    args = parser.parse_args()

    source_path = args.input.resolve()
    output_path = (args.output or args.input).resolve()
    values = {
        "top": mm_to_hwpunit(args.top),
        "bottom": mm_to_hwpunit(args.bottom),
        "left": mm_to_hwpunit(args.left),
        "right": mm_to_hwpunit(args.right),
        "header": mm_to_hwpunit(args.header),
        "footer": mm_to_hwpunit(args.footer),
        "gutter": mm_to_hwpunit(args.gutter),
    }

    if output_path == source_path:
        handle, temporary_name = tempfile.mkstemp(prefix=source_path.stem + "-", suffix=".hwpx", dir=source_path.parent)
        os.close(handle)
        temporary_path = Path(temporary_name)
        try:
            report = update_hwpx(source_path, temporary_path, values)
            os.replace(temporary_path, source_path)
            report["output"] = str(source_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    else:
        report = update_hwpx(source_path, output_path, values)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
