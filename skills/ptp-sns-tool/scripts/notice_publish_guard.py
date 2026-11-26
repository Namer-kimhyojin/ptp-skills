"""Local pre-submission checks for PTP notices; no network or publishing side effects."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def remaining_period_issues(period, required_days, *, conservative_date=False):
    from datetime import datetime
    if not isinstance(required_days,int) or required_days<0:
        return ['invalid_minimum_remaining_days']
    if not required_days:
        return []
    if not period.get('application_end'):
        return ['application_end_required_for_minimum_remaining_days']
    end = datetime.fromisoformat(period['application_end'])
    if conservative_date and period.get('end_precision') == 'day':
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    seconds = (end - datetime.fromisoformat(period['evaluated_at'])).total_seconds()
    return ['less_than_minimum_remaining_days'] if seconds<required_days*86400 else []


def check_start(source_key, manifest_path, eligibility_path, content_ledger=None, planned_publish_at=None, publication_ledger=None):
    from content_history import DEFAULT_LEDGER, read_latest, inspect, verify_manifest
    from notice_eligibility import evaluate

    errors = []
    if not eligibility_path:
        return {"allowed": False, "reasons": ["fresh_application_period_evidence_required"]}
    try:
        evidence_bytes = Path(eligibility_path).read_bytes()
        evidence = json.loads(evidence_bytes.decode("utf-8-sig"))
        announcement = source_key.startswith('ptp:2:')
        if announcement:
            from board_monitor import announcement_evidence
            period = announcement_evidence(evidence, source_key, planned_publish_at)
        else:
            period = evaluate(evidence, source_key, scheduled_at=planned_publish_at)
        if not period["allowed"]:
            errors.extend(period["reasons"])
        manifest = Path(manifest_path).resolve()
        fingerprint = hashlib.sha256(manifest.read_bytes()).hexdigest()
        verify_manifest(manifest, source_key, fingerprint)
        manifest_data=json.loads(manifest.read_text(encoding='utf-8-sig'))
        runtime_gate=None
        reviewed_images = None

        def absolute(value):
            return str((manifest.parent / value).resolve())

        registered = {absolute(item['file']): item['sha256'] for item in manifest_data['files']}
        if manifest_data.get('runtime_contract_version') is not None:
            if manifest_data['runtime_contract_version']!=1:
                errors.append('unsupported_runtime_contract')
            elif manifest_data.get('runtime', {}).get('mode') == 'interactive':
                from content_preflight import validate_report

                report_path = Path(absolute(manifest_data['runtime']['quality_review_path']))
                if str(report_path) not in registered:
                    errors.append('interactive_quality_report_must_be_registered')
                else:
                    issues = validate_report(report_path, source_key)
                    if issues:
                        errors.extend('interactive_quality:' + issue for issue in issues)
                    else:
                        report = json.loads(report_path.read_text(encoding='utf-8-sig'))
                        reviewed_images = report['images']
            else:
                from social_runtime import submission_guard
                import publication_history as publication
                # The caller may already own the publication lock. Read the
                # validated shared history without trying to lock it again.
                runtime_gate=submission_guard(manifest_data.get('runtime',{}),source_key,
                    publication.read_latest(Path(publication_ledger) if publication_ledger else Path(__file__).resolve().parent.parent/'state/publication-history.jsonl'))
                if not runtime_gate['allowed']:errors.append('runtime_guard:'+runtime_gate.get('reason','blocked'))
                else:
                    reviewed_images = runtime_gate['reviewed_images']
        if reviewed_images is not None:
            final_paths = manifest_data.get('final_image_paths')
            if not isinstance(final_paths, list) or not final_paths:
                errors.append('runtime_manifest_final_image_paths_required')
            else:
                declared = {absolute(path) for path in final_paths}
                reviewed = {image['path']: image['sha256'] for image in reviewed_images}
                if declared != set(reviewed) or any(registered.get(path) != digest for path, digest in reviewed.items()):
                    errors.append('runtime_reviewed_images_differ_from_submitted_manifest')
        content = inspect(read_latest(Path(content_ledger) if content_ledger else DEFAULT_LEDGER),
                          source_key, publication_latest={}, verify_files=True)
        event = content.get("event") or {}
        if content.get("status") != "produced":
            errors.append("completed_card_package_not_registered")
        if content.get("requires_recovery"):
            errors.append("registered_card_package_requires_recovery")
        if event.get("manifest_sha256") != fingerprint:
            errors.append("registered_package_fingerprint_mismatch")
        required_days=max(evidence.get('minimum_remaining_days',0), manifest_data.get('minimum_remaining_days',0), (runtime_gate or {}).get('minimum_remaining_days',0))
        monitored = bool((runtime_gate or {}).get('board_monitor'))
        if announcement and not monitored:
            errors.append('website_notice_requires_monitored_runtime')
        if monitored and planned_publish_at:
            errors.append('monitored_notice_requires_live_submission')
        if not announcement or period.get('application_end'):
            errors.extend(remaining_period_issues(period, required_days, conservative_date=monitored))
        return {"allowed": not errors, "reasons": errors, "eligibility": period,
                "eligibility_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
                "production_id": event.get("production_id"), "manifest_sha256": fingerprint,
                "runtime_gate":runtime_gate}
    except Exception as exc:
        # Every unreadable/corrupt state is a submission block, never an empty ledger.
        return {"allowed": False, "reasons": ["notice_guard_input_or_history_error"],
                "error": str(exc)}


def check_job(job, job_path):
    """Return None for unrelated creative jobs; notice jobs must pass all channels."""
    import publication_history as history
    source = job.get("source_notice")
    if job.get("workflow") != "notice-to-social" and source is None:
        return None
    if not isinstance(source, dict) or not str(source.get("source_key", "")).startswith("ptp:15:"):
        return {"allowed": False, "reasons": ["notice_source_key_required"]}
    publication = job.get("publication", {})
    if not isinstance(publication, dict):
        return {"allowed": False, "reasons": ["publication_object_required"]}
    base = Path(job_path).resolve().parent

    def resolved(value):
        if not isinstance(value, str) or not value:
            return None
        p = Path(value)
        return str(p if p.is_absolute() else base / p)

    manifest = resolved(publication.get("package_manifest"))
    evidence = resolved(source.get("eligibility_path"))
    check = check_start(source["source_key"], manifest, evidence,
                        planned_publish_at=publication.get("planned_publish_at"))
    if not check["allowed"]:
        return check
    # Production uses the fixed shared ledger. Isolated tests may call check_start directly.
    ledger = Path(__file__).resolve().parent.parent / "state/publication-history.jsonl"
    channels = publication.get("targets")
    if not isinstance(channels, list) or not channels:
        return {"allowed": False, "reasons": ["publication_targets_required"]}
    try:
        with history.ledger_lock(ledger):
            latest = history.read_latest(ledger)
            for channel in channels:
                platform, account = channel["platform"], channel["account_id"]
                if platform not in {"instagram", "facebook"}:
                    raise ValueError("unsupported publication target")
                report = history.inspect(latest, (source["source_key"], platform,
                                         history.canonical_account(account, platform)), check["manifest_sha256"])
                if not report["allowed"]:
                    return {"allowed": False, "reasons": ["existing_or_unresolved_publication"], "history": report}
        return check
    except Exception as exc:
        return {"allowed": False, "reasons": ["publication_history_or_targets_invalid"], "error": str(exc)}
