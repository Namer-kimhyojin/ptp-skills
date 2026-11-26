#!/usr/bin/env python3
"""Check and record reusable PTP production layers by content hash."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


LAYERS = {"source", "copy", "concept", "character", "background", "lettering", "assembly"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_pairs(values: list[str], label: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"{label} 값은 name=value 형식이어야 합니다: {raw}")
        name, value = raw.split("=", 1)
        if not name.strip() or name in result:
            raise ValueError(f"{label} 이름은 비어 있지 않고 중복되지 않아야 합니다: {name}")
        result[name] = value
    return result


def state_path(cache_dir: Path) -> Path:
    return cache_dir.resolve() / "layers.json"


def load_state(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"schema_version": "1.0", "layers": {}}
    if not isinstance(data, dict) or not isinstance(data.get("layers"), dict):
        return {"schema_version": "1.0", "layers": {}}
    return data


def write_state(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def fingerprint(dependencies: dict[str, str], values: dict[str, str], job: Path | None) -> tuple[str, dict[str, object]]:
    resolved: dict[str, object] = {"files": {}, "values": dict(sorted(values.items()))}
    files = dict(dependencies)
    if job is not None:
        files["job"] = str(job)
    for name, raw_path in sorted(files.items()):
        path = Path(raw_path).resolve()
        if not path.is_file():
            raise ValueError(f"의존 파일이 없습니다: {name}={path}")
        resolved["files"][name] = {"path": str(path), "sha256": sha256(path), "size": path.stat().st_size}
    encoded = json.dumps(resolved, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), resolved


def outputs_valid(outputs: object) -> bool:
    if not isinstance(outputs, list) or not outputs:
        return False
    for item in outputs:
        if not isinstance(item, dict):
            return False
        path = Path(str(item.get("path", "")))
        if not path.is_file() or item.get("sha256") != sha256(path):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "record", "show"])
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--layer", choices=sorted(LAYERS))
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--value", action="append", default=[])
    parser.add_argument("--job", type=Path)
    parser.add_argument("--output", action="append", default=[])
    args = parser.parse_args()

    path = state_path(args.cache_dir)
    state = load_state(path)
    layers = state["layers"]
    if args.action == "show":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if not args.layer:
        print("ERROR: check와 record에는 --layer가 필요합니다", file=sys.stderr)
        return 2
    try:
        dependencies = parse_pairs(args.dependency, "dependency")
        values = parse_pairs(args.value, "value")
        key, inputs = fingerprint(dependencies, values, args.job)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    current = layers.get(args.layer)
    reusable = isinstance(current, dict) and current.get("key") == key and outputs_valid(current.get("outputs"))
    if args.action == "check":
        print(json.dumps({"layer": args.layer, "key": key, "reuse": reusable, "outputs": current.get("outputs", []) if reusable else []}, ensure_ascii=False, indent=2))
        return 0 if reusable else 3

    if not args.output:
        print("ERROR: record에는 하나 이상의 --output이 필요합니다", file=sys.stderr)
        return 2
    output_items = []
    for raw in args.output:
        output = Path(raw).resolve()
        if not output.is_file():
            print(f"ERROR: 출력 파일이 없습니다: {output}", file=sys.stderr)
            return 2
        output_items.append({"path": str(output), "sha256": sha256(output), "size": output.stat().st_size})
    layers[args.layer] = {"key": key, "inputs": inputs, "outputs": output_items}
    write_state(path, state)
    print(json.dumps({"layer": args.layer, "key": key, "recorded": True, "outputs": output_items}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
