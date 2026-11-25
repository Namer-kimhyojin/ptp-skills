import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseSkillMd } from '../tools/lib/frontmatter.mjs';

test('CRLF와 BOM이 있어도 읽는다', () => {
  const r = parseSkillMd('\uFEFF---\r\nname: a-b\r\ndescription: 설명\r\n---\r\n본문');
  assert.equal(r.data.name, 'a-b');
  assert.equal(r.body.trim(), '본문');
});
test('프런트매터가 없으면 한국어 오류', () => {
  assert.throws(() => parseSkillMd('# 제목'), /프런트매터가 없습니다/);
});
