const {
  Document, Packer, Paragraph, TextRun, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, HeightRule,
} = require('docx');
const fs = require('fs');
const C = require('./content.js');

const INK = '1B1B1B', HEAD = '10243A', BLUE = '1A5FB4', PROMPT = '5F6B79';
const LINE = 'B9C4D0', TINT = 'F2F5F8', FULL = 9360, FONT = 'Arial';

const rich = (s, size = 19) => {
  const out = []; const re = /<(strong|em)>(.*?)<\/\1>/g; let last = 0, m;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(new TextRun({ text: s.slice(last, m.index), size, color: PROMPT }));
    out.push(new TextRun({ text: m[2], size, color: m[1] === 'strong' ? INK : PROMPT, bold: m[1] === 'strong', italics: m[1] === 'em' }));
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(new TextRun({ text: s.slice(last), size, color: PROMPT }));
  return out;
};
const P = (t, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, line: o.line ?? 276 },
  children: [new TextRun({ text: t, size: o.size ?? 21, color: o.color ?? INK, bold: o.bold, italics: o.italics })],
});
const borders = (color = LINE, size = 4) => ({
  top: { style: BorderStyle.SINGLE, size, color }, bottom: { style: BorderStyle.SINGLE, size, color },
  left: { style: BorderStyle.SINGLE, size, color }, right: { style: BorderStyle.SINGLE, size, color },
  insideHorizontal: { style: BorderStyle.SINGLE, size, color }, insideVertical: { style: BorderStyle.SINGLE, size, color },
});
const cell = (children, { w, fill, span, margins } = {}) => new TableCell({
  width: { size: w, type: WidthType.DXA }, columnSpan: span,
  shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
  margins: margins || { top: 110, bottom: 110, left: 150, right: 150 },
  children,
});
const kicker = (t, color = PROMPT) => new Paragraph({
  spacing: { after: 40 }, children: [new TextRun({ text: t, size: 17, bold: true, color, characterSpacing: 30 })],
});
const bigTitle = (t) => new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: t, size: 40, bold: true, color: HEAD })] });
const sub = (t) => new Paragraph({ spacing: { after: 200 }, children: [new TextRun({ text: t, size: 22, color: PROMPT })] });
const calloutBox = (label, children, color = BLUE) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(color, 8),
  rows: [new TableRow({ children: [cell([
    new Paragraph({ spacing: { after: 70 }, children: [new TextRun({ text: label, size: 17, bold: true, color, characterSpacing: 20 })] }),
    ...children,
  ], { w: FULL, margins: { top: 160, bottom: 160, left: 200, right: 200 } })] })],
});
const sectionHead = (t) => new Paragraph({
  spacing: { before: 120, after: 90 }, children: [new TextRun({ text: t, size: 18, bold: true, color: HEAD, characterSpacing: 20 })],
});
const makeDoc = (title, children) => new Document({
  creator: 'Criminal Justice Operations', title,
  styles: { default: { document: { run: { font: FONT, size: 21, color: INK } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: 1080, right: 1080 } } }, children }],
});
const save = (name, doc) => Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(name, b); console.log(' ', name, (b.length / 1024).toFixed(1) + ' KB');
});

/* ------------------------------------------------------ 1. the case file */
const caseKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle('Case File'),
  sub(C.subtitle),
  calloutBox('WHAT THIS IS', [
    P('Everything known about this incident is on this page: the dispatch entry and one witness statement. There is nothing else.', { size: 21, after: 90, line: 290 }),
    P('Keep this open beside your report form, or read it from the board. Do not add anything that is not here.', { size: 21, after: 0, line: 290 }),
  ]),
  P('', { after: 180 }),
  sectionHead('DISPATCH ENTRY'),
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [2700, 6660], borders: borders(),
    rows: C.dispatch.map(([k, v]) => new TableRow({
      children: [
        cell([new Paragraph({ children: [new TextRun({ text: k, size: 18, bold: true, color: PROMPT })] })], { w: 2700, fill: TINT, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
        cell([new Paragraph({ children: [new TextRun({ text: v, size: 22, color: INK })] })], { w: 6660, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
      ],
    })),
  }),
  P('', { after: 220 }),
  sectionHead(C.witnessHeading.toUpperCase()),
  P(C.witnessNote, { size: 18, italics: true, color: PROMPT, after: 100 }),
  new Table({
    width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(),
    rows: [new TableRow({ children: [cell(
      C.witness.map((para, i) => new Paragraph({
        spacing: { after: i === C.witness.length - 1 ? 0 : 150, line: 310 },
        children: [new TextRun({ text: `“${para}”`, size: 23, color: INK })],
      })),
      { w: FULL, fill: TINT, margins: { top: 190, bottom: 190, left: 230, right: 230 } },
    )] })],
  }),
];

/* --------------------------------------------------- 2. the report form */
const fieldHeight = (f) => (f.rows || 1) * 300 + 820;
const field = (f, width) => cell([
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: f.label.toUpperCase(), size: 17, bold: true, color: HEAD, characterSpacing: 10 })] }),
  new Paragraph({ spacing: { after: 90, line: 250 }, children: rich(f.prompt, 17) }),
  new Paragraph({ spacing: { after: 0, line: 300 }, children: [new TextRun({ text: '', size: 21 })] }),
], { w: width });

function blockTable(block) {
  const rows = [new TableRow({
    children: [cell([new Paragraph({ children: [
      new TextRun({ text: `BLOCK ${block.n}   `, size: 18, bold: true, color: 'FFFFFF' }),
      new TextRun({ text: block.name.toUpperCase(), size: 18, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
    ] })], { w: FULL, span: 2, fill: HEAD, margins: { top: 95, bottom: 95, left: 150, right: 150 } })],
  })];
  const q = [...block.fields];
  while (q.length) {
    const f = q.shift();
    if (f.w === 'half' && q[0] && q[0].w === 'half') {
      const g = q.shift();
      rows.push(new TableRow({ height: { value: Math.max(fieldHeight(f), fieldHeight(g)), rule: HeightRule.ATLEAST }, children: [field(f, FULL / 2), field(g, FULL / 2)] }));
    } else {
      rows.push(new TableRow({ height: { value: fieldHeight(f), rule: HeightRule.ATLEAST }, children: [field(f, FULL)] }));
    }
  }
  return new Table({ width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL / 2, FULL / 2], borders: borders(), rows });
}

const formKids = [
  kicker('CRIMINAL JUSTICE OPERATIONS'),
  bigTitle('Incident Report'),
  sub(C.subtitle),
  calloutBox('BEFORE YOU START', [
    P('Work from the Case File. Fill in every field you can support from it, and leave the rest blank — you will account for every blank on the last page.', { size: 21, after: 90, line: 290 }),
    P('Do not invent anything. A report is only worth what it can support.', { size: 21, after: 0, line: 290, bold: true }),
  ]),
  P('', { after: 200 }),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: 'Name: ______________________________          Date: ____________', size: 21, color: INK })] }),
];

C.blocks.forEach((b) => {
  if (b.n === 4) {
    formKids.push(calloutBox('SIX RULES FOR THE NARRATIVE', C.narrativeRules.map((r, i) => new Paragraph({
      spacing: { after: 75, line: 285 }, indent: { left: 340, hanging: 340 },
      children: [new TextRun({ text: `${i + 1}.  `, size: 19, bold: true, color: BLUE }), ...rich(r, 19)],
    }))));
    formKids.push(P('', { after: 150 }));
  }
  formKids.push(blockTable(b));
  formKids.push(P('', { after: 170 }));
});

formKids.push(new Paragraph({ children: [new PageBreak()] }));
formKids.push(new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: C.gapsHeading, size: 30, bold: true, color: HEAD })] }));
formKids.push(P(C.gapsPrompt, { size: 21, color: PROMPT, after: 190, line: 290 }));
const gw = [3700, 2700, 2960];
formKids.push(new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: gw, borders: borders(),
  rows: [
    new TableRow({ tableHeader: true, children: C.gapCols.map((t, i) => cell(
      [new Paragraph({ children: [new TextRun({ text: t.toUpperCase(), size: 17, bold: true, color: 'FFFFFF', characterSpacing: 10 })] })],
      { w: gw[i], fill: HEAD, margins: { top: 100, bottom: 100, left: 150, right: 150 } }))}),
    ...Array.from({ length: C.gapRows }, () => new TableRow({
      height: { value: 640, rule: HeightRule.ATLEAST },
      children: gw.map((w) => cell([new Paragraph({ spacing: { line: 300 }, children: [new TextRun({ text: '', size: 21 })] })], { w })),
    })),
  ],
}));

Promise.all([
  save('1 - Case File - Lincoln Community Center.docx', makeDoc('Case File', caseKids)),
  save('2 - Incident Report Form - Lincoln Community Center.docx', makeDoc('Incident Report', formKids)),
]).then(() => console.log('done'));
