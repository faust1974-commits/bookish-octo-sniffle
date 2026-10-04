// One source of truth for the deck. Rendered twice: to .pptx, and to HTML so the
// layout can actually be looked at before it ships.
const INK = '1B1B1B';       // body text
const HEAD = '10243A';      // headings - deep navy, not black
const BLUE = '1A5FB4';      // the single accent
const SOFT = 'F2F5F8';      // card tint
const LINE = 'D7DEE6';      // hairlines
const MUTE = '5F6B79';      // secondary text

const FONT = 'Arial';
const M = 0.85;             // left/right margin
const CW = 13.33 - M * 2;   // content width = 11.63

const S = [];
const slide = (els, notes) => { S.push({ els, notes }); return S[S.length - 1]; };

// shared element helpers -----------------------------------------------------
const eyebrow = (t, y = 0.62) => ({ type: 'text', text: t, x: M, y, w: CW, h: 0.34, size: 13, bold: true, color: BLUE, spacing: 2, align: 'left' });
const lines = (t) => String(t).split('\n').length;
// 1.22 line-height at this size, plus a little slack so a descender never clips
const title = (t, y = 1.05, size = 40) => ({
  type: 'text', text: t, x: M, y, w: CW,
  h: Math.round((lines(t) * (size * 1.22) / 72 + 0.14) * 100) / 100,
  size, bold: true, color: HEAD,
});
const body = (t, y = 2.45, size = 22, w = CW) => {
  const est = String(t).split('\n').reduce((n, ln) => n + Math.max(1, Math.ceil(ln.length / (w * 96 / (size * 0.52)))), 0);
  return { type: 'text', text: t, x: M, y, w, h: Math.round((est * (size * 1.45) / 72 + 0.2) * 100) / 100, size, color: INK, line: Math.round(size * 1.45) };
};
const footer = (t) => ({ type: 'text', text: t, x: M, y: 6.72, w: CW, h: 0.34, size: 12, color: MUTE });
const rule = (y) => ({ type: 'rect', x: M, y, w: CW, h: 0.02, fill: LINE });
const chip = (n, x, y, d = 1.0) => ([
  { type: 'ellipse', x, y, w: d, h: d, fill: BLUE },
  { type: 'text', text: String(n), x, y, w: d, h: d, size: Math.round(d * 26), bold: true, color: 'FFFFFF', align: 'center', valign: 'middle' },
]);
const card = (x, y, w, h, fill = SOFT) => ({ type: 'roundRect', x, y, w, h, fill });

// Progress rail - which of the eleven we are on.
function rail(active, y = 5.85) {
  const els = [];
  const d = 0.42, gap = (CW - d) / 10;
  for (let i = 1; i <= 11; i += 1) {
    const x = M + (i - 1) * gap;
    const isNow = i === active, isPast = i < active;
    els.push({ type: 'ellipse', x, y, w: d, h: d, fill: isNow ? BLUE : isPast ? 'C6D6EA' : 'E8EDF3' });
    els.push({ type: 'text', text: String(i), x, y, w: d, h: d, size: 12, bold: true,
      color: isNow ? 'FFFFFF' : isPast ? '3E5C80' : '9AA7B5', align: 'center', valign: 'middle' });
  }
  els.push({ type: 'text', text: 'THE ELEVEN STAGES', x: M, y: y + 0.55, w: CW, h: 0.3, size: 11, bold: true, color: '9AA7B5', spacing: 2 });
  return els;
}

// 1. title -------------------------------------------------------------------
slide([
  eyebrow('CRIMINAL JUSTICE OPERATIONS', 1.9),
  title('How a Case Moves', 2.35, 58),
  { type: 'text', text: 'One case, from the 911 call to release', x: M, y: 3.75, w: CW, h: 0.6, size: 24, color: MUTE },
  rule(4.6),
  { type: 'text', text: '90 minutes  ·  CJO 1, 2 and 3', x: M, y: 4.85, w: CW, h: 0.45, size: 16, color: MUTE },
], 'Open on the Collaborate Board instead of this slide, so students are typing within the first minute. Come back here to frame the day.');

// 2. collaborate board -------------------------------------------------------
slide([
  eyebrow('EVERYONE ANSWERS'),
  title('What job in criminal justice\nwould you actually want?', 1.25, 44),
  { type: 'text', text: 'Post it on the board. Add one word for why.', x: M, y: 3.35, w: CW, h: 0.6, size: 24, color: BLUE, bold: true },
  footer('Collaborate Board · answers appear on the board as students post'),
], 'NEARPOD: this slide is where the Collaborate Board goes. Build it with the title and instructions shown here. Let the board fill for two minutes before you say anything, then read three or four aloud and ask why that one. Leave it up while you introduce the day.');

// 3. framing -----------------------------------------------------------------
slide([
  eyebrow('TODAY'),
  title('One case. Start to finish.', 1.05, 46),
  body('Every job on that board touches the same case at a different point.\n\nToday we follow one case all the way through, so everything else this year has somewhere to hang.', 2.6, 24),
], 'Say it plainly and move on. Sixty seconds.');

// 4-6. the three framings ----------------------------------------------------
function rows(titleText, items, notes, eyebrowText) {
  const els = [eyebrow(eyebrowText), title(titleText)];
  const top = 2.45;
  const gap = items.length > 3 ? 1.02 : 1.25;
  items.forEach(([label, text], i) => {
    const y = top + i * gap;
    els.push(...chip(i + 1, M, y + 0.02, 0.6));
    els.push({ type: 'text', text: label, x: M + 0.85, y, w: 3.15, h: 0.6, size: 22, bold: true, color: HEAD });
    els.push({ type: 'text', text, x: M + 4.05, y, w: CW - 4.05, h: 0.85, size: 19, color: INK, line: 26 });
  });
  slide(els, notes);
}
rows('Three branches of government', [
  ['Legislative', 'Makes the law. The Florida Legislature writes the criminal statutes.'],
  ['Executive', 'Enforces the law. Police, sheriffs, corrections, the State Attorney.'],
  ['Judicial', 'Interprets the law. Judges and courts.'],
], 'Students mix these up constantly. Three sentences, then move - the matching game is where it sticks.', 'FRAMEWORK 1 OF 3');

rows('Three parts of the system', [
  ['Law enforcement', 'Responds, investigates, arrests.'],
  ['Courts', 'Charges, tries, sentences.'],
  ['Corrections', 'Jails, prisons, probation, supervision.'],
], 'A case passes through all three in that order. This is the spine of the whole lesson.', 'FRAMEWORK 2 OF 3');

rows('Four levels of government', [
  ['Federal', 'FBI, DEA, U.S. Attorney, federal courts and prisons.'],
  ['State', 'FHP, FDLE, State Attorney, circuit courts, Dept. of Corrections.'],
  ['County', 'Sheriff’s Office, county jail, county court.'],
  ['Local', 'City police department, code enforcement.'],
], 'Do not linger here. The matching game next is where this lands.', 'FRAMEWORK 3 OF 3');

// 7. matching ----------------------------------------------------------------
slide([
  eyebrow('EVERYONE ANSWERS'),
  title('Who does what?', 1.05, 46),
  body('Match each agency to its job. Fastest correct set wins.', 2.5, 26),
  footer('Matching Pairs · eight pairs · two minutes'),
], 'NEARPOD: Matching Pairs goes here. The eight pairs are in the build sheet. Run it as a race - the report shows you who is lost.');

// 8. section -----------------------------------------------------------------
slide([
  eyebrow('THE SPINE OF THE COURSE'),
  title('Eleven stages.\nEvery case moves the same way.', 1.15, 44),
  body('Report → patrol → arrest → booking → first appearance → charge → arraignment → pretrial → trial → sentence → corrections', 3.9, 19),
], 'Eleven slides coming. Say the stage, say what happens, move on. Do not stop for discussion - the polls are coming.');

// 9-19. the eleven stages ----------------------------------------------------
const STAGES = [
  ['Report or call for service', 'Someone calls 911, walks into a lobby, or an officer sees it happen. Dispatch assigns it to a unit.', 'Point out that a civilian starts the case almost every time, not the police.'],
  ['Patrol response', 'The officer secures the scene, finds witnesses, collects evidence, and writes a report.', 'Say this out loud: everything that happens later is built on this report. It sets up the next lesson.'],
  ['Arrest, or a notice to appear', 'An arrest needs probable cause — more than a hunch, less than certainty. For many misdemeanors an officer can issue a written notice to appear instead.', 'Students assume every crime means handcuffs. The notice to appear surprises them.'],
  ['Booking', 'Photographs, fingerprints, property inventory and medical screening at the jail.', 'Those fingerprints go into state and national systems. That matters again in CJO 3.'],
  ['First appearance', 'Within 24 hours a judge confirms probable cause, states the charge, advises the right to a lawyer, and sets bond.', 'Twenty-four hours is fast, and it is required. This one comes back in the game at the end.'],
  ['The charging decision', 'The State Attorney decides the charge, not the police. Most felonies are charged by an information. A capital crime requires a grand jury indictment.', 'The most surprising fact in the lesson. Let it land, then ask: so what does the officer actually control?'],
  ['Arraignment', 'The defendant is formally told the charge and enters a plea — guilty, not guilty, or no contest.', 'Quick slide. Keep moving.'],
  ['Pretrial', 'Both sides exchange evidence. The defense may move to suppress. Most cases end right here in a plea agreement.', 'Most cases never reach a trial. That surprises students raised on television.'],
  ['Trial', 'The State must prove guilt beyond a reasonable doubt. The defendant does not have to prove anything.', 'Say the second sentence twice. It is the most misunderstood idea in the course.'],
  ['Sentencing', 'Fines, probation, community control, jail, prison, restitution — often a combination.', 'Prison is not the default outcome. Worth saying.'],
  ['Corrections and release', 'Jail is county-run for a year or less. Prison is state-run for more than a year. Probation is served in the community.', 'This sets up the next slide.'],
];
STAGES.forEach(([name, text, notes], i) => {
  slide([
    eyebrow(`STAGE ${i + 1} OF 11`),
    ...chip(i + 1, M, 1.15, 1.05),
    { type: 'text', text: name, x: M + 1.35, y: 1.2, w: CW - 1.35, h: 0.95, size: 38, bold: true, color: HEAD },
    { type: 'text', text, x: M + 1.35, y: 2.55, w: CW - 1.35, h: 2.6, size: 24, color: INK, line: 35 },
    ...rail(i + 1),
  ], notes);
});

// 20. misdemeanor / felony ---------------------------------------------------
slide([
  eyebrow('THE LINE THAT DECIDES EVERYTHING'),
  title('Misdemeanor or felony?', 1.05, 44),
  card(M, 2.6, 5.6, 3.3),
  card(M + 6.03, 2.6, 5.6, 3.3, BLUE),
  { type: 'text', text: 'Misdemeanor', x: M + 0.45, y: 2.95, w: 4.7, h: 0.6, size: 28, bold: true, color: HEAD },
  { type: 'text', text: 'Up to one year\nCounty jail\nHeard in county court', x: M + 0.45, y: 3.7, w: 4.7, h: 1.9, size: 21, color: INK, line: 34 },
  { type: 'text', text: 'Felony', x: M + 6.48, y: 2.95, w: 4.7, h: 0.6, size: 28, bold: true, color: 'FFFFFF' },
  { type: 'text', text: 'More than one year\nState prison\nHeard in circuit court', x: M + 6.48, y: 3.7, w: 4.7, h: 1.9, size: 21, color: 'FFFFFF', line: 34 },
], 'One distinction decides the court, the sentence and the building. Then the poll - they will guess wrong, and that is the point.');

// 21. poll -------------------------------------------------------------------
slide([
  eyebrow('EVERYONE VOTES'),
  title('A $640 power washer is stolen.\nMisdemeanor or felony?', 1.25, 42),
  body('No talking. Vote first.', 3.5, 24),
  footer('Poll · two options'),
], 'NEARPOD: Poll goes here. Options: Misdemeanor / Felony. Most will say misdemeanor because it sounds small - in Florida this is grand theft, a felony. Reveal the split, then move to Gideon.');

// 22. Gideon -----------------------------------------------------------------
slide([
  eyebrow('ONE FLORIDA CASE · 1961'),
  title('He asked for a lawyer.\nFlorida said no.', 1.15, 44),
  body('Charged with breaking into a Panama City pool hall. He could not afford a lawyer, and Florida said it did not have to give him one. He defended himself, lost, and went to prison.\n\nFrom his cell he wrote to the U.S. Supreme Court in pencil. In 1963 the Court ruled that anyone facing serious charges has the right to a lawyer — paid for by the state if they cannot afford one.\n\nRetried with a lawyer, Gideon was acquitted.', 3.35, 19),
], 'Tell it as a story - ninety seconds. That is why there is a public defender in the room, and it started in Florida. Good spot for a stretch break afterwards.');

// 23. case intro -------------------------------------------------------------
slide([
  eyebrow('NOW WATCH IT HAPPEN'),
  title('State of Florida v. Ramirez', 1.05, 46),
  body('Eleven paragraphs. After each one, you call the stage.', 2.6, 26),
], 'Read each paragraph aloud. The class calls the stage, then you reveal it. Keep the pace up.');

// 24-45. the case, ask + reveal ---------------------------------------------
const CASE = [
  ['At 7:42 p.m. on a Tuesday, a hardware store owner in Ocala calls 911. He says a man just walked out with a power washer without paying and drove off in a grey pickup.', 'Report or call for service', 'A civilian starts the case. Dispatch assigns it.'],
  ['Deputy Ellis arrives six minutes later. She interviews the owner, watches the store camera footage, photographs the empty display stand, writes down two witnesses, and writes her report.', 'Patrol response', 'Everything after this is built on what she wrote down.'],
  ['Twenty minutes later another deputy stops a grey pickup two miles away. The power washer is in the bed, still tagged. The driver, Marco Ramirez, is arrested.', 'Arrest', 'Probable cause: the description, the location, the property in plain view.'],
  ['At the county jail Ramirez is photographed and fingerprinted, his property is inventoried, and he is screened by medical staff.', 'Booking', 'Routine - and it creates records that follow the case.'],
  ['The next morning Ramirez stands before a judge by video from the jail. The judge finds probable cause, states the charge, advises him of his right to a lawyer, and sets bond at $2,500.', 'First appearance', 'Less than twenty-four hours after arrest, exactly as required.'],
  ['An assistant state attorney reads the report, notes the power washer is worth $640, and files an information charging grand theft in the third degree.', 'The charging decision', 'The State Attorney chose the charge. Not the deputy, and not the store owner.'],
  ['Three weeks later Ramirez appears in circuit court, is told the charge, and pleads not guilty.', 'Arraignment', 'Circuit court, because grand theft is a felony.'],
  ['The two sides exchange evidence. The defense files a motion arguing the traffic stop was unlawful. The judge denies it. The State offers eighteen months of probation and restitution.', 'Pretrial', 'Discovery, a motion to suppress, and a plea offer.'],
  ['Ramirez turns the offer down. Six jurors hear the deputy and the owner testify. The video is played. After two hours the jury returns a verdict of guilty.', 'Trial', 'He traded a certain outcome for an uncertain one.'],
  ['The judge orders eighteen months of probation, $640 in restitution, and forty hours of community service.', 'Sentencing', 'No prison. Ask the room whether that surprises them.'],
  ['Ramirez is released the same day and reports to his probation officer on Monday. If he finishes the eighteen months without violating, the case is closed.', 'Corrections and release', 'Supervision in the community is the most common outcome in the system.'],
];
CASE.forEach(([text, stage, why], i) => {
  slide([
    eyebrow(`THE CASE · ${i + 1} OF 11`),
    { type: 'text', text, x: M, y: 1.45, w: CW, h: 3.5, size: 27, color: INK, line: 39 },
    { type: 'text', text: 'Which stage is this?', x: M, y: 5.1, w: CW, h: 0.6, size: 26, bold: true, color: BLUE },
  ], `Read aloud, then ask the room. Answer: stage ${i + 1}, ${stage}.`);
  slide([
    eyebrow('ANSWER'),
    ...chip(i + 1, M, 2.3, 1.15),
    { type: 'text', text: stage, x: M + 1.5, y: 2.3, w: CW - 1.5, h: 0.9, size: 40, bold: true, color: HEAD },
    { type: 'text', text: why, x: M + 1.5, y: 3.35, w: CW - 1.5, h: 1.4, size: 22, color: MUTE, line: 32 },
    ...rail(i + 1),
  ], 'Reveal, one sentence, next.');
});

// 46. plea poll --------------------------------------------------------------
slide([
  eyebrow('EVERYONE VOTES'),
  title('Should Ramirez have taken\nthe plea deal?', 1.25, 44),
  body('Eighteen months of probation, guaranteed — or take your chances at trial.', 3.9, 22),
  footer('Poll · then argue it'),
], 'NEARPOD: Poll goes here. Options: Yes, take the deal / No, go to trial. There is no right answer. Show the split, then push one student from each side to say why. This is the discussion the lesson was building toward.');

// 47. time to climb ----------------------------------------------------------
slide([
  eyebrow('WHOLE CLASS'),
  title('Ten questions. Go.', 1.05, 48),
  body('Everything from today. Speed counts.', 2.6, 26),
  footer('Time to Climb · this is the assessment — no worksheet'),
], 'NEARPOD: Time to Climb goes here. Ten questions and answers are in the build sheet. Nearpod gives you the report afterwards showing who got what, which is your record for the day.');

// 48. exit ticket ------------------------------------------------------------
slide([
  eyebrow('BEFORE YOU GO'),
  title('Which stage do you think\nmost cases go wrong at?', 1.25, 44),
  body('One or two sentences. Say why.', 3.45, 24),
  footer('Open-Ended Question · shared anonymously on the board'),
], 'NEARPOD: Open-Ended Question goes here. Share two or three responses anonymously before they leave. Nearpod saves every answer.');

// 49. next -------------------------------------------------------------------
slide([
  eyebrow('NEXT TIME'),
  title('The report that started it all', 1.05, 46),
  body('Every part of this case rested on what Deputy Ellis wrote down in the first hour.\n\nNext lesson we write one.', 2.6, 24),
], 'Ends on the hook for the next lesson, which is where CJO 2 and CJO 3 content takes over.');

module.exports = { S, INK, HEAD, BLUE, SOFT, LINE, MUTE, FONT, M, CW };
