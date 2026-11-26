import fs from 'node:fs';
import path from 'node:path';
import { zipSync } from 'fflate';
import { findForbiddenFiles } from './skills.mjs';

export const GPT_INSTRUCTION_LIMIT = 8000;
const MTIME = new Date('2026-01-01T00:00:00Z');

export function distributable(skill) {
  const forbidden = new Set(findForbiddenFiles(skill.files));
  return skill.files.filter(f => !forbidden.has(f) && f !== 'catalog.yaml');
}

function zip(skill, entries) {
  const obj = {};
  for (const [name, data] of entries) obj[`${skill.name}/${name}`] = [data, { mtime: MTIME }];
  return zipSync(obj);
}

const read = (skill, f) => new Uint8Array(fs.readFileSync(path.join(skill.dir, f)));

export function buildSkillZip(skill) {
  return zip(skill, distributable(skill).map(f => [f, read(skill, f)]));
}

export function buildStarterPrompt(skill) {
  return `첨부한 SKILL.md의 지침과 references 폴더의 문서를 작업 기준으로 삼아라. 사용자가 요청하면 그 기준에 따라 "${skill.catalog.title}" 작업을 수행하라. 첨부 문서와 사용자 지시가 다르면 사용자에게 확인하라.`;
}

// Gemini 앱 스킬 업로드 규칙(2026-11-26 확인, support.google.com/gemini/answer/17094296·18977944):
// SKILL.md가 zip 맨 위에 있어야 하고, 한 스킬에 파일 100개·100MB까지, 아래 형식만 받는다(HWPX·글꼴·압축 파일 불가).
export const GEMINI_MAX_FILES = 100;
const GEMINI_EXT = /\.(md|markdown|txt|rst|log|tex|pdf|docx|odt|rtf|csv|xlsx|ods|json|toml|xml|ya?ml|pptx|odp|png|jpe?g|svg|gif|webp|heic|ico|tiff?|py|sh|ipynb|js|html?|css)$/i;
// 파일이 100개를 넘으면 앞 순서부터 담는다: 지침 → 참고 문서 → 자산 → 설정 → 스크립트 → 시험 코드 → 나머지
function geminiRank(f) {
  if (f === 'SKILL.md') return 0;
  if (f.startsWith('references/')) return 1;
  if (f.startsWith('assets/')) return 2;
  if (f.startsWith('config/')) return 3;
  if (f.startsWith('scripts/') && !/(^|\/)test_[^/]*$/.test(f)) return 4;
  if (f.startsWith('scripts/')) return 5;
  return 6;
}

// catalog.yaml의 gemini_exclude(경로 앞부분 목록)에 걸리는 파일은 Gemini용 zip에서 뺀다.
export function geminiFiles(skill) {
  const skip = skill.catalog?.gemini_exclude ?? [];
  const excluded = f => skip.some(p => f === p || f.startsWith(p.endsWith('/') ? p : `${p}/`));
  const all = distributable(skill).filter(f => !excluded(f));
  const ok = all.filter(f => GEMINI_EXT.test(f));
  ok.sort((a, b) => geminiRank(a) - geminiRank(b) || a.localeCompare(b));
  const unsupported = all.filter(f => !GEMINI_EXT.test(f));
  const skipped = distributable(skill).filter(excluded);
  return { keep: ok.slice(0, GEMINI_MAX_FILES), dropped: [...skipped, ...unsupported, ...ok.slice(GEMINI_MAX_FILES)] };
}

// Gemini용 zip: 폴더 없이 SKILL.md가 맨 위에 오도록 담는다.
export function buildGeminiZip(skill) {
  const obj = {};
  for (const f of geminiFiles(skill).keep) obj[f] = [read(skill, f), { mtime: MTIME }];
  return zipSync(obj);
}

export function buildInstructions(skill) {
  const text = skill.body;
  return { text, overLimit: [...text].length > GPT_INSTRUCTION_LIMIT };
}
