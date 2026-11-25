import { execFileSync } from 'node:child_process';

export function skillHistory(rootDir, name) {
  let out;
  try {
    out = execFileSync('git', ['log', '--format=%cs%x09%s', '--', `skills/${name}`], {
      cwd: rootDir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
    });
  } catch {
    return [];
  }
  return out.split('\n').filter(Boolean).map(line => {
    const i = line.indexOf('\t');
    return { date: line.slice(0, i), subject: line.slice(i + 1) };
  });
}
