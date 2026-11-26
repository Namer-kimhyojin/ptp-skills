#!/usr/bin/env python3
"""Issue/reuse verified short links for public PTP notices and institution pages."""
import argparse
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVICES = {
    'dagd': ('https://da.gd/s?url=', 'da.gd'),
    'isgd': ('https://is.gd/create.php?format=simple&url=', 'is.gd'),
    'tinyurl-legacy': ('https://tinyurl.com/api-create.php?url=', 'tinyurl.com'),
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def valid_notice(url):
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    return (u.scheme == 'https' and u.netloc == 'www.ptp.or.kr' and
            u.path == '/main/board/view.do' and not u.fragment and
            set(q) == {'menu_idx', 'manage_idx', 'board_idx'} and
            (q['menu_idx'], q['manage_idx']) in [(['116'], ['15']), (['113'], ['2'])] and
            len(q['board_idx']) == 1 and q['board_idx'][0].isdigit())

def valid_target(url, purpose='notice'):
    if valid_notice(url):
        return True
    if purpose != 'institution':
        return False
    u = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
    if (u.scheme == 'https' and u.netloc == 'www.ptp.or.kr'
            and u.path == '/main/board/index.do' and not u.fragment
            and q == {'menu_idx': ['116'], 'manage_idx': ['15']}
            and url == url.strip()):
        return True
    return (u.scheme == 'https' and u.netloc == 'www.ptp.or.kr' and not u.fragment
            and u.path in {'/main/html.do', '/main/module/deptManager/index.do'}
            and set(q) == {'menu_idx'} and len(q['menu_idx']) == 1
            and q['menu_idx'][0].isdigit() and int(q['menu_idx'][0]) > 0
            and url == url.strip())

def issue(service, url):
    endpoint, host = SERVICES[service]
    request = urllib.request.Request(endpoint + urllib.parse.quote(url, safe=''), headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        short = response.read(1024).decode('utf-8').strip()
    u = urllib.parse.urlsplit(short)
    if u.scheme != 'https' or u.netloc != host or not u.path.strip('/') or u.query or u.fragment:
        raise ValueError('Unexpected short link response')
    return short

def verify(short, target):
    req = urllib.request.Request(short, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.build_opener(NoRedirect).open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        status = response.code
        location = response.headers.get('Location')
    if status not in (301, 302, 303, 307, 308) or location != target:
        raise ValueError('Short link did not redirect directly to the exact public target URL')
    return {'status': status, 'location': location}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True)
    p.add_argument('--purpose', choices=['notice','institution'], default='notice', help='notice keeps the original strict board URL check; institution permits verified public PTP info/staff pages')
    p.add_argument('--reuse-report', type=Path, help='Reuse an existing matching report only after live redirect verification')
    p.add_argument('--report', required=True, help='New output file; existing reports are never overwritten')
    p.add_argument('--services', nargs='+', choices=SERVICES, default=['dagd', 'isgd'])
    a = p.parse_args()
    if not valid_target(a.url, a.purpose):
        p.error('Only exact public PTP URLs for the declared purpose are permitted; login/private/query tokens are forbidden')
    path = Path(a.report)
    if path.exists():
        p.error('Report already exists')
    attempts = []
    if a.reuse_report:
        old = json.loads(a.reuse_report.read_text(encoding='utf-8'))
        if old.get('official_url') != a.url or not old.get('selected'):
            p.error('Reusable report does not match the exact public target')
        short=old['selected']
        u=urllib.parse.urlsplit(short)
        if u.scheme!='https' or u.netloc not in {s[1] for s in SERVICES.values()} or u.query or u.fragment:
            p.error('Reusable short URL is not an allowed shortener URL')
        try:
            attempts.append({'service':'reused','short_url':short,'redirect':verify(short,a.url),'passed':True})
        except (OSError, ValueError, UnicodeError) as exc:
            attempts.append({'service':'reused','passed':False,'error':str(exc)})
    for service in ([] if any(i['passed'] for i in attempts) else a.services):
        try:
            short = issue(service, a.url)
            verified = verify(short, a.url)
            attempts.append({'service': service, 'short_url': short, 'redirect': verified, 'passed': True})
            break
        except (OSError, ValueError, UnicodeError) as exc:
            attempts.append({'service': service, 'passed': False, 'error': str(exc)})
    result = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'official_url': a.url,
              'purpose': a.purpose,
              'attempts': attempts, 'selected': next((i['short_url'] for i in attempts if i['passed']), None),
              'scope': 'HTTPS direct redirect only; browser, future availability and public notice body require separate checks'}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['selected'] else 1

if __name__ == '__main__':
    sys.exit(main())
