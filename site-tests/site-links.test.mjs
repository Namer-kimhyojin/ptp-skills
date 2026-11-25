// 빌드된 사이트(dist) 점검. `npm run build` 뒤에 실행한다. dist가 없으면 실패한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve('dist');
const BASE = '/ptp-skills/';
const skill = 'write-pohang-tp-press-release';

function htmlFiles(dir) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...htmlFiles(p));
    else if (e.name.endsWith('.html')) out.push(p);
  }
  return out;
}

test('dist 폴더가 있다 (먼저 npm run build)', () => {
  assert.ok(fs.existsSync(dist), 'dist가 없습니다. npm run build를 먼저 실행하세요.');
});

test('필요한 페이지와 검색 색인이 있다', () => {
  for (const f of [
    'index.html',
    `skills/${skill}/index.html`,
    'install/index.html',
    'contribute/index.html',
    'pagefind/pagefind.js',
    `downloads/${skill}.zip`,
    `downloads/${skill}-gpt-gemini.zip`,
  ]) {
    assert.ok(fs.existsSync(path.join(dist, f)), `${f} 없음`);
  }
});

test('사이트 루트(/)로 시작하는 링크는 모두 /ptp-skills/ 아래에 있다', () => {
  const files = htmlFiles(dist);
  assert.ok(files.length > 0, 'HTML 파일이 없습니다');
  const bad = [];
  for (const f of files) {
    const html = fs.readFileSync(f, 'utf8');
    for (const m of html.matchAll(/\b(?:href|src)="(\/[^"]*)"/g)) {
      if (!m[1].startsWith(BASE) || m[1].startsWith(`${BASE}/`)) {
        bad.push(`${path.relative(dist, f)}: ${m[0]}`);
      }
    }
  }
  assert.deepEqual(bad, []);
});

test('상세 페이지에 Claude용 zip과 GPT·Gemini용 zip 링크가 있다', () => {
  const html = fs.readFileSync(path.join(dist, 'skills', skill, 'index.html'), 'utf8');
  assert.ok(html.includes(`href="${BASE}downloads/${skill}.zip"`), 'Claude zip 링크 없음');
  assert.ok(html.includes(`href="${BASE}downloads/${skill}-gpt-gemini.zip"`), 'GPT·Gemini zip 링크 없음');
  assert.ok(html.includes('data-pagefind-body'), '검색 색인 표시 없음');
});
