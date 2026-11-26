#!/usr/bin/env python3
"""Run safe local lifecycle hooks for quick, standard, and publication profiles."""

from __future__ import annotations

import argparse
import json
import locale
import subprocess
import sys
from pathlib import Path


EVENTS = {
    "after_intake",
    "before_generate",
    "after_generate",
    "before_export",
    "after_export",
    "before_publish",
}


def result(status: str, event: str, message: str, retryable: bool = False) -> dict[str, object]:
    return {
        "status": status,
        "event": event,
        "checks": [{"id": event, "status": status, "message": message}],
        "derived_artifacts": [],
        "warnings": [] if status == "pass" else [message],
        "retryable": retryable,
    }


def run(command: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", choices=sorted(EVENTS))
    parser.add_argument("job", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--profile", choices=["quick-draft", "standard", "publication"])
    parser.add_argument("--authorized", action="store_true", help="이미 받은 명시적 게시 요청을 반영; 반복 승인 질문이 아님")
    args = parser.parse_args()

    try:
        job = json.loads(args.job.resolve().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps(result("block", args.event, f"작업 JSON을 읽을 수 없습니다: {exc}"), ensure_ascii=True))
        return 2

    profile = args.profile or job.get("production_mode") or "standard"
    publication = job.get("publication") if isinstance(job.get("publication"), dict) else {}

    if args.event == "before_publish":
        if publication.get("authorized") is not True or not args.authorized:
            print(json.dumps(result("block", args.event, "명시적인 게시 승인과 --authorized가 모두 필요합니다"), ensure_ascii=True))
            return 3
        from notice_publish_guard import check_job
        gate = check_job(job, args.job)
        if gate is not None and not gate["allowed"]:
            blocked = result("block", args.event, "공고 접수기간·제작 완료·채널별 중복 검사에서 차단했습니다")
            blocked["notice_gate"] = gate
            print(json.dumps(blocked, ensure_ascii=True))
            return 3
        print(json.dumps(result("pass", args.event, "게시 승인 상태를 확인했습니다"), ensure_ascii=True))
        return 0

    if profile == "quick-draft":
        if args.event in {"after_intake", "before_generate"}:
            scripts = Path(__file__).resolve().parent
            code, output = run(
                [sys.executable, str(scripts / "validate_job.py"), str(args.job.resolve()), "--level", "fast"]
            )
            status = "pass" if code == 0 else "block"
            print(json.dumps(result(status, args.event, output or "빠른 초안 필수값 검증 완료", retryable=code != 0), ensure_ascii=True))
            return code
        print(json.dumps(result("not_run", args.event, "빠른 초안 모드에서 상세 훅 검증을 생략했습니다"), ensure_ascii=True))
        return 0

    scripts = Path(__file__).resolve().parent
    if args.event in {"after_intake", "before_generate", "before_export"}:
        level = "publication" if profile == "publication" else "standard"
        job_command = [
            sys.executable,
            str(scripts / "validate_job.py"),
            str(args.job.resolve()),
            "--level",
            level,
        ]
        code, output = run(job_command)
        if code == 0 and (profile == "publication" or args.event in {"before_generate", "before_export"}):
            # The per-job publication validator checks the approval of assets actually used.
            asset_code, asset_output = run(
                [
                    sys.executable,
                    str(scripts / "validate_assets.py"),
                    str(scripts.parent / "assets" / "asset-manifest.json"),
                    "--level",
                    "standard",
                    "--cache-dir",
                    str(scripts.parent / ".ptp-cache"),
                ]
            )
            code = asset_code
            output = "\n".join(part for part in (output, asset_output) if part)
        status = "pass" if code == 0 else "block"
        print(json.dumps(result(status, args.event, output or "작업 요청 검증 완료", retryable=code != 0), ensure_ascii=True))
        return code

    if args.event == "after_export":
        if not args.output_dir:
            print(json.dumps(result("block", args.event, "after_export에는 --output-dir가 필요합니다"), ensure_ascii=True))
            return 2
        code, output = run(
            [sys.executable, str(scripts / "validate_delivery.py"), str(args.job.resolve()), str(args.output_dir.resolve())]
        )
        status = "pass" if code == 0 else "block"
        print(json.dumps(result(status, args.event, output or "납품 검증 완료", retryable=code != 0), ensure_ascii=True))
        return code

    if args.event in {"after_generate"}:
        print(json.dumps(result("not_run", args.event, "연결된 시각 검사 훅이 없어 coordinator 검토로 넘겼습니다"), ensure_ascii=True))
        return 0
    print(json.dumps(result("pass", args.event, "기본 로컬 훅을 통과했습니다"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
