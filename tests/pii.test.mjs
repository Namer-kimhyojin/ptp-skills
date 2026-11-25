import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { zipSync, strToU8 } from 'fflate';
import { scanTextForPII, scanFileForPII } from '../tools/lib/pii.mjs';

const fx = path.join(import.meta.dirname, 'fixtures');

test('주민번호·휴대폰·개인 이메일 탐지', () => {
  const t = scanTextForPII('900101-1234567 / 010-1234-5678 / hong@naver.com / press@ptp.or.kr / 054-223-2000');
  assert.deepEqual(t.map(x => x.type).sort(), ['개인 이메일', '주민등록번호', '휴대전화번호']);
});
test('0으로 채운 예시 번호는 무시', () => assert.deepEqual(scanTextForPII('010-0000-0000'), []));
test('HWPX 내부 XML까지 검사', () => {
  fs.mkdirSync(fx, { recursive: true });
  const p = path.join(fx, 'sample.hwpx');
  fs.writeFileSync(p, zipSync({ 'Contents/section0.xml': strToU8('<p>010-9876-5432</p>'), 'a.png': strToU8('010-1111-2222') }));
  const r = scanFileForPII(p);
  assert.equal(r.length, 1);
  assert.equal(r[0].type, '휴대전화번호');
});
test('이미지 같은 바이너리는 건너뜀', () => {
  const p = path.join(fx, 'sample.png');
  fs.writeFileSync(p, Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x30, 0x31, 0x30]));
  assert.deepEqual(scanFileForPII(p), []);
});
test('텍스트 파일은 그대로 검사', () => {
  const p = path.join(fx, 'a.md');
  fs.writeFileSync(p, '문의 gmail 계정 kim@gmail.com');
  assert.equal(scanFileForPII(p)[0].type, '개인 이메일');
});
