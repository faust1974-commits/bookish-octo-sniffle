#!/usr/bin/env node
// Builds every generated artifact from data/*.  Run: npm run build
import fs from 'node:fs';
import path from 'node:path';
import { parseCourse } from './parse.mjs';
import {
  BLOOM, TOPICS, classify, citations, topics as topicsOf, keywords,
  weight, fullText, normalizeForMatch, jaccard,
} from './enrich.mjs';
import { buildGraph } from './graph.mjs';

const ROOT = path.resolve(import.meta.dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const out = (p, body) => {
  fs.mkdirSync(path.dirname(path.join(ROOT, p)), { recursive: true });
  fs.writeFileSync(path.join(ROOT, p), body);
  const kb = (Buffer.byteLength(body) / 1024).toFixed(1);
  console.log(`  wrote ${p} (${kb} KB)`);
};

const program = JSON.parse(read('data/program.json'));
const pathways = JSON.parse(read('data/pathways.json'));
const courseFiles = fs.readdirSync(path.join(ROOT, 'data/courses')).filter((f) => f.endsWith('.cjo')).sort();

const PERIODS_PER_COURSE = 170; // 180-day year less assessment/review days

const courses = courseFiles.map((file) => {
  const { meta, standards } = parseCourse(path.join(ROOT, 'data/courses', file));
  const seq = program.sequence.find((s) => s.courseNumber === meta.course) || {};

  const builtStandards = standards.map((std) => {
    const benchmarks = std.benchmarks.map((b) => {
      const text = fullText(b);
      const cls = classify(b.text, b.bullets.map((x) => x.text));
      const cite = citations(text);
      const w = weight(b, cls);
      return {
        id: b.id,
        uid: `${meta.course}:${b.id}`,
        standardId: std.id,
        courseNumber: meta.course,
        courseTitle: meta.title,
        text: b.text,
        bullets: b.bullets,
        bulletCount: b.bullets.length,
        ...cls,
        optional: /\(optional\)/i.test(b.text),
        mockActivity: /\bmock\b/i.test(text),
        citations: cite,
        citationCount: cite.statutes.length + cite.rules.length + cite.federal.length + cite.cases.length,
        topics: topicsOf(text),
        keywords: keywords(text),
        weight: w,
        sourceLine: b.line,
      };
    });

    const stdCls = classify(std.text, std.benchmarks.map((b) => b.text));
    return {
      id: std.id,
      uid: `${meta.course}:${std.id}`,
      number: Number(std.id.split('.')[0]),
      courseNumber: meta.course,
      courseTitle: meta.title,
      text: std.text,
      cognitiveLevel: Math.max(stdCls.cognitiveLevel, ...benchmarks.map((b) => b.cognitiveLevel)),
      modality: benchmarks.some((b) => b.modality === 'performance') ? 'performance' : 'knowledge',
      topics: [...new Set(benchmarks.flatMap((b) => b.topics))],
      benchmarkCount: benchmarks.length,
      performanceCount: benchmarks.filter((b) => b.modality === 'performance').length,
      optionalCount: benchmarks.filter((b) => b.optional).length,
      weight: Math.round(benchmarks.reduce((a, b) => a + b.weight, 0) * 10) / 10,
      benchmarks,
      sourceLine: std.line,
    };
  });

  const totalWeight = builtStandards.reduce((a, s) => a + s.weight, 0);
  builtStandards.forEach((s) => {
    s.suggestedPeriods = Math.round((s.weight / totalWeight) * PERIODS_PER_COURSE * 2) / 2;
    s.benchmarks.forEach((b) => {
      b.suggestedPeriods = Math.round((b.weight / totalWeight) * PERIODS_PER_COURSE * 4) / 4;
    });
  });

  return {
    courseNumber: meta.course,
    title: meta.title,
    altTitle: meta.altTitle || null,
    credit: meta.credit,
    level: meta.level,
    soc: meta.soc,
    socTitle: meta.socTitle,
    graduationRequirement: meta.grad,
    position: meta.position,
    track: meta.track,
    optionGroup: meta.optionGroup || null,
    certifications: meta.certifications || program.teacherCertifications,
    description: meta.description,
    standardRange: `${builtStandards[0].id} - ${builtStandards[builtStandards.length - 1].id}`,
    standardCount: builtStandards.length,
    benchmarkCount: builtStandards.reduce((a, s) => a + s.benchmarkCount, 0),
    totalWeight: Math.round(totalWeight * 10) / 10,
    periodsPerCourse: PERIODS_PER_COURSE,
    standards: builtStandards,
    ...seq.track ? {} : {},
  };
});

const allBenchmarks = courses.flatMap((c) => c.standards.flatMap((s) => s.benchmarks));
const allStandards = courses.flatMap((c) => c.standards);

// ---------------------------------------------------------------- crosswalk
// Benchmarks that repeat (verbatim or near-verbatim) in more than one course.
const norm = allBenchmarks.map((b) => ({ b, n: normalizeForMatch(b.text), t: normalizeForMatch(b.text).split(' ') }));
const parent = new Map(allBenchmarks.map((b) => [b.uid, b.uid]));
const find = (x) => (parent.get(x) === x ? x : (parent.set(x, find(parent.get(x))), parent.get(x)));
const union = (a, b) => { const ra = find(a), rb = find(b); if (ra !== rb) parent.set(ra, rb); };
const pairs = [];
for (let i = 0; i < norm.length; i += 1) {
  for (let j = i + 1; j < norm.length; j += 1) {
    if (norm[i].b.courseNumber === norm[j].b.courseNumber) continue;
    if (norm[i].t.length < 4 || norm[j].t.length < 4) continue;
    const exact = norm[i].n === norm[j].n;
    const sim = exact ? 1 : jaccard(norm[i].t, norm[j].t);
    if (sim >= 0.7) {
      pairs.push({ a: norm[i].b.uid, b: norm[j].b.uid, similarity: Math.round(sim * 100) / 100, exact });
      union(norm[i].b.uid, norm[j].b.uid);
    }
  }
}
const clusterMap = new Map();
allBenchmarks.forEach((b) => {
  const root = find(b.uid);
  if (!clusterMap.has(root)) clusterMap.set(root, []);
  clusterMap.get(root).push(b.uid);
});
const repeatedClusters = [...clusterMap.values()]
  .filter((members) => members.length > 1)
  .map((members, i) => {
    const bs = members.map((uid) => allBenchmarks.find((b) => b.uid === uid));
    return {
      id: `cluster-${i + 1}`,
      label: bs[0].text.length > 90 ? `${bs[0].text.slice(0, 87)}...` : bs[0].text,
      courses: [...new Set(bs.map((b) => b.courseNumber))],
      members,
      exact: bs.every((b) => normalizeForMatch(b.text) === normalizeForMatch(bs[0].text)),
    };
  })
  .sort((a, b) => b.members.length - a.members.length);

allBenchmarks.forEach((b) => {
  const cluster = repeatedClusters.find((c) => c.members.includes(b.uid));
  b.repeatsIn = cluster ? cluster.members.filter((m) => m !== b.uid) : [];
  b.clusterId = cluster ? cluster.id : null;
});

// ---------------------------------------------------------------- graph
const graph = buildGraph({ courses, threads: pathways.threads, clusters: repeatedClusters });
if (graph.cycles.length) console.log(`  note: ${graph.cycles.length} standard(s) placed by framework order after a dependency cycle`);

// Surface each standard's graph position on the standard itself.
courses.forEach((c) => c.standards.forEach((s) => {
  const m = graph.standardMeta[s.uid];
  s.threads = m.threads;
  s.programOrder = m.order;
  s.teachingDepth = m.depth;
  s.prereqCount = m.prereqs.length;
}));

// ---------------------------------------------------------------- indexes
const byTopic = {};
TOPICS.forEach((t) => {
  const members = allBenchmarks.filter((b) => b.topics.includes(t.id));
  if (members.length) {
    byTopic[t.id] = {
      id: t.id,
      label: t.label,
      count: members.length,
      courses: [...new Set(members.map((b) => b.courseNumber))],
      benchmarks: members.map((b) => b.uid),
    };
  }
});

const citationIndex = {};
const addCite = (kind, value, uid) => {
  const key = `${kind}::${value}`;
  citationIndex[key] = citationIndex[key] || { kind, value, benchmarks: [] };
  citationIndex[key].benchmarks.push(uid);
};
allBenchmarks.forEach((b) => {
  b.citations.statutes.forEach((v) => addCite('statute', v, b.uid));
  b.citations.rules.forEach((v) => addCite('rule', v, b.uid));
  b.citations.federal.forEach((v) => addCite('federal', v, b.uid));
  b.citations.cases.forEach((v) => addCite('case', v, b.uid));
  b.citations.named.forEach((v) => addCite('named', v, b.uid));
});

const keywordIndex = {};
allBenchmarks.forEach((b) => {
  new Set([...b.keywords, ...b.id.split('.'), b.id]).forEach((k) => {
    keywordIndex[k] = keywordIndex[k] || [];
    keywordIndex[k].push(b.uid);
  });
});

// ---------------------------------------------------------------- stats
const countBy = (items, key) => items.reduce((acc, it) => {
  const k = typeof key === 'function' ? key(it) : it[key];
  acc[k] = (acc[k] || 0) + 1;
  return acc;
}, {});

const stats = {
  courses: courses.length,
  standards: allStandards.length,
  uniqueStandardNumbers: new Set(allStandards.map((s) => s.id)).size,
  benchmarks: allBenchmarks.length,
  bullets: allBenchmarks.reduce((a, b) => a + b.bulletCount, 0),
  performanceBenchmarks: allBenchmarks.filter((b) => b.modality === 'performance').length,
  knowledgeBenchmarks: allBenchmarks.filter((b) => b.modality === 'knowledge').length,
  optionalBenchmarks: allBenchmarks.filter((b) => b.optional).length,
  mockActivities: allBenchmarks.filter((b) => b.mockActivity).length,
  benchmarksWithCitations: allBenchmarks.filter((b) => b.citationCount > 0).length,
  repeatedBenchmarks: allBenchmarks.filter((b) => b.repeatsIn.length).length,
  repeatedClusters: repeatedClusters.length,
  byCognitiveLevel: countBy(allBenchmarks, 'cognitiveLabel'),
  byCourse: Object.fromEntries(courses.map((c) => [c.courseNumber, c.benchmarkCount])),
  byModalityPerCourse: Object.fromEntries(courses.map((c) => [c.courseNumber, {
    performance: c.standards.flatMap((s) => s.benchmarks).filter((b) => b.modality === 'performance').length,
    knowledge: c.standards.flatMap((s) => s.benchmarks).filter((b) => b.modality === 'knowledge').length,
  }])),
  topTopics: Object.values(byTopic).sort((a, b) => b.count - a.count).slice(0, 12)
    .map((t) => ({ id: t.id, label: t.label, count: t.count })),
  distinctStatutes: new Set(allBenchmarks.flatMap((b) => b.citations.statutes)).size,
  distinctCases: new Set(allBenchmarks.flatMap((b) => b.citations.cases)).size,
};

// Data-integrity notes a curriculum office would want flagged rather than silently fixed.
const notes = [
  {
    kind: 'title-variance',
    detail: 'The program-structure table names course 8918050 "Public Service Officer"; the Student Performance Standards page for the same course number names it "Police Service Officer". Both titles are retained (title / altTitle).',
  },
  {
    kind: 'numbering',
    detail: 'Standards 28.0+ are re-used by all three fourth-credit options (8918050, 8918060, 8918070). A benchmark number such as 28.01 is only unique when paired with its course number.',
  },
  {
    kind: 'verbatim-source',
    detail: 'Benchmark text is transcribed verbatim, including source typos (e.g. 33.11 "Determining how the crash occurred.", 36.01 stray list marker "q) restitution", 42.05 "the circumstances and officer must consider").',
  },
  {
    kind: 'pathways',
    detail: 'Instructional threads, prerequisites and the canonical program order come from data/pathways.json (curated) plus the framework\'s own numbering. They are a teaching judgement, not an FLDOE mandate - edit the file and rebuild to change how sequences are generated.',
  },
  {
    kind: 'derived-fields',
    detail: 'cognitiveLevel, modality, topics, weight and suggestedPeriods are derived heuristics for planning support - they are not part of the FLDOE framework.',
  },
];

const framework = {
  meta: {
    generated: new Date().toISOString(),
    generator: 'build/build.mjs',
    sourceOfTruth: 'data/program.json + data/courses/*.cjo',
    schemaVersion: 1,
  },
  program,
  courses,
  crosswalk: { clusters: repeatedClusters, pairs },
  graph,
  indexes: { topics: byTopic, citations: citationIndex, keywords: keywordIndex },
  taxonomy: { bloom: BLOOM.map(({ level, name }) => ({ level, name })), topics: TOPICS.map(({ id, label }) => ({ id, label })) },
  stats: { ...stats, threads: pathways.threads.length, standardEdges: graph.standardEdges.length },
  notes,
};

out('dist/framework.json', `${JSON.stringify(framework, null, 2)}\n`);
out('docs/framework-data.js', `window.CJO_FRAMEWORK = ${JSON.stringify(framework)};\n`);

// ---------------------------------------------------------------- flat CSV
const csvCell = (v) => {
  const s = Array.isArray(v) ? v.join('; ') : String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
const csvRows = [[
  'course_number', 'course_title', 'standard_id', 'standard_text', 'benchmark_id', 'benchmark_text',
  'bullets', 'cognitive_level', 'cognitive_label', 'modality', 'optional', 'mock_activity',
  'topics', 'statutes', 'rules', 'cases', 'named_references', 'repeats_in', 'weight', 'suggested_periods',
]];
courses.forEach((c) => c.standards.forEach((s) => s.benchmarks.forEach((b) => {
  csvRows.push([
    c.courseNumber, c.title, s.id, s.text, b.id, b.text,
    b.bullets.map((x) => `${'  '.repeat(x.depth)}- ${x.text}`).join(' | '),
    b.cognitiveLevel, b.cognitiveLabel, b.modality, b.optional, b.mockActivity,
    b.topics, b.citations.statutes, b.citations.rules, b.citations.cases, b.citations.named,
    b.repeatsIn, b.weight, b.suggestedPeriods,
  ]);
})));
out('dist/benchmarks.csv', `${csvRows.map((r) => r.map(csvCell).join(',')).join('\n')}\n`);

// ---------------------------------------------------------------- markdown
const md = [];
md.push(`# ${program.programTitle} - ${program.documentType}`, '');
md.push(`${program.agency} | Program ${program.programNumber} | CIP ${program.cipNumber} | Grades ${program.gradeLevel} | ${program.programLength}`, '');
md.push('## Purpose', '', program.purpose, '');
md.push('## Program Structure', '', program.programStructure, '');
md.push('| Course | Title | Credit | SOC | Level | Grad Req |', '| --- | --- | --- | --- | --- | --- |');
courses.forEach((c) => md.push(`| ${c.courseNumber} | ${c.title} | ${c.credit} | ${c.soc} | ${c.level} | ${c.graduationRequirement} |`));
md.push('');
md.push('## Career Ready Practices', '');
program.careerReadyPractices.practices.forEach((p, i) => md.push(`${i + 1}. ${p}`));
md.push('');
courses.forEach((c) => {
  md.push(`## ${c.title} (${c.courseNumber}) - ${c.credit} credit`, '');
  md.push(`**Standards ${c.standardRange}** | ${c.standardCount} standards | ${c.benchmarkCount} benchmarks`, '');
  md.push(c.description, '');
  c.standards.forEach((s) => {
    md.push(`### ${s.id} ${s.text}`, '');
    s.benchmarks.forEach((b) => {
      md.push(`- **${b.id}** ${b.text}`);
      b.bullets.forEach((x) => md.push(`${'  '.repeat(x.depth + 1)}- ${x.text}`));
    });
    md.push('');
  });
});
md.push('## Additional Information', '');
program.additionalInformation.forEach((s) => md.push(`### ${s.heading}`, '', s.body, ''));
out('dist/framework.md', `${md.join('\n')}\n`);

console.log(`\n  ${stats.courses} courses | ${stats.standards} standards | ${stats.benchmarks} benchmarks | ${stats.bullets} bullets`);
console.log(`  ${stats.performanceBenchmarks} performance / ${stats.knowledgeBenchmarks} knowledge | ${stats.optionalBenchmarks} optional | ${stats.mockActivities} mock activities`);
console.log(`  ${stats.distinctStatutes} distinct statutes | ${stats.distinctCases} cases | ${stats.repeatedClusters} cross-course repeat clusters`);
