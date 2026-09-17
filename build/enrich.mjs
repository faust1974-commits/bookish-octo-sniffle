// Derives the query dimensions used by the app, CLI and reports.
// Every derived value is a heuristic over the verbatim framework text; the
// framework text itself is never altered.

export const BLOOM = [
  { level: 1, name: 'Remember', verbs: ['identify','list','define','state','know','recognize','locate','name','match','label','read','cite','be','memorize','definition'] },
  { level: 2, name: 'Understand', verbs: ['describe','explain','discuss','understand','comprehend','interpret','summarize','differentiate','distinguish','classify','compare','contrast','paraphrase','review','introduce','illustrate'] },
  { level: 3, name: 'Apply', verbs: ['apply','demonstrate','perform','use','utilize','conduct','complete','operate','process','roll','lift','take','secure','prepare','write','make','follow','display','produce','measure','sketch','photograph','record','document','plan','obtain','facilitate','issue','respond','participate','assist','accept','enter','plot'] },
  { level: 4, name: 'Analyze', verbs: ['analyze','examine','investigate','determine','organize','outline','diagnose','troubleshoot'] },
  { level: 5, name: 'Evaluate', verbs: ['evaluate','assess','judge','critique','debate','defend','justify','recommend','proofread','verify'] },
  { level: 6, name: 'Create', verbs: ['create','develop','design','compose','construct','generate','incorporate','build','formulate'] },
];

const VERB_LEVEL = new Map();
BLOOM.forEach((b) => b.verbs.forEach((v) => VERB_LEVEL.set(v, b.level)));

// Verbs that require the student to do something observable -> a performance task.
const PERFORMANCE_VERBS = new Set([
  'demonstrate','perform','conduct','participate','create','complete','process','roll','lift','sketch',
  'photograph','operate','secure','take','write','prepare','produce','use','utilize','apply','make',
  'measure','record','document','obtain','facilitate','assist','issue','develop','plot','enter','plan',
]);

// Topic tags come from each program's data/programs/<n>/topics.json, never from
// code: one program's vocabulary must not tag another program's benchmarks.
export function compileTopics(list) {
  return list.map((t) => ({
    id: t.id,
    label: t.label,
    materials: t.materials || [],
    activities: t.activities || [],
    patterns: t.patterns.map((p) => new RegExp(p, 'i')),
  }));
}

const NAMED_REFERENCES = [
  ['Miranda', /Miranda/i], ['Baker Act', /Baker Act/i], ['Marchman Act', /Marchman Act/i],
  ['Florida Good Samaritan Act', /Good Samaritan/i], ['FLSA', /Fair Labor Standards Act|FLSA/i],
  ['OSHA', /OSHA|Occupational Safety and Health/i], ['AFIS', /AFIS|Automated Fingerprint/i],
  ['FCIC/NCIC', /FCIC|NCIC/i], ['CPTED', /CPTED|crime prevention through environmental design/i],
  ['TWIC', /TWIC/i], ['S.A.R.A. model', /S\.A\.R\.A\./i], ['ICS 100/700', /ICS 100/i],
  ['BENICE', /BENICE/i], ['DHSMV', /DHSMV|Highway Safety and Motor Vehicles/i],
  ['DOACS', /DOACS/i], ['CJSTC', /CJSTC|Criminal Justice Standards and Training Commission/i],
  ['Uniform Traffic Citation', /Uniform Traffic Citation|\bUTC\b/i],
  ['Great Seal of the State of Florida', /Great Seal/i],
  ['National Safety Council', /National Safety Council/i],
  ['Right-to-Know Law', /right-to-know/i],
];

const STOPWORDS = new Set(('a an and or the to of in on for with as it its is are be that this these those at by from ' +
  'their there them they he she his her you your student students will able describe identify discuss explain ' +
  'demonstrate list define understand know recognize use using various different include including such etc other ' +
  'may should must can when how what who where why which than then also into out up over under but not all any ' +
  'each both more most some no nor so if while during about between within').split(' '));

export function fullText(benchmark) {
  return [benchmark.text, ...benchmark.bullets.map((b) => b.text)].join(' ');
}

export function detectVerbs(text) {
  const head = text.toLowerCase().replace(/[^a-z\s/.-]/g, ' ').split(/[\s/]+/).filter(Boolean).slice(0, 8);
  const found = [];
  head.forEach((word) => {
    const stem = word.replace(/[.,;:]+$/, '');
    if (VERB_LEVEL.has(stem) && !found.includes(stem)) found.push(stem);
  });
  return found;
}

// Some benchmarks are noun headings whose verbs live in their bullets
// (Code Enforcement 29.x/30.x/31.x). Fall back to the bullets in that case.
export function classify(text, bulletTexts = []) {
  let verbs = detectVerbs(text);
  let fromBullets = false;
  if (!verbs.length && bulletTexts.length) {
    const found = [];
    bulletTexts.forEach((bt) => detectVerbs(bt).forEach((v) => { if (!found.includes(v)) found.push(v); }));
    if (found.length) { verbs = found; fromBullets = true; }
  }
  const levels = verbs.map((v) => VERB_LEVEL.get(v));
  const level = levels.length ? Math.max(...levels) : 2;
  const bloom = BLOOM.find((b) => b.level === level);
  return {
    verbs,
    verbsFromBullets: fromBullets,
    cognitiveLevel: level,
    cognitiveLabel: bloom.name,
    cognitiveInferred: verbs.length === 0,
    modality: verbs.some((v) => PERFORMANCE_VERBS.has(v)) ? 'performance' : 'knowledge',
  };
}

export function citations(text) {
  const statutes = new Set();
  const rules = new Set();
  const federal = new Set();
  const cases = new Set();

  for (const m of text.matchAll(/(?:Chapter|chapter|Section|section|s\.|statute)?\s*(\d{2,3}(?:\.\d+)?(?:\(\d+\))?(?:\([a-z]\))?)\s*,?\s*F\.S\./g)) {
    statutes.add(`${m[1]}, F.S.`);
  }
  for (const m of text.matchAll(/\[(\d{2,3}\.\d+(?:\(\d+\))?(?:\([a-z]\))?)\s*,\s*F\.S\.\]/g)) statutes.add(`${m[1]}, F.S.`);
  // "s. 316.640(4)(a), Florida Statute (F.S.)" / "Section 493.6105, F.S." / "statute 316.1933(1)(b), F.S."
  for (const m of text.matchAll(/(?:\bs\.|\bSections?\b|\bsections?\b|\bstatutes?\b|\bChapter\b|\bchapter\b)\s*(\d{2,3}\.\d+)/g)) statutes.add(`${m[1]}, F.S.`);
  const fsList = /Florida Statutes \(F\.S\.\)\s*([\d,\s]*(?:and\/or\s*)?\d+)/.exec(text);
  if (fsList) fsList[1].split(/[,\s]|and\/or/).filter((s) => /^\d+$/.test(s)).forEach((n) => statutes.add(`${n}, F.S.`));
  for (const m of text.matchAll(/((?:Chapter\s*)?[\dA-Z]+N?-?[\dA-Z]*(?:\.\d+)?)\s*,?\s*F\.A\.C\./g)) {
    rules.add(`${m[1].replace(/^Chapter\s*/, '')}, F.A.C.`);
  }
  for (const m of text.matchAll(/(\d+\s?CFR[-\s]?[\d.]+)/g)) federal.add(m[1].replace(/\s+/g, ''));
  for (const m of text.matchAll(/\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\s+v\.\s+([A-Z][a-zA-Z]+)/g)) cases.add(`${m[1]} v. ${m[2]}`);

  // Drop a bare section when a more specific subsection of it was also matched.
  const specific = [...statutes];
  const trimmed = specific.filter((c) => !specific.some((o) => o !== c && o.startsWith(c.replace(/, F\.S\.$/, '('))));

  const named = NAMED_REFERENCES.filter(([, re]) => re.test(text)).map(([label]) => label);
  return {
    statutes: trimmed.sort(),
    rules: [...rules].sort(),
    federal: [...federal].sort(),
    cases: [...cases].sort(),
    named,
  };
}

export function topics(text, compiled) {
  return compiled.filter((t) => t.patterns.some((p) => p.test(text))).map((t) => t.id);
}

export function keywords(text) {
  const seen = new Set();
  return text.toLowerCase().replace(/[^a-z0-9\s.-]/g, ' ').split(/\s+/)
    .map((w) => w.replace(/^[.-]+|[.-]+$/g, ''))
    .filter((w) => w.length >= 4 && !STOPWORDS.has(w) && !/^\d+$/.test(w))
    .filter((w) => (seen.has(w) ? false : seen.add(w)));
}

// Relative instructional weight, used to suggest pacing. Heuristic, documented in README.
export function weight(benchmark, classification) {
  let w = classification.modality === 'performance' ? 2 : 1;
  w += Math.min(2, benchmark.bullets.length / 4);
  w += Math.min(1, fullText(benchmark).length / 400);
  if (/mock|scenario|survey|participate/i.test(fullText(benchmark))) w += 0.5;
  if (/\(optional\)/i.test(benchmark.text)) w -= 0.5;
  return Math.round(w * 10) / 10;
}

export function normalizeForMatch(text) {
  return text.toLowerCase().replace(/\(optional\)/g, '').replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

export function jaccard(a, b) {
  const A = new Set(a), B = new Set(b);
  const inter = [...A].filter((x) => B.has(x)).length;
  return inter / (A.size + B.size - inter || 1);
}
