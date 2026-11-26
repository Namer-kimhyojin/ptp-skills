import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { buildMarketplace, serializeMarketplace, marketplaceStaleResult, buildPluginFiles, writePluginFiles, pluginFilesStale } from '../tools/lib/marketplace.mjs';
import { makeSkill } from './helpers.mjs';

const skills = [makeSkill({ name: 'ptp-press' })];
const bundles = [
  { id: 'ptp-pr', title: '보도', description: '포항TP 보도·홍보 업무 스킬 모음', categories: ['보도·홍보'] },
  { id: 'ptp-all', title: '전체', description: '전체', categories: 'all' },
  { id: 'ptp-plan', title: '기획', description: '기획', categories: ['사업기획'] },
];

test('묶음마다 plugins/<id> 폴더를 가리킨다', () => {
  const m = buildMarketplace(bundles, skills);
  for (const id of ['ptp-pr', 'ptp-all']) {
    const p = m.plugins.find(x => x.name === id);
    assert.equal(p.source, `./plugins/${id}`);
    assert.equal(p.strict, undefined);
    assert.equal(p.skills, undefined);
  }
});

test('스킬이 없는 묶음은 빠진다', () => {
  const m = buildMarketplace(bundles, skills);
  assert.equal(m.plugins.find(x => x.name === 'ptp-plan'), undefined);
});

test('이름과 소유자', () => {
  const m = buildMarketplace(bundles, skills);
  assert.equal(m.name, 'pohang-tp');
  assert.deepEqual(m.plugins.map(p => p.name), ['ptp-pr', 'ptp-all']);
});

function tmpSkill(name, category = '보도·홍보') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-skill-'));
  fs.mkdirSync(path.join(dir, 'references'));
  fs.writeFileSync(path.join(dir, 'SKILL.md'), '---\nname: x\n---\n본문');
  fs.writeFileSync(path.join(dir, 'catalog.yaml'), 'title: x');
  fs.writeFileSync(path.join(dir, 'references', 'a.md'), '참고');
  fs.mkdirSync(path.join(dir, '__pycache__'));
  fs.writeFileSync(path.join(dir, '__pycache__', 'b.pyc'), 'x');
  const s = makeSkill({ name, dir, files: ['SKILL.md', '__pycache__/b.pyc', 'catalog.yaml', 'references/a.md'] });
  s.catalog.category = category;
  return s;
}

test('묶음 폴더: plugin.json과 스킬 파일 복사본, catalog.yaml·금지 파일은 빠짐', () => {
  const s = tmpSkill('b-skill');
  const files = buildPluginFiles(bundles, [s, tmpSkill('a-skill')]);
  const manifest = JSON.parse(files.get('plugins/ptp-pr/.claude-plugin/plugin.json'));
  assert.equal(manifest.name, 'ptp-pr');
  assert.ok(files.has('plugins/ptp-pr/skills/b-skill/SKILL.md'));
  assert.ok(files.has('plugins/ptp-all/skills/a-skill/references/a.md'));
  assert.ok(![...files.keys()].some(k => k.endsWith('catalog.yaml') || k.endsWith('.pyc')));
  assert.ok(![...files.keys()].some(k => k.startsWith('plugins/ptp-plan/')));
});

test('묶음 폴더 최신 여부: 쓰고 나면 최신, 파일이 바뀌거나 남으면 오래됨', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-root-'));
  const files = buildPluginFiles(bundles, [tmpSkill('a-skill')]);
  assert.equal(pluginFilesStale(root, files), true);
  writePluginFiles(root, files);
  assert.equal(pluginFilesStale(root, files), false);
  fs.writeFileSync(path.join(root, 'plugins/ptp-pr/skills/a-skill/SKILL.md'), '바뀜');
  assert.equal(pluginFilesStale(root, files), true);
  writePluginFiles(root, files);
  fs.writeFileSync(path.join(root, 'plugins/ptp-pr/extra.txt'), '남은 파일');
  assert.equal(pluginFilesStale(root, files), true);
});

test('직렬화는 2칸 들여쓰기와 끝 줄바꿈', () => {
  const s = serializeMarketplace({ a: 1 });
  assert.equal(s, '{\n  "a": 1\n}\n');
});

test('marketplace 최신 여부: 기본은 오류, warn-only는 경고', () => {
  assert.deepEqual(marketplaceStaleResult(false, false), { error: null, warning: null });
  assert.ok(marketplaceStaleResult(true, false).error);
  const r = marketplaceStaleResult(true, true);
  assert.equal(r.error, null);
  assert.ok(r.warning);
});
