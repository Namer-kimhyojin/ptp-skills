import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { skillHistory } from '../tools/lib/history.mjs';

test('history: 임시 git 저장소에서 커밋 2개 → 최신순 2개, 이력 없으면 []', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ptp-hist-'));
  try {
    const git = (...a) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@example.com', ...a], { cwd: dir, stdio: 'ignore' });
    git('init', '-q');
    fs.mkdirSync(path.join(dir, 'skills', 'foo'), { recursive: true });
    const f = path.join(dir, 'skills', 'foo', 'SKILL.md');
    fs.writeFileSync(f, 'a');
    git('add', '.'); git('commit', '-q', '-m', '첫 커밋');
    fs.writeFileSync(f, 'b');
    git('add', '.'); git('commit', '-q', '-m', '둘째 커밋');
    const h = skillHistory(dir, 'foo');
    assert.equal(h.length, 2);
    assert.deepEqual(h.map(x => x.subject), ['둘째 커밋', '첫 커밋']);
    assert.match(h[0].date, /^\d{4}-\d{2}-\d{2}$/);
    assert.deepEqual(skillHistory(dir, 'none'), []);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
