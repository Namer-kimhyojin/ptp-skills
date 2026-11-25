export const okCatalog = {
  title: '보도자료 작성',
  summary: '계획안을 주면 보도자료로 작성',
  category: '보도·홍보',
  version: '1.0.0',
  owner: '포항테크노파크',
  examples: ['보도자료 써줘'],
  outputs: ['hwpx'],
  compat: {
    claude: { level: 'full', note: '전체 지원' },
    codex: { level: 'full', note: '전체 지원' },
    chatgpt: { level: 'partial', note: '초안까지' },
    gemini: { level: 'none', note: '미지원' },
  },
};

export function makeSkill(overrides = {}) {
  const name = overrides.name ?? 'sample-skill';
  return {
    name,
    dir: `skills/${name}`,
    files: ['SKILL.md', 'catalog.yaml'],
    frontmatter: { name, description: '설명입니다' },
    body: '본문',
    catalog: structuredClone(okCatalog),
    catalogError: null,
    ...overrides,
  };
}
