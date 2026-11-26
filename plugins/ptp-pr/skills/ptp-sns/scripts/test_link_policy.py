"""Isolated URL-scope and short-link application regressions; no network calls."""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shorten_notice_url as shortener
import validate_link_policy as policy
from test_optimization import context

NOTICE='https://www.ptp.or.kr/main/board/view.do?menu_idx=116&manage_idx=15&board_idx=7997'
STAFF='https://www.ptp.or.kr/main/module/deptManager/index.do?menu_idx=138'
SHORT='https://da.gd/synthetic-only'

class ScopeTests(unittest.TestCase):
    def test_notice_default_keeps_strict_scope(self):
        self.assertTrue(shortener.valid_target(NOTICE))
        self.assertFalse(shortener.valid_target(STAFF))

    def test_institution_accepts_staff_and_public_info(self):
        self.assertTrue(shortener.valid_target(STAFF,'institution'))
        self.assertTrue(shortener.valid_target('https://www.ptp.or.kr/main/html.do?menu_idx=137','institution'))

    def test_sensitive_or_foreign_urls_rejected(self):
        for url in [STAFF+'&token=secret',STAFF+'&menu_idx=106',STAFF.replace('https:','http:'),STAFF.replace('www.ptp.or.kr','evil.test'),STAFF.replace('/main/module/deptManager/index.do','/login'),STAFF+'#auth',STAFF.replace('www.ptp.or.kr','www.ptp.or.kr:443')]:
            with self.subTest(url=url):self.assertFalse(shortener.valid_target(url,'institution'))

    def test_first_verified_service_stops_further_issuance(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'report.json'
            with patch.object(sys,'argv',['shorten_notice_url.py','--purpose','institution','--url',STAFF,'--report',str(output)]), patch.object(shortener,'issue',return_value=SHORT) as issue, patch.object(shortener,'verify',return_value={'status':302,'location':STAFF}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(shortener.main(),0)
            self.assertEqual(issue.call_count,1)
            self.assertEqual(json.loads(output.read_text('utf-8'))['selected'],SHORT)

    def test_reuse_live_verifies_without_new_link(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old.json';old.write_text(json.dumps({'official_url':STAFF,'selected':SHORT}),'utf-8')
            with patch.object(sys,'argv',['shorten_notice_url.py','--purpose','institution','--url',STAFF,'--report',str(Path(d)/'new.json'),'--reuse-report',str(old)]), patch.object(shortener,'issue') as issue, patch.object(shortener,'verify',return_value={'status':302,'location':STAFF}) as verify, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(shortener.main(),0)
            issue.assert_not_called();verify.assert_called_once_with(SHORT,STAFF)

    def test_creative_routing_also_loads_policy(self):
        result=context(content_type='social-toon')
        self.assertEqual(result['link_policy']['mode'],'short-preferred')
        self.assertIn('references/qr-code-workflow.md',result['references'])

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.image=self.root/'synthetic.png';self.image.write_bytes(b'synthetic test only, not real image evidence')
        self.short_report={'official_url':STAFF,'selected':SHORT,'attempts':[{'passed':True,'short_url':SHORT,'redirect':{'location':STAFF,'status':302}}]}
        self.decode={'passed':True,'expected_url':SHORT,'image_verification':{'image':str(self.image),'sha256':hashlib.sha256(self.image.read_bytes()).hexdigest(),'checks':[{'scale':1.0,'passed':True},{'scale':0.5,'passed':True}]}}
        self.job={'qr':{'link_policy_version':json.loads(policy.POLICY.read_text('utf-8'))['version'],'official_url':STAFF,'target_url':SHORT,'short_link_report':'short.json','visible_short_url':SHORT,'visible_short_url_review':'SYNTHETIC TEST ONLY','report_path':'qr.json'}}

    def check(self):
        (self.root/'short.json').write_text(json.dumps(self.short_report),'utf-8')
        (self.root/'qr.json').write_text(json.dumps(self.decode),'utf-8')
        return policy.validate(self.job,self.root/'job.json')

    def test_matching_reports_pass(self):self.assertEqual(self.check(),[])
    def test_old_job_without_qr_remains_compatible(self):self.assertEqual(policy.validate({},self.root/'job.json'),[])
    def test_policy_job_cannot_silently_omit_qr(self):self.assertTrue(policy.validate({'link_policy':{} or {'mode':'short-preferred'}},self.root/'job.json'))
    def test_missing_policy_version_blocks(self):
        del self.job['qr']['link_policy_version'];self.assertTrue(self.check())
    def test_long_original_qr_cannot_pass_as_shortened(self):
        self.job['qr']['target_url']=STAFF;self.assertTrue(self.check())
    def test_wrong_final_destination_blocks(self):
        self.short_report['attempts'][0]['redirect']['location']='https://www.ptp.or.kr/';self.assertTrue(self.check())
    def test_visible_short_url_must_match(self):
        self.job['qr']['visible_short_url']='https://da.gd/wrong';self.assertTrue(self.check())
    def test_changed_actual_image_blocks(self):
        self.image.write_bytes(b'changed');self.assertTrue(self.check())
    def test_half_size_check_is_required(self):
        self.decode['image_verification']['checks'].pop();self.assertTrue(self.check())
    def test_fallback_requires_real_failure_report_and_reason(self):
        self.short_report.update(selected=None,attempts=[{'passed':False,'error':'synthetic network failure'}])
        self.job['qr']['target_url']=STAFF;self.decode['expected_url']=STAFF
        self.assertTrue(self.check())
        self.job['qr']['fallback_reason']='SYNTHETIC: all services unavailable'
        self.assertEqual(self.check(),[])

if __name__=='__main__':unittest.main()
