#!/usr/bin/env node
// Packages each program into one self-contained .html file: no server, no
// network, no account. Double-click it and it works, forever, offline.
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const safe = (js) => js.replace(/<\/script>/gi, '<\\/script>');

const icon = fs.readFileSync(path.join(ROOT, 'docs/icons/icon-192.png')).toString('base64');

fs.readdirSync(path.join(ROOT, 'data/programs'))
  .filter((d) => fs.existsSync(path.join(ROOT, 'data/programs', d, 'program.json')))
  .forEach((dir) => {
    const program = JSON.parse(read(`data/programs/${dir}/program.json`));
    const web = program.webRoot;
    let html = read(`${web}/index.html`);

    // Drop everything that would reach out to the network or expect a server.
    html = html
      .replace(/<link rel="preconnect"[^>]*>\s*/g, '')
      .replace(/<link rel="stylesheet" href="https:\/\/fonts[^>]*>\s*/g, '')
      .replace(/<link rel="manifest"[^>]*>\s*/g, '')
      .replace(/<link rel="apple-touch-icon"[^>]*>\s*/g, '')
      .replace(/<link rel="icon"[^>]*>/, () => `<link rel="icon" href="data:image/png;base64,${icon}">`)
      // Replacer FUNCTIONS, not strings: the inlined sources contain $& and $1
      // (the app's own regex code), which a string replacement would expand.
      .replace(/<link rel="stylesheet" href="styles\.css">/, () => `<style>\n${read(`${web}/styles.css`)}\n</style>`)
      .replace(/<script src="framework-data\.js"><\/script>/, () => `<script>\n${safe(read(`${web}/framework-data.js`))}\n</script>`)
      .replace(/<script src="app\.js"><\/script>/, () => `<script>\n${safe(read(`${web}/app.js`))}\n</script>`);

    // The inlined app must match its source byte for byte.
    ['styles.css', 'app.js', 'framework-data.js'].forEach((f) => {
      const body = safe(read(`${web}/${f}`)).trim();
      if (!html.includes(body)) throw new Error(`${web}/${f} was altered while inlining - refusing to ship a corrupted file`);
    });

    const outPath = path.join(ROOT, 'dist', `${program.programTitle}.html`);
    fs.writeFileSync(outPath, html);
    const mb = (fs.statSync(outPath).size / 1024 / 1024).toFixed(2);
    const external = [...html.matchAll(/(?:src|href)="(https?:)?\/\/[^"]+"/g)].map((m) => m[0]);
    console.log(`  wrote dist/${program.programTitle}.html (${mb} MB) - external references: ${external.length ? external.join(', ') : 'none'}`);
  });
