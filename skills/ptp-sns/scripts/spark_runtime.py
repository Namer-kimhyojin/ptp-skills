#!/usr/bin/env python3
"""Daily industrial explainer schedule and immutable topic reservations."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit

import publication_history as ph
import social_runtime as sr

KEY_PATTERN = r'ptp:spark:industry-daily-\d{4}:ep\d{4}'
SCOPE = 'foundation-meta'


def fingerprint(value):
    return ''.join(ch for ch in unicodedata.normalize('NFKC', value).casefold() if ch.isalnum())


def topic_tokens(topic):
    return {fingerprint(value) for value in [topic['concept_key'], *topic['aliases']]}


def brief_path(policy_path, day):
    return Path(policy_path).resolve().parent / 'daily-topics' / (day.isoformat() + '.json')


def select(policy_path, history, now):
    from series_runtime import channel_actions

    policy = sr.load(policy_path)
    if (policy.get('schema_version') != 1 or policy.get('timezone') != 'Asia/Seoul'
            or policy.get('frequency') != 'daily' or policy.get('min_pages') != 5
            or policy.get('publication_policy') != 'immediate-after-review'):
        raise ValueError('invalid_spark_schedule_policy')
    day = now.astimezone(sr.KST).date()
    manual = day.isoformat() in policy.get('manual_dates', {})
    scheduled = date.fromisoformat(policy['start_date']) <= day <= date.fromisoformat(policy['end_date'])
    if not scheduled and not manual:
        return {'action': 'outside_schedule'}
    context = 'interactive' if manual else 'automation'
    planned = sr.stamp(day.isoformat() + 'T' + policy['start_time'] + ':00+09:00')
    key = f'ptp:spark:industry-daily-{day.year}:ep{day:%m%d}'
    channels = channel_actions(history, key)
    if all(channel['action'] == 'skip' for channel in channels.values()):
        action = 'complete'
    else:
        action = 'wait' if now < planned else 'work'
    path = brief_path(policy_path, day)
    return {'action': action, 'source_key': key, 'day': day.isoformat(),
            'planned_at': planned.isoformat(), 'channels': channels, 'execution_context': context,
            'topic_path': str(path), 'topic_reserved': path.is_file()}


def source_urls(sources, day, policy, *, correction=False):
    if not isinstance(sources, list):
        raise ValueError('spark_sources_required')
    issue_urls, definition_urls = set(), set()
    ages = []
    for source in sources:
        url = urlsplit(source['url'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            raise ValueError('spark_requires_public_https_sources')
        identity = (url.hostname, url.path.rstrip('/'), url.query)
        primary = 'service-primary' if correction else 'issue-primary'
        if source['role'] not in {primary, 'definition-primary', 'ptp-primary', 'corroboration'}:
            raise ValueError('invalid_spark_source_role')
        if not all(isinstance(source.get(field), str) and source[field].strip()
                   for field in ('title', 'publisher', 'supports')):
            raise ValueError('spark_source_claim_mapping_required')
        checked = date.fromisoformat(source['checked_date'])
        if checked != day:
            raise ValueError('spark_sources_must_be_checked_on_publication_date')
        if source['role'] == 'definition-primary':
            definition_urls.add(identity)
        if source['role'] == primary:
            issue_urls.add(identity)
        if source['role'] == 'issue-primary':
            age = (day - date.fromisoformat(source['event_date'])).days
            if age < 0 or age > policy['maximum_issue_age_days']:
                raise ValueError('spark_issue_outside_freshness_window')
            ages.append(age)
    if not any(issue != definition for issue in issue_urls for definition in definition_urls):
        raise ValueError('spark_requires_dated_primary_issue_and_separate_definition_sources')
    return min(ages) if ages else 0


def validate_topic(topic, selection, policy_path, *, correction=False):
    if (topic['source_key'] != selection['source_key'] or topic['publish_date'] != selection['day']
            or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', topic['concept_key'])
            or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', topic['issue_key'])):
        raise ValueError('spark_topic_identity_mismatch')
    for field in ('title', 'sector', 'reader_question', 'plain_definition', 'issue_summary',
                  'why_now', 'similarity_review'):
        if not isinstance(topic[field], str) or not topic[field].strip():
            raise ValueError('spark_topic_field_required:' + field)
    if not isinstance(topic['aliases'], list) or not topic['aliases'] or any(
            not isinstance(alias, str) or not fingerprint(alias) for alias in topic['aliases']):
        raise ValueError('spark_concept_aliases_required')
    if type(topic['page_count']) is not int or topic['page_count'] < 5 or not topic['page_count_reason'].strip():
        raise ValueError('spark_page_count_and_reason_required')
    if topic.get('mascots') != 'excluded':
        raise ValueError('spark_mascots_must_be_excluded')
    policy = sr.load(policy_path)
    if correction and not str(topic.get('correction_reason', '')).strip():
        raise ValueError('spark_correction_requires_user_request')
    day = date.fromisoformat(selection['day'])
    age = source_urls(topic['sources'], day, policy, correction=correction)
    if age > policy['freshness_days'] and not str(topic.get('extended_window_reason', '')).strip():
        raise ValueError('spark_extended_window_requires_reason')
    connection = topic.get('ptp_connection')
    direct_required = day >= date.fromisoformat(policy.get('direct_ptp_evidence_required_from', '0001-01-01'))
    if direct_required or connection is not None:
        validate_ptp_connection(connection, topic, direct_required=direct_required)
    topic_dir = brief_path(policy_path, day).parent
    for path in (*topic_dir.glob('????-??-??.json'), *topic_dir.glob('????-??-??.correction.json')):
        old = sr.load(path)
        if old['source_key'] == topic['source_key']:
            continue
        if (topic_tokens(topic) & topic_tokens(old)
                or topic['issue_key'] == old['issue_key']
                or any(fingerprint(topic[field]) == fingerprint(old[field])
                       for field in ('title', 'reader_question', 'plain_definition'))):
            raise ValueError('spark_topic_duplicates:' + old['source_key'])


def validate_ptp_connection(connection, topic, *, direct_required):
    if not isinstance(connection, dict):
        raise ValueError('spark_ptp_connection_review_required')
    if not direct_required and connection.get('status') == 'unverified':
        if isinstance(connection.get('reason'), str) and connection['reason'].strip():
            return
        raise ValueError('spark_unverified_ptp_connection_requires_reason')
    urls = connection.get('source_urls')
    allowed = {source['url'] for source in topic['sources']}
    if (connection.get('status') != 'verified'
            or not all(isinstance(connection.get(field), str) and connection[field].strip()
                       for field in ('team', 'support', 'story_link'))
            or type(connection.get('page')) is not int
            or not 1 <= connection['page'] <= topic['page_count']
            or not isinstance(urls, list) or not urls
            or any(not isinstance(url, str) or url not in allowed for url in urls)):
        raise ValueError('spark_verified_ptp_connection_requires_page_and_official_sources')
    if not direct_required:
        return
    if (connection.get('role') not in {'operator', 'supporter'}
            or not all(isinstance(connection.get(field), str) and connection[field].strip()
                       for field in ('program', 'direct_relevance'))):
        raise ValueError('spark_requires_direct_ptp_role_and_same_topic')
    proof = connection.get('official_evidence')
    if not isinstance(proof, dict) or not all(
            isinstance(proof.get(field), str) and proof[field].strip()
            for field in ('url', 'locator', 'excerpt')):
        raise ValueError('spark_requires_official_ptp_evidence_with_locator')
    primary_urls = {source['url'] for source in topic['sources'] if source['role'] == 'ptp-primary'}
    host = (urlsplit(proof['url']).hostname or '').lower().rstrip('.')
    ptp_site = host == 'ptp.or.kr' or host.endswith('.ptp.or.kr')
    public_site = host.endswith(('.go.kr', '.gov.kr')) or host == 'gov.kr'
    if (proof['url'] not in urls or proof['url'] not in primary_urls
            or not (ptp_site or public_site)):
        raise ValueError('spark_requires_ptp_or_government_primary_source')
    if not ptp_site and not any(actor in fingerprint(proof['excerpt'])
                               for actor in ('포항테크노파크', '포항tp', 'pohangtechnopark', 'pohangtp')):
        raise ValueError('spark_official_evidence_must_identify_pohang_tp')


def require_owner(policy_path, selection, run_id):
    owner = sr.load(sr.owner_path(sr.RUNTIME, SCOPE))
    if (owner['run_id'] != run_id or owner['source_key'] != selection['source_key']
            or owner['plan_sha256'] != sr.sha(policy_path)
            or owner['execution_context'] != selection['execution_context']):
        raise ValueError('spark_owner_or_policy_mismatch')
    return owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('select', 'check-topic', 'begin', 'reserve'))
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--triggered-at')
    parser.add_argument('--context', choices=('automation', 'interactive'), default='automation')
    parser.add_argument('--run-id')
    parser.add_argument('--brief', type=Path)
    parser.add_argument('--ledger', type=Path, default=sr.ROOT/'state/publication-history.jsonl')
    args = parser.parse_args()
    if args.command == 'begin' and args.context == 'automation' and not args.triggered_at:
        parser.error('begin requires the original --triggered-at timestamp')
    if args.command == 'reserve' and (not args.run_id or not args.brief):
        parser.error('reserve requires --run-id and --brief')
    if args.command == 'check-topic' and not args.brief:
        parser.error('check-topic requires --brief')
    with ph.ledger_lock(args.ledger):
        now = sr.current_time()
        policy_sha = sr.sha(args.policy)
        result = select(args.policy, ph.read_latest(args.ledger), now)
        if args.command != 'select' and result['action'] != 'work':
            raise ValueError('spark_not_due:' + result['action'])
        if args.command == 'check-topic':
            validate_topic(sr.load(args.brief), result, args.policy)
            result['topic_eligible'] = True
        if args.command == 'begin':
            if args.context != result['execution_context']:
                raise ValueError('spark_execution_context_mismatch')
            if args.triggered_at and sr.stamp(args.triggered_at).date() != now.date():
                raise ValueError('spark_trigger_does_not_match_publication_date')
            if sr.sha(args.policy) != policy_sha:
                raise ValueError('spark_policy_changed')
            result['owner'] = sr.claim(sr.RUNTIME, SCOPE, result['source_key'], 'publish',
                                       result['planned_at'], args.context, plan_sha256=policy_sha,
                                       triggered_at=args.triggered_at)
        if args.command == 'reserve':
            require_owner(args.policy, result, args.run_id)
            path = Path(result['topic_path'])
            topic = sr.load(args.brief)
            if topic.get('ptp_connection') is None:
                raise ValueError('spark_ptp_connection_review_required')
            validate_topic(topic, result, args.policy)
            if path.exists():
                if sr.load(path) != topic:
                    raise ValueError('spark_daily_topic_already_reserved')
            else:
                sr.atomic_json(path, topic)
            result.update(topic_reserved=True, topic_sha256=sr.sha(path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        main()
    except (OSError, TypeError, ValueError, KeyError, AttributeError, ph.HistoryError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
