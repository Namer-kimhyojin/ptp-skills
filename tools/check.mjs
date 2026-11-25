import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadSkills, loadCategories, findForbiddenFiles } from './lib/skills.mjs';
import { validateSkill } from './lib/validate.mjs';
import { scanFileForPII, maskMatch } from './lib/pii.mjs';

const MB = 1024 * 1024;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const categories = loadCategories(root);
const skills = loadSkills(root);
const errors = [];
const warnings = [];

for (const s of skills) {
  errors.push(...validateSkill(s, categories));
  for (const f of findForbiddenFiles(s.files)) {
    errors.push(`skills/${s.name}/${f}: 배포에 넣을 수 없는 파일입니다`);
  }
  let total = 0;
  for (const f of s.files) {
    const abs = path.join(s.dir, f);
    total += fs.statSync(abs).size;
    let hits = [];
    try {
      hits = scanFileForPII(abs);
    } catch (e) {
      if (e.code !== 'ZIP_UNREADABLE') throw e;
      errors.push(`skills/${s.name}/${f}: ${e.message}`);
    }
    for (const hit of hits) {
      errors.push(`skills/${s.name}/${f}: 개인정보로 보이는 ${hit.type}이(가) 있습니다 (${maskMatch(hit)})`);
    }
  }
  const mb = (total / MB).toFixed(1);
  if (total > 50 * MB) errors.push(`skills/${s.name}/: 전체 크기가 ${mb}MB로 50MB를 넘습니다`);
  else if (total > 10 * MB) warnings.push(`skills/${s.name}/: 전체 크기가 ${mb}MB로 10MB를 넘습니다`);
}

for (const w of warnings) console.warn(`경고: ${w}`);
if (errors.length) {
  console.error(`점검 실패: 오류 ${errors.length}건`);
  for (const e of errors) console.error(` - ${e}`);
  process.exit(1);
}
console.log(`점검 통과: 스킬 ${skills.length}개`);
