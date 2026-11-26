#!/usr/bin/env python3
"""Offline safety/selection regressions for the public PTP notice collector."""

import tempfile
import unittest
from pathlib import Path

from collect_ptp_notice import (BASE, download_attachment, parse_detail, parse_listing,
                                safe_filename, select_latest, validate_attachment, validate_url)


def listing(rows):
    return ('<input name="order_name" value="add_date"><input name="order_type" value="DESC">'
            '<input name="viewPage" value="1"><div class="board-list"><table>' + rows + '</table></div>')


def row(board_id, date, pinned=False):
    return (f'<tr title="Notice {board_id}"><td>' + ('<span class="ico-notice">공지</span>' if pinned else '')
            + f'</td><td><a onclick="viewBoard({board_id});">Notice {board_id}</a></td><td class="date">{date}</td></tr>')


class CollectorTests(unittest.TestCase):
    def test_detail_identity_mismatch_fails_even_for_same_title(self):
        body = '<div class="board-view"><div class="view-cont-biz"><p class="subject">Notice 20</p></div></div>'
        selected = {'title': 'Notice 20', 'board_id': '20'}
        for fields in ['<input name="board_idx" value="21">', '<input name="manage_idx" value="16">']:
            with self.assertRaises(ValueError):
                parse_detail(fields + body, selected)
        result = parse_detail('<input name="board_idx" value="20"><input name="manage_idx" value="15">' + body, selected)
        self.assertEqual(result['detail_identity_fields'], {'board_idx': '20', 'manage_idx': '15'})
        self.assertEqual(result['registration_date_verified_from'], 'listing')
        self.assertFalse(result['registration_date_detail_verified'])

    def test_old_pinned_and_duplicate_do_not_win(self):
        rows = parse_listing(listing(row(99, "2026.01.01", True) + row(20, "2026.10.21", True)
                                     + row(20, "2026.10.21") + row(19, "2026.10.20")), BASE)["rows"]
        selected, evidence = select_latest(rows)
        self.assertEqual(selected["board_id"], "20")
        self.assertEqual(evidence["duplicates_removed"], 1)

    def test_same_day_tie_is_deterministic_not_timestamp(self):
        rows = parse_listing(listing(row(20, "2026.10.21") + row(21, "2026.10.21")), BASE)["rows"]
        selected, evidence = select_latest(rows)
        self.assertEqual(selected["board_id"], "21")
        self.assertTrue(evidence["same_day_tie"])
        self.assertFalse(evidence["exact_registration_time_known"])

    def test_new_closed_notice_can_beat_default_active(self):
        active = parse_listing(listing(row(20, "2026.10.20")), BASE)["rows"]
        closed = parse_listing(listing(row(21, "2026.10.21")), BASE)["rows"]
        self.assertEqual(select_latest(active + closed)[0]["board_id"], "21")

    def test_unknown_structure_or_unsorted_rows_fails(self):
        for html in ('<html>Error</html>', listing(row(20, "2026.10.20") + row(21, "2026.10.21"))):
            with self.assertRaises(ValueError):
                parse_listing(html, BASE)

    def test_conflicting_duplicates_fail(self):
        rows = parse_listing(listing(row(20, "2026.10.21", True) + row(20, "2026.10.20")), BASE)["rows"]
        with self.assertRaises(ValueError):
            select_latest(rows)

    def test_filename_cannot_escape_or_execute(self):
        name = safe_filename('../../CON:bad?.pdf', '10')
        self.assertEqual(name, '10_CON_bad_.pdf')
        self.assertNotIn('/', name)
        for name in ('evil.exe', 'fake.pdf.exe', 'missing'):
            with self.assertRaises(ValueError):
                safe_filename(name, '10')

    def test_foreign_and_private_redirects_are_rejected(self):
        for url in ('http://www.ptp.or.kr/main/board/view.do', 'https://127.0.0.1/a.pdf',
                    'https://www.ptp.or.kr.evil.example/a', 'https://www.ptp.or.kr/admin',
                    'https://www.ptp.or.kr/data/board/15/%2e%2e/private', 'https://user@www.ptp.or.kr/main/board/view.do'):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_error_html_and_file_signature_rejected(self):
        for data, mime in ((b'<html>error</html>', 'application/octet-stream'), (b'%PDF-fake', 'text/html'),
                           (b'not a pdf', 'application/octet-stream'), (b'', 'application/pdf')):
            with self.assertRaises(ValueError):
                validate_attachment(data, 'notice.pdf', mime)
        validate_attachment(b'%PDF-1.7\nfixture', 'notice.pdf', 'application/octet-stream')

    def test_failed_download_has_no_success_file(self):
        item = {'file_id': '10', 'source_name': 'notice.pdf', 'url': BASE + '/board/boardFile/download/15/20/10.do'}
        with tempfile.TemporaryDirectory() as directory:
            result = download_attachment(item, Path(directory), lambda _: (b'<html>Error</html>', {'content_type': 'text/html'}))
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(list(Path(directory).rglob('*.pdf')))

    def test_success_download_has_hash_and_refuses_overwrite(self):
        item = {'file_id': '10', 'source_name': 'notice.pdf', 'url': BASE + '/board/boardFile/download/15/20/10.do'}
        with tempfile.TemporaryDirectory() as directory:
            fetch = lambda _: (b'%PDF-1.7\nfixture', {'content_type': 'application/pdf'})
            result = download_attachment(item, Path(directory), fetch)
            self.assertEqual(result['status'], 'downloaded')
            self.assertEqual(len(result['sha256']), 64)
            self.assertEqual(download_attachment(item, Path(directory), fetch)['status'], 'failed')

    def test_detail_scope_and_image_only_notice_are_explicit(self):
        html = '<div class="board-view"><div class="view-cont-biz"><p class="subject">Notice 20</p><dl><dt>접수방법</dt><dd>온라인</dd></dl><img src="/data/board/15/20/a.jpg"></div><div class="board-view-attach"><a href="/board/boardFile/download/15/20/10.do">공고.pdf(30.0KB)</a></div></div>'
        result = parse_detail(html, {'title': 'Notice 20', 'board_id': '20'})
        self.assertEqual(result['fields']['접수방법'], '온라인')
        self.assertTrue(result['body_may_require_image_or_attachment_reading'])
        self.assertEqual(result['attachments'][0]['source_name'], '공고.pdf')
        with self.assertRaises(ValueError):
            parse_detail(html, {'title': 'Wrong title', 'board_id': '20'})


if __name__ == '__main__':
    unittest.main()
