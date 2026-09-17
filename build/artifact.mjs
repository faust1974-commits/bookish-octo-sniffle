#!/usr/bin/env node
// Emits dist/artifact*/ - each program packaged for publishing as an Artifact,
// where the host supplies the doctype/head/body skeleton.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

fs.readdirSync(path.join(ROOT, 'data/programs'))
  .filter((d) => fs.existsSync(path.join(ROOT, 'data/programs', d, 'program.json')))
  .forEach((dir) => {
    const program = JSON.parse(read(`data/programs/${dir}/program.json`));
    const web = program.webRoot;
    const src = read(`${web}/index.html`);

    const head = src.slice(src.indexOf('<title>'), src.indexOf('</head>'));
    const body = src.slice(src.indexOf('<body>') + 6, src.lastIndexOf('</body>'));
    const page = `${head
      .split('\n')
      .filter((l) => !/rel="icon"|rel="apple-touch-icon"|rel="manifest"|apple-mobile-web-app|mobile-web-app-capable|name="theme-color"/.test(l))
      .join('\n')
      .trim()}\n${body.trim()}\n`;

    // The Criminal Justice artifact is already published from dist/artifact.
    const outDir = path.join(ROOT, program.slug === 'criminal-justice' ? 'dist/artifact' : `dist/artifact-${program.slug}`);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'index.html'), page);
    ['app.js', 'styles.css', 'framework-data.js'].forEach((f) => {
      fs.copyFileSync(path.join(ROOT, web, f), path.join(outDir, f));
    });
    const rel = path.relative(ROOT, outDir);
    const kb = (f) => (fs.statSync(path.join(outDir, f)).size / 1024).toFixed(1);
    console.log(`  ${rel}/index.html (${kb('index.html')} KB) + app.js, styles.css, framework-data.js (${kb('framework-data.js')} KB)`);
  });
