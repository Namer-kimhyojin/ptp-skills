import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'yaml';
import { parseSkillMd } from './frontmatter.mjs';

function walk(dir, base = '') {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules') continue;
    const rel = base ? `${base}/${e.name}` : e.name;
    if (e.isDirectory()) out.push(...walk(path.join(dir, e.name), rel));
    else out.push(rel);
  }
  return out;
}

export function loadSkills(rootDir) {
  const skillsDir = path.join(rootDir, 'skills');
  if (!fs.existsSync(skillsDir)) return [];
  const names = fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter(e => e.isDirectory()).map(e => e.name).sort();
  return names.map(name => {
    const dir = path.join(skillsDir, name);
    const files = walk(dir).sort();
    const skill = { name, dir, files, frontmatter: {}, body: '', catalog: null, catalogError: null };
    const mdPath = path.join(dir, 'SKILL.md');
    if (fs.existsSync(mdPath)) {
      try {
        const r = parseSkillMd(fs.readFileSync(mdPath, 'utf8'));
        skill.frontmatter = r.data;
        skill.body = r.body;
      } catch (e) {
        skill.skillMdError = e.message;
      }
    }
    const catPath = path.join(dir, 'catalog.yaml');
    if (fs.existsSync(catPath)) {
      try {
        const c = parse(fs.readFileSync(catPath, 'utf8'));
        if (c && typeof c === 'object' && !Array.isArray(c)) skill.catalog = c;
        else skill.catalogError = '최상위가 키-값 형태가 아닙니다';
      } catch (e) {
        skill.catalogError = e.message;
      }
    }
    return skill;
  });
}

function readYaml(rootDir, file) {
  return parse(fs.readFileSync(path.join(rootDir, file), 'utf8')) ?? {};
}

export function loadCategories(rootDir) {
  return readYaml(rootDir, 'categories.yaml').categories ?? [];
}

export function loadBundles(rootDir) {
  return (readYaml(rootDir, 'bundles.yaml').bundles ?? []).map(b => ({
    id: b.id, title: b.title, description: b.description, categories: b.categories,
  }));
}

export function findForbiddenFiles(files) {
  return files.filter(f => {
    const segs = f.split('/');
    const base = segs[segs.length - 1];
    if (base === '.env' || base === 'runtime-python.txt' || base.endsWith('.pyc')) return true;
    return segs.slice(0, -1).some(s => s === '__pycache__' || s === '.venv' || s === 'venv' || s.includes('.backup-'));
  });
}
