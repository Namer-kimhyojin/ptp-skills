#!/usr/bin/env python3
"""Validate the approved Teo/Pio 3D pose-reference library."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = ROOT / "assets/characters/3d/poses/pose-library.json"
EXPECTED = [
    "neutral", "open-hand-guide", "index-explain", "thumbs-up",
    "action-step", "concerned-kind", "tablet", "wave",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        signature = stream.read(24)
    if len(signature) != 24 or signature[:8] != b"\x89PNG\r\n\x1a\n" or signature[12:16] != b"IHDR":
        raise ValueError("not a PNG with an IHDR header")
    return struct.unpack(">II", signature[16:24])


def validate(library_path: Path = DEFAULT_LIBRARY) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(library_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"library read failed: {exc}"]
    if data.get("status") != "approved":
        errors.append("library status must be approved")
    if data.get("pose_order") != EXPECTED:
        errors.append("pose_order does not match the eight approved roles")
    if "not an alpha transparency layer" not in str(data.get("usage_scope", "")):
        errors.append("usage_scope must disclose the baked checkerboard limitation")
    characters = data.get("characters")
    if not isinstance(characters, dict) or set(characters) != {"teo", "pio"}:
        return errors + ["characters must contain exactly teo and pio"]
    base = library_path.parent
    for character_name in ("teo", "pio"):
        entry = characters.get(character_name)
        if not isinstance(entry, dict):
            errors.append(f"{character_name}: invalid character entry")
            continue
        items = [entry.get("atlas")] + list(entry.get("poses", []))
        pose_ids = [item.get("id") for item in entry.get("poses", []) if isinstance(item, dict)]
        if pose_ids != EXPECTED:
            errors.append(f"{character_name}: expected eight ordered poses")
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{character_name}: invalid asset entry")
                continue
            relative = item.get("path")
            if not isinstance(relative, str):
                errors.append(f"{character_name}: missing asset path")
                continue
            path = base / relative
            if not path.is_file():
                errors.append(f"{character_name}: missing {relative}")
                continue
            if sha256(path) != item.get("sha256"):
                errors.append(f"{character_name}: hash mismatch {relative}")
            try:
                width, height = png_size(path)
            except (OSError, ValueError) as exc:
                errors.append(f"{character_name}: {relative}: {exc}")
                continue
            if width != item.get("width") or height != item.get("height"):
                errors.append(f"{character_name}: dimension mismatch {relative}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", nargs="?", type=Path, default=DEFAULT_LIBRARY)
    args = parser.parse_args()
    errors = validate(args.library.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: approved Teo/Pio 3D pose library (2 atlases, 16 pose references)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
