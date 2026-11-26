import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from resolve_concept import load_catalog,resolve,presentation_choices,recent_designs
from validate_lettering import validate


class VariationTests(unittest.TestCase):
    def test_consecutive_concept_changes(self):
        catalog=load_catalog();signals={'process','place'}
        before=resolve(catalog,signals,{'friendly'},'none',3)
        after=resolve(catalog,signals,{'friendly'},'none',3,[{'concept_id':before[0]['id']}])
        self.assertNotEqual(before[0]['id'],after[0]['id'])
        self.assertEqual(len({p['medium_family'] for p in after}),3)

    def test_format_changes_narrative_and_structure(self):
        initial=presentation_choices({'process'},[])[0]
        following=presentation_choices({'process'},[{'format_id':initial['id'],'layout_family':initial['layout_family']}])[0]
        self.assertNotEqual(initial['id'],following['id'])
        self.assertNotEqual(initial['layout_family'],following['layout_family'])

    def test_history_missing_is_distinguished(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(recent_designs(Path(d)/'missing'),([],[]))

    def test_history_corrupt_does_not_look_empty(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Path(d)/'history';ledger.write_text('garbage\n','utf-8')
            with self.assertRaises(Exception): recent_designs(ledger)

    def test_read_legacy_style_and_skip_current(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);m=base/'manifest.json';m.write_text('{}','utf-8')
            (base/'job.json').write_text(json.dumps({'concept_strategy':{'selected_concept_id':'3d-miniature-diorama'}}),'utf-8')
            event={'source_key':'ptp:15:8189','status':'produced','recorded_at':'2026-10-22T08:17:00Z','manifest_path':str(m),'manifest_sha256':hashlib.sha256(m.read_bytes()).hexdigest()}
            with patch('content_history.read_latest',return_value={'ptp:15:8189':event}):
                recent,warnings=recent_designs(base/'ledger')
                self.assertEqual(recent[0]['concept_id'],'3d-miniature-diorama');self.assertTrue(warnings)
                self.assertEqual(recent_designs(base/'ledger',exclude_source='ptp:15:8189'),([],[]))

    def test_changed_old_manifest_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as d:
            m=Path(d)/'manifest.json';m.write_text('{}','utf-8')
            event={'source_key':'ptp:15:8189','status':'produced','recorded_at':'2026-10-22T08:17:00Z','manifest_path':str(m),'manifest_sha256':'0'*64}
            with patch('content_history.read_latest',return_value={'ptp:15:8189':event}):
                recent,warnings=recent_designs(Path(d)/'ledger')
                self.assertFalse(recent);self.assertIn('fingerprint mismatch',warnings[0])

    def test_lettering_report_detects_overflow_and_changed_pixels(self):
        import struct
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);image=p/'image.png'
            image.write_bytes(b'\x89PNG\r\n\x1a\n'+b'\x00'*8+struct.pack('>II',100,100))
            block={'box':{'x':0,'y':0,'width':100,'height':100},'inner':{'left':20,'top':20,'right':80,'bottom':80},'requiredHeight':90,'lines':[{'text':'검사','ink':{'left':20,'top':20,'right':70,'bottom':75}}]}
            report={'engine':'actual-canvas-glyph-metrics','image':str(image),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'text_blocks':[block]}
            f=p/'report.json';f.write_text(json.dumps(report),'utf-8');self.assertEqual(validate(f),[])
            block['lines'][0]['ink']['bottom']=85;f.write_text(json.dumps(report),'utf-8')
            self.assertTrue(any('glyph_outside_parent' in e for e in validate(f)))
            image.write_bytes(image.read_bytes()+b'changed');self.assertIn('final_image_hash_changed',validate(f))


if __name__=='__main__': unittest.main()
