#!/usr/bin/env python3
"""Select a due webtoon, bind its reviewed package, and reconcile each channel."""
import argparse
import json
import re
from pathlib import Path
import sys

from content_history import DEFAULT_LEDGER, HistoryError as ProductionError, verify_manifest
from content_history import read_latest as read_production
from content_preflight import validate_report
import publication_history as ph
import social_runtime as sr

SCOPE = 'foundation-meta'
PLATFORMS = ('instagram', 'facebook')


def accounts():
    config = sr.load(sr.ROOT / 'config/social-accounts.json')
    return {platform: config[platform]['account_id'] for platform in PLATFORMS}


def channel_actions(history, source_key):
    actions = {}
    for platform, account in accounts().items():
        identity = (source_key, platform, ph.canonical_account(account, platform))
        report = ph.inspect(history, identity, None)
        attempts = report['blocking_attempts']
        if len(attempts) > 1:
            actions[platform] = {'action': 'reconcile', 'attempts': attempts}
        elif attempts:
            event = attempts[0]
            action = 'skip' if event['status'] in ph.SUCCESS else 'reconcile'
            actions[platform] = {'action': action, 'event': event}
        else:
            failed = [event for event in history.values() if ph.key(event) == identity and event['status'] == 'failed']
            actions[platform] = {'action': 'pending'}
            if failed:
                actions[platform]['event'] = max(failed, key=lambda event: sr.stamp(event['recorded_at']))
    return actions


def select(plan, execution, history, now, *, recovery_key=None):
    now = now.astimezone(sr.KST)
    day = now.date().isoformat()
    if (execution['timezone'] != 'Asia/Seoul' or plan['end_date'] != execution['end_date']
            or plan['automation']['production_time'] != execution['production_time']
            or execution.get('publication_policy') != 'immediate-after-review'
            or plan['automation'].get('publication_policy') != execution['publication_policy']):
        raise ValueError('series_plan_execution_mismatch')
    if day > execution['end_date']:
        return {'action': 'ended'}
    if execution.get('status') != 'active':
        return {'action': 'inactive'}
    if recovery_key:
        authorization = execution.get('interactive_recoveries', {}).get(recovery_key, {})
        if authorization.get('authorized_date') != day or not str(authorization.get('reason', '')).strip():
            raise ValueError('series_recovery_requires_current_dated_authorization')
        rows = [row for row in plan['episodes'] if row['source_key'] == recovery_key and row['date'] < day]
        if len(rows) != 1:
            raise ValueError('series_recovery_requires_one_missed_episode')
    else:
        rows = [row for row in plan['episodes'] if row['date'] == day]
    if not rows:
        return {'action': 'no_episode'}
    if len(rows) != 1 or rows[0]['timezone'] != 'Asia/Seoul':
        raise ValueError('invalid_series_assignment')
    row = rows[0]
    if row['episode'] < execution['immediate_from_episode']:
        return {'action': 'historical_episode'}
    if row.get('production_time') != execution['production_time'] or row.get('publication_policy') != execution['publication_policy']:
        raise ValueError('episode_policy_mismatch')
    planned = sr.stamp(row['date'] + 'T' + execution['production_time'] + ':00+09:00')
    channels = channel_actions(history, row['source_key'])
    state = execution['episodes'][str(row['episode'])]
    for platform, channel in channels.items():
        summary = state.get('channels', {}).get(platform)
        if isinstance(summary, dict):
            summary = summary.get('status')
        if ('event' not in channel and channel['action'] == 'pending'
                and (str(summary).startswith('published') or summary in {'scheduled', 'submitting', 'unknown'})):
            channel.update(action='reconcile', reason='summary_without_matching_ledger')
    result = {'episode': row['episode'], 'source_key': row['source_key'],
              'planned_at': planned.isoformat(), 'channels': channels}
    if all(c['action'] == 'skip' for c in channels.values()):
        action = 'complete'
    elif now < planned:
        action = 'wait'
    else:
        action = 'work'
    return dict(result, action=action)


def submission_guard(manifest_path, source_key, platform, account, history, now=None, *, replacement=False):
    """Called under the publication ledger lock for each new series submission."""
    now = sr.current_time() if now is None else now.astimezone(sr.KST)
    manifest_path = Path(manifest_path).resolve()
    manifest = sr.load(manifest_path)
    if manifest.get('runtime_contract_version') != 1:
        raise ValueError('series_runtime_contract_required')
    contract = manifest['runtime']
    from spark_runtime import KEY_PATTERN, select as select_spark, validate_topic
    spark = re.fullmatch(KEY_PATTERN, source_key)
    plan_path = Path(contract['plan_path'])
    if contract.get('scope') != SCOPE:
        raise ValueError('series_scope_mismatch')
    owner = sr.load(sr.owner_path(sr.RUNTIME, SCOPE))
    topic_digest = None
    if spark:
        selection = select_spark(plan_path, history, now)
        if (selection.get('source_key') != source_key or selection['action'] not in ('work', 'complete')
                or not selection['topic_reserved']
                or owner.get('execution_context') != selection['execution_context']):
            raise ValueError('spark_no_reserved_topic_for_active_day')
        topic_path = Path(selection['topic_path'])
        if replacement:
            if owner['execution_context'] != 'interactive' or contract.get('replaces_topic_sha256') != sr.sha(topic_path):
                raise ValueError('spark_correction_requires_interactive_owner_and_original_topic')
            topic_path = topic_path.with_suffix('.correction.json')
        elif selection['action'] != 'work' or selection['channels'][platform]['action'] != 'pending':
            raise ValueError('spark_reconcile_or_preserve_existing_channel')
        topic = sr.load(topic_path)
        validate_topic(topic, selection, plan_path, correction=replacement)
        topic_digest = sr.sha(topic_path)
        if topic_digest != contract.get('topic_sha256'):
            raise ValueError('spark_reserved_topic_digest_mismatch')
        planned_at = selection['planned_at']
    elif replacement:
        plan = sr.load(plan_path)
        if owner['execution_context'] != 'interactive':
            raise ValueError('series_replacement_requires_interactive_owner')
        rows = [row for row in plan['episodes'] if row['source_key'] == source_key]
        if len(rows) != 1:
            raise ValueError('series_replacement_episode_not_in_plan')
        planned_at = owner['planned_at']
    else:
        plan = sr.load(plan_path)
        execution = sr.load(contract['execution_path'])
        selection = select(plan, execution, history, now)
        if selection.get('source_key') != source_key and owner['execution_context'] == 'interactive':
            selection = select(plan, execution, history, now, recovery_key=source_key)
        if selection.get('source_key') != source_key or selection['action'] != 'work':
            raise ValueError('series_not_due_now')
        if selection['channels'][platform].get('reason') == 'summary_without_matching_ledger':
            raise ValueError('reconcile_channel_summary_first')
        planned_at = selection['planned_at']
    if (owner['source_key'] != source_key or owner['phase'] != 'publish'
            or owner['stage'] not in {'ready', 'submission', 'verification'}
            or owner['plan_sha256'] != sr.sha(plan_path)):
        raise ValueError('active_series_owner_or_plan_mismatch')
    preflight = owner['preflight']
    observation = sr.load(preflight['path'])
    if (sr.sha(preflight['path']) != preflight['sha256'] or observation.get('passed') is not True
            or observation.get('execution_context') != owner['execution_context']
            or not -60 <= (now - sr.stamp(observation['observation_at'])).total_seconds() <= 600
            or ph.canonical_account(observation['verified_accounts'][platform], platform) != ph.canonical_account(account, platform)):
        raise ValueError('refresh_series_preflight_for_target_account')
    quality = owner['quality']
    if sr.sha(quality['path']) != quality['sha256'] or validate_report(Path(quality['path']), source_key):
        raise ValueError('series_review_changed_or_failed')
    report = sr.load(quality['path'])
    reviewed = [Path(image['path']).resolve() for image in report['images']]
    declared = [(manifest_path.parent / path).resolve() for path in manifest['final_image_paths']]
    if declared != reviewed or (len(declared) != topic['page_count'] if spark else not 5 <= len(declared) <= 7):
        raise ValueError('series_reviewed_image_order_or_count_mismatch')
    if spark and (sr.load(report['spec_path']).get('industry_topic_sha256') != topic_digest
                  or not any(item['sha256'] == topic_digest for item in manifest['files'])):
        raise ValueError('spark_review_and_package_must_include_reserved_topic')
    try:
        package = verify_manifest(manifest_path, source_key)
        production = read_production(DEFAULT_LEDGER).get(source_key, {})
    except ProductionError as exc:
        raise ValueError(str(exc)) from exc
    registered = {(manifest_path.parent / item['file']).resolve() for item in manifest['files']}
    if not set(declared).issubset(registered):
        raise ValueError('series_reviewed_images_not_registered_in_manifest')
    if production.get('status') != 'produced' or production.get('manifest_sha256') != package['manifest_sha256']:
        raise ValueError('series_production_registration_mismatch')
    return {'allowed': True, 'runtime_run_id': owner['run_id'], 'source_key': source_key,
            'platform': platform, 'checked_at': now.isoformat(),
            'planned_at': planned_at, 'manifest_sha256': package['manifest_sha256']}


def refresh_execution(execution_path, plan_path, history, source_key, *, results_path=None):
    """Idempotently project channel evidence without rewriting an original event."""
    execution = sr.load(execution_path)
    plan = sr.load(plan_path)
    row = next(row for row in plan['episodes'] if row['source_key'] == source_key)
    state = execution['episodes'][str(row['episode'])]
    actions = channel_actions(history, source_key)
    recorded = {p: item['event'] for p, item in actions.items() if 'event' in item}
    if not recorded:
        return state
    state.setdefault('channels', {})
    state.setdefault('urls', {})
    state.setdefault('attempts', {})
    if not isinstance(state.get('published_at'), dict):
        state['published_at'] = {}
    previous_ids = dict(state['attempts'])
    for platform, event in recorded.items():
        status = event['status']
        if (previous_ids.get(platform) != event['attempt_id']
                or not str(state['channels'].get(platform)).startswith('published') or status != 'published'):
            state['channels'][platform] = 'published-confirmed-in-Meta' if status == 'published' else status
        state['attempts'][platform] = event['attempt_id']
        if event.get('remote_url'):
            state['urls'][platform] = event['remote_url']
        elif previous_ids.get(platform) != event['attempt_id']:
            state['urls'].pop(platform, None)
        if event.get('published_at'):
            state['published_at'][platform] = event['published_at']
        elif previous_ids.get(platform) != event['attempt_id']:
            state['published_at'].pop(platform, None)
    if results_path:
        evidence = sr.load(results_path)
        if evidence['source_key'] != source_key:
            raise ValueError('publication_results_source_mismatch')
        for platform, info in evidence['channels'].items():
            event = recorded.get(platform, {})
            if (event.get('status') != 'published' or info['attempt_id'] != event.get('attempt_id')
                    or info['post_id'] != event.get('post_id') or info['url'] != event.get('remote_url')):
                raise ValueError('publication_results_do_not_match_ledger')
            if info.get('public_verified') is True:
                verify_public_evidence(info, evidence, results_path)
                state['channels'][platform] = 'published-publicly-verified'
        state['publication_results'] = str(Path(results_path).resolve())
        if 'card_count' in evidence:
            state['card_count'] = evidence['card_count']
    if all(str(state['channels'].get(p)).startswith('published') for p in PLATFORMS):
        state['status'] = 'published'
        state.pop('blocker', None)
        state.pop('resume_stage', None)
    elif any(item['action'] == 'reconcile' for item in actions.values()):
        state['status'] = 'reconcile'
    else:
        state['status'] = 'partial'
    now = sr.current_time().isoformat()
    progress = execution.get('in_progress')
    if state['status'] == 'published' and progress and progress.get('source_key') == source_key:
        execution['in_progress'] = None
    next_row = next((item for item in plan['episodes'] if item['episode'] > row['episode']), None)
    if state['status'] == 'published' and execution.get('next_episode') == row['episode']:
        execution.update(next_episode=next_row['episode'] if next_row else None,
                         next_scheduled_date=next_row['date'] if next_row else None)
    execution.update(updated_at=now, last_checked_at=now,
                     last_execution={'episode': row['episode'], 'source_key': source_key,
                                     'status': state['status'], 'checked_at': now})
    sr.atomic_json(execution_path, execution)
    return state


def verify_public_evidence(info, evidence, results_path):
    count = evidence['card_count']
    if (not 5 <= count <= 7 or info['card_order'] != list(range(1, count + 1))
            or info.get('alt_text_verified') is not True
            or info.get('ai_display') not in {'native-label', 'caption-disclosure', 'native-and-caption', 'unverified'}
            or not str(info.get('observation', '')).strip()):
        raise ValueError('series_public_readback_incomplete')
    qr = sr.load(Path(results_path).parent / info['served_qr_report'])
    image = qr['image_verification']
    scales = {check['scale'] for check in image['checks'] if check.get('passed') is True}
    if (qr.get('passed') is not True or image.get('passed') is not True
            or qr.get('expected_url') != evidence['qr_url'] or not {1.0, 0.5}.issubset(scales)
            or sr.sha(image['image']) != image['sha256']):
        raise ValueError('series_platform_qr_evidence_invalid')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('select', 'begin', 'gate', 'refresh'))
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--execution', type=Path)
    parser.add_argument('--ledger', type=Path, default=sr.ROOT / 'state/publication-history.jsonl')
    parser.add_argument('--triggered-at', help='Original heartbeat time with timezone')
    parser.add_argument('--context', choices=('automation', 'interactive'), default='automation')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--source-key')
    parser.add_argument('--platform', choices=PLATFORMS)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--results', type=Path)
    parser.add_argument('--replacement', action='store_true')
    parser.add_argument('--recover-source-key', help='Explicitly authorized missed episode for interactive select or begin')
    args = parser.parse_args()
    if args.recover_source_key and (args.command not in {'select', 'begin'} or args.context != 'interactive'):
        parser.error('--recover-source-key requires interactive select or begin')
    required = {'gate': ('manifest', 'source_key', 'platform', 'report', 'preview'),
                'refresh': ('plan', 'execution', 'source_key')}.get(args.command, ('plan', 'execution'))
    for name in required:
        if not getattr(args, name):
            parser.error('--' + name.replace('_', '-') + ' is required for ' + args.command)
    with ph.ledger_lock(args.ledger):
        history = ph.read_latest(args.ledger)
        if args.command == 'gate':
            result = submission_guard(args.manifest, args.source_key, args.platform,
                                      accounts()[args.platform], history, replacement=args.replacement)
            preview = sr.load(args.preview)
            if (preview.get('platform') != args.platform
                    or preview.get('manifest_sha256') != result['manifest_sha256']
                    or not str(preview.get('observation', '')).strip()
                    or not all(preview.get(field) is True for field in (
                        'order_verified', 'alt_text_verified', 'caption_verified', 'public_audience',
                        'no_crop_warning', 'immediate_publish_enabled', 'no_extra_sharing'))):
                raise ValueError('series_channel_preview_incomplete')
            result.update(preview_path=str(args.preview.resolve()), preview_sha256=sr.sha(args.preview))
            sr.immutable_json(args.report, result)
        elif args.command == 'refresh':
            owner = sr.load(sr.owner_path(sr.RUNTIME, SCOPE))
            if owner['source_key'] != args.source_key or owner['plan_sha256'] != sr.sha(args.plan):
                raise ValueError('refresh_requires_current_series_owner')
            result = refresh_execution(args.execution, args.plan, history, args.source_key,
                                       results_path=args.results)
        else:
            plan_sha = sr.sha(args.plan)
            result = select(sr.load(args.plan), sr.load(args.execution), history, sr.current_time(),
                            recovery_key=args.recover_source_key)
            if args.command == 'begin' and result['action'] == 'work':
                if args.context == 'automation' and not args.triggered_at:
                    raise ValueError('actual_heartbeat_timestamp_required')
                if sr.sha(args.plan) != plan_sha:
                    raise ValueError('series_plan_changed_since_selection')
                result['owner'] = sr.claim(sr.RUNTIME, SCOPE, result['source_key'], 'publish',
                                           result['planned_at'], args.context, plan_sha256=plan_sha,
                                           triggered_at=args.triggered_at)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, ph.HistoryError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
