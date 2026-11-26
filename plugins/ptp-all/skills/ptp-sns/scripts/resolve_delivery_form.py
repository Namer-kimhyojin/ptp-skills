"""Resolve an optional SNS format preference; never grants publishing approval.

The agent asks through its supported question tool. This script does not display
that question, receive chat replies, run a background timer or submit a post.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json

FORMS={'single-image','card-news'}
WAIT_SECONDS=10


def timestamp(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError('Timezone required')
    return t


def resolve(asked_at=None, now=None, response=None, received_at=None, explicit=None):
    if explicit is not None and explicit not in FORMS: raise ValueError('Unknown explicit format')
    if response is not None and response not in FORMS: raise ValueError('Map an actual user format answer before calling this tool')
    current=timestamp(now) if now else datetime.now(timezone.utc)
    if explicit:
        return {'state':'selected','delivery_form':explicit,'reason':'explicit-user-choice','scope':'format-preference-only'}
    if not asked_at: raise ValueError('Actual question delivery time required')
    asked=timestamp(asked_at);deadline=asked+timedelta(seconds=WAIT_SECONDS)
    if current<asked: raise ValueError('Current time precedes question')
    if response:
        if not received_at: raise ValueError('Actual response receipt time required')
        receipt=timestamp(received_at)
        if receipt<asked or receipt>current: raise ValueError('Invalid response receipt time')
        state='selected';chosen=response
        reason='user-response' if receipt<=deadline else 'late-user-response-review-current-stage'
    elif current<deadline:
        state='waiting';chosen=None;reason='preference-window-open'
    else:
        state='selected';chosen='single-image';reason='user-configured-timeout-default'
    return {'state':state,'delivery_form':chosen,'reason':reason,'asked_at':asked.isoformat(),
            'deadline':deadline.isoformat(),'evaluated_at':current.isoformat(),
            'remaining_seconds':max(0,(deadline-current).total_seconds()),'scope':'format-preference-only'}


def validate_form(job):
    """Opt-in field; legacy card-news jobs remain readable without migration."""
    form=job.get('delivery_form')
    if form is None: return []
    if form not in FORMS: return ['delivery_form must be single-image or card-news']
    errors=[];output=job.get('output',{})
    if not isinstance(output,dict): return ['delivery_form requires an output object']
    targets=job.get('platform_targets',[])
    if not isinstance(targets,list): return ['delivery_form requires platform_targets array']
    count=output.get('target_count')
    valid=lambda n:type(n) is int and (n==1 if form=='single-image' else n>=2)
    if not valid(count): errors.append(f'{form}: output.target_count must be '+('1' if form=='single-image' else 'at least 2'))
    for i,t in enumerate(targets):
        if not isinstance(t,dict):
            errors.append(f'platform_targets[{i}] must be an object');continue
        if not valid(t.get('target_count')): errors.append(f'{form}: platform_targets[{i}].target_count conflicts with delivery_form')
        if form=='single-image' and t.get('content_type')!='social-post': errors.append(f'single-image: platform_targets[{i}].content_type must be social-post')
    if form=='single-image' and output.get('mode')!='social-post': errors.append('single-image: output.mode must be social-post')
    if form=='single-image' and job.get('comic') is not None: errors.append('single-image: do not inherit a multi-card comic contract; use a compact single-scene composition')
    return errors


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asked-at');p.add_argument('--now');p.add_argument('--received-at')
    p.add_argument('--response',choices=sorted(FORMS));p.add_argument('--explicit',choices=sorted(FORMS))
    args=p.parse_args()
    try: result=resolve(args.asked_at,args.now,args.response,args.received_at,args.explicit)
    except (ValueError,TypeError) as exc:
        print(json.dumps({'state':'error','error':str(exc)},ensure_ascii=False));return 1
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__': raise SystemExit(main())
