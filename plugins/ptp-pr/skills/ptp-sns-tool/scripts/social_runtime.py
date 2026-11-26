#!/usr/bin/env python3
"""PTP schedule, execution ownership and observable runtime evidence.

No browser is controlled and no post is submitted by this CLI. Browser facts
come from the current CUA UI; publication facts remain in the existing ledgers.
Production CLI uses the actual clock. Injectable clocks are for isolated tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from publication_history import HistoryError, canonical_account, ledger_lock, read_latest

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
RUNTIME = ROOT / 'state' / 'runtime'
PHASE_TIME = {'prepare': '11:00', 'publish': '14:00', 'monitor': '11:20'}
STAGES = ['preflight', 'source', 'duplicate-check', 'production', 'quality', 'ready', 'submission', 'verification']


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError('explicit timezone required')
    return d.astimezone(KST)


def current_time():
    return datetime.now(KST)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + str(uuid.uuid4()) + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def immutable_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def batch_authorization(plan, day, source_key=None):
    """A dated, file-bound user request may replace the one-notice cadence."""
    batch = plan.get('batch_publication')
    if not batch or batch.get('date') != day:
        return None
    evidence = load(batch['authorization_path'])
    if sha(batch['authorization_path']) != batch['authorization_sha256']:
        raise ValueError('batch_authorization_changed')
    for field in ('id', 'date', 'source_keys', 'already_published_source_keys', 'minimum_remaining_days'):
        if evidence.get(field) != batch.get(field):
            raise ValueError('batch_authorization_scope_mismatch:' + field)
    keys = batch['source_keys']
    if (not evidence.get('user_request') or not isinstance(keys, list) or not keys
            or len(set(keys)) != len(keys) or any(not k.startswith('ptp:15:') for k in keys)
            or not isinstance(batch['minimum_remaining_days'], int) or batch['minimum_remaining_days'] < 0):
        raise ValueError('invalid_batch_authorization')
    if source_key is not None and source_key not in keys:
        return None
    return batch


def validate_schedule(plan, execution):
    errors = []
    if plan.get('timezone') != 'Asia/Seoul' or execution.get('timezone') != 'Asia/Seoul':
        errors.append('timezone_must_be_Asia/Seoul')
    rows = plan.get('schedule')
    if not isinstance(rows, list) or not rows:
        return errors + ['schedule_required']
    seen, per_day = set(), {}
    allowed = {str(x) for x in execution.get('allowed_notice_ids', [])}
    forbidden = {str(x) for x in execution.get('held_notice_ids', []) + execution.get('excluded_already_published', [])}
    for row in rows:
        try:
            ident = str(row['board_id'])
            board = str(row.get('manage_idx', '15'))
            if board != '15' and not (board == '2' and plan.get('board_monitor')):
                raise ValueError('board_not_authorized')
            key = f'ptp:{board}:{ident}'
            day = datetime.strptime(row['publish_date'], '%Y-%m-%d').date().isoformat()
            if row.get('source_key') != key or not ident.isdigit() or ident in seen:
                raise ValueError('duplicate or invalid source identity')
            seen.add(ident)
            if ident not in allowed or ident in forbidden:
                errors.append('unapproved_notice:' + ident)
            state = execution['entries'][key]
            if state.get('scheduled_date') != day:
                errors.append('plan_state_date_mismatch:' + ident)
            # Past exceptions remain historical. Future/new assignments must
            # never share a day; successful historical exceptions are retained.
            per_day.setdefault(day, []).append((ident, state))
            if not plan['start_date'] <= day <= plan['end_date']:
                errors.append('date_outside_plan:' + ident)
            if row.get('timezone', 'Asia/Seoul') != 'Asia/Seoul':
                errors.append('row_timezone_mismatch:' + ident)
        except (KeyError, ValueError, TypeError) as exc:
            errors.append('invalid_row:' + str(exc))
    for day, items in per_day.items():
        if len(items) > 1 and not all(x[1].get('status') == 'published' for x in items):
            try:
                batch = batch_authorization(plan, day)
                permitted = set(batch['source_keys'] + batch['already_published_source_keys']) if batch else set()
                if not batch or not {'ptp:15:' + x[0] for x in items} <= permitted:
                    errors.append('multiple_notices_on_day:' + day)
            except (OSError, KeyError, ValueError, TypeError) as exc:
                errors.append('invalid_batch:' + str(exc))
    if plan.get('end_date') != execution.get('end_date'):
        errors.append('end_date_mismatch')
    return errors


def channel_state(state, platform, key, remote_history):
    channel = state.get('channels', {}).get(platform, {})
    account = canonical_account(channel.get('account', ''), platform)
    matching = [e for e in remote_history.values() if e['source_key'] == key
                and e['platform'] == platform and canonical_account(e['account'], platform) == account]
    # read_latest validates transitions. A terminal or unresolved event takes
    # precedence over a stale per-schedule summary.
    statuses = {e['status'] for e in matching} | {channel.get('status')}
    if statuses & {'published', 'scheduled'}:
        action = 'skip'
    elif statuses & {'submitting', 'unknown'}:
        action = 'reconcile'
    else:
        action = 'pending'
    return {'account': account, 'action': action, 'recorded_status': channel.get('status'),
            'attempt_ids': list(dict.fromkeys([e['attempt_id'] for e in matching] + ([channel['attempt_id']] if channel.get('attempt_id') else [])))}


def select_today(plan, execution, phase, history, now=None):
    now = current_time() if now is None else now.astimezone(KST)
    errors = validate_schedule(plan, execution)
    result = {'allowed_to_work': False, 'phase': phase, 'checked_at': now.isoformat(),
              'timezone': 'Asia/Seoul', 'errors': errors, 'submits_posts': False}
    if errors:
        return result
    day = now.date().isoformat()
    if not plan['start_date'] <= day <= plan['end_date']:
        result['reason'] = 'outside_authorized_dates'; return result
    today_rows = [r for r in plan['schedule'] if r['publish_date'] == day]
    row = next((r for r in today_rows if not all(channel_state(execution['entries'][r['source_key']], p, r['source_key'], history)['action'] == 'skip' for p in ('instagram', 'facebook'))), today_rows[0] if today_rows else None)
    if row is None:
        result['reason'] = 'no_assignment_today'; return result
    key = row['source_key']; state = execution['entries'][key]
    channels = {p: channel_state(state, p, key, history) for p in ('instagram', 'facebook')}
    target = row.get('publish_time', plan.get('daily_publish_time', '14:00')) if phase == 'publish' else plan.get('prepare_time', PHASE_TIME[phase])
    if phase == 'monitor':
        target = PHASE_TIME['monitor']
    planned = stamp(day + 'T' + target + ':00+09:00')
    result.update(source_key=key, board_id=row['board_id'], channels=channels,
                  planned_at=planned.isoformat(), start_delay_seconds=round((now-planned).total_seconds()),
                  production_id=state.get('production_id'), package_path=state.get('package_path'),
                  resume_point=state.get('resume_point'))
    if all(c['action'] == 'skip' for c in channels.values()):
        result['reason'] = 'all_channels_already_complete'; return result
    if any(c['action'] == 'reconcile' for c in channels.values()):
        result['reason'] = 'original_attempt_requires_reconciliation'; return result
    # Existing partial success for this same notice is permitted. Another
    # notice actually published today prevents a new notice, even if its old
    # planned date differs from its actual date.
    published_today = set()
    for e in history.values():
        if e.get('status') == 'published' and e.get('source_key','').startswith('ptp:15:'):
            when = e.get('published_at') or e.get('recorded_at')
            if when and stamp(when).date().isoformat() == day:
                published_today.add(e['source_key'])
    for k, e in execution['entries'].items():
        for c in e.get('channels', {}).values():
            if c.get('status') == 'published' and c.get('published_at') and stamp(c['published_at']).date().isoformat() == day:
                published_today.add(k)
    try:
        batch = batch_authorization(plan, day, key)
    except (OSError, KeyError, ValueError, TypeError) as exc:
        result['reason'] = 'invalid_batch:' + str(exc); return result
    permitted_today = set(batch['source_keys'] + batch['already_published_source_keys']) if batch else {key}
    if plan.get('board_monitor'):
        from board_monitor import check_window
        try:
            check_window(plan, key, history, now)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            result['reason'] = str(exc)
            return result
    elif published_today - permitted_today:
        result['reason'] = 'another_notice_published_today'; return result
    result['submission_not_before']=planned.isoformat() if phase=='publish' else None
    result['submission_time_reached']=phase=='publish' and now>=planned
    if now < planned - (timedelta(minutes=15) if phase=='publish' else timedelta(0)):
        result['reason'] = 'before_phase_time'; return result
    if state.get('status') == 'published':
        result['reason'] = 'published_summary_requires_reconciliation'; return result
    result.update(allowed_to_work=True, reason='assigned_work_only', fresh_remote_check_required=True)
    if batch:
        result.update(batch_id=batch['id'], requires_interactive_batch=True)
    return result


def evaluate_preflight(observation, expected_accounts, execution_context, now=None):
    now = current_time() if now is None else now.astimezone(KST)
    result = {'passed': False, 'checked_at': now.isoformat(), 'execution_context': execution_context,
              'evidence_validation_only': True, 'unattended_success_verified': False}
    try:
        age = (now - stamp(observation['checked_at'])).total_seconds()
        if not -60 <= age <= 600:
            raise ValueError('preflight_evidence_stale_or_future')
        if observation.get('execution_context') != execution_context:
            raise ValueError('execution_context_mismatch')
        if not observation.get('evidence') or not isinstance(observation.get('evidence'), str):
            raise ValueError('actual_ui_evidence_required')
        if observation.get('browser') != 'iab':
            raise ValueError('designated_browser_required')
        if observation.get('browser_available') is not True:
            raise ValueError('browser_unavailable')
        if observation.get('open_result') == 'queued' and observation.get('reattached_after_open') is not True:
            raise ValueError('browser_open_queued_not_connected')
        status = observation.get('session_status')
        if status in {'login_required', 'challenge_required'}:
            raise ValueError(status)
        if status != 'target_verified':
            raise ValueError('target_permission_not_verified')
        for platform, account in expected_accounts.items():
            actual = observation.get('accounts', {}).get(platform, {})
            if canonical_account(actual.get('account', ''), platform) != canonical_account(account, platform):
                raise ValueError('wrong_target:' + platform)
            if actual.get('can_create_post') is not True:
                raise ValueError('permission_missing:' + platform)
        result.update(passed=True, state='target_verified', observation_at=observation['checked_at'],
                      unattended_success_verified=execution_context == 'automation',
                      verified_accounts={p:canonical_account(a,p) for p,a in expected_accounts.items()})
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        result['state'] = str(exc)
    return result


def owner_path(directory, scope):
    return Path(directory) / ('owner-' + hashlib.sha256(scope.encode()).hexdigest()[:24] + '.json')


def append_runtime(directory, event):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'execution-events.jsonl'
    with ledger_lock(path):
        # Fail closed on torn history, preserving it for reconciliation.
        if path.exists():
            raw=path.read_text('utf-8')
            if raw and not raw.endswith('\n'):raise ValueError('runtime_history_truncated')
            for line in raw.splitlines():
                if not line or not isinstance(json.loads(line), dict):
                    raise ValueError('runtime_history_corrupt')
        with path.open('a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n'); f.flush(); os.fsync(f.fileno())


def claim(directory, scope, source_key, phase, planned_at, context, now=None, plan_sha256=None, triggered_at=None):
    now = current_time() if now is None else now.astimezone(KST)
    if phase not in PHASE_TIME or context not in {'interactive', 'automation'}:
        raise ValueError('invalid phase/context')
    stamp(planned_at)
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    owner = {'run_id': str(uuid.uuid4()), 'scope': scope, 'source_key': source_key,
             'phase': phase, 'execution_context': context, 'stage': 'preflight',
             'planned_at': planned_at, 'started_at': now.isoformat(), 'plan_sha256': plan_sha256,
             'start_delay_seconds': round((now-stamp(planned_at)).total_seconds())}
    if triggered_at is not None:
        trigger = stamp(triggered_at)
        owner['triggered_at_utc'] = trigger.astimezone(timezone.utc).isoformat()
        owner['triggered_at_kst'] = trigger.isoformat()
    target = owner_path(directory, scope)
    # Keep write + initialization serialized with other mutations. An old
    # ownership record is never reclaimed by timeout or PID assumptions.
    with ledger_lock(directory / 'ownership'):
        if target.exists():
            raise ValueError('account_work_already_owned:' + str(target))
        immutable_json(target, owner)
        append_runtime(directory, dict(owner, event='started', recorded_at=now.isoformat()))
    return owner


def change_run(directory, scope, run_id, *, stage=None, outcome=None, evidence=None, now=None):
    now = current_time() if now is None else now.astimezone(KST)
    if not evidence or not Path(evidence).is_file():
        raise ValueError('evidence_file_required')
    directory = Path(directory); target = owner_path(directory, scope)
    with ledger_lock(directory / 'ownership'):
        owner = load(target)
        if owner.get('run_id') != run_id or owner.get('scope') != scope:
            raise ValueError('run_owner_mismatch')
        event = dict(owner, evidence_path=str(Path(evidence).resolve()), evidence_sha256=sha(evidence), recorded_at=now.isoformat())
        if stage is not None:
            if stage not in STAGES:
                raise ValueError('invalid_stage')
            report=load(evidence)
            if stage=='preflight':
                if report.get('passed') is not True or report.get('state')!='target_verified' or report.get('execution_context')!=owner['execution_context']:
                    raise ValueError('passed_preflight_for_this_context_required')
                age=(now-stamp(report['observation_at'])).total_seconds()
                if not -60<=age<=600:raise ValueError('preflight_stale')
                owner['preflight']={'path':str(Path(evidence).resolve()),'sha256':sha(evidence),'observation_at':report['observation_at']}
            elif not owner.get('preflight'):
                raise ValueError('passed_preflight_required_before_work')
            if STAGES.index(stage) < STAGES.index(owner['stage']) and stage!='preflight':
                raise ValueError('cannot_move_run_stage_backwards')
            if stage in {'quality','ready'}:
                from content_preflight import validate_report
                issues=validate_report(Path(evidence),owner['source_key'])
                if issues:raise ValueError('; '.join(issues))
                owner['quality']={'path':str(Path(evidence).resolve()),'sha256':sha(evidence)}
            if stage=='submission':
                if owner['phase']!='publish' or report.get('allowed') is not True or report.get('runtime_run_id')!=run_id:
                    raise ValueError('submission_gate_report_required')
            if stage!='preflight' or owner['stage']=='preflight':owner['stage'] = stage
            event.update(event='stage', stage=stage)
            append_runtime(directory, event)
            atomic_json(target, owner)
        elif outcome in {'prepared', 'blocked', 'reconciled', 'handoff', 'checked'}:
            if outcome=='prepared' and not owner.get('quality'):raise ValueError('quality_report_required_for_prepared')
            event.update(event='finished', outcome=outcome, elapsed_seconds=round((now-stamp(owner['started_at'])).total_seconds()))
            append_runtime(directory, event)
            target.unlink()
        else:
            raise ValueError('invalid_outcome; publication success is recorded only in publication_history')
    return event


def submission_guard(contract, source_key, history, now=None):
    """Called inside the publication ledger lock, without acquiring it again."""
    now=current_time() if now is None else now.astimezone(KST)
    try:
        plan,execution=load(contract['plan_path']),load(contract['execution_path'])
        issues=validate_schedule(plan,execution)
        if issues:raise ValueError('; '.join(issues))
        day=now.date().isoformat()
        rows=[r for r in plan['schedule'] if r['publish_date']==day and r['source_key']==source_key]
        if len(rows)!=1:raise ValueError('not_assigned_today')
        row=rows[0];planned=stamp(day+'T'+row.get('publish_time',plan.get('daily_publish_time','14:00'))+':00+09:00')
        batch=batch_authorization(plan,day,source_key)
        if not plan['start_date']<=day<=plan['end_date'] or now<planned:raise ValueError('outside_authorized_publication_time')
        directory=Path(contract.get('runtime_dir',RUNTIME));scope=contract.get('scope','foundation-meta')
        owner=load(owner_path(directory,scope))
        if owner.get('source_key')!=source_key or owner.get('phase')!='publish' or owner.get('stage') not in {'ready','submission','verification'}:
            raise ValueError('active_publish_run_at_ready_stage_required')
        if batch and owner.get('execution_context')!='interactive':
            raise ValueError('explicit_batch_requires_interactive_run')
        if owner.get('plan_sha256')!=sha(contract['plan_path']):raise ValueError('plan_changed_during_run')
        pf=owner['preflight'];pr=load(pf['path'])
        if sha(pf['path'])!=pf['sha256'] or pr.get('passed') is not True or pr.get('execution_context')!=owner['execution_context']:
            raise ValueError('preflight_changed_or_wrong_context')
        if not -60<=(now-stamp(pr['observation_at'])).total_seconds()<=600:raise ValueError('refresh_preflight_before_submission')
        quality=owner['quality']
        if sha(quality['path'])!=quality['sha256']:raise ValueError('quality_report_changed')
        from content_preflight import validate_report
        issues=validate_report(Path(quality['path']),source_key)
        if issues:raise ValueError('; '.join(issues))
        monitored = bool(plan.get('board_monitor'))
        if monitored:
            from board_monitor import check_window
            check_window(plan, source_key, history, now)
        for e in history.values():
            permitted_today=set(batch['source_keys']+batch['already_published_source_keys']) if batch else {source_key}
            if not monitored and e.get('source_key','').startswith('ptp:15:') and e.get('source_key') not in permitted_today and e.get('status')=='published' and stamp(e.get('published_at') or e['recorded_at']).date().isoformat()==day:
                raise ValueError('another_notice_already_published_today')
            if e.get('source_key')==source_key and e.get('status') in {'unknown','submitting'}:
                if e['status']=='unknown' or e.get('runtime_run_id')!=owner['run_id']:
                    raise ValueError('reconcile_original_submission_before_new_channel')
        reviewed=load(quality['path'])['images']
        return {'allowed':True,'runtime_run_id':owner['run_id'],'verified_accounts':pr.get('verified_accounts',{}),
                'reviewed_images':[{'path':i['path'],'sha256':i['sha256']} for i in reviewed],
                'checked_at':now.isoformat(),'source_key':source_key,'evidence_validation_only':True,
                'board_monitor':monitored,
                'minimum_remaining_days':max(3 if monitored else 0, batch['minimum_remaining_days'] if batch else plan.get('minimum_remaining_days',0))}
    except (OSError,ValueError,TypeError,KeyError) as exc:
        return {'allowed':False,'reason':str(exc),'source_key':source_key}


def display_state(row):
    cs = [v.get('status') for v in row.get('channels', {}).values()]
    if len(cs) >= 2 and all(x == 'published' for x in cs):
        return '게시 완료'
    if any(x in {'unknown', 'submitting'} for x in cs) or row.get('status', '').startswith(('blocked', 'held', 'failed')):
        return '조치 필요'
    if any(x in {'published', 'scheduled'} for x in cs):
        return '조치 필요'
    if row.get('status') in {'ready', 'prepared', 'produced', 'produced-awaiting-browser'}:
        return '게시 준비'
    if row.get('status') in {'producing', 'preparing'}:
        return '제작 중'
    return '대기'


def safe_url(value):
    if not isinstance(value, str):
        return None
    u = urlsplit(value)
    return value if u.scheme == 'https' and u.hostname and not u.username and not u.password else None


def dashboard(plan, execution, series=None, events=None):
    errors = validate_schedule(plan, execution)
    view = []
    for r in sorted(plan['schedule'], key=lambda x: (x['publish_date'], x.get('rank', 0))):
        state = execution['entries'].get(r['source_key'], {})
        view.append({'date': r['publish_date'], 'time': r.get('publish_time', '14:00'), 'kind': '사업공고',
                     'id': str(r['board_id']), 'title': r.get('short', r.get('official_title', '')),
                     'state': display_state(state), 'channels': state.get('channels', {}),
                     'reason': state.get('publish_blocker') or state.get('preparation_blocker') or state.get('resume_point', ''),
                     'deadline': r.get('deadline', ''), 'concept': r.get('concept', ''),
                     'url': r.get('url'), 'history': state.get('schedule_history', []),
                     'plan_detail':{k:r[k] for k in ('official_title','target','benefit','cta','note','condition','layout','characters','hook') if r.get(k)}})
    if series:
        for ident, state in series.get('episodes', {}).items():
            channels = {}
            times = state.get('published_at', {})
            for platform, result in state.get('channels', {}).items():
                channel = dict(result) if isinstance(result, dict) else {'status': result}
                if str(channel['status']).startswith('published'):
                    channel['verification_status'] = channel['status']
                    channel['status'] = 'published'
                    if isinstance(times, dict) and times.get(platform):
                        channel['published_at'] = times[platform]
                channels[platform] = channel
            for platform, url in state.get('urls', {}).items():
                channels.setdefault(platform, {})['url'] = url
            show_immediate = (series.get('publication_policy') == 'immediate-after-review'
                              and str(ident).isdigit() and int(ident) >= series.get('immediate_from_episode', 9))
            time_label = (series['production_time'] + ' 시작 · 검수 직후 게시' if show_immediate
                          else series.get('target_publish_time') or '09:30')
            view.append({'date': state.get('scheduled_date', state.get('publish_date', '')), 'time': time_label,
                         'kind': '웹툰', 'id': str(ident), 'title': state.get('title', '기관소개 웹툰 ' + str(ident) + '화'),
                         'state': ('예약 확인' if len(channels) == 2 and all(c.get('status') == 'scheduled' for c in channels.values())
                                   else display_state(dict(state, channels=channels))), 'channels': channels,
                         'reason': state.get('resume_stage', ''), 'deadline': '', 'concept': '', 'url': None, 'history': []})
    esc = lambda v: html.escape(str(v if v is not None else ''))
    counts = {s: sum(v['state'] == s for v in view) for s in ('대기','제작 중','게시 준비','예약 확인','게시 완료','조치 필요')}
    cards = ''.join('<span><b>'+esc(n)+'</b> '+esc(s)+'</span>' for s,n in counts.items())
    trs=[]
    for r in sorted(view, key=lambda x: (x['date'] or '9999', x['time'], x['kind'], x['id'])):
        links=[]
        for platform in ('instagram','facebook'):
            c=r['channels'].get(platform,{})
            u=safe_url(c.get('url'))
            status = c.get('verification_status', c.get('status','미확인'))
            label=platform+': '+str(status)
            if r['kind'] == '웹툰':
                names = {'published-publicly-verified': '공개 확인', 'published-confirmed-in-Meta': 'Meta 게시 확인',
                         'published': '게시 기록', 'scheduled': '예약 확인', 'submitting': '게시 요청',
                         'unknown': '결과 확인 필요', 'not-submitted': '미제출', 'failed': '확정 실패'}
                label = platform + ' · ' + names.get(status, str(status))
                if c.get('published_at'):
                    label += ' · ' + stamp(c['published_at']).strftime('%m-%d %H:%M KST')
            links.append('<a href="'+esc(u)+'">'+esc(label)+'</a>' if u else esc(label))
        detail=esc(r['reason'])+'<br>접수: '+esc(r['deadline'])+'<br>콘셉트: '+esc(r['concept'])
        if r['history']:
            detail+='<br>재편성 이력: '+esc(json.dumps(r['history'],ensure_ascii=False))
        if r.get('plan_detail'):
            detail+='<br>편성 상세: '+esc(json.dumps(r['plan_detail'],ensure_ascii=False))
        trs.append('<tr><td>'+esc(r['date'] or '편성 데이터 연결 필요')+'<br>'+esc(r['time'])+'</td><td>'+esc(r['kind'])+' '+esc(r['id'])+'</td><td>'+esc(r['title'])+'</td><td>'+esc(r['state'])+'</td><td>'+'<br>'.join(links)+'</td><td><details><summary>상세</summary>'+detail+'</details></td></tr>')
    # Only measured events are summarized; no fabricated on-time/success rates.
    events=events or []
    starts=[e for e in events if e.get('event')=='started']
    delays=[e['start_delay_seconds'] for e in starts if isinstance(e.get('start_delay_seconds'),(int,float))]
    attempts={};metric_warnings=[]
    for event in events:
        if event.get('execution_context')!='automation' or not event.get('evidence_path'):continue
        try:
            if sha(event['evidence_path'])!=event['evidence_sha256']:raise ValueError('evidence_changed')
            evidence=load(event['evidence_path'])
            if evidence.get('execution_context')=='automation' and 'passed' in evidence and 'state' in evidence:
                attempts[event['run_id']]=evidence['passed'] is True
        except (OSError,ValueError,KeyError):metric_warnings.append('runtime_metric_evidence_unavailable')
    notice_rows=[v for v in view if v['kind']=='사업공고']
    metrics={'recorded_runs':len(starts),'max_start_delay_seconds':max(delays) if delays else None,
             'blocked_runs':sum(e.get('outcome')=='blocked' for e in events),
             'automation_preflight_runs':len(attempts),
             'automation_preflight_passed':sum(attempts.values()),
             'automation_preflight_pass_rate':sum(attempts.values())/len(attempts) if attempts else None,
             'notice_scope_count':len(notice_rows),
             'notice_both_channels_published':sum(v['state']=='게시 완료' for v in notice_rows),
             'recorded_user_interventions':sum(e.get('note_type')=='user-intervention' for e in events),
             'recorded_quality_reworks':sum(e.get('note_type')=='quality-rework' for e in events),
             'recorded_duplicate_preventions':sum(e.get('note_type')=='duplicate-prevented' for e in events),
             'warnings':list(dict.fromkeys(metric_warnings))}
    page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>포항TP SNS 운영 현황</title><style>body{font:15px/1.7 "Malgun Gothic",sans-serif;background:#edf2f7;color:#20334c;margin:0}main{max-width:1200px;margin:24px auto;background:white;padding:28px;border-radius:12px}h1{font-size:25px}.counts{display:flex;gap:12px;flex-wrap:wrap}.counts span{background:#eaf2fa;padding:10px 18px;border-radius:6px}.table{overflow:auto}table{border-collapse:collapse;width:100%;min-width:800px}th,td{padding:12px;border:1px solid #d8e1eb;vertical-align:top;text-align:left}th{background:#eaf2fa}a{color:#125ca5}details{max-width:340px;overflow-wrap:anywhere}.warning{color:#a23b23}@media print{body{background:white}main{padding:0;margin:0}details{display:block}tr{break-inside:avoid}}</style><main><h1>포항테크노파크 SNS 운영 현황</h1>'''
    page+='<p>편성 기준: Asia/Seoul · '+esc(plan['start_date'])+' ~ '+esc(plan['end_date'])+' · 출력 갱신 '+esc(current_time().isoformat())+'</p><div class="counts">'+cards+'</div>'
    if errors:
        page+='<p class="warning">편성 불일치: '+esc('; '.join(errors))+'</p>'
    page+='<p>로컬 기록을 정리한 화면입니다. 준비·예약·공개 확인은 구분하며, 과거 확인이 현재 원격 상태를 대신하지 않습니다.</p><div class="table"><table><tr><th>예정(KST)</th><th>구분</th><th>내용</th><th>상태</th><th>채널별 결과</th><th>조치·근거</th></tr>'+''.join(trs)+'</table></div><p>측정된 실행 '+str(metrics['recorded_runs'])+'회 · 차단 '+str(metrics['blocked_runs'])+'회 · 최대 시작 지연 '+esc(metrics['max_start_delay_seconds'] if delays else '미측정')+'</p><details><summary>기록된 운영 지표</summary><pre>'+esc(json.dumps(metrics,ensure_ascii=False,indent=2))+'</pre><p>개입·재작업·중복 차단은 기록된 사건 수이며 전체 발생 건수의 자동 증명을 뜻하지 않습니다. 무인 preflight 기록이 없으면 성공률은 미측정입니다.</p></details></main></html>'
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(['예정일','시각','구분','ID','내용','상태','접수','콘셉트','사유'])
    for r in view:w.writerow([r[k] for k in ('date','time','kind','id','title','state','deadline','concept','reason')])
    return page,buf.getvalue(),{'generated_at':current_time().isoformat(),'errors':errors,'counts':counts,'metrics':metrics,'items':view,'remote_verification_performed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ('select','render','begin'):
        s=sub.add_parser(name);s.add_argument('--plan',type=Path,required=True);s.add_argument('--execution',type=Path,required=True)
        s.add_argument('--publication-ledger',type=Path,default=ROOT/'state/publication-history.jsonl')
        if name in ('select','begin'):s.add_argument('--phase',choices=PHASE_TIME,required=True)
        if name=='render':s.add_argument('--output-dir',type=Path,required=True);s.add_argument('--series',type=Path);s.add_argument('--series-plan',type=Path);s.add_argument('--plan-html',type=Path)
        if name=='begin':s.add_argument('--scope',default='foundation-meta');s.add_argument('--context',choices=['interactive','automation'],required=True);s.add_argument('--runtime-dir',type=Path,default=RUNTIME);s.add_argument('--expected-plan-sha256',required=True)
    s=sub.add_parser('preflight');s.add_argument('--observation',type=Path,required=True);s.add_argument('--context',choices=['interactive','automation'],required=True);s.add_argument('--report',type=Path,required=True);s.add_argument('--accounts',type=Path,default=ROOT/'config/social-accounts.json')
    s.add_argument('--platform', choices=('instagram', 'facebook'), action='append', help='Verify only the observed target channels')
    s=sub.add_parser('submission-check');s.add_argument('--contract',type=Path,required=True);s.add_argument('--source-key',required=True);s.add_argument('--report',type=Path,required=True);s.add_argument('--publication-ledger',type=Path,default=ROOT/'state/publication-history.jsonl')
    s=sub.add_parser('note');s.add_argument('--runtime-dir',type=Path,default=RUNTIME);s.add_argument('--source-key',required=True);s.add_argument('--run-id');s.add_argument('--type',dest='note_type',choices=['user-intervention','quality-rework','duplicate-prevented','source-change'],required=True);s.add_argument('--evidence',type=Path,required=True)
    for name in ('stage','finish'):
        s=sub.add_parser(name);s.add_argument('--runtime-dir',type=Path,default=RUNTIME);s.add_argument('--scope',default='foundation-meta');s.add_argument('--run-id',required=True);s.add_argument('--evidence',type=Path,required=True)
        if name=='stage':s.add_argument('--stage',choices=STAGES,required=True)
        else:s.add_argument('--outcome',choices=['prepared','blocked','reconciled','handoff','checked'],required=True)
    a=p.parse_args()
    try:
        if a.command in ('select','begin','render'):
            plan,execution=load(a.plan),load(a.execution)
            if a.command=='render':
                series=load(a.series) if a.series else None
                if series and a.series_plan:
                    sp=load(a.series_plan)
                    schedule=sp.get('episodes',sp.get('schedule',[]))
                    rows=schedule.values() if isinstance(schedule,dict) else schedule
                    for row in rows:
                        ident=str(row.get('episode',row.get('number',row.get('episode_number',''))))
                        if ident in series.get('episodes',{}):
                            series['episodes'][ident].setdefault('scheduled_date',row.get('publish_date',row.get('date','')))
                            series['episodes'][ident].setdefault('title',row.get('title',''))
                events=[];event_path=RUNTIME/'execution-events.jsonl'
                if event_path.exists():events=[json.loads(l) for l in event_path.read_text('utf-8').splitlines()]
                page,csvtext,summary=dashboard(plan,execution,series,events)
                a.output_dir.mkdir(parents=True,exist_ok=True)
                for name,text,enc in [('운영현황.html',page,'utf-8'),('일일_홍보일정.csv',csvtext,'utf-8-sig')]:
                    tmp=a.output_dir/(name+'.tmp');tmp.write_text(text,encoding=enc);os.replace(tmp,a.output_dir/name)
                if a.plan_html:
                    tmp=a.plan_html.with_name(a.plan_html.name+'.tmp');tmp.write_text(page,encoding='utf-8');os.replace(tmp,a.plan_html)
                atomic_json(a.output_dir/'운영현황.json',summary)
                result={'generated':str(a.output_dir.resolve()),'errors':summary['errors']}
            else:
                with ledger_lock(a.publication_ledger):history=read_latest(a.publication_ledger)
                result=select_today(plan,execution,a.phase,history)
                result['plan_sha256']=sha(a.plan)
                if a.command=='begin':
                    if result['plan_sha256'] != a.expected_plan_sha256:raise ValueError('plan_changed_since_selection')
                    if not result['allowed_to_work']:raise ValueError('not_allowed:'+result.get('reason',str(result['errors'])))
                    result['owner']=claim(a.runtime_dir,a.scope,result['source_key'],a.phase,result['planned_at'],a.context,plan_sha256=result['plan_sha256'])
                    # Detect edits racing with selection. Ownership is retained
                    # as a blocker until the operator reconciles this run.
                    if sha(a.plan)!=result['plan_sha256']:raise ValueError('plan_changed_after_claim; reconcile_owner')
        elif a.command=='preflight':
            accounts=load(a.accounts)
            platforms = a.platform or ('instagram', 'facebook')
            result=evaluate_preflight(load(a.observation),{q:accounts[q]['account_id'] for q in platforms},a.context)
            immutable_json(a.report,result)
        elif a.command=='submission-check':
            with ledger_lock(a.publication_ledger):result=submission_guard(load(a.contract),a.source_key,read_latest(a.publication_ledger))
            immutable_json(a.report,result)
        elif a.command=='note':
            result={'event':'note','note_type':a.note_type,'source_key':a.source_key,'run_id':a.run_id,'evidence_path':str(a.evidence.resolve()),'evidence_sha256':sha(a.evidence),'recorded_at':current_time().isoformat()}
            append_runtime(a.runtime_dir,result)
        else:
            result=change_run(a.runtime_dir,a.scope,a.run_id,stage=a.stage if a.command=='stage' else None,outcome=a.outcome if a.command=='finish' else None,evidence=a.evidence)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('errors') or result.get('passed') is False or result.get('allowed') is False else 0
    except (OSError,ValueError,KeyError,TypeError,HistoryError) as exc:
        print(json.dumps({'error':str(exc),'submits_posts':False},ensure_ascii=False));return 2


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
