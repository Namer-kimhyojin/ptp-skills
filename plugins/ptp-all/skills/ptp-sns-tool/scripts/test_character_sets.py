#!/usr/bin/env python3
"""Character-set regressions. Custom identities below are isolated synthetic fixtures."""
import argparse
import contextlib
import io
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import character_sets as sets
import resolve_context as routing
import validate_job
import validate_publication
from test_optimization import context
from test_publication_validation import valid_fixture

ROOT = sets.ROOT


class CharacterSetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ptp-character-set-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = sets.load_registry()
        self.manifest = sets.read(ROOT / 'assets/asset-manifest.json')
        paths = {s['identity_spec'] for s in self.registry['sets']}
        paths.update(p for s in self.registry['sets'] for p in s['references'])
        paths.update('assets/' + a['path'] for a in self.manifest['assets'] if a['kind'] == 'character-anchor')
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        # Synthetic new character ID deliberately outside the legacy enum.
        original = next(a for a in self.manifest['assets'] if a['id'] == 'AST-ANCHOR-TEO-V12')
        green = {**original, 'id': 'AST-TEST-GREEN', 'character_id': 'CHR-TEST-GREEN'}
        self.manifest['assets'].append(green)
        self.custom = {
            'id': 'synthetic-team', 'name': 'Synthetic test team', 'version': '1.0', 'status': 'ready',
            'aliases': ['test team'], 'identity_spec': self.registry['sets'][0]['identity_spec'],
            'references': [], 'render_styles': ['2d'],
            'members': [{'id': 'CHR-TEST-GREEN', 'name': 'Test only', 'role': 'Synthetic test role', 'anchor_ids': ['AST-TEST-GREEN']}]
        }
        self.registry['sets'].append(self.custom)
        self.save()

    def save(self):
        (self.root / 'assets/asset-manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.root / 'assets/character-sets.json').write_text(json.dumps(self.registry), encoding='utf-8')

    def test_default_and_legacy_compatibility(self):
        self.assertEqual(sets.select_set()['id'], 'teo-pio')
        for old, expected in sets.LEGACY.items():
            self.assertEqual(sets.select_set(legacy=old)['id'], expected)

    def test_korean_name_alias_and_none(self):
        self.assertEqual(sets.select_set('테오만')['id'], 'teo')
        self.assertEqual(sets.select_set('테오·피오')['id'], 'teo-pio')
        self.assertEqual(sets.select_set('캐릭터 없이')['members'], [])

    def test_unknown_and_conflicting_choices_fail(self):
        with self.assertRaises(ValueError):
            sets.select_set('missing')
        with self.assertRaises(ValueError):
            sets.select_set('none', legacy='both')

    def test_alias_collision_rejected(self):
        self.custom['aliases'] = ['테오만']
        self.save()
        with self.assertRaisesRegex(ValueError, '충돌'):
            sets.load_registry(root=self.root)

    def test_wrong_character_anchor_and_hash_fail(self):
        self.custom['members'][0]['id'] = 'CHR-WRONG'
        with self.assertRaises(ValueError):
            sets.validate_entry(self.custom, self.root)
        self.custom['members'][0]['id'] = 'CHR-TEST-GREEN'
        self.manifest['assets'][-1]['sha256'] = '0' * 64
        self.save()
        with self.assertRaisesRegex(ValueError, '해시'):
            sets.validate_entry(self.custom, self.root)

    def test_pending_assets_cannot_be_ready(self):
        self.manifest['assets'][-1]['approval'] = 'review_only'
        self.save()
        with self.assertRaises(ValueError):
            sets.validate_entry(self.custom, self.root)
        self.custom['status'] = 'draft'
        sets.validate_entry(self.custom, self.root)

    def test_disabled_draft_and_unsupported_style(self):
        self.custom['status'] = 'draft'
        self.assertEqual(sets.select_set('test team', registry=self.registry)['status'], 'draft')
        with self.assertRaises(ValueError):
            sets.select_set('test team', registry=self.registry, publication=True)
        with self.assertRaises(ValueError):
            sets.select_set('test team', registry=self.registry, render_style='3d')
        self.custom['status'] = 'disabled'
        with self.assertRaises(ValueError):
            sets.select_set('test team', registry=self.registry)

    def test_no_character_route_has_no_character_refs_or_poses(self):
        result = context(character='none')
        self.assertEqual(result['resolved_characters'], [])
        self.assertEqual(result['character_set']['id'], 'none')
        self.assertFalse(any('/characters/' in p or '/guides/' in p for p in result['assets']))
        self.assertNotIn('references/character-identity.md', result['references'])
        self.assertNotIn('scripts/validate_pose_library.py', result['validators'])

    def test_single_cast_route_excludes_other_member(self):
        result = context(character=None, character_set='pio')
        self.assertEqual([m['id'] for m in result['resolved_characters']], ['CHR-ORANGE'])
        self.assertFalse(any('teo' in p or 'family' in p for p in result['assets']))

    def test_custom_route_has_no_legacy_identity_refs(self):
        load = routing.load_json
        def load_mock(path):
            return self.manifest if path == 'assets/asset-manifest.json' else load(path)
        with patch.object(routing, 'select_set', return_value=self.custom), patch.object(routing, 'snapshot', side_effect=lambda e: sets.snapshot(e, self.root)), patch.object(routing, 'load_json', side_effect=load_mock):
            result = context(character=None, character_set='synthetic-team', render_style=None)
        self.assertEqual(result['resolved_characters'][0]['id'], 'CHR-TEST-GREEN')
        self.assertEqual(result['request']['render_style'], '2d')
        self.assertNotIn('references/character-identity.md', result['references'])
        self.assertNotIn('references/3d-generation-prompts.md', result['references'])

    def test_job_none_application_and_standard_validation(self):
        original = sets.read(ROOT / 'assets/single-image-job-template.json')
        job = sets.apply_to_job(original, sets.select_set('none'), 'Synthetic explicit no-character request')
        self.assertEqual(len(original['characters']), 2)
        self.assertEqual(job['characters'], [])
        path = self.root / 'job.json'
        path.write_text(json.dumps(job), encoding='utf-8')
        self.assertEqual(validate_job.validate(path, False)[0], [])
        job['characters'] = original['characters']
        self.assertTrue(sets.validate_selection(job)[0])

    def test_set_snapshot_detects_definition_or_member_change(self):
        job = sets.apply_to_job({'status': 'draft'}, self.custom, 'Synthetic test choice', self.root)
        self.assertEqual(sets.validate_selection(job, root=self.root)[0], [])
        job['character_set']['version'] = 'forged'
        self.assertTrue(sets.validate_selection(job, root=self.root)[0])
        job['character_set'] = sets.snapshot(self.custom, self.root)
        job['characters'][0]['anchor_ids'] = []
        self.assertTrue(sets.validate_selection(job, root=self.root)[0])

    def test_none_blocks_leftover_character_layer(self):
        job = sets.apply_to_job({'status': 'draft'}, sets.select_set('none'), 'test')
        job['design'] = {'visual_system': {'layer_plan': [{'role': 'character'}]}}
        self.assertTrue(sets.validate_selection(job)[0])

    def test_register_command_adds_without_touching_installed_registry(self):
        entry = deepcopy(sets.load_registry()['sets'][0])
        entry.update(id='isolated-duo', name='Isolated test duo', aliases=['isolated alias'])
        source = self.root / 'entry.json'
        target = self.root / 'registry.json'
        source.write_text(json.dumps(entry), encoding='utf-8')
        before = sets.REGISTRY.read_bytes()
        with patch.object(sets, 'REGISTRY', target), patch.object(sys, 'argv', ['character_sets.py', 'register', '--file', str(source)]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sets.main(), 0)
        self.assertEqual(sets.read(target)['sets'][-1]['id'], 'isolated-duo')
        self.assertEqual(sets.REGISTRY.read_bytes(), before)

    def test_register_collision_leaves_no_partial_file(self):
        entry = deepcopy(sets.load_registry()['sets'][0])
        entry.update(id='isolated-bad', name='Isolated bad', aliases=['테오만'])
        source = self.root / 'entry.json'
        target = self.root / 'registry.json'
        source.write_text(json.dumps(entry), encoding='utf-8')
        with patch.object(sets, 'REGISTRY', target), patch.object(sys, 'argv', ['character_sets.py', 'register', '--file', str(source)]), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sets.main(), 1)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_suffix('.json.tmp').exists())

    def test_locked_jobs_not_mutated_and_cast_review_required(self):
        with self.assertRaises(ValueError):
            sets.apply_to_job({'status': 'locked'}, sets.select_set('none'), 'test')
        job = sets.apply_to_job({'status': 'draft', 'comic': {'panel_contract': [{'characters': ['CHR-BLUE']}] }}, sets.select_set('pio'), 'test')
        self.assertTrue(job['comic']['cast_revision_required'])
        self.assertEqual(job['comic']['panel_contract'][0]['characters'], [])

    def test_real_publication_validator_accepts_selected_builtin(self):
        job = valid_fixture()
        entry = sets.select_set('teo-pio')
        job.update(character_set=sets.snapshot(entry), character_mode='set', character_selection_evidence='Synthetic test selection')
        job['design']['character_integration']['actions'] = {m['id']: 'Synthetic test action' for m in entry['members']}
        path = self.root / 'job.json'
        path.write_text(json.dumps(job), encoding='utf-8')
        self.assertEqual(validate_publication.validate(path)[0], [])

    def test_custom_character_passes_job_and_publication_authority(self):
        job = valid_fixture()
        job['characters'] = [{'id': 'CHR-TEST-GREEN', 'role': 'Synthetic fixture role', 'outfit_slot': 'default', 'anchor_ids': ['AST-TEST-GREEN'], 'approval': 'approved'}]
        job.update(character_set=sets.snapshot(self.custom, self.root), character_mode='set', character_selection_evidence='Synthetic test selection', publication_asset_ids=['AST-TEST-GREEN'])
        job['design']['character_integration'] = {'actions': {'CHR-TEST-GREEN': 'Synthetic test action'}, 'functional_target': 'Synthetic test purpose'}
        path = self.root / 'job.json'
        path.write_text(json.dumps(job), encoding='utf-8')
        real_validate = sets.validate_selection
        with patch.object(sets, 'validate_selection', side_effect=lambda data, **kw: real_validate(data, root=self.root, **kw)), patch.object(validate_job, 'load_asset_approvals', return_value={a['id']: a['approval'] for a in self.manifest['assets']}), patch.object(validate_publication, 'MANIFEST', self.root / 'assets/asset-manifest.json'), patch.object(validate_publication.validate_assets, 'validate', return_value=([], [])):
            self.assertEqual(validate_job.validate(path, True)[0], [])
            self.assertEqual(validate_publication.validate(path)[0], [])

    def test_cli_listing_and_conflict(self):
        script = ROOT / 'scripts/resolve_context.py'
        result = subprocess.run([sys.executable, '-X', 'utf8', str(script), '--list-character-sets'], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s['id'] for s in json.loads(result.stdout)], ['none', 'teo-pio', 'teo', 'pio'])
        bad = subprocess.run([sys.executable, '-X', 'utf8', str(script), '--character-set', 'none', '--character', 'both'], capture_output=True)
        self.assertNotEqual(bad.returncode, 0)


if __name__ == '__main__':
    unittest.main()
