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

export const TOPICS = [
  { id: 'patrol', label: 'Patrol Operations', patterns: [/\bpatrol/i, /\bzone/i, /fixed post/i, /police hazard/i] },
  { id: 'traffic-control', label: 'Traffic Direction & Control', patterns: [/traffic (control|direction|signal|device)/i, /direct(ing)? traffic/i, /hand signal/i, /whistle/i, /\bflare/i, /baton/i, /light stick/i, /crossing/i, /pedestrian/i, /traffic controller/i] },
  { id: 'crash-investigation', label: 'Traffic Crash Investigation', patterns: [/\bcrash/i, /collision/i, /skid mark/i, /tow truck/i, /DHSMV/i, /uniform traffic citation/i, /\bUTC\b/i, /vehicular speed/i] },
  { id: 'use-of-force', label: 'Use of Force & Arrest', patterns: [/use[- ]of[- ]force/i, /use of force/i, /deadly force/i, /reasonable force/i, /defensive tactics/i, /\barrest/i, /custody/i, /prisoner/i, /booking/i, /frisk/i, /Garner/i, /Graham/i, /Terry v/i, /de-escalation/i, /subject resistance/i, /firearm/i, /\bweapon/i] },
  { id: 'investigations', label: 'Criminal Investigation', patterns: [/investigat/i, /interrogat/i, /confession/i, /search warrant/i, /seizure/i, /exclusionary/i, /polygraph/i, /\bsuspect/i, /levels of proof/i, /probable[- ]cause/i] },
  { id: 'forensics', label: 'Forensic Science', patterns: [/fingerprint/i, /latent/i, /\bDNA\b/i, /hair and fiber/i, /broken glass/i, /crime lab/i, /\bAFIS\b/i, /Henry Modified/i, /blood type/i, /impression/i, /Plaster of Paris/i, /photo laboratory/i] },
  { id: 'crime-scene', label: 'Crime Scene & Evidence', patterns: [/crime scene/i, /\bevidence/i, /chain of custody/i, /property control/i, /contaminat/i, /preserv/i, /mock crime scene/i, /field sketch/i] },
  { id: 'report-writing', label: 'Report Writing & Documentation', patterns: [/\breport/i, /note taking/i, /field notes/i, /narrative/i, /affidavit/i, /diagram/i, /who-what-when/i, /interrogatives/i, /bullet-style/i] },
  { id: 'courts-testimony', label: 'Courts & Testimony', patterns: [/\bcourt/i, /\btrial/i, /testimony/i, /testif/i, /deposition/i, /subpoena/i, /\bjury\b/i, /\bjudge\b/i, /prosecutor/i, /defense attorney/i, /demeanor/i, /cross[- ]examination/i, /hearing/i, /pretrial/i, /venue/i, /duces tecum/i] },
  { id: 'law-legal', label: 'Law & Legal Authority', patterns: [/\bstatute/i, /F\.S\./, /F\.A\.C\./, /ordinance/i, /constitutional/i, /misdemeanor/i, /felony/i, /\bchapter \d/i, /\blegal\b/i, /Miranda/i, /jurisdiction/i, /civil and criminal/i, /rights of/i, /right-to-know/i, /liabilit/i, /Good Samaritan/i] },
  { id: 'juvenile', label: 'Juvenile Justice', patterns: [/juvenile/i, /delinquen/i] },
  { id: 'corrections', label: 'Corrections', patterns: [/correction/i, /\binmate/i, /\bprison/i, /\bjail\b/i] },
  { id: 'communication', label: 'Communication Skills', patterns: [/communicat/i, /\bradio\b/i, /telephone/i, /interview/i, /rapport/i, /etiquette/i, /interpersonal/i, /phonetic/i, /listening/i, /public speaking/i, /body language/i, /\bmessage/i] },
  { id: 'diversity', label: 'Human Diversity & Community', patterns: [/diversit/i, /cultural/i, /minority/i, /bias[- ]based/i, /disabilit/i, /elderly/i, /homeless/i, /veteran/i, /human relations/i, /special concerns/i, /older population/i, /community relations/i, /transient/i] },
  { id: 'ethics', label: 'Ethics & Professionalism', patterns: [/\bethic/i, /professionalism/i, /professional conduct/i, /integrity/i, /harassment/i, /discriminat/i, /command presence/i, /grooming/i, /\buniform\b(?!\s+(?:traffic|crime))/i, /honesty/i, /code of conduct/i, /discipline/i] },
  { id: 'employability', label: 'Employability & Career', patterns: [/employ/i, /\bjob\b/i, /resume/i, /job application/i, /\bcareer/i, /training opportunit/i, /work habits/i, /performance evaluation/i, /letter of introduction/i, /prerequisite/i] },
  { id: 'crime-prevention', label: 'Crime Prevention', patterns: [/crime prevention/i, /CPTED/i, /security survey/i, /prevention of/i, /preventive patrol/i, /crime analysis/i] },
  { id: 'security-industry', label: 'Private Security Industry', patterns: [/security officer/i, /private security/i, /493/, /DOACS/i, /licens/i, /access control/i, /CCTV/i, /\bTWIC\b/i, /security vehicle/i, /security business/i, /security patrol/i] },
  { id: 'emergency-response', label: 'Emergency & Crisis Response', patterns: [/emergency/i, /first aid/i, /bloodborne/i, /disaster/i, /hurricane/i, /active shooter/i, /weapons of mass destruction/i, /evacuation/i, /\bcrisis/i, /Baker Act/i, /Marchman/i, /mental illness/i, /suicide/i, /trauma team/i, /medical response/i] },
  { id: 'fire-life-safety', label: 'Fire & Life Safety', patterns: [/\bfire\b/i, /fires/i, /extinguish/i, /life safety/i, /fire watch/i, /incendiary/i] },
  { id: 'terrorism', label: 'Terrorism Awareness', patterns: [/terror/i, /OPSEC/i, /\bbomb\b/i, /BENICE/i, /threat level/i, /mail screening/i] },
  { id: 'crowd-control', label: 'Crowd Control', patterns: [/\bcrowd/i, /\briot/i, /protest/i, /demonstration/i, /civil disturbance/i, /disturbance/i] },
  { id: 'technology', label: 'Technology & Records', patterns: [/computer/i, /software/i, /database/i, /spreadsheet/i, /word processor/i, /\bCAD\b/i, /technolog/i, /e-mail/i, /keyboarding/i, /\bFCIC\b/i, /\bNCIC\b/i, /records management/i, /electronic/i, /internet/i, /networking/i, /3D model/i, /cell phone/i] },
  { id: 'math', label: 'Applied Math', patterns: [/\bmath\b/i, /arithmetic/i, /measurement/i, /estimat/i, /\bgraph\b/i, /dollar amount/i, /fractions/i, /decimals/i, /computations/i] },
  { id: 'code-enforcement', label: 'Code Enforcement', patterns: [/code enforcement/i, /code violation/i, /code board/i, /\blien/i, /county code/i, /right of entry/i, /forfeiture/i] },
  { id: 'legal-office', label: 'Legal Office Practice', patterns: [/legal office/i, /notary/i, /filing/i, /accounting/i, /legal document/i, /\bclient/i, /legal terminolog/i, /legal business/i, /legal professional/i, /legal workplace/i, /legal operating system/i, /trust bank/i] },
  { id: 'safety-wellness', label: 'Officer Safety & Wellness', patterns: [/officer safety/i, /\bstress/i, /wellness/i, /\bhazard/i, /OSHA/i, /HAZMAT/i, /protective equipment/i, /substance/i, /aggressive animal/i, /fight or flight/i, /safety precaution/i, /officer survival/i, /right-to-know/i, /workplace violence/i, /violence in the workplace/i] },
  { id: 'entrepreneurship', label: 'Entrepreneurship', patterns: [/entrepreneur/i, /starting a .*business/i, /business investment/i] },
  { id: 'ctso', label: 'CTSO & Leadership', patterns: [/\bFPSA\b/i, /\bCTSO\b/i, /SkillsUSA/i, /leadership/i, /supervision/i, /managerial/i, /performance management/i] },
  { id: 'time-management', label: 'Time & Task Management', patterns: [/time management/i, /scheduling/i, /prioritization/i, /goal setting/i, /self-motivation/i] },
  { id: 'public-relations', label: 'Media & Public Relations', patterns: [/\bmedia\b/i, /press release/i, /public relations/i, /public records/i, /courtesy and etiquette/i] },
  { id: 'system-overview', label: 'CJ System Overview', patterns: [/criminal justice system/i, /branches/i, /history and goals/i, /history of/i, /roles and responsibilities/i, /court system/i] },
];

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

export function topics(text) {
  return TOPICS.filter((t) => t.patterns.some((p) => p.test(text))).map((t) => t.id);
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
