"""Isolated behavioral checks; synthetic evidence never enters production state."""
import copy
import json
import tempfile
import unittest
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image
import social_runtime as r
import content_preflight as q
import asset_regions as patches


NOW=datetime(2026,11,2,14,0,tzinfo=r.KST)
KEY='ptp:15:7814'
SIG={'format_id':'question-reveal','layout_family':'diagonal-scene','hook_device':'기업의 질문','character_acting':'공동 실험'}


def fixture():
    row={'board_id':'7814','source_key':KEY,'publish_date':'2026-11-02','publish_time':'14:00','timezone':'Asia/Seoul','short':'SYNTHETIC TEST ONLY'}
    plan={'timezone':'Asia/Seoul','start_date':'2026-11-02','end_date':'2026-11-06','prepare_time':'11:00','schedule':[row]}
    state={'timezone':'Asia/Seoul','end_date':'2026-11-06','allowed_notice_ids':['7814'],'held_notice_ids':['7680'],'entries':{KEY:{'scheduled_date':'2026-11-02','status':'pending','channels':{p:{'status':'not-submitted','account':a} for p,a in [('instagram','pohangtp_official'),('facebook','pohangtpoffcial')]}}}}
    return plan,state


def observation(context='automation'):
    return {'checked_at':NOW.isoformat(),'execution_context':context,'browser':'iab','browser_available':True,
            'session_status':'target_verified','evidence':'SYNTHETIC TEST UI OBSERVATION ONLY',
            'accounts':{p:{'account':a,'can_create_post':True} for p,a in [('instagram','pohangtp_official'),('facebook','pohangtpoffcial')]}}


def spec_fixture(root):
    root=Path(root);a=root/'final.png';b=root/'mobile.png'
    Image.new('RGB',(1080,1350),'navy').save(a);Image.new('RGB',(360,450),'navy').save(b)
    reviews={k:{'status':'passed','evidence':'SYNTHETIC OBSERVATION ONLY','checked_at':NOW.isoformat()} for k in ('facts','text','mobile','layout','character','brand')}
    return {'source_key':KEY,'reviewer':'synthetic model fixture','generation_method':'whole-image',
            'images':[{'path':str(a),'sha256':r.sha(a),'mobile_path':str(b),'mobile_sha256':r.sha(b),
                       'expected_text':['기업 지원 안내'],'observed_text':['기업 지원 안내'],'reviews':reviews}],
            'creative':{'signature':SIG.copy(),'recent':[],'no_history_evidence':'SYNTHETIC first fixture'}}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ptp-upgrade-test-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.plan,self.state=fixture()

    def test_plan_state_disagreement_blocks(self):
        self.state['entries'][KEY]['scheduled_date']='2026-11-03'
        self.assertFalse(r.select_today(self.plan,self.state,'publish',{},NOW)['allowed_to_work'])

    def test_unapproved_notice_and_duplicate_day_block(self):
        second=dict(self.plan['schedule'][0],board_id='7938',source_key='ptp:15:7938')
        self.plan['schedule'].append(second);self.state['entries'][second['source_key']]=copy.deepcopy(self.state['entries'][KEY])
        errors=r.validate_schedule(self.plan,self.state)
        self.assertIn('unapproved_notice:7938',errors);self.assertIn('multiple_notices_on_day:2026-11-02',errors)

    def test_partial_success_only_other_channel_pending(self):
        self.state['entries'][KEY]['channels']['instagram']['status']='published'
        out=r.select_today(self.plan,self.state,'publish',{},NOW)
        self.assertEqual(out['channels']['instagram']['action'],'skip');self.assertEqual(out['channels']['facebook']['action'],'pending')

    def test_unknown_requires_reconcile(self):
        h={'a':{'source_key':KEY,'platform':'instagram','account':'pohangtp_official','status':'unknown','attempt_id':'a'}}
        self.assertEqual(r.select_today(self.plan,self.state,'publish',h,NOW)['reason'],'original_attempt_requires_reconciliation')

    def test_same_day_webtoon_does_not_consume_notice_quota(self):
        h={'a':{'source_key':'ptp:institution:ep04','platform':'instagram','account':'pohangtp_official','status':'published','attempt_id':'a','published_at':NOW.isoformat()}}
        self.assertTrue(r.select_today(self.plan,self.state,'publish',h,NOW)['allowed_to_work'])

    def test_different_notice_published_today_blocks(self):
        h={'a':{'source_key':'ptp:15:7938','platform':'instagram','account':'pohangtp_official','status':'published','attempt_id':'a','published_at':NOW.isoformat()}}
        self.assertEqual(r.select_today(self.plan,self.state,'publish',h,NOW)['reason'],'another_notice_published_today')

    def test_early_final_checks_do_not_allow_early_submission(self):
        out=r.select_today(self.plan,self.state,'publish',{},NOW-timedelta(minutes=5))
        self.assertTrue(out['allowed_to_work']);self.assertFalse(out['submission_time_reached'])
        self.assertFalse(r.select_today(self.plan,self.state,'publish',{},NOW-timedelta(hours=1))['allowed_to_work'])

    def test_past_end_date_blocks(self):
        self.assertEqual(r.select_today(self.plan,self.state,'publish',{},NOW+timedelta(days=10))['reason'],'outside_authorized_dates')

    def test_interactive_cannot_stand_in_for_automation(self):
        e={'instagram':'pohangtp_official','facebook':'pohangtpoffcial'}
        self.assertFalse(r.evaluate_preflight(observation('interactive'),e,'automation',NOW)['passed'])
        self.assertTrue(r.evaluate_preflight(observation(),e,'automation',NOW)['passed'])

    def test_queued_unavailable_and_stale_do_not_pass(self):
        e={'instagram':'pohangtp_official','facebook':'pohangtpoffcial'}
        for update in ({'open_result':'queued'},{'browser_available':False},{'checked_at':(NOW-timedelta(hours=1)).isoformat()},{'session_status':'challenge_required'}):
            self.assertFalse(r.evaluate_preflight(dict(observation(),**update),e,'automation',NOW)['passed'])

    def test_duplicate_owner_not_reclaimed_by_age(self):
        a=r.claim(self.root,'foundation-meta',KEY,'prepare',NOW.isoformat(),'automation',NOW-timedelta(days=2))
        with self.assertRaises(ValueError):r.claim(self.root,'foundation-meta',KEY,'publish',NOW.isoformat(),'automation',NOW)
        self.assertEqual(r.load(r.owner_path(self.root,'foundation-meta'))['run_id'],a['run_id'])

    def test_torn_history_not_appended(self):
        p=self.root/'execution-events.jsonl';p.write_text('{"event":"started"}',encoding='utf-8');before=p.read_bytes()
        with self.assertRaises(ValueError):r.append_runtime(self.root,{'event':'finished'})
        self.assertEqual(before,p.read_bytes())

    def test_report_required_before_ready(self):
        a=r.claim(self.root,'foundation-meta',KEY,'prepare',NOW.isoformat(),'automation',NOW)
        evidence=self.root/'e.txt';evidence.write_text('SYNTHETIC',encoding='utf-8')
        with self.assertRaises(ValueError):r.change_run(self.root,'foundation-meta',a['run_id'],stage='ready',evidence=evidence,now=NOW)

    def test_unmeasured_automation_rate_remains_null(self):
        _,_,summary=r.dashboard(self.plan,self.state)
        self.assertIsNone(summary['metrics']['automation_preflight_pass_rate'])

    def test_automation_metrics_use_bound_observed_reports(self):
        pf=r.evaluate_preflight(observation(),{'instagram':'pohangtp_official','facebook':'pohangtpoffcial'},'automation',NOW)
        p=self.root/'pf.json';r.atomic_json(p,pf)
        events=[{'event':'stage','execution_context':'automation','run_id':'synthetic-run','evidence_path':str(p),'evidence_sha256':r.sha(p)}]
        _,_,summary=r.dashboard(self.plan,self.state,events=events)
        self.assertEqual(summary['metrics']['automation_preflight_runs'],1);self.assertEqual(summary['metrics']['automation_preflight_pass_rate'],1)
        r.atomic_json(p,dict(pf,passed=False))
        _,_,summary=r.dashboard(self.plan,self.state,events=events)
        self.assertIsNone(summary['metrics']['automation_preflight_pass_rate'])

    def test_webtoon_defaults_to_integrated_generation_and_honors_override(self):
        args=[sys.executable,str(Path(__file__).with_name('resolve_context.py')),'--content-type','four-panel','--character-set','none']
        result=json.loads(subprocess.check_output(args,encoding='utf-8'))
        self.assertEqual(result['request']['generation_method'],'whole-image')
        result=json.loads(subprocess.check_output(args+['--generation-method','separate-lettering'],encoding='utf-8'))
        self.assertEqual(result['request']['generation_method'],'separate-lettering')

    def test_quality_and_submission_guard(self):
        planpath=self.root/'plan.json';statepath=self.root/'state.json';r.atomic_json(planpath,self.plan);r.atomic_json(statepath,self.state)
        owner=r.claim(self.root,'foundation-meta',KEY,'publish',NOW.isoformat(),'automation',NOW,plan_sha256=r.sha(planpath))
        pf=r.evaluate_preflight(observation(),{'instagram':'pohangtp_official','facebook':'pohangtpoffcial'},'automation',NOW)
        pfpath=self.root/'pf.json';r.atomic_json(pfpath,pf)
        r.change_run(self.root,'foundation-meta',owner['run_id'],stage='preflight',evidence=pfpath,now=NOW)
        spec=spec_fixture(self.root);specpath=self.root/'spec.json';r.atomic_json(specpath,spec)
        report=q.review_quality(spec,self.root);report.update(spec_path=str(specpath),spec_sha256=r.sha(specpath))
        reportpath=self.root/'quality.json';r.atomic_json(reportpath,report)
        r.change_run(self.root,'foundation-meta',owner['run_id'],stage='ready',evidence=reportpath,now=NOW)
        contract={'plan_path':str(planpath),'execution_path':str(statepath),'runtime_dir':str(self.root)}
        self.assertTrue(r.submission_guard(contract,KEY,{},NOW)['allowed'])
        self.assertFalse(r.submission_guard(contract,KEY,{},NOW-timedelta(seconds=1))['allowed'])
        self.assertFalse(r.submission_guard(contract,KEY,{},NOW+timedelta(minutes=11))['allowed'])
        h={'a':{'source_key':KEY,'status':'submitting','runtime_run_id':owner['run_id']}}
        self.assertTrue(r.submission_guard(contract,KEY,h,NOW)['allowed'])
        h['a']['status']='unknown';self.assertFalse(r.submission_guard(contract,KEY,h,NOW)['allowed'])
        self.plan['end_date']='2026-11-07';r.atomic_json(planpath,self.plan)
        self.assertFalse(r.submission_guard(contract,KEY,{},NOW)['allowed'])

    def test_dashboard_escapes_and_shows_partial_success(self):
        self.plan['schedule'][0]['short']='<script>bad()</script>'
        self.state['entries'][KEY]['channels']['instagram']['status']='published'
        page,_,summary=r.dashboard(self.plan,self.state)
        self.assertNotIn('<script>bad()',page);self.assertIn('&lt;script&gt;',page)
        self.assertEqual(summary['counts']['조치 필요'],1)


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ptp-quality-test-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.spec=spec_fixture(self.root)

    def test_actual_image_and_text_pass(self):
        self.assertTrue(q.review_quality(self.spec,self.root)['passed'])

    def test_changed_image_or_typo_fail(self):
        self.spec['images'][0]['observed_text']=['기입 지원 안내'];self.assertFalse(q.review_quality(self.spec,self.root)['passed'])
        self.spec['images'][0]['observed_text']=['기업 지원 안내']
        Image.new('RGB',(1080,1350),'red').save(self.root/'final.png');self.assertFalse(q.review_quality(self.spec,self.root)['passed'])

    def test_corrupt_png_fails_even_with_matching_hash(self):
        p=self.root/'final.png';p.write_bytes(p.read_bytes()[:24]);self.spec['images'][0]['sha256']=r.sha(p)
        self.assertFalse(q.review_quality(self.spec,self.root)['passed'])

    def test_repeated_narrative_and_layout_require_exception(self):
        self.spec['creative']['recent']=[{'source_key':'ptp:15:7938','preview_path':str(self.root/'final.png'),'sha256':r.sha(self.root/'final.png'),'signature':SIG.copy(),'review_evidence':'SYNTHETIC previous preview'}]
        self.spec['creative']['difference_evidence']='SYNTHETIC color-only change'
        self.assertIn('consecutive_narrative_layout_repetition',q.review_quality(self.spec,self.root)['errors'])
        self.spec['creative']['exception_evidence']='SYNTHETIC intentional sequel selection';self.assertTrue(q.review_quality(self.spec,self.root)['passed'])

    def test_changed_attachment_requires_fact_review(self):
        before={'source_key':KEY,'source_url':'same','fields':{'접수기간':'11/30'},'attachments':{'a':{'sha256':'old'}},'complete':True}
        after=copy.deepcopy(before);after['attachments']['a']['sha256']='new'
        out=q.compare_sources(before,after);self.assertTrue(out['requires_fact_review']);self.assertEqual(out['changed_attachment_ids'],['a'])

    def test_job_cannot_review_a_different_delivered_image(self):
        specpath=self.root/'spec.json';r.atomic_json(specpath,self.spec)
        report=q.review_quality(self.spec,self.root);report.update(spec_path=str(specpath),spec_sha256=r.sha(specpath));rp=self.root/'report.json';r.atomic_json(rp,report)
        job={'runtime_contract_version':1,'source_key':KEY,'quality_review_path':str(rp),'creative_signature':SIG.copy(),'final_image_paths':[str(self.root/'mobile.png')]}
        self.assertTrue(q.validate_job_quality(job,self.root/'job.json'))
        job['final_image_paths']=[str(self.root/'final.png')];self.assertEqual(q.validate_job_quality(job,self.root/'job.json'),[])

    def test_patch_permission_and_pixel_invariant(self):
        base=self.root/'base.png';asset=self.root/'qr.png';out=self.root/'patched.png';report=self.root/'patch.json'
        Image.new('RGB',(100,100),'navy').save(base);Image.new('RGB',(20,20),'white').save(asset)
        region={'kind':'qr','rect':[10,10,20,20],'asset_path':str(asset),'asset_sha256':r.sha(asset)}
        with self.assertRaises(ValueError):patches.patch(base,KEY,[region],{'grants':[]},out,report)
        grants={'grants':[{'id':'test-only','active':True,'source_keys':[KEY],'regions':['qr'],'user_request_evidence':'SYNTHETIC AUTHORIZATION ONLY'}]}
        result=patches.patch(base,KEY,[region],grants,out,report)
        self.assertTrue(result['outside_regions_unchanged']);self.assertFalse(result['final_qr_decode_verified'])
        with Image.open(out) as im:self.assertEqual(im.convert('RGB').getpixel((0,0)),(0,0,128))
        with self.assertRaises(ValueError):patches.patch(base,KEY,[region],grants,out,report)


if __name__=='__main__':unittest.main()
