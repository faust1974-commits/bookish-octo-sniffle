const C = require('./common.js');
const { P, RUNS, BULLET, NUM, RULE, BOX, labelCell, headerCells, table, docShell, Paragraph, TextRun, HeadingLevel, PageBreak, Packer } = C;
const { TableRow } = require('docx');
const fs = require('fs');

const H1 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_1 });
const H2 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_2 });
const H3 = (t) => new Paragraph({ text: t, heading: HeadingLevel.HEADING_3 });

const IC = [900, 2500, 5960];
const insertRow = (slide, activity, content) => new TableRow({
  children: [labelCell(IC[0], slide), labelCell(IC[1], activity), labelCell(IC[2], content, { bold: false })],
});

const TTC = [
  ['Who decides what charge is filed?', ['The arresting officer', 'The judge', 'The State Attorney', 'The victim'], 3],
  ['How soon after arrest must a defendant see a judge?', ['Within 24 hours', 'Within 72 hours', 'Within 10 days', 'Within 30 days'], 1],
  ['A crime punishable by more than one year is a...', ['Misdemeanor', 'Felony', 'Infraction', 'Citation'], 2],
  ['Which Florida court hears felony cases?', ['County court', 'Circuit court', 'Small claims court', 'Traffic court'], 2],
  ['Who has to prove the case at trial?', ['The defendant', 'The judge', 'The State', 'The jury'], 3],
  ['What standard of proof is needed to convict?', ['Probable cause', 'Preponderance of the evidence', 'Beyond a reasonable doubt', 'Reasonable suspicion'], 3],
  ['Which branch of government writes criminal laws?', ['Executive', 'Judicial', 'Legislative', 'Corrections'], 3],
  ['Jail is run by the county. Prison is run by the...', ['City', 'State', 'Federal government', 'Sheriff'], 2],
  ['Most criminal cases end with...', ['A jury trial', 'A plea agreement', 'Dismissal at first appearance', 'An appeal'], 2],
  ['Gideon v. Wainwright established the right to...', ['Remain silent', 'A speedy trial', 'A lawyer', 'A jury of twelve'], 3],
];

const MATCH = [
  ['FBI', 'Federal investigations'],
  ['Florida Highway Patrol', 'State traffic enforcement'],
  ['Sheriff’s Office', 'County law enforcement and the jail'],
  ['City police department', 'Local municipal policing'],
  ['State Attorney', 'Files the charges'],
  ['Public defender', 'Represents people who cannot pay'],
  ['Circuit court', 'Hears felonies'],
  ['County court', 'Hears misdemeanors'],
];

const children = [
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: 'NEARPOD BUILD SHEET', size: 18, bold: true, color: C.GREY })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'How a Case Moves', size: 44, bold: true, color: C.NAVY })] }),
  new Paragraph({ spacing: { after: 220 }, children: [new TextRun({ text: '90 minutes · CJO 1, 2 and 3 together · nothing to print', size: 24, color: C.GREY })] }),

  BOX('Why this is a build sheet and not a finished Nearpod file', [
    'Nearpod activities only exist inside Nearpod - there is no file format that carries a Collaborate Board or a Time to Climb, so no deck from anywhere can arrive with them already in it. Building them in Nearpod is the only way, for anyone.',
    'What this does instead: the deck is a complete, teachable lesson on its own, and the six question slides are written so the lesson still works if you run out of time and just take answers by hand. Adding the activities upgrades it - it does not rescue it.',
    'Every activity\u2019s exact setup is also in that slide\u2019s speaker notes, so you never have to hunt for this page while you are building.',
  ]),
  P(''),
  BOX('Build it once, about ten minutes', [
    '1. In Nearpod: My Library > Create > Lesson in Nearpod.',
    '2. Add Slide > Upload Files, and upload "How a Case Moves - NEARPOD SLIDES.pptx". All forty-nine slides come in with their notes.',
    '3. Work down the table below. For each row, click Add Activity after that slide number and paste in the content given.',
    '4. Save. Launch it Live for each class - the same lesson runs for every section.',
  ]),
  P(''),
  BOX('If you only have time for one thing', [
    'Build the Collaborate Board (after slide 2) and the Time to Climb (after slide 47). Those two carry the lesson.',
    'The other four work fine as a show of hands on the slide as written. Add them later.',
  ]),

  H1('The five activities'),
  table(IC, [
    headerCells(['Slide', 'Nearpod activity', 'Exactly what to put in it'], IC),
    insertRow('2', 'Collaborate Board', 'Title: What job in criminal justice would you actually want?|Instructions: Post the job you would want and one word for why. You can post more than once.|Turn on: let students see each other’s posts. Leave names off.|This is the opener - their answers fill the board while you talk.'),
    insertRow('7', 'Matching Pairs', 'Title: Who does what?|The eight pairs are listed on the next page. Type them in the order given.'),
    insertRow('21', 'Poll', 'Question: A $640 power washer is stolen. Misdemeanor or felony?|Option 1: Misdemeanor|Option 2: Felony|Correct answer is felony - in Florida this is grand theft. Most of the class will guess wrong, which is the point. Reveal the result, then move to the Gideon slide.'),
    insertRow('47', 'Poll', 'Question: Should Ramirez have taken the plea deal?|Option 1: Yes, take the eighteen months|Option 2: No, go to trial|There is no right answer. Show the split, then ask one student from each side to say why.'),
    insertRow('48', 'Time to Climb', 'Title: How a Case Moves|Ten questions with answers on the next page. Nearpod gives you a report afterwards showing who got what.'),
    insertRow('49', 'Open-Ended Question', 'Question: Which stage do you think most cases go wrong at, and why?|This is the exit ticket. Share two or three answers anonymously on the board before they leave. Nearpod saves every response.'),
  ]),

  P(''),
  BOX('Optional, if you want more interaction in the case section', [
    'Slides 24 to 45 alternate: a case paragraph, then the answer. You can convert any of those answer slides into a two-option Poll ("Which stage was that?") so the quiet students have to commit to an answer instead of listening to whoever shouts first.',
    'Do not do this for all eleven - it drags. Three or four is plenty. Good ones: the charging decision, the trial, and sentencing.',
  ]),

  new Paragraph({ children: [new PageBreak()] }),

  H1('Matching Pairs — slide 7'),
  P('Eight pairs. Type the left item and the right item as a pair.'),
  table([4200, 5160], [
    headerCells(['This...', 'matches this'], [4200, 5160]),
    ...MATCH.map(([a, b]) => new TableRow({ children: [labelCell(4200, a), labelCell(5160, b, { bold: false })] })),
  ]),

  H1('Time to Climb — slide 48'),
  P('Ten questions. The correct answer is marked in bold.'),
  ...TTC.flatMap(([q, opts, correct], i) => [
    new Paragraph({ spacing: { before: 200, after: 60 }, children: [
      new TextRun({ text: `${i + 1}.  `, bold: true, size: 22, color: C.NAVY }),
      new TextRun({ text: q, size: 22, bold: true }),
    ] }),
    ...opts.map((o, j) => new Paragraph({
      spacing: { after: 30 },
      indent: { left: 520 },
      children: [new TextRun({
        text: `${String.fromCharCode(65 + j)}.  ${o}${j + 1 === correct ? '   ✓ correct' : ''}`,
        size: 21,
        bold: j + 1 === correct,
        color: j + 1 === correct ? '1F6B43' : '32414F',
      })],
    })),
  ]),

  new Paragraph({ children: [new PageBreak()] }),

  H1('What you need to know before you teach it'),
  P('Read this once. It is more than you will need to say out loud. If a student asks something past it, "good question, let us look it up" is a legitimate answer - and looking it up together is a criminal justice lesson in itself.', { italics: true, color: C.GREY }),

  H2('The eleven stages'),
  NUM('Report or call for service. A civilian starts almost every case.'),
  NUM('Patrol response. The officer secures the scene, finds witnesses, collects evidence, writes the report. Everything later is built on that report.'),
  NUM('Arrest, or a notice to appear. An arrest needs probable cause. For many misdemeanors an officer can issue a written notice to appear instead of making an arrest.'),
  NUM('Booking. Photographs, fingerprints, property inventory, medical screening.'),
  NUM('First appearance, within 24 hours. A judge confirms probable cause, states the charge, advises the right to counsel, sets bond.'),
  NUM('Charging decision. The State Attorney decides the charge, not the police. Most felonies are charged by an information; a capital crime requires a grand jury indictment. The State Attorney can also decline to charge.'),
  NUM('Arraignment. The charge is read and a plea is entered.'),
  NUM('Pretrial. Discovery, motions to suppress, plea negotiation. Most cases end here.'),
  NUM('Trial. The State must prove guilt beyond a reasonable doubt. The defendant proves nothing and need not testify.'),
  NUM('Sentencing. Fines, probation, community control, jail, prison, restitution.'),
  NUM('Corrections and release. Jail is county-run for a year or less; prison is state-run for more than a year; probation is served in the community.'),

  H2('Three ideas students mix up'),
  BULLET('Branches: legislative makes law, executive enforces it, judicial interprets it.'),
  BULLET('Parts of the system: law enforcement, courts, corrections - a case passes through all three in that order.'),
  BULLET('Levels: federal, state, county, local.'),

  H2('If a student asks'),
  RUNS([{ text: '"What if they never read me my rights?" ', bold: true }, { text: 'Miranda is required before questioning someone in custody. Skipping it does not undo the arrest - it means statements can be thrown out.' }]),
  RUNS([{ text: '"Can the victim drop the charges?" ', bold: true }, { text: 'No. The case is the State against the defendant. The State Attorney decides.' }]),
  RUNS([{ text: '"Jail or prison?" ', bold: true }, { text: 'Jail is county, a year or less. Prison is state, more than a year.' }]),
  RUNS([{ text: '"Does everyone get a lawyer?" ', bold: true }, { text: 'For serious charges, yes - Gideon v. Wainwright, a Florida case.' }]),
  RUNS([{ text: '"How long does it take?" ', bold: true }, { text: 'Months. There is a speedy trial rule but continuances are routine and most cases plead out.' }]),
  RUNS([{ text: '"What if the search was illegal?" ', bold: true }, { text: 'The defense can move to suppress. If the judge agrees it violated the Fourth Amendment, that evidence cannot be used. Stop there - the exceptions get complicated fast.' }]),

  BOX('One thing that changed recently - do not teach the old version', [
    'Florida’s speedy trial rule used to start the clock at arrest: 90 days for a misdemeanor, 175 for a felony.',
    'Effective July 1, 2025 the Florida Supreme Court revised Rule 3.191. The clock now starts when the State files formal charges.',
    'Most lesson plans online still show the old rule. If a student finds the old numbers, that is a good moment about checking the date on a source.',
  ]),

  H1('The 90 minutes'),
  table([1300, 3400, 4660], [
    headerCells(['Time', 'Slides', 'What is happening'], [1300, 3400, 4660]),
    new TableRow({ children: [labelCell(1300, '0–10'), labelCell(3400, 'Slide 2 + Collaborate Board', { bold: false }), labelCell(4660, 'Students post jobs from their Chromebooks as they walk in. Read a few out loud. Do not rush this.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '10–22'), labelCell(3400, 'Slides 3–7', { bold: false }), labelCell(4660, 'Frame the day, three branches, three parts, four levels, then Matching Pairs as a race.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '22–45'), labelCell(3400, 'Slides 8–21', { bold: false }), labelCell(4660, 'The eleven stages, one slide each. Then the misdemeanor/felony line and the poll they get wrong.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '45–50'), labelCell(3400, 'Slides 22–23', { bold: false }), labelCell(4660, 'The Gideon story. Ninety seconds, told as a story. Good point for a stretch break.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '50–72'), labelCell(3400, 'Slides 24–46', { bold: false }), labelCell(4660, 'The case. Read each paragraph aloud, class calls the stage, reveal, move on.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '72–78'), labelCell(3400, 'Slide 46 + Poll', { bold: false }), labelCell(4660, 'Should he have taken the plea? Show the split and argue it. This is the discussion the lesson was building to.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '78–87'), labelCell(3400, 'Slide 47 + Time to Climb', { bold: false }), labelCell(4660, 'Ten questions, whole class, competitive. This is your assessment - no worksheet needed.', { bold: false })] }),
    new TableRow({ children: [labelCell(1300, '87–90'), labelCell(3400, 'Slides 48\u201349 + Open-Ended', { bold: false }), labelCell(4660, 'Exit ticket, share two answers, then the hook for next lesson.', { bold: false })] }),
  ]),

  RULE(),
  H2('Standards'),
  P('Criminal Justice Operations 1 (8918010): 01.01 parts and functions of the system and the three branches at federal, state, county and local levels · 01.02 history and goals · 01.03 career opportunities (the Collaborate Board) · 03.06 criminal law procedures in Florida · 03.07 misdemeanor and felony procedures · 04.03 pretrial, trial and post-trial processes · 04.04 roles and responsibilities of people in the trial process · 06.02 local, state and federal correctional systems.', { size: 21 }),
  P('Florida specifics verified September 2026, including the revision to speedy trial Rule 3.191 effective July 1, 2025.', { italics: true, color: C.GREY, size: 20 }),
];

Packer.toBuffer(docShell('How a Case Moves - Nearpod Build Sheet', children)).then((b) => {
  fs.writeFileSync('How a Case Moves - NEARPOD BUILD SHEET.docx', b);
  console.log('build sheet:', (b.length / 1024).toFixed(1), 'KB');
});
