import { execFileSync } from 'node:child_process';

// formerNames: 이름을 바꾼 스킬의 예전 폴더 이름. 예전 이력도 함께 보여 준다.
export function skillHistory(rootDir, name, formerNames = []) {
  let out;
  const paths = [name, ...formerNames].map(n => `skills/${n}`);
  try {
    out = execFileSync('git', ['log', '--format=%cs%x09%s', '--', ...paths], {
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
