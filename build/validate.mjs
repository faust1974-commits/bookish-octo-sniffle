#!/usr/bin/env node
// Structural checks over the source files and the built dataset. Run: npm test
import fs from 'node:fs';
import path from 'node:path';
import { parseCourse } from './parse.mjs';

const ROOT = path.resolve(import.meta.dirname, '..');
const errors = [];
const warnings = [];
const fail = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

const EXPECTED = {
  '8918000': { sections: 6, standards: 80, benchmarks: 535 },
  '8607100': { sections: 5, standards: 71, benchmarks: 332 },
};

const programDirs = fs.readdirSync(path.join(ROOT, 'data/programs'))
  .filter((d) => fs.existsSync(path.join(ROOT, 'data/programs', d, 'program.json')))
  .sort();

programDirs.forEach(checkProgram);

function checkProgram(dir) {
const base = `data/programs/${dir}`;
const program = JSON.parse(fs.readFileSync(path.join(ROOT, base, 'program.json'), 'utf8'));
const files = fs.readdirSync(path.join(ROOT, base, 'courses')).filter((f) => f.endsWith('.cjo')).sort();
const where0 = `${program.programTitle} (${program.programNumber})`;

let totalStandards = 0;
let totalBenchmarks = 0;
const seenStandardNumbers = new Map();

files.forEach((file) => {
  const { meta, standards } = parseCourse(path.join(ROOT, base, 'courses', file));
  const where = `${dir}/${file}`;

  // @soc is only required where the framework assigns occupational codes.
  const required = ['course', 'title', 'credit', 'grad', 'description'];
  if (program.socCodes.length) required.push('soc');
  required.forEach((k) => {
    if (meta[k] === undefined || meta[k] === '') fail(`${where}: missing @${k}`);
  });
  if (meta.track !== 'program-wide' && !program.sequence.some((s) => s.courseNumber === meta.course)) {
    fail(`${where}: course ${meta.course} is not listed in the program sequence`);
  }
  const seq = program.sequence.find((s) => s.courseNumber === meta.course);
  if (seq && seq.title !== meta.title && seq.title !== meta.altTitle) {
    warn(`${where}: title "${meta.title}" differs from program.json "${seq.title}" (recorded as altTitle: ${meta.altTitle || 'none'})`);
  }
  if (seq && seq.soc && seq.soc !== meta.soc) fail(`${where}: SOC ${meta.soc} differs from program.json ${seq.soc}`);
  if (seq && seq.credit !== meta.credit) fail(`${where}: credit ${meta.credit} differs from program.json ${seq.credit}`);

  totalStandards += standards.length;
  const stdNumbers = standards.map((s) => Number(s.id.split('.')[0]));

  standards.forEach((std, i) => {
    if (!/^\d{2}\.0$/.test(std.id)) fail(`${where}:${std.line} standard id "${std.id}" is not NN.0`);
    if (i > 0 && stdNumbers[i] !== stdNumbers[i - 1] + 1) {
      fail(`${where}:${std.line} standard ${std.id} does not follow ${standards[i - 1].id}`);
    }
    if (!std.text.trim()) fail(`${where}:${std.line} standard ${std.id} has no text`);
    if (!std.benchmarks.length) fail(`${where}:${std.line} standard ${std.id} has no benchmarks`);

    const key = std.id;
    if (!seenStandardNumbers.has(key)) seenStandardNumbers.set(key, []);
    seenStandardNumbers.get(key).push(meta.course);

    totalBenchmarks += std.benchmarks.length;
    const ids = new Set();
    std.benchmarks.forEach((b, j) => {
      if (!/^\d{2}\.\d{2}$/.test(b.id)) fail(`${where}:${b.line} benchmark id "${b.id}" is not NN.NN`);
      if (b.id.split('.')[0] !== std.id.split('.')[0]) {
        fail(`${where}:${b.line} benchmark ${b.id} does not belong to standard ${std.id}`);
      }
      if (ids.has(b.id)) fail(`${where}:${b.line} duplicate benchmark id ${b.id}`);
      ids.add(b.id);
      if (Number(b.id.split('.')[1]) !== j + 1) {
        warn(`${where}:${b.line} benchmark ${b.id} is out of sequence (expected .${String(j + 1).padStart(2, '0')})`);
      }
      if (!b.text.trim()) fail(`${where}:${b.line} benchmark ${b.id} has no text`);
      b.bullets.forEach((x) => {
        if (x.depth > 2) warn(`${where}:${b.line} bullet nested ${x.depth} deep under ${b.id}`);
        if (!x.text.trim()) fail(`${where}:${b.line} empty bullet under ${b.id}`);
      });
    });
  });
});

// ------------------------------------------------------------- pathways
const pathways = JSON.parse(fs.readFileSync(path.join(ROOT, base, 'pathways.json'), 'utf8'));
const allStandardUids = new Set();
const sequencedUids = new Set();
files.forEach((file) => {
  const { meta, standards } = parseCourse(path.join(ROOT, base, 'courses', file));
  standards.forEach((s) => {
    allStandardUids.add(`${meta.course}:${s.id}`);
    if (meta.track !== 'program-wide') sequencedUids.add(`${meta.course}:${s.id}`);
  });
});
const onThread = new Set();
const threadIds = new Set();
pathways.threads.forEach((t) => {
  if (threadIds.has(t.id)) fail(`pathways.json: duplicate thread id "${t.id}"`);
  threadIds.add(t.id);
  if (!t.label || !t.rationale) fail(`pathways.json: thread "${t.id}" needs a label and a rationale`);
  if (t.standards.length < 2) fail(`pathways.json: thread "${t.id}" needs at least two standards`);
  const seenInThread = new Set();
  t.standards.forEach((uid) => {
    if (!allStandardUids.has(uid)) fail(`pathways.json: thread "${t.id}" references unknown standard ${uid}`);
    if (seenInThread.has(uid)) fail(`pathways.json: thread "${t.id}" lists ${uid} twice`);
    seenInThread.add(uid);
    onThread.add(uid);
  });
});
// Program-wide sections (career readiness) are not course-sequenced, so they are
// deliberately off the threads.
[...sequencedUids].filter((uid) => !onThread.has(uid)).forEach((uid) => {
  warn(`standard ${uid} is not on any instructional thread - sequences will place it by course order only`);
});

// Criminal Justice: the core sequence 01.0-27.0 must run once across the three core courses.
if (program.programNumber === '8918000') {
for (let n = 1; n <= 27; n += 1) {
  const id = `${String(n).padStart(2, '0')}.0`;
  const owners = seenStandardNumbers.get(id) || [];
  if (owners.length === 0) fail(`core standard ${id} is missing from every course`);
  if (owners.length > 1) fail(`core standard ${id} appears in more than one course: ${owners.join(', ')}`);
}
// 28.0+ are shared by the three fourth-credit options by design.
[...seenStandardNumbers.entries()].filter(([id]) => Number(id.split('.')[0]) >= 28).forEach(([id, owners]) => {
  const options = program.sequence.filter((s) => s.position === 4).map((s) => s.courseNumber);
  owners.forEach((o) => {
    if (!options.includes(o)) fail(`standard ${id} appears in ${o}, which is not a fourth-credit option`);
  });
});
} else {
  // Every other framework numbers its standards once, straight through.
  [...seenStandardNumbers.entries()].forEach(([id, owners]) => {
    if (owners.length > 1) fail(`standard ${id} appears in more than one course: ${owners.join(', ')}`);
  });
}

const expected = EXPECTED[program.programNumber];
if (expected) {
  if (totalStandards !== expected.standards) fail(`${where0}: expected ${expected.standards} standards, parsed ${totalStandards}`);
  if (totalBenchmarks !== expected.benchmarks) fail(`${where0}: expected ${expected.benchmarks} benchmarks, parsed ${totalBenchmarks}`);
  if (files.length !== expected.sections) fail(`${where0}: expected ${expected.sections} course files, found ${files.length}`);
}

// Built artifacts should be in step with the source.
const dist = path.join(ROOT, `dist/${program.slug}/framework.json`);
if (!fs.existsSync(dist)) {
  warn('dist/framework.json not built yet - run `npm run build`');
} else {
  const F = JSON.parse(fs.readFileSync(dist, 'utf8'));
  if (F.stats.benchmarks !== totalBenchmarks) fail(`dist/framework.json is stale (${F.stats.benchmarks} benchmarks vs ${totalBenchmarks} in source) - run \`npm run build\``);
  const webData = path.join(ROOT, program.webRoot, 'framework-data.js');
  if (!fs.existsSync(webData)) fail(`${program.webRoot}/framework-data.js is missing - run \`npm run build\``);
  F.courses.forEach((c) => {
    c.standards.forEach((s) => {
      if (s.benchmarks.some((b) => b.suggestedPeriods === undefined)) fail(`${c.courseNumber} ${s.id}: pacing not computed`);
    });
  });
  if (!F.graph) fail('dist/framework.json has no graph - run `npm run build`');
  else {
    if (F.graph.cycles.length) fail(`instructional graph has ${F.graph.cycles.length} standard(s) in a dependency cycle: ${F.graph.cycles.join(', ')}`);
    // Program-wide sections sit outside the course sequence by design.
    if (F.graph.programOrder.length !== sequencedUids.size) {
      fail(`${where0}: program order covers ${F.graph.programOrder.length} of ${sequencedUids.size} sequenced standards`);
    }
    F.graph.standardEdges.forEach((e) => {
      if (!allStandardUids.has(e.from) || !allStandardUids.has(e.to)) fail(`${where0}: graph edge references a standard that does not exist: ${e.from} -> ${e.to}`);
    });
  }
}

console.log(`${where0}: ${files.length} files, ${totalStandards} standards, ${totalBenchmarks} benchmarks`);
}
warnings.forEach((w) => console.log(`  warn  ${w}`));
errors.forEach((e) => console.log(`  ERROR ${e}`));
if (errors.length) { console.log(`\n${errors.length} error(s).`); process.exit(1); }
console.log(`\nOK${warnings.length ? ` (${warnings.length} warning(s))` : ''}`);
