#!/usr/bin/env python3
"""Append-only card production registry; never generates content or publishes remotely.

Use the shared default ledgers in normal work. Explicit ledger paths are for isolated
tests or deliberate migrations, never to evade an existing record. A producing run
has no automatic expiry. Reconcile it with the same production ID; only a confirmed
failure permits a fresh run. Produced packages remain immutable and must be
reused or recovered, including when files have moved or been damaged.
revise-produced may append a separately verified package for an unpublished
notice, with unchanged images and explicit revision evidence. Earlier events
and packages are never overwritten.

Exit codes: 0 allowed/recorded, 1 invalid data, 2 duplicate/recovery/lock block.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import uuid

import publication_history as publication
from publication_history import HistoryError, Parser, append_event, iso_time, ledger_lock

STATE_ROOT = Path(__file__).resolve().parent.parent / "state"
DEFAULT_LEDGER = STATE_ROOT / "content-history.jsonl"
DEFAULT_PUBLICATION_LEDGER = STATE_ROOT / "publication-history.jsonl"
STATES = {"producing", "produced", "failed"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def source_key(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"(?:ptp:15:[1-9][0-9]*|ptp:institution:[a-z0-9]+(?:-[a-z0-9]+)*:ep[0-9]{2,4}|ptp:spark:[a-z0-9]+(?:-[a-z0-9]+)*:(?:oneshot|ep[0-9]{2,4})|event:[a-z0-9]+(?:-[a-z0-9]+)*:[0-9]{4}-[0-9]{2}-[0-9]{2})", value):
        raise HistoryError("source-key must identify a PTP notice, institution explainer, ptp:spark:<slug>:oneshot|epNN, or event:<slug>:YYYY-MM-DD")
    if value.startswith("event:"):
        try:
            datetime.strptime(value.rsplit(":", 1)[1], "%Y-%m-%d")
        except ValueError as exc:
            raise HistoryError("event source-key requires a valid event date") from exc
    return value


def nonempty(value, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise HistoryError(f"{label} must be nonempty text within 4000 characters")
    return value.strip()


def uuid_field(value, label: str):
    try:
        if str(uuid.UUID(value)) != value:
            raise ValueError("noncanonical UUID")
    except (TypeError, ValueError, AttributeError) as exc:
        raise HistoryError(f"{label} must be a canonical UUID") from exc


def complete_lines(path: Path):
    if path.exists() and path.stat().st_size and not path.read_bytes().endswith(b"\n"):
        raise HistoryError("Ledger has an incomplete final line; preserve it and reconcile before proceeding")


def image_signature(data: bytes, suffix: str) -> bool:
    if suffix == ".png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return data.startswith(b"\xff\xd8\xff")
    if suffix == ".webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    return data[:6] in {b"GIF87a", b"GIF89a"}


def verify_manifest(path: Path, target: str, expected_sha256: str | None = None) -> dict:
    """Read the real package manifest and check every listed file against its hash.

    Compatible with the existing PTP package-manifest.json: source_key,
    files:[{file: package-relative path, sha256: hex, bytes: optional integer}].
    This checks integrity and image magic, not visual quality or remote publication.
    """
    path = Path(path).expanduser().resolve()
    try:
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 and digest != expected_sha256:
            raise HistoryError("Produced manifest changed; recover the original package before reuse", 2)
        document = json.loads(data.decode("utf-8-sig"))
        if not isinstance(document, dict) or document.get("source_key") != target:
            raise HistoryError("Manifest source_key does not match this notice")
        entries = document.get("files")
        if not isinstance(entries, list) or not entries or len(entries) > 1000:
            raise HistoryError("Manifest requires a nonempty files list (maximum 1000 entries)")
        seen, images = set(), []
        for entry in entries:
            if not isinstance(entry, dict):
                raise HistoryError("Each manifest file must be an object")
            relative, fingerprint = entry.get("file"), entry.get("sha256")
            if not isinstance(relative, str) or not relative or "\\" in relative:
                raise HistoryError("Manifest files must use package-relative forward-slash paths")
            parts = PurePosixPath(relative)
            if parts.is_absolute() or any(part in {"..", "."} or ":" in part for part in parts.parts):
                raise HistoryError("Manifest file must stay inside its package directory")
            asset = (path.parent / relative).resolve()
            if not asset.is_relative_to(path.parent) or asset == path:
                raise HistoryError("Manifest file escapes its package or references itself")
            normalized = str(asset).casefold()
            if normalized in seen:
                raise HistoryError("Duplicate manifest file")
            seen.add(normalized)
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                raise HistoryError("Manifest file requires a lowercase SHA-256 fingerprint")
            content = asset.read_bytes()
            if hashlib.sha256(content).hexdigest() != fingerprint:
                raise HistoryError(f"Package file hash mismatch: {relative}", 2)
            if "bytes" in entry and (type(entry["bytes"]) is not int or entry["bytes"] != len(content)):
                raise HistoryError(f"Package file size mismatch: {relative}", 2)
            if asset.suffix.lower() in IMAGE_SUFFIXES:
                if not image_signature(content, asset.suffix.lower()):
                    raise HistoryError(f"Package image signature is invalid: {relative}", 2)
                images.append(relative)
        if not images:
            raise HistoryError("A produced package must include at least one actual card image")
        return {"manifest_path": str(path), "manifest_sha256": digest,
                "file_count": len(entries), "image_count": len(images), "image_files": images}
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HistoryError("Package is missing or unreadable; recover the original files before reuse", 2) from exc


def validate_event(event: dict):
    if not isinstance(event, dict) or event.get("schema_version") != 1 or event.get("status") not in STATES:
        raise HistoryError("Unsupported content ledger event")
    source_key(event.get("source_key"))
    for name in ("event_id", "production_id"):
        uuid_field(event.get(name), name)
    iso_time(event.get("recorded_at"), "recorded_at")
    imported = event.get("imported")
    if type(imported) is not bool:
        raise HistoryError("Content ledger requires an imported boolean")
    if imported and event["status"] != "produced":
        raise HistoryError("Only existing produced packages can be imported")
    if event["status"] in {"produced", "failed"}:
        nonempty(event.get("evidence"), "evidence")
    if event["status"] == "failed" and event.get("definitive_failure") is not True:
        raise HistoryError("Uncertain production must remain producing; failure requires definitive evidence")
    if event["status"] == "produced":
        if not isinstance(event.get("manifest_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", event["manifest_sha256"]):
            raise HistoryError("Produced event requires a manifest fingerprint")
        if not isinstance(event.get("manifest_path"), str) or not Path(event["manifest_path"]).is_absolute():
            raise HistoryError("Produced event requires an absolute manifest path")
        if type(event.get("image_count")) is not int or event["image_count"] < 1:
            raise HistoryError("Produced event requires at least one image")
    if imported:
        nonempty(event.get("provenance"), "provenance")
    if "revision" in event:
        revision = event["revision"]
        if event["status"] != "produced" or imported or not isinstance(revision, dict):
            raise HistoryError("A revision must be a non-imported produced event")
        uuid_field(revision.get("previous_event_id"), "revision.previous_event_id")
        if not isinstance(revision.get("original_manifest_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", revision["original_manifest_sha256"]):
            raise HistoryError("Revision requires the original manifest fingerprint")
        if not isinstance(revision.get("original_manifest_path"), str) or not Path(revision["original_manifest_path"]).is_absolute():
            raise HistoryError("Revision requires the original absolute manifest path")
        nonempty(revision.get("reason"), "revision.reason")
        creative = revision.get("kind") == "user-requested-creative"
        if creative:
            nonempty(revision.get("user_request_evidence"), "revision.user_request_evidence")
        if (not creative and revision.get("images_unchanged") is not True) or revision.get("publication_blockers_checked") is not True:
            raise HistoryError("Revision requires unchanged images or an explicit creative request, and a publication-blocker check")


def read_latest(path: Path) -> dict[str, dict]:
    """Return latest validated event for each source_key; never rewrites history."""
    path = Path(path)
    if not path.exists():
        return {}
    complete_lines(path)
    latest, seen_events, used_productions = {}, set(), {}
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise HistoryError(f"Blank content event at line {number}")
            event = json.loads(line)
            validate_event(event)
            target, production_id = event["source_key"], event["production_id"]
            if event["event_id"] in seen_events:
                raise HistoryError("Duplicate content event ID")
            seen_events.add(event["event_id"])
            previous = latest.get(target)
            revision = event.get("revision")
            if previous and previous["status"] == "produced":
                if (not revision or event["status"] != "produced"
                        or production_id != previous["production_id"]
                        or revision["previous_event_id"] != previous["event_id"]
                        or revision["original_manifest_sha256"] != previous["manifest_sha256"]
                        or revision["original_manifest_path"] != previous["manifest_path"]
                        or Path(event["manifest_path"]).resolve() == Path(previous["manifest_path"]).resolve()
                        or event["manifest_sha256"] == previous["manifest_sha256"]):
                    raise HistoryError("Produced content is immutable; only a linked, separately verified revision may follow it")
            elif revision:
                raise HistoryError("A revision must follow this notice's latest produced event")
            elif previous and previous["status"] == "producing":
                if (production_id != previous["production_id"] or event["imported"]
                        or event["status"] not in {"produced", "failed"}):
                    raise HistoryError("An unfinished production must be reconciled with the same production ID")
            else:
                if production_id in used_productions:
                    raise HistoryError("Production ID cannot be reused for a new run or notice")
                if event["status"] != "producing" and not event["imported"]:
                    raise HistoryError("A new production must start as producing or import verified existing content")
            if production_id in used_productions and used_productions[production_id] != target:
                raise HistoryError("Production identity changed inside ledger")
            used_productions[production_id] = target
            latest[target] = event
    except (UnicodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise HistoryError("Content ledger is malformed; preserve and reconcile it") from exc
    return latest


def inspect(latest: dict[str, dict], target: str, publication_latest: dict | None = None,
            verify_files: bool = True) -> dict:
    source_key(target)
    event = latest.get(target)
    status = event["status"] if event else "not_recorded"
    blockers = [item for item in (publication_latest or {}).values()
                if item["source_key"] == target and item["status"] in publication.BLOCKING]
    reason = "No successful or unresolved production/publication exists for this notice."
    recovery, integrity = False, None
    if status == "producing":
        recovery, reason = True, "An unfinished production exists; reconcile its outcome with the same production ID."
    elif status == "produced":
        reason = "Card news already exists; reuse this package. Do not automatically generate a revision."
        if verify_files:
            try:
                integrity = verify_manifest(Path(event["manifest_path"]), target, event["manifest_sha256"])
            except HistoryError as exc:
                recovery, reason = True, str(exc)
    if blockers and status not in {"producing", "produced"}:
        reason = "Successful or unresolved publication exists; locate/import existing content before considering further work."
        recovery = True
    allowed = status in {"not_recorded", "failed"} and not blockers
    return {"source_key": target, "status": status, "allowed": allowed, "can_create": allowed,
            "requires_recovery": recovery, "event": event, "integrity": integrity,
            "publication_blockers": blockers, "reason": reason}


def new_event(target: str, status: str, production_id: str | None = None) -> dict:
    return {"schema_version": 1, "event_id": str(uuid.uuid4()),
            "production_id": production_id or str(uuid.uuid4()), "source_key": target,
            "recorded_at": datetime.now(timezone.utc).isoformat(), "status": status,
            "imported": False}


def run(args) -> tuple[dict, int]:
    target = source_key(args.source_key)
    path = Path(args.ledger).expanduser().resolve()
    publication_path = Path(args.publication_ledger).expanduser().resolve()
    if path == publication_path:
        raise HistoryError("Production and publication ledgers must be separate files")
    # All commands share this order. Keep publication locked through start's append.
    with ledger_lock(path):
        latest = read_latest(path)
        with ledger_lock(publication_path):
            complete_lines(publication_path)
            published = publication.read_latest(publication_path)
            report = inspect(latest, target, published)
            if args.command == "check":
                return {"ok": True, "action": "check", **report}, 0 if report["allowed"] else 2
            if args.command == "start":
                if not report["allowed"]:
                    return {"ok": False, "action": "start", **report}, 2
                event = new_event(target, "producing")
            else:
                evidence = nonempty(args.evidence, "evidence")
                if args.command in {"revise-produced", "revise-creative"}:
                    previous = latest.get(target)
                    if not previous or previous["status"] != "produced":
                        raise HistoryError("revise-produced requires this notice's latest produced event", 2)
                    if args.previous_event_id != previous["event_id"]:
                        raise HistoryError("previous-event-id must match the latest produced event", 2)
                    if args.original_manifest_sha256 != previous["manifest_sha256"]:
                        raise HistoryError("original-manifest-sha256 does not match the produced event", 2)
                    creative = args.command == "revise-creative"
                    blockers = [e for e in report["publication_blockers"] if not creative or e['status'] != 'published']
                    if blockers:
                        raise HistoryError("Cannot revise while any channel is submitting, unknown, published or scheduled", 2)
                    reason = nonempty(args.reason, "reason")
                    original = Path(previous["manifest_path"]).resolve()
                    verify_manifest(original, target, args.original_manifest_sha256)
                    replacement = Path(args.manifest).expanduser().resolve()
                    if replacement == original:
                        raise HistoryError("A revision requires a separate manifest path; preserve the original package", 2)
                    event = new_event(target, "produced", previous["production_id"])
                    event["revision"] = {
                        "previous_event_id": previous["event_id"],
                        "original_manifest_path": previous["manifest_path"],
                        "original_manifest_sha256": previous["manifest_sha256"],
                        "reason": reason, "images_unchanged": not creative,
                        "publication_blockers_checked": True,
                    }
                    if creative:
                        event['revision'].update(kind='user-requested-creative', user_request_evidence=nonempty(args.user_request_evidence,'user-request-evidence'), published_channels_remain_blocked=True)
                elif args.command == "finish":
                    previous = latest.get(target)
                    if not previous or previous["production_id"] != args.production_id:
                        raise HistoryError("production-id does not match this notice's current production")
                    if previous["status"] != "producing":
                        raise HistoryError("Terminal production is immutable; reuse or recover the existing package", 2)
                    event = new_event(target, args.status, args.production_id)
                    if args.status == "failed":
                        if not args.definitive_failure or args.manifest:
                            raise HistoryError("failed requires --definitive-failure and evidence of no usable package; omit --manifest")
                        event["definitive_failure"] = True
                    elif args.definitive_failure:
                        raise HistoryError("--definitive-failure is only valid for failed")
                else:
                    if report["status"] in {"producing", "produced"}:
                        return {"ok": False, "action": "import-produced", **report}, 2
                    event = new_event(target, "produced")
                    event.update(imported=True, provenance=nonempty(args.provenance, "provenance"))
                event["evidence"] = evidence
                if event["status"] == "produced":
                    if not args.manifest:
                        raise HistoryError("produced requires --manifest with verified card images")
                    event.update(verify_manifest(Path(args.manifest), target))
                    if args.command in {"revise-produced", "revise-creative"}:
                        if event["manifest_sha256"] == previous["manifest_sha256"]:
                            raise HistoryError("Revision manifest is unchanged; reuse the current package", 2)
                        def image_fingerprints(manifest):
                            document = json.loads(manifest.read_text(encoding="utf-8-sig"))
                            return {item["file"]: item["sha256"] for item in document["files"]
                                    if Path(item["file"]).suffix.lower() in IMAGE_SUFFIXES}
                        if args.command == 'revise-produced' and image_fingerprints(original) != image_fingerprints(replacement):
                            raise HistoryError("A platform-copy revision must preserve all original image files and hashes", 2)
            validate_event(event)
            append_event(path, event)
            return {"ok": True, "action": args.command, "event": event}, 0


def main(argv=None) -> int:
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        for command in ("check", "start", "finish", "import-produced", "revise-produced", "revise-creative"):
            item = sub.add_parser(command)
            item.add_argument("--ledger", default=str(DEFAULT_LEDGER))
            item.add_argument("--publication-ledger", default=str(DEFAULT_PUBLICATION_LEDGER))
            item.add_argument("--source-key", required=True)
            if command in {"finish", "import-produced", "revise-produced", "revise-creative"}:
                item.add_argument("--manifest", required=command in {"revise-produced", "revise-creative"})
                item.add_argument("--evidence", required=True)
            if command == "finish":
                item.add_argument("--production-id", required=True)
                item.add_argument("--status", required=True, choices=("produced", "failed"))
                item.add_argument("--definitive-failure", action="store_true")
            elif command == "import-produced":
                item.add_argument("--provenance", required=True)
            elif command in {"revise-produced", "revise-creative"}:
                item.add_argument("--previous-event-id", required=True)
                item.add_argument("--original-manifest-sha256", required=True)
                item.add_argument("--reason", required=True)
                if command == 'revise-creative':
                    item.add_argument('--user-request-evidence',required=True)
        result, code = run(parser.parse_args(argv))
        print(json.dumps(result, ensure_ascii=False))
        return code
    except HistoryError as exc:
        print(json.dumps({"ok": False, "allowed": False, "error": str(exc)}, ensure_ascii=False))
        return exc.code
    except OSError as exc:
        print(json.dumps({"ok": False, "allowed": False,
                          "error": f"Local file operation failed: {exc.strerror or type(exc).__name__}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
