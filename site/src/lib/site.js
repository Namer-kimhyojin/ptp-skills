// 사이트 공통 도우미. 모든 내부 주소는 url()로 만든다 (BASE_URL 기준).
import data from '../data/skills.json';

export const REPO = 'Namer-kimhyojin/ptp-skills';
export const REPO_URL = `https://github.com/${REPO}`;
export const MARKETPLACE = 'pohang-tp';
export const SITE_NAME = '포항TP 업무 스킬';

const BASE = import.meta.env.BASE_URL.replace(/\/?$/, '/');

/** 사이트 안 주소. url('skills/x/') → '/ptp-skills/skills/x/' */
export function url(path = '') {
  return BASE + String(path).replace(/^\/+/, '');
}

export const skills = data.skills;
export const categories = data.categories;
export const bundles = data.bundles;

export function skillUrl(skill) {
  return url(`skills/${skill.name}/`);
}

/** '2026-11-25' → '2026. 11. 25.' */
export function formatDate(iso) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return `${y}. ${Number(m)}. ${Number(d)}.`;
}

/** 'feat: 설치 파일 추가' → '설치 파일 추가' */
export function plainSubject(subject) {
  return String(subject).replace(/^[a-z]+(\([^)]*\))?!?:\s*/i, '');
}

export function lastUpdated(skill) {
  return skill.catalog.updated || skill.history[0]?.date || '';
}

export const AIS = [
  { key: 'claude', label: 'Claude' },
  { key: 'codex', label: 'Codex' },
  { key: 'chatgpt', label: 'ChatGPT' },
  { key: 'gemini', label: 'Gemini' },
];

export const LEVELS = {
  full: { text: '지원' },
  partial: { text: '일부' },
  none: { text: '안 됨' },
};

export function bundleSkills(bundle) {
  if (bundle.categories === 'all') return skills;
  const cats = [].concat(bundle.categories);
  return skills.filter(s => cats.includes(s.catalog.category));
}

/** 이 스킬이 들어 있는 묶음. 업무별 묶음이 먼저, 전체 묶음이 뒤. */
export function bundlesFor(skill) {
  const has = bundles.filter(b => bundleSkills(b).some(s => s.name === skill.name));
  return [...has.filter(b => b.categories !== 'all'), ...has.filter(b => b.categories === 'all')];
}

export function installCommand(bundle) {
  return `/plugin install ${bundle.id}@${MARKETPLACE}`;
}

export const MARKETPLACE_ADD = `/plugin marketplace add ${REPO}`;

export function categoryId(category) {
  return `cat-${categories.indexOf(category) + 1}`;
}

export function categoryUrl(category) {
  return url(`categories/${categoryId(category)}/`);
}

/** 홈에서 분류마다 보여 주는 카드 수. 넘으면 분류 페이지로 안내한다. */
export const HOME_LIMIT = 6;

/** 결과물 형식 표시 이름. 허용 값은 tools/lib/validate.mjs의 OUTPUTS와 같다. */
export const OUTPUTS = {
  hwpx: '한글 파일',
  docx: '워드 파일',
  xlsx: '엑셀 파일',
  pptx: 'PPT 파일',
  pdf: 'PDF 파일',
  html: 'HTML 파일',
  text: '글(채팅 답변)',
};

export function outputLabels(skill) {
  return (skill.catalog.outputs ?? []).map(o => OUTPUTS[o] ?? o);
}

/** 분류 안의 스킬: 최근 업데이트 순, 같으면 이름 순. */
export function skillsIn(category) {
  return skills
    .filter(s => s.catalog.category === category)
    .sort((a, b) => lastUpdated(b).localeCompare(lastUpdated(a)) || a.catalog.title.localeCompare(b.catalog.title, 'ko'));
}

/** 이 분류만 담은 묶음(전체 묶음 제외). 없으면 undefined. */
export function categoryBundle(category) {
  return bundles.find(b => b.categories !== 'all' && [].concat(b.categories).includes(category));
}
