import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMarketplace, serializeMarketplace, marketplaceStaleResult } from '../tools/lib/marketplace.mjs';
import { makeSkill } from './helpers.mjs';

const skills = [makeSkill({ name: 'write-pohang-tp-press-release' })];
const bundles = [
  { id: 'ptp-pr', title: '보도', description: '포항TP 보도·홍보 업무 스킬 모음', categories: ['보도·홍보'] },
  { id: 'ptp-all', title: '전체', description: '전체', categories: 'all' },
  { id: 'ptp-plan', title: '기획', description: '기획', categories: ['사업기획'] },
];

test('ptp-pr와 ptp-all은 스킬 경로를 포함한다', () => {
  const m = buildMarketplace(bundles, skills);
  for (const id of ['ptp-pr', 'ptp-all']) {
    const p = m.plugins.find(x => x.name === id);
    assert.deepEqual(p.skills, ['./skills/write-pohang-tp-press-release']);
    assert.equal(p.source, './');
    assert.equal(p.strict, false);
  }
});

test('스킬이 없는 묶음은 빠진다', () => {
  const m = buildMarketplace(bundles, skills);
  assert.equal(m.plugins.find(x => x.name === 'ptp-plan'), undefined);
});

test('이름과 소유자, 경로 정렬', () => {
  const m = buildMarketplace(bundles, [makeSkill({ name: 'b' }), makeSkill({ name: 'a' })]);
  assert.equal(m.name, 'pohang-tp');
  assert.deepEqual(m.plugins[1].skills, ['./skills/a', './skills/b']);
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
