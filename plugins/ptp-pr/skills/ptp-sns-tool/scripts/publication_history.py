#!/usr/bin/env python3
"""Local, append-only SNS attempt ledger. This tool never posts or verifies a remote post.

Exit codes: 0 = recorded/allowed; 1 = invalid input or ledger; 2 = duplicate/lock block.
`check` is advisory. `record` always rechecks under the same exclusive ledger lock.
Account aliases normalize to handle:<casefolded handle> or id:<numeric ID>.
Keep the same stable account ID in configuration across runs: this local tool cannot
map a vanity handle to an immutable numeric ID or track account renames. Never supply
passwords, tokens, or cookies.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, unquote, urlsplit
import uuid


STATES = {"submitting", "published", "scheduled", "unknown", "failed"}
BLOCKING = {"submitting", "published", "scheduled", "unknown"}
SUCCESS = {"published", "scheduled"}
IDENTITY = ("source_key", "platform", "account")


class HistoryError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise HistoryError(message)


def iso_time(value: str, name: str) -> str:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("timezone missing")
    except (AttributeError, TypeError, ValueError) as exc:
        raise HistoryError(f"{name} must be ISO 8601 with an explicit timezone") from exc
    return value


def public_url(value: str, platform: str) -> str:
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        domain = "instagram.com" if platform == "instagram" else "facebook.com"
        if (url.scheme != "https" or url.username or url.password or url.port
                or not (host == domain or host.endswith("." + domain))
                or url.path in ("", "/")):
            raise ValueError("not a public platform URL")
        allowed_query = {"id", "fbid", "story_fbid", "set"} if platform == "facebook" else set()
        if any(key not in allowed_query for key, _ in parse_qsl(url.query)) or url.fragment:
            raise ValueError("remove tracking, authentication, or fragment parameters")
    except ValueError as exc:
        raise HistoryError(f"Use a public https {platform} URL without credentials or tracking parameters") from exc
    return value


def canonical_account(value: str, platform: str) -> str:
    """Collapse syntax aliases only; never infer a handle-to-immutable-ID mapping."""
    value = value.strip()

    def numeric_id(raw: str) -> str:
        if not re.fullmatch(r"[0-9]{1,200}", raw):
            raise HistoryError("Numeric account IDs must contain only digits")
        return "id:" + (raw.lstrip("0") or "0")

    def handle(raw: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", raw):
            raise HistoryError("Account handles must use their public ASCII username")
        return "handle:" + raw.casefold()

    if value.casefold().startswith("id:"):
        return numeric_id(value[3:])
    if value.casefold().startswith("handle:"):
        return handle(value[7:])
    if value.casefold().startswith("https://"):
        public_url(value, platform)
        url = urlsplit(value)
        parts = unquote(url.path).strip("/").split("/")
        query = parse_qsl(url.query, keep_blank_values=True)
        if platform == "facebook":
            if parts == ["profile.php"] and len(query) == 1 and query[0][0] == "id":
                return numeric_id(query[0][1])
            if query:
                raise HistoryError("Account URL must identify a public profile, not a post or media item")
            if len(parts) == 3 and parts[0].casefold() in {"pages", "people"}:
                return numeric_id(parts[2])
            if len(parts) == 2 and parts[0].casefold() == "pg":
                return handle(parts[1])
            if len(parts) != 1 or parts[0].casefold() in {"profile.php", "permalink.php", "photo.php", "story.php", "watch", "share", "posts"}:
                raise HistoryError("Use a Facebook public page profile URL or numeric page ID")
            return numeric_id(parts[0]) if parts[0].isdigit() else handle(parts[0])
        if query or len(parts) != 1 or parts[0].casefold() in {"p", "reel", "reels", "stories", "explore", "accounts"}:
            raise HistoryError("Use an Instagram public profile URL, not a post URL")
        return handle(parts[0])
    if value.startswith("@"):
        return handle(value[1:])
    return numeric_id(value) if value.isdigit() else handle(value)


def identity(args) -> tuple[str, str, str]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", args.source_key):
        raise HistoryError("source-key must be a stable public identifier, e.g. ptp:15:123")
    return args.source_key, args.platform, canonical_account(args.account, args.platform)


def manifest_hash(path: str | None) -> str | None:
    if path is None:
        return None
    data = Path(path).read_bytes()
    try:
        document = json.loads(data.decode("utf-8-sig"))
        if not isinstance(document, dict):
            raise ValueError("manifest is not an object")
    except (UnicodeError, ValueError) as exc:
        raise HistoryError("manifest must be a UTF-8 JSON object") from exc
    return hashlib.sha256(data).hexdigest()


@contextmanager
def ledger_lock(path: Path):
    """Do not auto-remove preexisting locks: a prior interrupted submission may exist."""
    lock = path.with_name(path.name + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise HistoryError("Ledger is locked; reconcile the other run before retrying. Do not automatically remove the lock.", 2) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        lock.unlink()


def key(event: dict) -> tuple[str, str, str]:
    # Normalize legacy events in memory; never rewrite the append-only history.
    return event["source_key"], event["platform"], canonical_account(event["account"], event["platform"])


def validate_event(event: dict):
    if not isinstance(event, dict) or event.get("schema_version") != 1:
        raise HistoryError("Unsupported ledger event schema")
    if event.get("status") not in STATES:
        raise HistoryError("Invalid ledger status")
    for name in (*IDENTITY, "attempt_id", "event_id", "manifest_sha256"):
        if not isinstance(event.get(name), str) or not event[name]:
            raise HistoryError(f"Missing ledger field: {name}")
    if event["platform"] not in ("instagram", "facebook") or not re.fullmatch(r"[0-9a-f]{64}", event["manifest_sha256"]):
        raise HistoryError("Invalid ledger platform or fingerprint")
    canonical_account(event["account"], event["platform"])
    iso_time(event.get("recorded_at"), "recorded_at")
    if event["status"] in SUCCESS:
        if not event.get("evidence") or not (event.get("remote_url") or event.get("post_id")):
            raise HistoryError("Successful ledger event lacks remote evidence")
        iso_time(event.get("published_at" if event["status"] == "published" else "scheduled_at"), event["status"] + " timestamp")
    if event["status"] == "failed" and (event.get("definitive_failure") is not True or not event.get("evidence")):
        raise HistoryError("Failure is not definitive; reconcile its remote state before retrying")
    replacement = event.get('replacement')
    if replacement is not None:
        if not isinstance(replacement,dict) or not all(isinstance(replacement.get(k),str) and replacement[k].strip() for k in ('previous_attempt_id','previous_post_id','user_request_evidence','deletion_evidence_path','deletion_evidence_sha256','removed_at')):
            raise HistoryError('Replacement requires the original published attempt, explicit user request and verified removal evidence')
        if replacement.get('old_removed_verified') is not True or not re.fullmatch(r'[0-9a-f]{64}',replacement['deletion_evidence_sha256']):
            raise HistoryError('Replacement requires a verified removal and evidence fingerprint')
        iso_time(replacement['removed_at'],'replacement.removed_at')


def read_latest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    if path.stat().st_size and not path.read_bytes().endswith(b"\n"):
        raise HistoryError("Ledger has an incomplete final line; preserve and reconcile it")
    latest: dict[str, dict] = {}
    seen = set()
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                raise HistoryError(f"Blank event at ledger line {line_number}")
            event = json.loads(line)
            validate_event(event)
            if event["event_id"] in seen:
                raise HistoryError("Duplicate ledger event ID")
            seen.add(event["event_id"])
            previous = latest.get(event["attempt_id"])
            if previous:
                if key(previous) != key(event) or previous["manifest_sha256"] != event["manifest_sha256"]:
                    raise HistoryError("Attempt identity or manifest changed inside ledger")
                if previous["status"] not in {"submitting", "unknown"} or event["status"] not in {"unknown", "published", "scheduled", "failed"}:
                    raise HistoryError("Invalid or overwritten terminal ledger transition")
                if previous.get('replacement') != event.get('replacement'):
                    raise HistoryError('Replacement linkage changed during reconciliation')
            elif event.get('replacement'):
                original = latest.get(event['replacement']['previous_attempt_id'])
                if not original or original['status']!='published' or key(original)!=key(event) or original.get('post_id')!=event['replacement']['previous_post_id']:
                    raise HistoryError('Replacement must link an existing published post on the same source and account')
                if any(x.get('replacement', {}).get('previous_attempt_id') == original['attempt_id'] and x['status'] != 'failed' for x in latest.values()):
                    raise HistoryError('Original post already has a replacement attempt; reconcile it first')
            latest[event["attempt_id"]] = event
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise HistoryError("Ledger is malformed; preserve it and reconcile before submitting") from exc
    return latest


def inspect(latest: dict[str, dict], target: tuple[str, str, str], fingerprint: str | None) -> dict:
    matching = [event for event in latest.values() if key(event) == target]
    replaced = {e['replacement']['previous_attempt_id'] for e in matching if e.get('replacement')}
    blockers = [event for event in matching if event["status"] in BLOCKING and event['attempt_id'] not in replaced]
    return {
        "allowed": not blockers,
        "source_key": target[0], "platform": target[1], "account": target[2],
        "manifest_sha256": fingerprint,
        "fingerprint_changed": bool(fingerprint and any(event["manifest_sha256"] != fingerprint for event in matching)),
        "blocking_attempts": blockers,
        "definitive_failed_attempts": sum(event["status"] == "failed" for event in matching),
        "reason": "Existing successful or unresolved attempt; reconcile it before another submission." if blockers else "No successful or unresolved attempt for this exact source/platform/account.",
    }


def append_event(path: Path, event: dict):
    # A torn append is detected and blocks all future submissions on this ledger.
    if path.exists() and path.stat().st_size:
        with path.open("rb") as stream:
            stream.seek(-1, os.SEEK_END)
            if stream.read(1) != b"\n":
                raise HistoryError("Ledger has an incomplete final line; preserve and reconcile it")
    with path.open("ab") as stream:
        stream.write((json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def record(args, path: Path, target, fingerprint) -> tuple[dict, int]:
    if not fingerprint:
        raise HistoryError("record requires --manifest")
    status = args.status
    evidence = (args.evidence or "").strip()
    if len(evidence) > 2000:
        raise HistoryError("Keep evidence within 2000 characters; never include credentials")
    if status in SUCCESS:
        if not evidence or not (args.remote_url or args.post_id):
            raise HistoryError("published/scheduled require --evidence and --remote-url or --post-id")
        if args.remote_url:
            public_url(args.remote_url, args.platform)
        if args.post_id and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", args.post_id):
            raise HistoryError("post-id must be a public identifier")
        iso_time(args.published_at if status == "published" else args.scheduled_at, status + " timestamp")
    elif args.remote_url or args.post_id or args.published_at or args.scheduled_at:
        raise HistoryError("Remote result fields are accepted only for published or scheduled outcomes")
    if status == "failed" and (not args.definitive_failure or not evidence):
        raise HistoryError("Use failed only with --definitive-failure and --evidence; uncertain outcomes must be unknown")
    if status != "failed" and args.definitive_failure:
        raise HistoryError("--definitive-failure is valid only for failed outcomes")
    if (status == "published" and args.scheduled_at) or (status == "scheduled" and args.published_at):
        raise HistoryError("Supply only the timestamp for the selected outcome")
    with ledger_lock(path):
        latest = read_latest(path)
        report = inspect(latest, target, fingerprint)
        replacement = None
        if getattr(args,'replacement_evidence',None):
            if args.attempt_id or status!='submitting':
                raise HistoryError('Replacement evidence is only valid for a new submitting attempt')
            try:
                replacement=json.loads(Path(args.replacement_evidence).read_text('utf-8'))
            except (OSError,ValueError) as exc:
                raise HistoryError('Cannot read replacement evidence') from exc
            validate_event({'schema_version':1,'status':'submitting','source_key':target[0],'platform':target[1],'account':target[2],'attempt_id':'validation','event_id':'validation','manifest_sha256':fingerprint,'recorded_at':datetime.now(timezone.utc).isoformat(),'replacement':replacement})
            original=latest.get(replacement['previous_attempt_id'])
            if (not original or original['status']!='published' or key(original)!=target or original.get('post_id')!=replacement['previous_post_id'] or replacement.get('replacement_manifest_sha256')!=fingerprint):
                raise HistoryError('Replacement evidence does not match the original post, target account or replacement package')
            proof=Path(replacement['deletion_evidence_path'])
            if not proof.is_absolute() or not proof.is_file() or hashlib.sha256(proof.read_bytes()).hexdigest()!=replacement['deletion_evidence_sha256']:
                raise HistoryError('Replacement removal evidence file is missing or changed')
            blockers = [event['attempt_id'] for event in report['blocking_attempts']]
            earlier = [event for event in latest.values()
                       if event.get('replacement', {}).get('previous_attempt_id') == original['attempt_id']]
            prior_failed = earlier and all(event['status'] == 'failed' for event in earlier)
            if blockers != [original['attempt_id']] and not (not blockers and prior_failed):
                raise HistoryError('Replacement is blocked by another successful or unresolved attempt', 2)
        if args.attempt_id:
            previous = latest.get(args.attempt_id)
            if not previous or key(previous) != target:
                raise HistoryError("attempt-id does not match this source/platform/account")
            if previous["manifest_sha256"] != fingerprint:
                raise HistoryError("Reconciliation requires the original package manifest")
            if previous["status"] not in {"submitting", "unknown"}:
                raise HistoryError("Terminal history cannot be overwritten or automatically reposted", 2)
            if status not in {"unknown", "published", "scheduled", "failed"}:
                raise HistoryError("Reconcile an existing attempt to unknown, published, scheduled, or failed")
        elif not report["allowed"] and replacement is None:
            return {"ok": False, "action": "record", **report}, 2
        if not args.attempt_id and replacement is None and status == 'submitting':
            if any(key(event) == target and event['status'] == 'failed' and event.get('replacement')
                   for event in latest.values()) and not report['blocking_attempts']:
                raise HistoryError('Retry a failed replacement with its verified removal evidence', 2)
        series_gate = None
        episode = re.fullmatch(r'ptp:institution:support-guide-2026:ep(\d{2})', target[0])
        from spark_runtime import KEY_PATTERN
        spark = re.fullmatch(KEY_PATTERN, target[0])
        if spark and status == 'scheduled':
            raise HistoryError('Daily Spark publishing requires an immediate public post')
        if not args.attempt_id and (spark or (episode and 9 <= int(episode[1]) <= 34)):
            if status != 'submitting':
                raise HistoryError('Start with a verified series submitting attempt')
            from series_runtime import submission_guard
            try:
                from social_runtime import current_time, load, sha, stamp
                if replacement:
                    removal = load(replacement['deletion_evidence_path'])
                    if (removal.get('post_id') != replacement['previous_post_id']
                            or removal.get('old_removed_verified') is not True
                            or stamp(removal['removed_at']) != stamp(replacement['removed_at'])
                            or not str(removal.get('observations', '')).strip()):
                        raise ValueError('series_removal_evidence_does_not_match_original_post')
                series_gate = submission_guard(args.manifest, target[0], target[1], target[2], latest,
                                               replacement=replacement is not None)
                proof_path = getattr(args, 'series_gate', None)
                if not proof_path:
                    raise ValueError('series_channel_gate_report_required')
                proof = load(proof_path)
                fields = ('source_key', 'platform', 'runtime_run_id', 'manifest_sha256', 'planned_at')
                if (proof.get('allowed') is not True or any(proof[k] != series_gate[k] for k in fields)
                        or sha(proof['preview_path']) != proof['preview_sha256']
                        or not -60 <= (current_time() - stamp(proof['checked_at'])).total_seconds() <= 300):
                    raise ValueError('series_channel_gate_stale_or_changed')
                series_gate['gate_report_sha256'] = sha(proof_path)
            except (ValueError, OSError, KeyError, TypeError, HistoryError) as exc:
                raise HistoryError('Series submission blocked: ' + str(exc), 2) from exc
        notice_gate = None
        if not args.attempt_id and status == "submitting" and target[0].startswith(("ptp:15:", "ptp:2:")):
            from notice_publish_guard import check_start
            notice_gate = check_start(target[0], args.manifest, getattr(args, "eligibility", None),
                                      getattr(args, "content_ledger", None), getattr(args, "planned_publish_at", None), path)
            if not notice_gate["allowed"]:
                return {"ok": False, "allowed": False, "action": "record", "notice_gate": notice_gate}, 2
            if notice_gate.get('runtime_gate') and notice_gate['runtime_gate'].get('verified_accounts',{}).get(target[1])!=canonical_account(target[2],target[1]):
                return {"ok":False,"allowed":False,"action":"record","error":"Runtime preflight verified a different account"},2
        event = {
            "schema_version": 1, "event_id": str(uuid.uuid4()),
            "attempt_id": args.attempt_id or str(uuid.uuid4()),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "source_key": target[0], "platform": target[1], "account": target[2],
            "manifest_sha256": fingerprint, "status": status, "evidence": evidence or None,
            "remote_url": args.remote_url, "post_id": args.post_id,
            "published_at": args.published_at, "scheduled_at": args.scheduled_at,
            "definitive_failure": bool(args.definitive_failure),
        }
        if replacement is not None:
            event['replacement']=replacement
        elif args.attempt_id and previous.get('replacement'):
            event['replacement']=previous['replacement']
        if notice_gate:
            event["notice_gate"] = notice_gate
            event["planned_publish_at"] = getattr(args, "planned_publish_at", None)
            if notice_gate.get('runtime_gate',{}):
                event['runtime_run_id']=notice_gate['runtime_gate']['runtime_run_id']
        elif series_gate:
            event['runtime_run_id'] = series_gate['runtime_run_id']
            event['series_gate'] = series_gate
        elif args.attempt_id and previous.get('runtime_run_id'):
            event['runtime_run_id']=previous['runtime_run_id']
        validate_event(event)
        append_event(path, event)
        return {"ok": True, "action": "record", "event": event, "remote_verification": "operator-supplied evidence; no remote call performed"}, 0


def main(argv=None) -> int:
    try:
        parser = Parser(description=__doc__)
        sub = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
        for command in ("check", "record"):
            item = sub.add_parser(command)
            item.add_argument("--ledger", default=str(Path(__file__).resolve().parent.parent / "state/publication-history.jsonl"))
            item.add_argument("--source-key", required=True)
            item.add_argument("--platform", required=True, choices=("instagram", "facebook"))
            item.add_argument("--account", required=True, help="Stable public ID, handle, or profile URL; aliases normalize, but handle-to-numeric-ID mapping must stay fixed in account configuration")
            item.add_argument("--manifest", required=command == "record")
            if command == "record":
                item.add_argument("--status", required=True, choices=sorted(STATES))
                item.add_argument("--attempt-id")
                item.add_argument("--remote-url")
                item.add_argument("--post-id")
                item.add_argument("--evidence")
                item.add_argument("--published-at")
                item.add_argument("--scheduled-at")
                item.add_argument("--definitive-failure", action="store_true")
                item.add_argument("--eligibility", help="Fresh checked application-period evidence; required for new PTP submissions")
                item.add_argument("--content-ledger", help="Isolated test registry override; production uses the shared skill registry")
                item.add_argument("--planned-publish-at", help="Timezone-aware target time for a user-requested scheduled post")
                item.add_argument('--series-gate', help='Current per-channel series composer verification report')
                item.add_argument('--replacement-evidence',help='Explicit user-requested replacement only; original published attempt and actual removal proof, bound to this package')
        args = parser.parse_args(argv)
        target, fingerprint = identity(args), manifest_hash(args.manifest)
        path = Path(args.ledger).expanduser().resolve()
        if args.command == "record":
            result, code = record(args, path, target, fingerprint)
        else:
            with ledger_lock(path):
                report = inspect(read_latest(path), target, fingerprint)
            result, code = {"ok": True, "action": "check", **report}, (0 if report["allowed"] else 2)
        print(json.dumps(result, ensure_ascii=False))
        return code
    except HistoryError as exc:
        print(json.dumps({"ok": False, "allowed": False, "error": str(exc)}, ensure_ascii=False))
        return exc.code
    except OSError as exc:
        print(json.dumps({"ok": False, "allowed": False, "error": f"Local file operation failed: {exc.strerror or type(exc).__name__}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
