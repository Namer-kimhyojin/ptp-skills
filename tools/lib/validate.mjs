const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const LEVELS = ['full', 'partial', 'none'];
// 지원 범위는 Claude 앱·ChatGPT 앱(Codex 포함)·Gemini 앱 세 곳으로 적는다.
export const TOOLS = ['claude', 'chatgpt', 'gemini'];
// 결과물 형식. 사이트 표시 이름은 site/src/lib/site.js의 OUTPUTS에 있다.
export const OUTPUTS = ['hwpx', 'docx', 'xlsx', 'pptx', 'pdf', 'html', 'png', 'mp4', 'text'];
// claude.ai 스킬 업로드의 description 한도
export const DESC_MAX = 200;
// 스킬 상세 화면의 작업 흐름 도식(catalog.yaml process) 단계 수와 글자 수
export const PROCESS_MIN = 3;
export const PROCESS_MAX = 6;
export const PROCESS_TITLE_MAX = 12;
export const PROCESS_DESC_MAX = 40;
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
  if (c.gemini_exclude !== undefined && (!Array.isArray(c.gemini_exclude) || !c.gemini_exclude.every(isStr))) {
    add('catalog.yaml', 'gemini_exclude는 경로 목록이어야 합니다 (예: [scripts/, assets/logos/])');
  }
  if (c.process !== undefined) {
    const p = c.process;
    if (!Array.isArray(p) || p.length < PROCESS_MIN || p.length > PROCESS_MAX) {
      add('catalog.yaml', `process는 단계 ${PROCESS_MIN}~${PROCESS_MAX}개의 목록이어야 합니다`);
    } else {
      p.forEach((s, i) => {
        const n = i + 1;
        if (!s || typeof s !== 'object' || Array.isArray(s)) { add('catalog.yaml', `process ${n}단계는 title·desc 항목이어야 합니다`); return; }
        if (!isStr(s.title)) add('catalog.yaml', `process ${n}단계의 title이 없거나 비어 있습니다`);
        else if ([...s.title].length > PROCESS_TITLE_MAX) add('catalog.yaml', `process ${n}단계의 title은 ${PROCESS_TITLE_MAX}자 이내여야 합니다`);
        if (s.desc !== undefined && !isStr(s.desc)) add('catalog.yaml', `process ${n}단계의 desc는 글이어야 합니다`);
        else if (s.desc !== undefined && [...s.desc].length > PROCESS_DESC_MAX) add('catalog.yaml', `process ${n}단계의 desc는 ${PROCESS_DESC_MAX}자 이내여야 합니다`);
        const extra = Object.keys(s).filter(k => k !== 'title' && k !== 'desc');
        if (extra.length) add('catalog.yaml', `process ${n}단계에 알 수 없는 항목(${extra.join(', ')})이 있습니다. desc에 쉼표가 있으면 따옴표로 감싸세요`);
      });
    }
  }
  if (!c.compat || typeof c.compat !== 'object') {
    add('catalog.yaml', '필수 항목 compat이(가) 없습니다');
  } else {
    const unknownTools = Object.keys(c.compat).filter(k => !TOOLS.includes(k));
    if (unknownTools.length) add('catalog.yaml', `compat에 알 수 없는 AI(${unknownTools.join(', ')})가 있습니다. ${TOOLS.join(', ')} 세 곳만 적습니다 (Codex는 chatgpt에 함께 적습니다)`);
    for (const t of TOOLS) {
      const e = c.compat[t];
      if (!e || typeof e !== 'object') { add('catalog.yaml', `compat.${t}이(가) 없습니다`); continue; }
      if (!LEVELS.includes(e.level)) {
        add('catalog.yaml', `compat.${t}.level은 ${LEVELS.join('|')} 중 하나여야 합니다 (현재: ${e.level})`);
      }
      if (!isStr(e.note)) add('catalog.yaml', `compat.${t}.note가 없거나 비어 있습니다`);
      const extra = Object.keys(e).filter(k => k !== 'level' && k !== 'note');
      if (extra.length) add('catalog.yaml', `compat.${t}에 알 수 없는 항목(${extra.join(', ')})이 있습니다. note에 쉼표가 있으면 note 전체를 따옴표로 감싸세요`);
    }
  }
  return errs;
}
