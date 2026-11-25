import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { zipSync, strToU8 } from 'fflate';
import { scanTextForPII, scanFileForPII, maskMatch } from '../tools/lib/pii.mjs';

const fx = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-pii-'));
after(() => fs.rmSync(fx, { recursive: true, force: true }));

test('주민번호·휴대폰·개인 이메일 탐지', () => {
  const t = scanTextForPII('900101-1234567 / 010-1234-5678 / hong@naver.com / press@ptp.or.kr / 054-223-2000');
  assert.deepEqual(t.map(x => x.type).sort(), ['개인 이메일', '주민등록번호', '휴대전화번호']);
});
test('0으로 채운 예시 번호는 무시', () => assert.deepEqual(scanTextForPII('010-0000-0000'), []));
test('HWPX 내부 XML까지 검사', () => {
  const p = path.join(fx, 'sample.hwpx');
  fs.writeFileSync(p, zipSync({ 'Contents/section0.xml': strToU8('<p>010-9876-5432</p>'), 'Preview/PrvText.txt': strToU8('hong@naver.com'), 'a.png': strToU8('010-1111-2222') }));
  const r = scanFileForPII(p);
  assert.deepEqual(r.map(x => x.type).sort(), ['개인 이메일', '휴대전화번호']);
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
test('손상된 zip은 검사 불가 오류(fail closed)', () => {
  const p = path.join(fx, 'broken.hwpx');
  fs.writeFileSync(p, 'not a zip');
  assert.throws(() => scanFileForPII(p), /개인정보 검사를 하지 못했습니다/);
});
test('maskMatch는 값을 가린다', () => {
  assert.equal(maskMatch({ type: '휴대전화번호', match: '010-1234-5678' }), '010-****-5678');
  assert.equal(maskMatch({ type: '휴대전화번호', match: '01012345678' }), '010****5678');
  assert.equal(maskMatch({ type: '주민등록번호', match: '900101-1234567' }), '******-*******');
  assert.equal(maskMatch({ type: '개인 이메일', match: 'hong@naver.com' }), 'h***@naver.com');
});
