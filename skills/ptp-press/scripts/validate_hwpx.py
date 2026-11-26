#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fill_press_release_hwpx import validate_package


def main() -> int:
    parser = argparse.ArgumentParser(
        description="포항TP 보도자료 HWPX의 패키지와 XML 무결성을 검사합니다."
    )
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        validate_package(args.file)
    except Exception as exc:
        print(f"INVALID: {args.file}", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {args.file}")
    print("  HWPX 패키지와 XML 구조 검사를 통과했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
