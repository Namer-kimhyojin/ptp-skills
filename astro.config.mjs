// @ts-check
import { defineConfig } from 'astro/config';

// GitHub Pages: https://namer-kimhyojin.github.io/ptp-skills/
export default defineConfig({
  site: 'https://namer-kimhyojin.github.io',
  base: '/ptp-skills',
  trailingSlash: 'always',
  srcDir: './site/src',
  publicDir: './site/public',
  outDir: './dist',
  build: { format: 'directory' },
  // 스킬 이름을 ptp-짧은이름으로 바꾸기 전 주소(2026-11-26)로 들어와도 새 주소로 보낸다.
  redirects: {
    '/skills/write-pohang-tp-press-release/': '/ptp-skills/skills/ptp-press/',
    '/skills/ptp-sns-tool/': '/ptp-skills/skills/ptp-sns/',
    '/skills/meeting-docs/': '/ptp-skills/skills/ptp-meeting/',
    '/skills/tp-presentation-deck/': '/ptp-skills/skills/ptp-deck/',
    '/skills/announcement-radar/': '/ptp-skills/skills/ptp-radar/',
  },
});
