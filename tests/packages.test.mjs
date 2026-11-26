import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { unzipSync } from 'fflate';
import { makeSkill } from './helpers.mjs';
import {
  buildSkillZip, buildGeminiZip, geminiFiles, GEMINI_MAX_FILES, buildInstructions, buildStarterPrompt,
} from '../tools/lib/packages.mjs';

const name = 'ptp-press';
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-pkg-'));
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const files = {
  'SKILL.md': '---\nname: x\n---\n본문',
  'catalog.yaml': 'title: t',
  'install_windows.bat': '@echo off\r\necho hi\r\n',
  'references/a.md': '문서',
  'assets/b.txt': 'asset',
  'assets/form.hwpx': 'PK',
  'assets/pic.PNG': 'img',
  'scripts/run.py': 'print(1)',
  'scripts/__pycache__/run.pyc': 'x',
  'runtime-python.txt': 'x',
};
for (const [f, c] of Object.entries(files)) {
  fs.mkdirSync(path.dirname(path.join(tmp, f)), { recursive: true });
  fs.writeFileSync(path.join(tmp, f), c);
}
const skill = makeSkill({ name, dir: tmp, files: Object.keys(files).sort() });

test('Claude zip: 최상위 폴더, catalog.yaml·금지 파일 제외, CRLF 유지', () => {
  const z = unzipSync(buildSkillZip(skill));
  const entries = Object.keys(z);
  assert.ok(entries.every(e => e.startsWith(`${name}/`)));
  assert.ok(entries.includes(`${name}/SKILL.md`));
  assert.ok(entries.includes(`${name}/scripts/run.py`));
  assert.ok(!entries.some(e => e.endsWith('catalog.yaml') || e.includes('__pycache__') || e.endsWith('runtime-python.txt')));
  assert.equal(Buffer.from(z[`${name}/install_windows.bat`]).toString(), files['install_windows.bat']);
});

test('Gemini zip: SKILL.md가 맨 위, 지원 형식만(스크립트 포함, HWPX·bat 제외)', () => {
  const z = unzipSync(buildGeminiZip(skill));
  assert.deepEqual(Object.keys(z).sort(), [
    'SKILL.md', 'assets/b.txt', 'assets/pic.PNG', 'references/a.md', 'scripts/run.py',
  ].sort());
  const { dropped } = geminiFiles(skill);
  assert.ok(dropped.includes('assets/form.hwpx') && dropped.includes('install_windows.bat'));
});

test('Gemini zip: 파일이 100개를 넘으면 지침·참고 문서부터 담고 시험 코드를 먼저 뺀다', () => {
  const many = ['SKILL.md', ...Array.from({ length: 60 }, (_, i) => `references/r${i}.md`),
    ...Array.from({ length: 50 }, (_, i) => `scripts/s${i}.py`), ...Array.from({ length: 20 }, (_, i) => `scripts/test_${i}.py`)];
  const s = makeSkill({ files: many });
  const { keep, dropped } = geminiFiles(s);
  assert.equal(keep.length, GEMINI_MAX_FILES);
  assert.equal(keep[0], 'SKILL.md');
  assert.ok(keep.every(f => !f.includes('test_')));
  assert.equal(dropped.length, many.length - GEMINI_MAX_FILES);
});

test('Gemini zip: catalog.yaml의 gemini_exclude 경로는 뺀다', () => {
  const s = makeSkill({ files: ['SKILL.md', 'references/a.md', 'scripts/a.py', 'scripts/b.py', 'assets/logo/x.png', 'assets/logo.json'] });
  s.catalog.gemini_exclude = ['scripts/', 'assets/logo'];
  const { keep, dropped } = geminiFiles(s);
  assert.deepEqual(keep, ['SKILL.md', 'references/a.md', 'assets/logo.json']);
  assert.deepEqual(dropped.sort(), ['assets/logo/x.png', 'scripts/a.py', 'scripts/b.py']);
});

test('zip은 입력이 같으면 바이트가 같다', () => {
  assert.deepEqual(buildSkillZip(skill), buildSkillZip(skill));
});

test('시작 프롬프트에 제목이 들어간다', () => {
  assert.match(buildStarterPrompt(skill), /"보도자료 작성" 작업을 수행하라/);
});

test('8000자 초과 판정', () => {
  assert.equal(buildInstructions(makeSkill({ body: '가'.repeat(8001) })).overLimit, true);
  assert.equal(buildInstructions(makeSkill({ body: '가'.repeat(8000) })).overLimit, false);
});
