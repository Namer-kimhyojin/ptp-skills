import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadSkills, loadCategories, loadBundles } from './lib/skills.mjs';
import { buildMarketplace, serializeMarketplace, buildPluginFiles, writePluginFiles } from './lib/marketplace.mjs';
import { buildSkillZip, buildGptGeminiZip, buildInstructions, buildStarterPrompt } from './lib/packages.mjs';
import { skillHistory } from './lib/history.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const skills = loadSkills(root);
const categories = loadCategories(root);
const bundles = loadBundles(root);

const dlDir = path.join(root, 'site', 'public', 'downloads');
fs.rmSync(dlDir, { recursive: true, force: true });
fs.mkdirSync(dlDir, { recursive: true });

const data = skills.map(s => {
  const { text, overLimit } = buildInstructions(s);
  fs.writeFileSync(path.join(dlDir, `${s.name}.zip`), buildSkillZip(s));
  fs.writeFileSync(path.join(dlDir, `${s.name}-gpt-gemini.zip`), buildGptGeminiZip(s));
  return {
    name: s.name,
    catalog: s.catalog,
    description: s.frontmatter.description,
    instructions: text,
    overLimit,
    starterPrompt: buildStarterPrompt(s),
    history: skillHistory(root, s.name),
    files: s.files,
    downloads: {
      claude: `downloads/${s.name}.zip`,
      gptGemini: `downloads/${s.name}-gpt-gemini.zip`,
    },
  };
});

const dataPath = path.join(root, 'site', 'src', 'data', 'skills.json');
fs.mkdirSync(path.dirname(dataPath), { recursive: true });
fs.writeFileSync(dataPath, JSON.stringify({ skills: data, categories, bundles }, null, 2) + '\n');

const mpPath = path.join(root, '.claude-plugin', 'marketplace.json');
fs.mkdirSync(path.dirname(mpPath), { recursive: true });
fs.writeFileSync(mpPath, serializeMarketplace(buildMarketplace(bundles, skills)));
writePluginFiles(root, buildPluginFiles(bundles, skills));

console.log(`빌드 완료: 스킬 ${skills.length}개`);
