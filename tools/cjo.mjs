#!/usr/bin/env node
/* Command-line query tool for the Criminal Justice Operations framework.
   Usage: node tools/cjo.mjs <command> [args]   (see `help`) */
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const DATA = path.join(ROOT, 'dist/framework.json');
if (!fs.existsSync(DATA)) {
  console.error('dist/framework.json is missing - run `npm run build` first.');
  process.exit(1);
}
const F = JSON.parse(fs.readFileSync(DATA, 'utf8'));
const BENCH = F.courses.flatMap((c) => c.standards.flatMap((s) => s.benchmarks));
const STANDARDS = F.courses.flatMap((c) => c.standards);
const BY_UID = new Map(BENCH.map((b) => [b.uid, b]));
const TOPIC_LABEL = new Map(F.taxonomy.topics.map((t) => [t.id, t.label]));

const E = String.fromCharCode(27);
const paint = (code) => (s) => `${E}[${code}m${s}${E}[0m`;
const C = process.stdout.isTTY
  ? { dim: paint(2), b: paint(1), cy: paint(36), y: paint(33), g: paint(32) }
  : { dim: (s) => s, b: (s) => s, cy: (s) => s, y: (s) => s, g: (s) => s };

const wrap = (text, width = 92, indent = '      ') => {
  const words = String(text).split(/\s+/);
  const lines = [];
  let line = '';
  words.forEach((w) => {
    if ((line + w).length > width) { lines.push(line.trimEnd()); line = ''; }
    line += `${w} `;
  });
  if (line.trim()) lines.push(line.trimEnd());
  return lines.map((l, i) => (i ? indent + l : l)).join('\n');
};

const DOT = ' - ';
const meta = (b) => [
  b.cognitiveLabel,
  b.modality === 'performance' ? 'performance' : null,
  b.optional ? 'OPTIONAL' : null,
  b.mockActivity ? 'mock' : null,
  ...b.citations.statutes, ...b.citations.rules, ...b.citations.cases, ...b.citations.federal,
].filter(Boolean).join(' | ');

function printBenchmark(b, { context = true } = {}) {
  if (context) console.log(C.dim(`   ${b.courseTitle} / ${b.standardId}`));
  console.log(`   ${C.cy(b.id.padEnd(6))} ${wrap(b.text)}`);
  b.bullets.forEach((x) => console.log(C.dim(`      ${'  '.repeat(x.depth)}- ${wrap(x.text, 86, '        ')}`)));
  console.log(C.dim(`          ${meta(b)}`));
  if (b.repeatsIn.length) console.log(C.dim(`          repeats: ${b.repeatsIn.join(', ')}`));
  console.log();
}

const LIMIT = Number(process.env.CJO_LIMIT || 25);

const COMMANDS = {
  search(args) {
    const q = args.join(' ').toLowerCase();
    if (!q) { console.error('usage: search <words>'); return; }
    const tokens = q.split(/\s+/).filter((t) => t.length > 1);
    const hits = BENCH.map((b) => {
      const hay = [b.id, b.text, b.bullets.map((x) => x.text).join(' '), b.courseTitle,
        b.topics.map((t) => TOPIC_LABEL.get(t)).join(' '),
        [...b.citations.statutes, ...b.citations.cases, ...b.citations.named].join(' ')].join(' ').toLowerCase();
      let score = 0;
      tokens.forEach((t) => { if (hay.includes(t)) score += b.text.toLowerCase().includes(t) ? 3 : 1; });
      if (b.id === q) score += 100;
      return { b, score, all: tokens.every((t) => hay.includes(t)) };
    }).filter((r) => r.score > 0 && r.all).sort((a, b) => b.score - a.score);
    console.log(C.b(`\n${hits.length} benchmark(s) matching "${q}"\n`));
    hits.slice(0, LIMIT).forEach((r) => printBenchmark(r.b));
    if (hits.length > LIMIT) console.log(C.dim(`   ...${hits.length - LIMIT} more (set CJO_LIMIT to see more)\n`));
  },

  show(args) {
    const id = args[0];
    if (!id) { console.error('usage: show <benchmark-id|standard-id|uid>   e.g. show 15.04'); return; }
    const bs = BENCH.filter((b) => b.id === id || b.uid === id);
    const ss = STANDARDS.filter((s) => s.id === id || s.uid === id);
    if (!bs.length && !ss.length) { console.error(`No benchmark or standard "${id}".`); return; }
    ss.forEach((s) => {
      console.log(C.b(`\n${s.id} ${s.text}`));
      console.log(C.dim(`   ${s.courseTitle} (${s.courseNumber}) | ${s.benchmarkCount} benchmarks | ~${s.suggestedPeriods} periods\n`));
      s.benchmarks.forEach((b) => printBenchmark(b, { context: false }));
    });
    bs.forEach((b) => { console.log(); printBenchmark(b); });
  },

  course(args) {
    const key = (args[0] || '').toLowerCase();
    const c = F.courses.find((x) => x.courseNumber === key || (key && x.title.toLowerCase().includes(key)));
    if (!c) {
      console.log(C.b('\nCourses\n'));
      F.courses.forEach((x) => console.log(`   ${C.cy(x.courseNumber)}  ${x.title.padEnd(32)} ${C.dim(`${x.standardCount} std | ${x.benchmarkCount} bench | credit ${x.credit}`)}`));
      console.log();
      return;
    }
    console.log(C.b(`\n${c.title} (${c.courseNumber})`));
    console.log(C.dim(`   ${c.credit} credit | level ${c.level} | SOC ${c.soc} ${c.socTitle} | standards ${c.standardRange}`));
    if (c.altTitle) console.log(C.dim(`   also titled "${c.altTitle}" in the program-structure table`));
    console.log(`\n${wrap(c.description, 96, '   ')}\n`);
    c.standards.forEach((s) => {
      console.log(`   ${C.cy(s.id.padEnd(6))} ${wrap(s.text, 88, '          ')}`);
      console.log(C.dim(`          ${s.benchmarkCount} benchmarks | ${s.performanceCount} performance | ~${s.suggestedPeriods} periods`));
    });
    console.log();
  },

  topic(args) {
    const key = args.join(' ').toLowerCase();
    const topics = Object.values(F.indexes.topics);
    if (!key) {
      console.log(C.b('\nTopics\n'));
      topics.sort((a, b) => b.count - a.count).forEach((t) => console.log(`   ${String(t.count).padStart(4)}  ${t.label} ${C.dim(`(${t.id})`)}`));
      console.log();
      return;
    }
    const t = topics.find((x) => x.id === key || x.label.toLowerCase().includes(key));
    if (!t) { console.error(`No topic matching "${key}". Run \`topic\` to list them.`); return; }
    console.log(C.b(`\n${t.label} - ${t.count} benchmarks in ${t.courses.length} course(s)\n`));
    t.benchmarks.map((uid) => BY_UID.get(uid)).forEach((b) => printBenchmark(b));
  },

  law(args) {
    const key = args.join(' ').toLowerCase();
    const entries = Object.values(F.indexes.citations);
    const hits = key ? entries.filter((e) => e.value.toLowerCase().includes(key)) : entries;
    if (!hits.length) { console.error(`No legal reference matching "${key}".`); return; }
    console.log(C.b(`\n${hits.length} legal reference(s)${key ? ` matching "${key}"` : ''}\n`));
    hits.sort((a, b) => b.benchmarks.length - a.benchmarks.length).forEach((e) => {
      console.log(`   ${C.y(e.value)} ${C.dim(`(${e.kind}, ${e.benchmarks.length})`)}`);
      e.benchmarks.forEach((uid) => {
        const b = BY_UID.get(uid);
        console.log(C.dim(`      ${b.uid}  ${b.text.slice(0, 84)}${b.text.length > 84 ? '...' : ''}`));
      });
      console.log();
    });
  },

  crosswalk() {
    console.log(C.b(`\n${F.crosswalk.clusters.length} benchmark(s) required in more than one course\n`));
    F.crosswalk.clusters.forEach((cl) => {
      console.log(`   ${cl.exact ? C.g('verbatim') : C.y('near-match')}  ${cl.label}`);
      cl.members.forEach((uid) => console.log(C.dim(`      ${uid}  ${BY_UID.get(uid).courseTitle}`)));
      console.log();
    });
  },

  stats() {
    const s = F.stats;
    console.log(C.b(`\n${F.program.programTitle} - program ${F.program.programNumber} (CIP ${F.program.cipNumber})\n`));
    console.log(`   ${s.courses} courses | ${s.standards} standards | ${s.benchmarks} benchmarks | ${s.bullets} sub-points`);
    console.log(`   ${s.performanceBenchmarks} performance | ${s.knowledgeBenchmarks} knowledge | ${s.optionalBenchmarks} optional | ${s.mockActivities} mock activities`);
    console.log(`   ${s.distinctStatutes} statutes | ${s.distinctCases} cases | ${s.benchmarksWithCitations} benchmarks cite law`);
    console.log(`   ${s.repeatedBenchmarks} benchmarks repeat across courses (${s.repeatedClusters} clusters)\n`);
    console.log(C.b('   Cognitive spread (derived)'));
    Object.entries(s.byCognitiveLevel).forEach(([k, v]) => console.log(`      ${k.padEnd(12)} ${String(v).padStart(4)}  ${'#'.repeat(Math.round(v / 6))}`));
    console.log(`\n   ${C.b('By course')}`);
    F.courses.forEach((c) => {
      const m = s.byModalityPerCourse[c.courseNumber];
      console.log(`      ${c.courseNumber}  ${c.title.padEnd(30)} ${String(c.benchmarkCount).padStart(4)} bench  ${String(m.performance).padStart(3)} perf`);
    });
    console.log(`\n   ${C.b('Top topics')}`);
    s.topTopics.forEach((t) => console.log(`      ${String(t.count).padStart(4)}  ${t.label}`));
    console.log();
  },

  plan(args) {
    const c = F.courses.find((x) => x.courseNumber === args[0]);
    if (!c) {
      console.error(`usage: plan <course-number>   e.g. plan 8918020\n${F.courses.map((x) => `   ${x.courseNumber} ${x.title}`).join('\n')}`);
      return;
    }
    console.log(C.b(`\nPacing outline - ${c.title} (${c.courseNumber})`));
    console.log(C.dim(`   ${c.periodsPerCourse} instructional periods distributed by framework weight\n`));
    let day = 1;
    c.standards.forEach((s) => {
      const span = Math.max(1, Math.round(s.suggestedPeriods));
      console.log(`   ${C.cy(`days ${String(day).padStart(3)}-${String(day + span - 1).padStart(3)}`)}  ${s.id} ${s.text.slice(0, 74)}`);
      console.log(C.dim(`                  ${s.benchmarkCount} benchmarks | ${s.performanceCount} performance${s.optionalCount ? ` | ${s.optionalCount} optional` : ''}`));
      day += span;
    });
    console.log(C.dim(`\n   Total: ${day - 1} periods of ${c.periodsPerCourse} | remaining ${c.periodsPerCourse - (day - 1)} for review, assessment and CTSO activity\n`));
  },

  help() {
    console.log(`
${C.b('cjo')} - query the Criminal Justice Operations curriculum framework

   ${C.cy('search')} <words>        full-text search across every benchmark
   ${C.cy('show')} <id>            a benchmark or standard in full (e.g. 15.04, 22.0, 8918030:22.15)
   ${C.cy('course')} [id|name]     course outline, or list all courses
   ${C.cy('topic')} [name]         benchmarks by topic, or list all topics
   ${C.cy('law')} [citation]       benchmarks by statute, rule, case or named reference
   ${C.cy('crosswalk')}            content required in more than one course
   ${C.cy('plan')} <course>        pacing outline for a course
   ${C.cy('stats')}                program totals and distributions
   ${C.cy('help')}                 this message

   Examples:
      node tools/cjo.mjs search miranda
      node tools/cjo.mjs show 22.15
      node tools/cjo.mjs law 493
      node tools/cjo.mjs plan 8918020
`);
  },
};

const [cmd, ...args] = process.argv.slice(2);
(COMMANDS[cmd] || COMMANDS.help)(args);
