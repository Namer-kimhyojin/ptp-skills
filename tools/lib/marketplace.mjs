export function buildMarketplace(bundles, skills) {
  const plugins = [];
  for (const b of bundles) {
    const picked = b.categories === 'all'
      ? skills
      : skills.filter(s => (b.categories ?? []).includes(s.catalog?.category));
    if (picked.length === 0) continue;
    plugins.push({
      name: b.id,
      description: b.description,
      source: './',
      strict: false,
      skills: picked.map(s => `./skills/${s.name}`).sort(),
    });
  }
  return {
    name: 'pohang-tp',
    description: '포항테크노파크 업무 스킬 모음',
    owner: { name: '포항테크노파크 업무 스킬 (Namer-kimhyojin)' },
    plugins,
  };
}

export function serializeMarketplace(obj) {
  return JSON.stringify(obj, null, 2) + '\n';
}

// marketplace.json이 최신이 아닐 때 오류로 셀지 경고로 셀지 정한다.
export function marketplaceStaleResult(stale, warnOnly) {
  if (!stale) return { error: null, warning: null };
  const msg = 'marketplace.json이 최신이 아닙니다. npm run build 후 커밋하세요';
  return warnOnly ? { error: null, warning: msg } : { error: msg, warning: null };
}
