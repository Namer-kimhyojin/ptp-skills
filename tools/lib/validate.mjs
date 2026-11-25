const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const LEVELS = ['full', 'partial', 'none'];
const TOOLS = ['claude', 'codex', 'chatgpt', 'gemini'];
// 결과물 형식. 사이트 표시 이름은 site/src/lib/site.js의 OUTPUTS에 있다.
export const OUTPUTS = ['hwpx', 'docx', 'xlsx', 'pptx', 'pdf', 'text'];
// claude.ai 스킬 업로드의 description 한도
export const DESC_MAX = 200;
const isStr = v => typeof v === 'string' && v.trim() !== '';

export function validateSkill(skill, categories) {
  const errs = [];
  const add = (f, msg) => errs.push(`skills/${skill.name}/${f}: ${msg}`);

  if (!NAME_RE.test(skill.name) || skill.name.length > 64) {
    add('', '폴더 이름은 영문 소문자·숫자·하이픈(-)만 쓰고 64자 이내여야 합니다');
  }
  if (/claude|anthropic/.test(skill.name)) {
    add('', '폴더 이름에 claude, anthropic은 쓸 수 없습니다 (Claude 업로드 규칙)');
  }

  if (skill.skillMdError) add('SKILL.md', skill.skillMdError);
  else if (!skill.files.includes('SKILL.md')) add('SKILL.md', '파일이 없습니다');
  else {
    const fm = skill.frontmatter ?? {};
    if (!isStr(fm.name)) add('SKILL.md', '프런트매터 name이 없습니다');
    else if (fm.name !== skill.name) add('SKILL.md', `프런트매터 name(${fm.name})이 폴더 이름(${skill.name})과 다릅니다`);
    if (!isStr(fm.description)) add('SKILL.md', '프런트매터 description이 없습니다');
    else {
      const n = [...fm.description.trim()].length;
      if (n > DESC_MAX) add('SKILL.md', `프런트매터 description이 ${n}자입니다. claude.ai에 올리려면 ${DESC_MAX}자 이내여야 합니다`);
      if (/[<>]/.test(fm.description)) add('SKILL.md', '프런트매터 description에 < 또는 > 기호를 쓸 수 없습니다');
    }
  }

  const c = skill.catalog;
  if (!c) {
    add('catalog.yaml', skill.catalogError ? `읽을 수 없습니다: ${skill.catalogError}` : '파일이 없습니다');
    return errs;
  }
  for (const k of ['title', 'summary', 'version', 'owner']) {
    if (!isStr(c[k])) add('catalog.yaml', `필수 항목 ${k}이(가) 없거나 비어 있습니다`);
  }
  if (!isStr(c.category)) add('catalog.yaml', '필수 항목 category이(가) 없거나 비어 있습니다');
  else if (!categories.includes(c.category)) {
    add('catalog.yaml', `category "${c.category}"은(는) categories.yaml에 없습니다 (가능: ${categories.join(', ')})`);
  }
  if (!Array.isArray(c.examples) || c.examples.length < 1 || !c.examples.every(isStr)) {
    add('catalog.yaml', 'examples는 문자열 1개 이상의 목록이어야 합니다');
  }
  if (!Array.isArray(c.outputs) || c.outputs.length < 1) {
    add('catalog.yaml', `outputs는 결과물 형식 1개 이상의 목록이어야 합니다 (가능: ${OUTPUTS.join(', ')})`);
  } else {
    const bad = c.outputs.filter(o => !OUTPUTS.includes(o));
    if (bad.length) add('catalog.yaml', `outputs 값 ${bad.join(', ')}은(는) 쓸 수 없습니다 (가능: ${OUTPUTS.join(', ')})`);
  }
  if (c.tags !== undefined && (!Array.isArray(c.tags) || !c.tags.every(isStr))) {
    add('catalog.yaml', 'tags는 문자열 목록이어야 합니다 (예: [보도, 언론])');
  }
  if (!c.compat || typeof c.compat !== 'object') {
    add('catalog.yaml', '필수 항목 compat이(가) 없습니다');
  } else {
    for (const t of TOOLS) {
      const e = c.compat[t];
      if (!e || typeof e !== 'object') { add('catalog.yaml', `compat.${t}이(가) 없습니다`); continue; }
      if (!LEVELS.includes(e.level)) {
        add('catalog.yaml', `compat.${t}.level은 ${LEVELS.join('|')} 중 하나여야 합니다 (현재: ${e.level})`);
      }
      if (!isStr(e.note)) add('catalog.yaml', `compat.${t}.note가 없거나 비어 있습니다`);
    }
  }
  return errs;
}
