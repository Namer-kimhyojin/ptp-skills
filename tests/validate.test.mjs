import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateSkill } from '../tools/lib/validate.mjs';
import { findForbiddenFiles } from '../tools/lib/skills.mjs';
import { makeSkill, okCatalog } from './helpers.mjs';

const C = ['보도·홍보'];

test('정상 스킬은 오류 없음', () => assert.deepEqual(validateSkill(makeSkill(), C), []));
test('catalog에 선택 키(updated)가 있어도 통과', () => {
  assert.deepEqual(validateSkill(makeSkill({ catalog: { ...okCatalog, updated: '2026-11-25', extra: 1 } }), C), []);
});
test('폴더명 규칙 위반', () => {
  const e = validateSkill(makeSkill({ name: '보도자료 Skill' }), C);
  assert.ok(e.some(m => m.includes('폴더 이름')));
});
test('name과 폴더명 불일치', () => {
  const e = validateSkill(makeSkill({ frontmatter: { name: 'other', description: 'x' } }), C);
  assert.ok(e.some(m => m.includes('name')));
});
test('description 없음', () => {
  const e = validateSkill(makeSkill({ frontmatter: { name: 'sample-skill' } }), C);
  assert.ok(e.some(m => m.includes('description')));
});
test('모든 메시지는 skills/<name>/<파일>: 접두어', () => {
  const e = validateSkill(makeSkill({ catalog: null, frontmatter: {} }), C);
  assert.ok(e.length > 0 && e.every(m => m.startsWith('skills/sample-skill/')));
});
test('catalog.yaml 없음', () => {
  const e = validateSkill(makeSkill({ catalog: null }), C);
  assert.ok(e.some(m => m.includes('catalog.yaml') && m.includes('없습니다')));
});
test('catalog.yaml 파싱 오류', () => {
  const e = validateSkill(makeSkill({ catalog: null, catalogError: 'bad yaml' }), C);
  assert.ok(e.some(m => m.includes('catalog.yaml') && m.includes('bad yaml')));
});
test('필수 키 누락', () => {
  const { owner, ...rest } = okCatalog;
  const e = validateSkill(makeSkill({ catalog: rest }), C);
  assert.ok(e.some(m => m.includes('owner')));
});
test('examples 비어 있음', () => {
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, examples: [] } }), C);
  assert.ok(e.some(m => m.includes('examples')));
});
test('분류가 목록에 없음', () => {
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, category: '기타' } }), C);
  assert.ok(e.some(m => m.includes('category') && m.includes('기타')));
});
test('compat level 값 오류', () => {
  const compat = { ...okCatalog.compat, claude: { level: 'yes', note: 'x' } };
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, compat } }), C);
  assert.ok(e.some(m => m.includes('compat.claude.level')));
});
test('compat 도구 누락', () => {
  const { gemini, ...compat } = okCatalog.compat;
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, compat } }), C);
  assert.ok(e.some(m => m.includes('compat.gemini')));
});
test('outputs 없음', () => {
  const { outputs, ...rest } = okCatalog;
  const e = validateSkill(makeSkill({ catalog: rest }), C);
  assert.ok(e.some(m => m.includes('outputs')));
});
test('outputs 값 오류', () => {
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, outputs: ['hwp'] } }), C);
  assert.ok(e.some(m => m.includes('outputs') && m.includes('hwp')));
});
test('tags는 선택이지만 쓰면 문자열 목록', () => {
  assert.deepEqual(validateSkill(makeSkill({ catalog: { ...okCatalog, tags: ['보도', '언론'] } }), C), []);
  const e = validateSkill(makeSkill({ catalog: { ...okCatalog, tags: '보도' } }), C);
  assert.ok(e.some(m => m.includes('tags')));
});
test('description은 claude.ai 업로드 한도 200자 이내', () => {
  const ok = validateSkill(makeSkill({ frontmatter: { name: 'sample-skill', description: '가'.repeat(200) } }), C);
  assert.deepEqual(ok, []);
  const e = validateSkill(makeSkill({ frontmatter: { name: 'sample-skill', description: '가'.repeat(201) } }), C);
  assert.ok(e.some(m => m.includes('description') && m.includes('200')));
});
test('description에 < > 금지', () => {
  const e = validateSkill(makeSkill({ frontmatter: { name: 'sample-skill', description: '<b>보도</b>' } }), C);
  assert.ok(e.some(m => m.includes('description') && m.includes('<')));
});
test('이름에 claude·anthropic 금지', () => {
  const e = validateSkill(makeSkill({ name: 'claude-helper', frontmatter: { name: 'claude-helper', description: 'x' } }), C);
  assert.ok(e.some(m => m.includes('claude')));
});
test('금지 파일', () => {
  assert.deepEqual(
    findForbiddenFiles(['SKILL.md', 'scripts/__pycache__/a.pyc', 'runtime-python.txt']).sort(),
    ['runtime-python.txt', 'scripts/__pycache__/a.pyc'],
  );
});
test('금지 파일: .env, backup 폴더, venv, 단독 pyc', () => {
  const f = ['.env', 'x/y.backup-2026/a.md', '.venv/a', 'venv/b', 'a/b.pyc', 'a/env.md', 'a/.env.example'];
  assert.deepEqual(findForbiddenFiles(f).sort(), ['.env', '.venv/a', 'a/b.pyc', 'venv/b', 'x/y.backup-2026/a.md'].sort());
});
