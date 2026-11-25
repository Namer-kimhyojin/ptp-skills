import fs from 'node:fs';
import path from 'node:path';
import { zipSync } from 'fflate';
import { findForbiddenFiles } from './skills.mjs';

export const GPT_INSTRUCTION_LIMIT = 8000;
const MTIME = new Date('2026-01-01T00:00:00Z');

function distributable(skill) {
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

export function buildGptGeminiZip(skill) {
  const keep = distributable(skill)
    .filter(f => f === 'SKILL.md' || f.startsWith('references/') || f.startsWith('assets/'));
  const entries = keep.map(f => [f, read(skill, f)]);
  entries.push(['사용법.txt', new TextEncoder().encode(buildStarterPrompt(skill))]);
  return zip(skill, entries);
}

export function buildInstructions(skill) {
  const text = skill.body;
  return { text, overLimit: [...text].length > GPT_INSTRUCTION_LIMIT };
}
