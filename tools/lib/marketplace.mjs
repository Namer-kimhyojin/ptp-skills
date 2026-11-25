import fs from 'node:fs';
import path from 'node:path';
import { distributable } from './packages.mjs';

// 묶음마다 plugins/<묶음 id>/ 폴더를 따로 둔다.
// 데스크톱 앱(Cowork·Code 탭)은 묶음 폴더가 따로 있는 형식만 확실히 읽는다.
export const PLUGINS_DIR = 'plugins';

export function bundlePlugins(bundles, skills) {
  const out = [];
  for (const b of bundles) {
    const picked = b.categories === 'all'
      ? skills
      : skills.filter(s => (b.categories ?? []).includes(s.catalog?.category));
    if (picked.length === 0) continue;
    out.push({ bundle: b, skills: [...picked].sort((x, y) => x.name.localeCompare(y.name)) });
  }
  return out;
}

export function buildMarketplace(bundles, skills) {
  return {
    name: 'pohang-tp',
    description: '포항테크노파크 업무 스킬 모음',
    owner: { name: '포항테크노파크 업무 스킬 (Namer-kimhyojin)' },
    plugins: bundlePlugins(bundles, skills).map(({ bundle: b }) => ({
      name: b.id,
      description: b.description,
      source: `./${PLUGINS_DIR}/${b.id}`,
    })),
  };
}

export function serializeMarketplace(obj) {
  return JSON.stringify(obj, null, 2) + '\n';
}

// 묶음 폴더에 들어갈 파일: 저장소 기준 경로 → 내용(Buffer)
export function buildPluginFiles(bundles, skills) {
  const files = new Map();
  for (const { bundle: b, skills: picked } of bundlePlugins(bundles, skills)) {
    const base = `${PLUGINS_DIR}/${b.id}`;
    const manifest = { name: b.id, description: b.description, author: { name: '포항테크노파크' } };
    files.set(`${base}/.claude-plugin/plugin.json`, Buffer.from(serializeMarketplace(manifest)));
    for (const s of picked) {
      for (const f of distributable(s)) {
        files.set(`${base}/skills/${s.name}/${f}`, fs.readFileSync(path.join(s.dir, f)));
      }
    }
  }
  return files;
}

function listFiles(dir, base) {
  if (!fs.existsSync(dir)) return [];
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = `${base}/${e.name}`;
    if (e.isDirectory()) out.push(...listFiles(path.join(dir, e.name), rel));
    else out.push(rel);
  }
  return out;
}

export function writePluginFiles(root, files) {
  fs.rmSync(path.join(root, PLUGINS_DIR), { recursive: true, force: true });
  for (const [rel, data] of files) {
    const abs = path.join(root, rel);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, data);
  }
}

// plugins/ 폴더가 만들어야 할 내용과 다르면 true
export function pluginFilesStale(root, files) {
  const actual = listFiles(path.join(root, PLUGINS_DIR), PLUGINS_DIR);
  if (actual.length !== files.size) return true;
  for (const rel of actual) {
    const want = files.get(rel);
    if (!want || !want.equals(fs.readFileSync(path.join(root, rel)))) return true;
  }
  return false;
}

// 묶음 정보(marketplace.json·plugins 폴더)가 최신이 아닐 때 오류로 셀지 경고로 셀지 정한다.
export function marketplaceStaleResult(stale, warnOnly) {
  if (!stale) return { error: null, warning: null };
  const msg = '묶음 정보(marketplace.json·plugins 폴더)가 최신이 아닙니다. npm run build 후 커밋하세요';
  return warnOnly ? { error: null, warning: msg } : { error: msg, warning: null };
}
