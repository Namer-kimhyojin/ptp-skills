import { parse } from 'yaml';

export function parseSkillMd(text) {
  const src = text.replace(/^﻿/, '').replace(/\r\n/g, '\n');
  const m = src.match(/^---\n([\s\S]*?)\n---[ \t]*(?:\n|$)/);
  if (!m) throw new Error('SKILL.md 맨 위에 --- 로 시작하는 프런트매터가 없습니다');
  const data = parse(m[1]) ?? {};
  return { data, body: src.slice(m[0].length) };
}
