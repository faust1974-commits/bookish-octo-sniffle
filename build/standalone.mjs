#!/usr/bin/env node
// Packages the whole app into one self-contained .html file: no server, no
// network, no account. Double-click it and it works, forever, offline.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const safe = (js) => js.replace(/<\/script>/gi, '<\\/script>');

const icon = fs.readFileSync(path.join(ROOT, 'docs/icons/icon-192.png')).toString('base64');
let html = read('docs/index.html');

// Drop everything that would reach out to the network or expect a server.
html = html
  .replace(/<link rel="preconnect"[^>]*>\s*/g, '')
  .replace(/<link rel="stylesheet" href="https:\/\/fonts[^>]*>\s*/g, '')
  .replace(/<link rel="manifest"[^>]*>\s*/g, '')
  .replace(/<link rel="apple-touch-icon"[^>]*>\s*/g, '')
  // Replacer FUNCTIONS, not strings: the inlined sources contain $& and $1
  // (the app's own regex code), which a string replacement would expand.
  .replace(/<link rel="icon"[^>]*>/, () => `<link rel="icon" href="data:image/png;base64,${icon}">`)
  .replace(/<link rel="stylesheet" href="styles\.css">/, () => `<style>\n${read('docs/styles.css')}\n</style>`)
  .replace(/<script src="framework-data\.js"><\/script>/, () => `<script>\n${safe(read('docs/framework-data.js'))}\n</script>`)
  .replace(/<script src="app\.js"><\/script>/, () => `<script>\n${safe(read('docs/app.js'))}\n</script>`);

// The inlined app must match its source byte for byte.
['docs/styles.css', 'docs/app.js', 'docs/framework-data.js'].forEach((f) => {
  const body = safe(read(f)).trim();
  if (!html.includes(body)) throw new Error(`${f} was altered while inlining - refusing to ship a corrupted file`);
});

const outPath = path.join(ROOT, 'dist/Criminal Justice Operations.html');
fs.writeFileSync(outPath, html);
const mb = (fs.statSync(outPath).size / 1024 / 1024).toFixed(2);
const external = [...html.matchAll(/(?:src|href)="(https?:)?\/\/[^"]+"/g)].map((m) => m[0]);
console.log(`  wrote dist/Criminal Justice Operations.html (${mb} MB)`);
console.log(`  external references: ${external.length ? external.join(', ') : 'none'}`);
