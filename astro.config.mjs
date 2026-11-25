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
});
