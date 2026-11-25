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
