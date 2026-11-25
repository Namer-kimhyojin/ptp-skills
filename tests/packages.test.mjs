import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { unzipSync } from 'fflate';
import { makeSkill } from './helpers.mjs';
import {
  buildSkillZip, buildGptGeminiZip, buildInstructions, buildStarterPrompt,
} from '../tools/lib/packages.mjs';

const name = 'write-pohang-tp-press-release';
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-pkg-'));
test.after(() => fs.rmSync(tmp, { recursive: true, force: true }));
const files = {
  'SKILL.md': '---\nname: x\n---\n본문',
  'catalog.yaml': 'title: t',
  'install_windows.bat': '@echo off\r\necho hi\r\n',
  'references/a.md': '문서',
  'assets/b.txt': 'asset',
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

test('GPT·Gemini zip: scripts 제외, 사용법.txt 포함', () => {
  const z = unzipSync(buildGptGeminiZip(skill));
  const entries = Object.keys(z).sort();
  assert.deepEqual(entries, [
    `${name}/SKILL.md`, `${name}/assets/b.txt`, `${name}/references/a.md`, `${name}/사용법.txt`,
  ].sort());
  assert.equal(Buffer.from(z[`${name}/사용법.txt`]).toString(), buildStarterPrompt(skill));
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
