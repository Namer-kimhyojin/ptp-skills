"""Isolated tests for dated user-authorized batches and remaining-period rules."""
import copy
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta
import social_runtime as r
from notice_publish_guard import remaining_period_issues
from test_runtime_upgrade import fixture,NOW,KEY

class ExplicitBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.plan,self.state=fixture()
        second=dict(self.plan['schedule'][0],board_id='7938',source_key='ptp:15:7938')
        self.plan['schedule'].append(second)
        self.state['allowed_notice_ids'].append('7938')
        self.state['entries'][second['source_key']]=copy.deepcopy(self.state['entries'][KEY])
        auth={'id':'TEST ONLY','date':'2026-11-02','source_keys':['ptp:15:7938'],'already_published_source_keys':[KEY],'minimum_remaining_days':3,'user_request':'SYNTHETIC explicit two-post exception'}
        path=self.root/'auth.json';r.atomic_json(path,auth)
        self.plan['batch_publication']={**auth,'authorization_path':str(path),'authorization_sha256':r.sha(path)}
    def test_exact_dated_request_allows_pending_notice_after_previous_publication(self):
        self.state['entries'][KEY]['status']='published'
        for c in self.state['entries'][KEY]['channels'].values():c.update(status='published',published_at=NOW.isoformat())
        out=r.select_today(self.plan,self.state,'publish',{},NOW)
        self.assertTrue(out['allowed_to_work']);self.assertEqual(out['source_key'],'ptp:15:7938')
        self.assertTrue(out['requires_interactive_batch'])
    def test_absent_tampered_and_out_of_date_request_do_not_expand_quota(self):
        clean=copy.deepcopy(self.plan)
        for mutate in [lambda p:p.pop('batch_publication'),lambda p:p['batch_publication'].update(authorization_sha256='0'*64),lambda p:p['batch_publication'].update(date='2026-11-03')]:
            p=copy.deepcopy(clean);mutate(p);self.assertTrue(r.validate_schedule(p,self.state))
    def test_unlisted_other_notice_still_blocks(self):
        self.state['entries'][KEY]['status']='published'
        for c in self.state['entries'][KEY]['channels'].values():c.update(status='published',published_at=NOW.isoformat())
        history={'x':{'source_key':'ptp:15:7904','platform':'instagram','account':'pohangtp_official','status':'published','attempt_id':'x','published_at':NOW.isoformat()}}
        self.assertEqual(r.select_today(self.plan,self.state,'publish',history,NOW)['reason'],'another_notice_published_today')
    def test_remaining_time_boundary_and_closed_period(self):
        for delta,expected in [(timedelta(days=3),[]),(timedelta(days=3)-timedelta(seconds=1),['less_than_minimum_remaining_days']),(timedelta(days=-1),['less_than_minimum_remaining_days'])]:
            self.assertEqual(remaining_period_issues({'evaluated_at':NOW.isoformat(),'application_end':(NOW+delta).isoformat()},3),expected)
        self.assertTrue(remaining_period_issues({'evaluated_at':NOW.isoformat()},3))

if __name__=='__main__':unittest.main()
