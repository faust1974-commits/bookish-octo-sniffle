#!/usr/bin/env node
// Emits dist/artifact/ - the same app packaged for publishing as an Artifact,
// where the host supplies the doctype/head/body skeleton.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const src = fs.readFileSync(path.join(ROOT, 'docs/index.html'), 'utf8');

const head = src.slice(src.indexOf('<title>'), src.indexOf('</head>'));
const body = src.slice(src.indexOf('<body>') + 6, src.lastIndexOf('</body>'));

const page = `${head
  .split('\n')
  .filter((l) => !/rel="icon"|rel="apple-touch-icon"|rel="manifest"|apple-mobile-web-app|mobile-web-app-capable|name="theme-color"/.test(l))
  .join('\n')
  .trim()}\n${body.trim()}\n`;

const outDir = path.join(ROOT, 'dist/artifact');
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, 'index.html'), page);
['app.js', 'styles.css', 'framework-data.js'].forEach((f) => {
  fs.copyFileSync(path.join(ROOT, 'docs', f), path.join(outDir, f));
});

const kb = (f) => (fs.statSync(path.join(outDir, f)).size / 1024).toFixed(1);
console.log(`  dist/artifact/index.html (${kb('index.html')} KB) + app.js (${kb('app.js')} KB), styles.css (${kb('styles.css')} KB), framework-data.js (${kb('framework-data.js')} KB)`);
