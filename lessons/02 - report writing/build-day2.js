/* Emits the three Day 2 student files plus the teacher run sheet.
   Run:  NODE_PATH=<dir containing docx> node build-day2.js            */
const K = require('../kit.js');
const C = require('./content-day2.js');
const T = require('./content-teacher.js');
const SC = require('./content-script.js');
const F = require('./content-final.js');
const CV = require('./content-canvas.js');
const {
  Paragraph, TextRun, PageBreak, Table, TableRow, WidthType, HeightRule, AlignmentType,
  INK, HEAD, BLUE, PROMPT, WARN, TINT, WARNTINT, FULL,
  rich, P, borders, cell, kicker, bigTitle, sub, sectionHead, calloutBox,
  statementPanel, labelValueTable, blockTable, gridTable, numberedList, canvasSection,
  makeDoc, save, nameDateLine,
} = K;

/* ------------------------------------------- 3. interview preparation sheet */
const Pr = C.prep;
const prepKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(Pr.title),
  sub(C.subtitle),
  calloutBox('HAND THIS IN FIRST', [
    P(Pr.brief, { size: 21, after: 0, line: 290 }),
  ]),
  P('', { after: 200 }),
  nameDateLine(),

  calloutBox('FIVE RULES FOR ASKING', numberedList(Pr.rules)),
  P('', { after: 200 }),

  sectionHead(Pr.exampleHeading.toUpperCase()),
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(),
    rows: [
      new TableRow({ children: [cell([P(Pr.exampleGap, { size: 20, bold: true, after: 0 })], { w: FULL, fill: TINT })] }),
      new TableRow({ children: [cell([
        new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: 'WEAK', size: 16, bold: true, color: WARN, characterSpacing: 20 })] }),
        P(Pr.exampleBad, { size: 22, italics: true, after: 60 }),
        new Paragraph({ spacing: { after: 0, line: 270 }, children: rich(Pr.exampleBadWhy, 18) }),
      ], { w: FULL, fill: WARNTINT })] }),
      new TableRow({ children: [cell([
        new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: 'BETTER', size: 16, bold: true, color: BLUE, characterSpacing: 20 })] }),
        P(Pr.exampleGood, { size: 22, bold: true, after: 60 }),
        new Paragraph({ spacing: { after: 0, line: 270 }, children: rich(Pr.exampleGoodWhy, 18) }),
      ], { w: FULL })] }),
    ],
  }),
  P('', { after: 240 }),

  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: Pr.gridHeading, size: 30, bold: true, color: HEAD })] }),
  P(Pr.gridPrompt, { size: 21, color: PROMPT, after: 170, line: 290 }),
  gridTable(Pr.gridCols, [3500, 5860], Pr.gridRows, 700),
  P('', { after: 240 }),

  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: Pr.rayHeading, size: 26, bold: true, color: HEAD })] }),
  P(Pr.rayPrompt, { size: 21, color: PROMPT, after: 150, line: 290 }),
  gridTable(['#', 'The question I should have asked'], [700, 8660], Pr.rayRows, 700),
];

/* ------------------------------------------------- 4. the Vance statement */
const V = C.vance;
const vanceKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(V.title),
  sub(V.who),
  calloutBox('WHAT THIS IS', [
    P('The second witness. This is everything she told you — there is nothing else, and there is no third witness coming.', { size: 21, after: 90, line: 290 }),
    P('Read it against your question sheet. Some of what you asked is answered here. Some of it is not, and that is also information.', { size: 21, after: 0, line: 290 }),
  ]),
  P('', { after: 180 }),

  sectionHead('INTERVIEW DETAILS'),
  labelValueTable(V.admin),
  P('', { after: 220 }),

  sectionHead('STATEMENT'),
  P(V.note, { size: 18, italics: true, color: PROMPT, after: 100 }),
  statementPanel(V.statement),
  P('', { after: 220 }),

  calloutBox(V.couldNotAnswerHeading.toUpperCase(), [
    ...V.couldNotAnswer.map((t) => new Paragraph({
      spacing: { after: 60, line: 285 }, indent: { left: 300, hanging: 300 },
      children: [new TextRun({ text: '—   ', size: 19, bold: true, color: WARN }), new TextRun({ text: t, size: 20, color: INK })],
    })),
    P('An interview that leaves questions open is normal. Record them — do not fill them in yourself.', { size: 19, italics: true, color: PROMPT, after: 0, line: 280 }),
  ], WARN, WARNTINT),
];

/* --------------------------------------------- 5. the supplemental report */
const S = C.supp;
const suppKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(S.title),
  sub(C.subtitle),
  calloutBox('BEFORE YOU START', [
    P(S.brief, { size: 21, after: 0, line: 290 }),
  ]),
  P('', { after: 200 }),
  nameDateLine(),
];
S.blocks.forEach((b) => { suppKids.push(blockTable(b)); suppKids.push(P('', { after: 170 })); });

suppKids.push(new Paragraph({ children: [new PageBreak()] }));
suppKids.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: S.conflictHeading, size: 30, bold: true, color: HEAD })] }));
suppKids.push(new Paragraph({ spacing: { after: 180, line: 290 }, children: rich(S.conflictPrompt, 21) }));
suppKids.push(gridTable(S.conflictCols, [4680, 4680], 1, 1800));
suppKids.push(P('', { after: 150 }));
suppKids.push(blockTable({ name: S.conflictResolve, fields: [{ id: 'resolve', label: 'Write it as one sentence you would put in the report', prompt: 'Attribute both accounts. Do not decide which witness is right.', w: 'full', rows: 3 }] }));
suppKids.push(P('', { after: 240 }));

suppKids.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: S.leadsHeading, size: 26, bold: true, color: HEAD })] }));
suppKids.push(new Paragraph({ spacing: { after: 160, line: 290 }, children: rich(S.leadsPrompt, 21) }));
suppKids.push(gridTable(S.leadsCols, [3200, 3200, 2960], S.leadsRows, 680));
suppKids.push(P('', { after: 240 }));

suppKids.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: S.openHeading, size: 26, bold: true, color: HEAD })] }));
suppKids.push(P(S.openPrompt, { size: 21, color: PROMPT, after: 160, line: 290 }));
suppKids.push(gridTable(S.openCols, [5400, 3960], S.openRows, 660));

/* ----------------------------------------------- 6. the final narrative sheet */
/* An empty bordered square they can click and type an X into, then the item. */
const checkRow = (t) => new TableRow({
  height: { value: 560, rule: HeightRule.ATLEAST },
  children: [
    cell([new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '', size: 26 })] })],
      { w: 620, margins: { top: 120, bottom: 120, left: 80, right: 80 } }),
    cell([new Paragraph({ spacing: { line: 285 }, children: [new TextRun({ text: t, size: 20, color: INK })] })],
      { w: FULL - 620, margins: { top: 120, bottom: 120, left: 150, right: 150 } }),
  ],
});

const finalKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(F.title),
  sub(F.subtitle),
  calloutBox('THIS IS THE ONE THAT COUNTS', [P(F.brief, { size: 21, after: 0, line: 290 })]),
  P('', { after: 200 }),
  nameDateLine(),

  calloutBox('SIX RULES FOR THE NARRATIVE', numberedList(F.rules)),
  P('', { after: 200 }),

  sectionHead(F.openerHeading.toUpperCase()),
  P(F.openerNote, { size: 18, italics: true, color: PROMPT, after: 100 }),
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(BLUE, 8),
    rows: [new TableRow({ children: [cell([
      ...F.opener.map((t, i) => new Paragraph({
        spacing: { after: i === F.opener.length - 1 ? 110 : 140, line: 310 },
        children: [new TextRun({ text: t, size: 22, color: INK })],
      })),
      new Paragraph({ spacing: { after: 0, line: 280 }, children: [new TextRun({ text: F.openerAfter, size: 18, italics: true, color: PROMPT })] }),
    ], { w: FULL, fill: TINT, margins: { top: 180, bottom: 180, left: 220, right: 220 } })] })],
  }),
  P('', { after: 230 }),

  blockTable({ name: F.narrativeLabel, fields: [{ id: 'narrative', label: F.narrativeLabel, prompt: F.narrativePrompt, w: 'full', rows: F.narrativeRows }] }),

  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: F.conflictHeading, size: 30, bold: true, color: HEAD })] }),
  new Paragraph({ spacing: { after: 180, line: 290 }, children: rich(F.conflictPrompt, 21) }),
  gridTable(F.conflictCols, [4680, 4680], 1, 1800),
  P('', { after: 150 }),
  blockTable({ name: F.conflictResolveLabel, fields: [{ id: 'resolve', label: F.conflictResolveLabel, prompt: F.conflictResolvePrompt, w: 'full', rows: 3 }] }),
  P('', { after: 240 }),

  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: F.checkHeading, size: 26, bold: true, color: HEAD })] }),
  P(F.checkPrompt, { size: 21, color: PROMPT, after: 160, line: 290 }),
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [620, FULL - 620], borders: borders(),
    rows: F.check.map(checkRow),
  }),
  P('', { after: 240 }),

  blockTable({ name: F.lastHeading, fields: [{ id: 'last', label: F.lastHeading, prompt: F.lastPrompt, w: 'full', rows: 2 }] }),
];

/* ------------------------------------------------- 0. the teacher run sheet */
const timeRow = (s) => new TableRow({
  children: [
    cell([new Paragraph({ children: [new TextRun({ text: s.t, size: 20, bold: true, color: HEAD })] })],
      { w: 1100, fill: TINT, margins: { top: 120, bottom: 120, left: 120, right: 120 } }),
    cell([
      P(s.what, { size: 20, after: s.say ? 90 : 0, line: 285 }),
      ...(s.say ? [new Paragraph({
        spacing: { after: 0, line: 285 }, indent: { left: 260 },
        children: [
          new TextRun({ text: 'SAY   ', size: 15, bold: true, color: BLUE, characterSpacing: 20 }),
          new TextRun({ text: `“${s.say}”`, size: 20, color: BLUE, italics: true }),
        ],
      })] : []),
    ], { w: 8260, margins: { top: 120, bottom: 120, left: 150, right: 150 } }),
  ],
});

const teacherKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS · TEACHER COPY', WARN),
  bigTitle(T.title),
  sub(T.subtitle),
  ...canvasSection(CV),
  new Paragraph({ children: [new PageBreak()] }),
  calloutBox('THE ONE IDEA', [P(T.bigIdea, { size: 21, after: 0, line: 290 })]),
  P('', { after: 180 }),
  sectionHead('STANDARDS COVERED'),
  labelValueTable(T.standards, 2300),
  P('', { after: 200 }),
  calloutBox('BEFORE EACH CLASS', numberedList(T.prep, WARN), WARN, WARNTINT),
  P('', { after: 200 }),
  calloutBox('GRADING — YOU HAVE 150 STUDENTS', T.grading.map((t) => new Paragraph({
    spacing: { after: 70, line: 285 }, indent: { left: 300, hanging: 300 },
    children: [new TextRun({ text: '—   ', size: 19, bold: true, color: BLUE }), ...rich(t, 19)],
  }))),
];

/* ------------------------------------------------ the teacher speaking script */
const DIRECTION = /^\[.*\]$/;

/* One spoken line, or one stage direction. Spoken text is set large with open
   leading so it can be read off the page mid-sentence without losing your
   place; directions are small, grey and italic so the eye skips them. */
const scriptLine = (t) => (DIRECTION.test(t.trim())
  ? new Paragraph({
      spacing: { before: 60, after: 110, line: 280 }, indent: { left: 300 },
      children: [new TextRun({ text: t.trim().slice(1, -1), size: 19, italics: true, color: PROMPT })],
    })
  : new Paragraph({
      spacing: { after: 130, line: 320 },
      children: [new TextRun({ text: t, size: 23, color: INK })],
    }));

const partBlock = (p) => {
  const accent = p.sendoff ? WARN : HEAD;
  const head = new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [7100, 2260], borders: borders(accent, 8),
    rows: [new TableRow({
      children: [
        cell([new Paragraph({ children: [
          new TextRun({ text: `PART ${p.n}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 30 }),
          new TextRun({ text: `    ${p.name.toUpperCase()}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
        ] })], { w: 7100, fill: accent, margins: { top: 100, bottom: 100, left: 170, right: 150 } }),
        cell([new Paragraph({ alignment: AlignmentType.RIGHT, children: [
          new TextRun({ text: `MIN ${p.min}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
        ] })], { w: 2260, fill: accent, margins: { top: 100, bottom: 100, left: 150, right: 170 } }),
      ],
    })],
  });
  const body = new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(accent, 8),
    rows: [
      new TableRow({ children: [cell([new Paragraph({
        spacing: { after: 0, line: 275 },
        children: [
          new TextRun({ text: 'CUE   ', size: 15, bold: true, color: accent, characterSpacing: 20 }),
          new TextRun({ text: p.cue, size: 19, italics: true, color: PROMPT }),
        ],
      })], { w: FULL, fill: p.sendoff ? WARNTINT : TINT, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] }),
      new TableRow({ children: [cell(
        p.lines.map(scriptLine),
        { w: FULL, margins: { top: 170, bottom: 150, left: 200, right: 200 } },
      )] }),
    ],
  });
  return [head, body, P('', { after: 230 })];
};

teacherKids.push(new Paragraph({ children: [new PageBreak()] }));
teacherKids.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: SC.heading, size: 38, bold: true, color: HEAD })] }));
teacherKids.push(P(SC.blurb, { size: 21, color: PROMPT, after: 120, line: 290 }));
teacherKids.push(calloutBox('HOW TO READ THIS PAGE', [
  P('Large black text is yours to say out loud. Small grey italic text in brackets is a direction — do not read it out.', { size: 20, after: 70, line: 285 }),
  P('The three orange parts are the send-offs: the moment you turn them loose on an assignment. Those are the ones to get right.', { size: 20, after: 0, line: 285 }),
]));
teacherKids.push(P('', { after: 230 }));

let lastDay = null;
SC.parts.forEach((p) => {
  if (p.day !== lastDay) {
    if (lastDay !== null) teacherKids.push(new Paragraph({ children: [new PageBreak()] }));
    teacherKids.push(kicker(`${p.day} · YOUR PARTS`, BLUE));
    teacherKids.push(P('', { after: 110 }));
    lastDay = p.day;
  }
  teacherKids.push(...partBlock(p));
});

teacherKids.push(new Paragraph({ children: [new PageBreak()] }));
teacherKids.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: SC.spotsHeading, size: 32, bold: true, color: HEAD })] }));
teacherKids.push(P(SC.spotsBlurb, { size: 21, color: PROMPT, after: 200, line: 290 }));
SC.spots.forEach((sp) => {
  teacherKids.push(new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(BLUE, 8),
    rows: [
      new TableRow({ children: [cell([new Paragraph({ spacing: { after: 0, line: 280 }, children: [
        new TextRun({ text: 'WHEN   ', size: 15, bold: true, color: BLUE, characterSpacing: 20 }),
        new TextRun({ text: sp.when, size: 20, bold: true, color: INK }),
      ] })], { w: FULL, fill: TINT, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] }),
      new TableRow({ children: [cell(sp.lines.map(scriptLine), { w: FULL, margins: { top: 170, bottom: 150, left: 200, right: 200 } })] }),
    ],
  }));
  teacherKids.push(P('', { after: 230 }));
});

T.days.forEach((d) => {
  teacherKids.push(new Paragraph({ children: [new PageBreak()] }));
  teacherKids.push(kicker(d.label, BLUE));
  teacherKids.push(new Paragraph({ spacing: { after: 140 }, children: [new TextRun({ text: d.heading, size: 34, bold: true, color: HEAD })] }));
  teacherKids.push(calloutBox('WHAT THEY WALK OUT WITH', [P(d.goal, { size: 21, after: 0, line: 290 })]));
  teacherKids.push(P('', { after: 170 }));
  teacherKids.push(sectionHead('FILES IN PLAY'));
  teacherKids.push(...d.files.map((f) => new Paragraph({
    spacing: { after: 60, line: 280 }, indent: { left: 300, hanging: 300 },
    children: [new TextRun({ text: '■   ', size: 17, color: HEAD }), new TextRun({ text: f, size: 20, color: INK })],
  })));
  teacherKids.push(P('', { after: 200 }));
  teacherKids.push(sectionHead('RUN OF SHOW — 90 MINUTES'));
  teacherKids.push(new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [1100, 8260], borders: borders(),
    rows: d.steps.map(timeRow),
  }));
  teacherKids.push(P('', { after: 200 }));
  teacherKids.push(calloutBox('WATCH FOR THIS', d.watch.map((t) => new Paragraph({
    spacing: { after: 80, line: 285 }, indent: { left: 300, hanging: 300 },
    children: [new TextRun({ text: '!   ', size: 19, bold: true, color: WARN }), ...rich(t, 19)],
  })), WARN, WARNTINT));
});

teacherKids.push(new Paragraph({ children: [new PageBreak()] }));
teacherKids.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: T.answerKeyHeading, size: 30, bold: true, color: HEAD })] }));
teacherKids.push(P('Do not give this page to students.', { size: 20, bold: true, color: WARN, after: 170 }));
teacherKids.push(labelValueTable(T.answerKey, 1900));

Promise.all([
  save('0 - TEACHER - Run Sheet - Day 1 and Day 2.docx', makeDoc('Run Sheet', teacherKids)),
  save('3 - Interview Preparation.docx', makeDoc('Interview Preparation', prepKids)),
  save('4 - Witness Statement - Marisa Vance.docx', makeDoc('Witness Statement', vanceKids)),
  save('5 - Supplemental Report.docx', makeDoc('Supplemental Report', suppKids)),
  save('6 - Final Narrative and Self-Check.docx', makeDoc('Final Narrative', finalKids)),
]).then(() => console.log('done')).catch((e) => { console.error(e); process.exit(1); });
