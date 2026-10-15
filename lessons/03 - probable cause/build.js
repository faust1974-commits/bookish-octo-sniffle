/* Run: NODE_PATH=<dir containing docx> node build.js */
const K = require('../kit.js');
const PW = require('./content-pawn.js');
const A = require('./content-affidavit.js');
const T = require('./content-teacher.js');
const {
  Paragraph, TextRun, PageBreak, Table, TableRow, WidthType, HeightRule, AlignmentType,
  INK, HEAD, BLUE, PROMPT, WARN, TINT, WARNTINT, FULL,
  rich, P, borders, cell, kicker, bigTitle, sub, sectionHead, calloutBox,
  labelValueTable, blockTable, gridTable, dataTable, numberedList,
  makeDoc, save, nameDateLine,
} = K;

const partHead = (label, heading) => [
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(HEAD, 8),
    rows: [new TableRow({ children: [cell([new Paragraph({ children: [
      new TextRun({ text: `${label}    `, size: 18, bold: true, color: 'FFFFFF', characterSpacing: 30 }),
      new TextRun({ text: heading.toUpperCase(), size: 18, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
    ] })], { w: FULL, fill: HEAD, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] })],
  }),
  P('', { after: 130 }),
];

const checkRow = (t) => new TableRow({
  height: { value: 560, rule: HeightRule.ATLEAST },
  children: [
    cell([new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: '', size: 26 })] })],
      { w: 620, margins: { top: 120, bottom: 120, left: 80, right: 80 } }),
    cell([new Paragraph({ spacing: { line: 285 }, children: [new TextRun({ text: t, size: 20, color: INK })] })],
      { w: FULL - 620, margins: { top: 120, bottom: 120, left: 150, right: 150 } }),
  ],
});

/* ------------------------------------------------- 1. the pawn record */
const pawnKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(PW.title),
  sub(PW.subtitle),
  calloutBox('HOW THIS REACHED YOU', PW.howItCame.map((t, i) => P(t, { size: 21, after: i === PW.howItCame.length - 1 ? 0 : 90, line: 290 }))),
  P('', { after: 190 }),
  sectionHead('TRANSACTION'),
  labelValueTable(PW.transaction, 2900),
  P('', { after: 210 }),
  sectionHead('PERSON PRESENTING THE PROPERTY'),
  labelValueTable(PW.seller, 2900),
  P('', { after: 210 }),
  sectionHead('ITEMS RECEIVED'),
  dataTable(PW.itemCols, PW.itemWidths, [...PW.items, PW.itemTotal], { boldFirstCol: false }),
  P('', { after: 210 }),
  calloutBox(PW.noteHeading.toUpperCase(), [P(PW.note, { size: 21, after: 0, line: 295 })]),
  P('', { after: 210 }),
  calloutBox(PW.footerHeading.toUpperCase(), [
    ...PW.footer.map((t) => new Paragraph({
      spacing: { after: 60, line: 285 }, indent: { left: 300, hanging: 300 },
      children: [new TextRun({ text: '■   ', size: 16, color: WARN }), new TextRun({ text: t, size: 20, color: INK })],
    })),
    P(PW.footerNote, { size: 20, bold: true, color: WARN, after: 0, line: 285 }),
  ], WARN, WARNTINT),
];

/* ------------------------------------------- 2. the probable cause worksheet */
const w = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle(A.title),
  sub(A.subtitle),
  calloutBox('WHAT MAKES THIS DIFFERENT', [P(A.brief, { size: 21, after: 0, line: 290 })]),
  P('', { after: 200 }),
  nameDateLine(),

  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: A.ladderHeading, size: 28, bold: true, color: HEAD })] }),
  P(A.ladderPrompt, { size: 20, color: PROMPT, after: 150, line: 285 }),
  dataTable(A.ladderCols, A.ladderWidths, A.ladder, { boldFirstCol: true, size: 19 }),
  P('', { after: 110 }),
  new Paragraph({ spacing: { after: 0, line: 285 }, children: rich(A.ladderNote, 20) }),
  P('', { after: 240 }),
];

/* A */
w.push(...partHead(A.partA.label, A.partA.heading));
w.push(P(A.partA.prompt, { size: 21, color: PROMPT, after: 140, line: 290 }));
w.push(P(A.partA.checkIntro, { size: 19, italics: true, color: PROMPT, after: 110 }));
w.push(new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: [620, FULL - 620], borders: borders(),
  rows: A.partA.check.map(checkRow),
}));
w.push(P('', { after: 160 }));
w.push(blockTable({ name: A.partA.fixLabel, fields: [{ id: 'fix', label: A.partA.fixLabel, prompt: A.partA.fixPrompt, w: 'full', rows: 3 }] }));
w.push(P('', { after: 140 }));
w.push(blockTable({ name: A.partA.whereLabel, fields: [{ id: 'where', label: A.partA.whereLabel, prompt: A.partA.wherePrompt, w: 'full', rows: 3 }] }));

/* B */
w.push(new Paragraph({ children: [new PageBreak()] }));
w.push(...partHead(A.partB.label, A.partB.heading));
w.push(P(A.partB.prompt, { size: 21, color: PROMPT, after: 140, line: 290 }));
w.push(calloutBox('HOW TO FIND IT', numberedList(A.partB.howTo)));
w.push(P('', { after: 180 }));
w.push(blockTable({ name: 'What you found', fields: A.partB.fields }));

/* C */
w.push(P('', { after: 240 }));
w.push(...partHead(A.partC.label, A.partC.heading));
w.push(P(A.partC.prompt, { size: 21, color: PROMPT, after: 130, line: 290 }));
w.push(new Paragraph({ spacing: { after: 160, line: 285 }, children: rich(A.partC.note, 20) }));
w.push(gridTable(A.partC.cols, A.partC.widths, A.partC.rows, 820));

/* D */
w.push(new Paragraph({ children: [new PageBreak()] }));
w.push(...partHead(A.partD.label, A.partD.heading));
w.push(P(A.partD.prompt, { size: 21, color: PROMPT, after: 160, line: 290 }));
A.partD.blocks.forEach((b) => { w.push(blockTable(b)); w.push(P('', { after: 160 })); });
w.push(calloutBox(A.partD.oathHeading.toUpperCase(), [
  P(A.partD.oathText, { size: 21, after: 150, line: 295 }),
  ...A.partD.oathFields.split('\n').map((line) => P(line, { size: 20, after: line ? 80 : 40, line: 330 })),
], WARN, WARNTINT));

/* E */
w.push(new Paragraph({ children: [new PageBreak()] }));
w.push(...partHead(A.partE.label, A.partE.heading));
w.push(P(A.partE.prompt, { size: 21, color: PROMPT, after: 170, line: 290 }));
w.push(gridTable(A.partE.cols, A.partE.widths, A.partE.rows, 760));
w.push(P('', { after: 200 }));
w.push(blockTable({ name: A.partE.bigQuestionLabel, fields: [{ id: 'burg', label: A.partE.bigQuestionLabel, prompt: A.partE.bigQuestionPrompt, w: 'full', rows: 6 }] }));

/* --------------------------------------------------- 0. teacher run sheet */
const DIRECTION = /^\[.*\]$/;
const scriptLine = (t) => (DIRECTION.test(t.trim())
  ? new Paragraph({ spacing: { before: 60, after: 110, line: 280 }, indent: { left: 300 },
      children: [new TextRun({ text: t.trim().slice(1, -1), size: 19, italics: true, color: PROMPT })] })
  : new Paragraph({ spacing: { after: 130, line: 320 },
      children: [new TextRun({ text: t, size: 23, color: INK })] }));

const partBlock = (p) => {
  const accent = p.sendoff ? WARN : HEAD;
  return [
    new Table({
      width: { size: FULL, type: WidthType.DXA }, columnWidths: [7100, 2260], borders: borders(accent, 8),
      rows: [new TableRow({ children: [
        cell([new Paragraph({ children: [
          new TextRun({ text: `PART ${p.n}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 30 }),
          new TextRun({ text: `    ${p.name.toUpperCase()}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
        ] })], { w: 7100, fill: accent, margins: { top: 100, bottom: 100, left: 170, right: 150 } }),
        cell([new Paragraph({ alignment: AlignmentType.RIGHT, children: [
          new TextRun({ text: `MIN ${p.min}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
        ] })], { w: 2260, fill: accent, margins: { top: 100, bottom: 100, left: 150, right: 170 } }),
      ] })],
    }),
    new Table({
      width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(accent, 8),
      rows: [
        new TableRow({ children: [cell([new Paragraph({ spacing: { after: 0, line: 275 }, children: [
          new TextRun({ text: 'CUE   ', size: 15, bold: true, color: accent, characterSpacing: 20 }),
          new TextRun({ text: p.cue, size: 19, italics: true, color: PROMPT }),
        ] })], { w: FULL, fill: p.sendoff ? WARNTINT : TINT, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] }),
        new TableRow({ children: [cell(p.lines.map(scriptLine), { w: FULL, margins: { top: 170, bottom: 150, left: 200, right: 200 } })] }),
      ],
    }),
    P('', { after: 230 }),
  ];
};

const t = [
  kicker('CRIMINAL JUSTICE OPERATIONS · TEACHER COPY', WARN),
  bigTitle(T.title),
  sub(T.subtitle),
  calloutBox('THE ONE IDEA', [P(T.bigIdea, { size: 21, after: 0, line: 290 })]),
  P('', { after: 180 }),
  sectionHead('STANDARDS COVERED'),
  labelValueTable(T.standards, 1500),
  P('', { after: 200 }),
  calloutBox('BEFORE CLASS', numberedList(T.prep, WARN), WARN, WARNTINT),
  P('', { after: 200 }),
  calloutBox('GRADING — YOU HAVE 150 STUDENTS', T.grading.map((x) => new Paragraph({
    spacing: { after: 70, line: 285 }, indent: { left: 300, hanging: 300 },
    children: [new TextRun({ text: '—   ', size: 19, bold: true, color: BLUE }), ...rich(x, 19)],
  }))),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'Your Parts', size: 38, bold: true, color: HEAD })] }),
  P('Large black text is yours to say out loud. Small grey italic in brackets is a direction — do not read it out. The three orange parts are the send-offs.', { size: 21, color: PROMPT, after: 230, line: 290 }),
];
T.script.forEach((p) => t.push(...partBlock(p)));

t.push(new Paragraph({ children: [new PageBreak()] }));
t.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: T.spotsHeading, size: 32, bold: true, color: HEAD })] }));
t.push(P('These three come up in nearly every room. Have the words ready.', { size: 21, color: PROMPT, after: 200, line: 290 }));
T.spots.forEach((sp) => {
  t.push(new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(BLUE, 8),
    rows: [
      new TableRow({ children: [cell([new Paragraph({ spacing: { after: 0, line: 280 }, children: [
        new TextRun({ text: 'WHEN   ', size: 15, bold: true, color: BLUE, characterSpacing: 20 }),
        new TextRun({ text: sp.when, size: 20, bold: true, color: INK }),
      ] })], { w: FULL, fill: TINT, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] }),
      new TableRow({ children: [cell(sp.lines.map(scriptLine), { w: FULL, margins: { top: 170, bottom: 150, left: 200, right: 200 } })] }),
    ],
  }));
  t.push(P('', { after: 230 }));
});

t.push(new Paragraph({ children: [new PageBreak()] }));
t.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: T.answerKeyHeading, size: 30, bold: true, color: HEAD })] }));
t.push(P('Do not give this page to students.', { size: 20, bold: true, color: WARN, after: 170 }));
t.push(labelValueTable(T.answerKey, 1500));

Promise.all([
  save('0 - TEACHER - Run Sheet - Probable Cause.docx', makeDoc('Run Sheet', t)),
  save('1 - Pawn Transaction Record.docx', makeDoc('Pawn Transaction Record', pawnKids)),
  save('2 - Probable Cause Worksheet.docx', makeDoc('Probable Cause', w)),
]).then(() => console.log('done')).catch((e) => { console.error(e); process.exit(1); });
