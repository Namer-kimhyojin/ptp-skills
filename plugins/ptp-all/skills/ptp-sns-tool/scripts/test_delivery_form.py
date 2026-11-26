import argparse
import copy
from datetime import datetime,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from resolve_delivery_form import resolve,validate_form
from resolve_context import resolve as route
from validate_job import validate
from test_delivery_validation import SharedDeliveryTests

ROOT=Path(__file__).resolve().parent.parent
ASK='2026-10-22T18:00:00+09:00'
def at(seconds): return (datetime.fromisoformat(ASK)+timedelta(seconds=seconds)).isoformat()


class PreferenceTests(unittest.TestCase):
    def test_no_early_default(self):
        for t in (0,5,9.999):
            self.assertEqual(resolve(ASK,at(t))['state'],'waiting')
            self.assertIsNone(resolve(ASK,at(t))['delivery_form'])

    def test_default_at_ten_seconds_without_publication_authority(self):
        result=resolve(ASK,at(10))
        self.assertEqual(result['delivery_form'],'single-image')
        self.assertEqual(result['reason'],'user-configured-timeout-default')
        self.assertNotIn('authorized',result);self.assertEqual(result['scope'],'format-preference-only')

    def test_timely_answer_wins_even_if_observed_later(self):
        self.assertEqual(resolve(ASK,at(12),'card-news',at(9))['delivery_form'],'card-news')

    def test_explicit_choice_needs_no_wait(self):
        self.assertEqual(resolve(explicit='card-news')['reason'],'explicit-user-choice')

    def test_late_answer_is_flagged_for_stage_review(self):
        self.assertEqual(resolve(ASK,at(20),'card-news',at(20))['reason'],'late-user-response-review-current-stage')

    def test_bad_timing_and_unmapped_text_fail(self):
        for kwargs in ({'now':at(-1)},{'now':at(10),'response':'publish'},{'now':at(10),'response':'card-news'}, {'now':'2026-10-22T18:00:11'}):
            with self.assertRaises(ValueError):resolve(asked_at=ASK,**kwargs)

    def test_single_template_structure_and_routing(self):
        job=ROOT/'assets/single-image-job-template.json'
        errors,_=validate(job,False);self.assertEqual(errors,[])
        args=argparse.Namespace(workflow='notice-to-social',delivery_form='single-image',content_type='card-news',production_mode='standard',render_style='3d',platform='instagram',formats=['png'],character='both',pose=None,photoreal=False,print_output=False)
        result=route(args)
        self.assertEqual(result['request']['content_type'],'social-post')
        self.assertIn('assets/single-image-job-template.json',result['assets'])
        self.assertNotIn('assets/job-template.json',result['assets'])
        self.assertNotIn('scripts/validate_webtoon_mode.py',result['validators'])

    def test_wrong_single_count_is_blocked_by_real_job_validator(self):
        j=json.loads((ROOT/'assets/single-image-job-template.json').read_text('utf-8'))
        j['platform_targets'][0]['target_count']=2
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'job.json';p.write_text(json.dumps(j),'utf-8')
            errors,_=validate(p,False)
            self.assertTrue(any('delivery_form' in e for e in errors))

    def test_card_news_requires_multiple_images(self):
        j=json.loads((ROOT/'assets/single-image-job-template.json').read_text('utf-8'));j['delivery_form']='card-news'
        self.assertTrue(validate_form(j))


class SingleImageDeliveryTest(SharedDeliveryTests):
    # Reuse the existing file validation harness, not its unrelated test methods.
    def test_one_shared_image_is_checked_in_both_channels(self):
        self.cards[1].unlink();self.cards=self.cards[:1]
        for t in self.job['platform_targets']:
            t.update({'target_count':1,'format_counts':{'png':1},'shared_output_paths':[str(self.cards[0])]})
        code,manifest=self.run_delivery()
        self.assertEqual(code,0);self.assertEqual(len(manifest['files']),2)
        self.assertEqual(manifest['files'][0]['sha256'],manifest['files'][1]['sha256'])


if __name__=='__main__':
    suite=unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(PreferenceTests))
    suite.addTest(SingleImageDeliveryTest('test_one_shared_image_is_checked_in_both_channels'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
