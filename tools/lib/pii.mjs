import fs from 'node:fs';
import path from 'node:path';
import { unzipSync } from 'fflate';

const PERSONAL_DOMAINS = ['gmail.com', 'naver.com', 'daum.net', 'hanmail.net', 'kakao.com', 'nate.com', 'hotmail.com', 'outlook.com', 'icloud.com'];
const ZIP_EXT = new Set(['.hwpx', '.docx', '.xlsx', '.pptx']);
const TEXT_EXT = new Set(['.md', '.txt', '.py', '.yaml', '.yml', '.json', '.bat', '.js', '.mjs', '.html', '.csv']);

const RRN = /(?<!\d)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-[1-4]\d{6}(?!\d)/g;
const MOBILE = /(?<!\d)01[016789][-. ]?\d{3,4}[-. ]?\d{4}(?!\d)/g;
const EMAIL = new RegExp(
  `[A-Za-z0-9._%+-]+@(?:${PERSONAL_DOMAINS.map(d => d.replace('.', '\\.')).join('|')})(?![A-Za-z0-9.-])`,
  'gi',
);

export function scanTextForPII(text) {
  const out = [];
  for (const m of text.matchAll(RRN)) out.push({ type: '주민등록번호', match: m[0] });
  for (const m of text.matchAll(MOBILE)) {
    if (/^0+$/.test(m[0].replace(/\D/g, '').slice(3))) continue; // 0으로 채운 예시 번호
    out.push({ type: '휴대전화번호', match: m[0] });
  }
  for (const m of text.matchAll(EMAIL)) out.push({ type: '개인 이메일', match: m[0] });
  return out;
}

export function scanFileForPII(absPath) {
  const ext = path.extname(absPath).toLowerCase();
  if (ZIP_EXT.has(ext)) {
    let entries;
    try {
      entries = unzipSync(new Uint8Array(fs.readFileSync(absPath)), { filter: f => /\.(xml|txt)$/i.test(f.name) });
    } catch (cause) {
      const err = new Error('압축 파일을 읽을 수 없어 개인정보 검사를 하지 못했습니다', { cause });
      err.code = 'ZIP_UNREADABLE';
      throw err;
    }
    const out = [];
    for (const data of Object.values(entries)) {
      out.push(...scanTextForPII(Buffer.from(data).toString('utf8')));
    }
    return out;
  }
  if (TEXT_EXT.has(ext)) return scanTextForPII(fs.readFileSync(absPath, 'utf8'));
  return [];
}

export function maskMatch(hit) {
  const m = hit.match;
  if (hit.type === '개인 이메일') {
    const at = m.lastIndexOf('@');
    return `${m.slice(0, 1)}***${m.slice(at)}`;
  }
  if (hit.type === '주민등록번호') return m.replace(/\d/g, '*');
  const digits = m.replace(/\D/g, '');
  const sep = m.match(/[-. ]/)?.[0] ?? '';
  return `${digits.slice(0, 3)}${sep}${'*'.repeat(digits.length - 7)}${sep}${digits.slice(-4)}`;
}
