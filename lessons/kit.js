/* Shared document furniture for every file in this unit.
   Lifted verbatim from build.js so Day 1 and Day 2 are visually identical:
   same Arial, same navy heads, same tinted statement boxes, same borders. */
const {
  Document, Packer, Paragraph, TextRun, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, HeightRule,
  AlignmentType,
} = require('docx');
const fs = require('fs');

const INK = '1B1B1B', HEAD = '10243A', BLUE = '1A5FB4', PROMPT = '5F6B79';
const WARN = '9A3412', LINE = 'B9C4D0', TINT = 'F2F5F8', WARNTINT = 'FDF3EC';
const FULL = 9360, FONT = 'Arial';

/* <strong>/<em> inline markup so prompts can emphasise without a second field. */
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
const sectionHead = (t) => new Paragraph({
  spacing: { before: 120, after: 90 }, children: [new TextRun({ text: t, size: 18, bold: true, color: HEAD, characterSpacing: 20 })],
});

const calloutBox = (label, children, color = BLUE, fill) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(color, 8),
  rows: [new TableRow({ children: [cell([
    new Paragraph({ spacing: { after: 70 }, children: [new TextRun({ text: label, size: 17, bold: true, color, characterSpacing: 20 })] }),
    ...children,
  ], { w: FULL, fill, margins: { top: 160, bottom: 160, left: 200, right: 200 } })] })],
});

/* A quoted statement: tinted panel, larger type, generous leading — made to be
   read off a Promethean board from the back of the room. */
const statementPanel = (paras, fill = TINT) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: [FULL], borders: borders(),
  rows: [new TableRow({ children: [cell(
    paras.map((para, i) => new Paragraph({
      spacing: { after: i === paras.length - 1 ? 0 : 150, line: 310 },
      children: [new TextRun({ text: `“${para}”`, size: 23, color: INK })],
    })),
    { w: FULL, fill, margins: { top: 190, bottom: 190, left: 230, right: 230 } },
  )] })],
});

const labelValueTable = (rows, lw = 2700) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: [lw, FULL - lw], borders: borders(),
  rows: rows.map(([k, v]) => new TableRow({
    children: [
      cell([new Paragraph({ children: [new TextRun({ text: k, size: 18, bold: true, color: PROMPT })] })], { w: lw, fill: TINT, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
      cell([new Paragraph({ children: [new TextRun({ text: v, size: 22, color: INK })] })], { w: FULL - lw, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
    ],
  })),
});

/* A field the student types into. Height is ATLEAST so the cell grows as they
   type instead of clipping — this is what makes the .docx usable on a
   Chromebook in Word for the web. */
const fieldHeight = (f) => (f.rows || 1) * 300 + 820;
const field = (f, width) => cell([
  /* The header bar already carries the name when a one-field block is named
     after its field, so printing the label again just stutters. */
  ...(f.hideLabel ? [] : [new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: f.label.toUpperCase(), size: 17, bold: true, color: HEAD, characterSpacing: 10 })] })]),
  ...(f.prompt ? [new Paragraph({ spacing: { after: f.hideLabel ? 110 : 90, line: 250 }, children: rich(f.prompt, 17) })] : []),
  new Paragraph({ spacing: { after: 0, line: 300 }, children: [new TextRun({ text: '', size: 21 })] }),
], { w: width });

function blockTable(block) {
  const rows = [new TableRow({
    children: [cell([new Paragraph({ children: [
      ...(block.n ? [new TextRun({ text: `BLOCK ${block.n}   `, size: 18, bold: true, color: 'FFFFFF' })] : []),
      new TextRun({ text: block.name.toUpperCase(), size: 18, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
    ] })], { w: FULL, span: 2, fill: HEAD, margins: { top: 95, bottom: 95, left: 150, right: 150 } })],
  })];
  const norm = (t) => String(t || '').trim().toLowerCase();
  const q = block.fields.map((f) => (
    block.fields.length === 1 && norm(f.label) === norm(block.name) ? { ...f, hideLabel: true } : f
  ));
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

/* A write-in grid: header row plus N empty typeable rows. */
const gridTable = (cols, widths, nRows, rowHeight = 640) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: widths, borders: borders(),
  rows: [
    new TableRow({ tableHeader: true, children: cols.map((t, i) => cell(
      [new Paragraph({ children: [new TextRun({ text: t.toUpperCase(), size: 17, bold: true, color: 'FFFFFF', characterSpacing: 10 })] })],
      { w: widths[i], fill: HEAD, margins: { top: 100, bottom: 100, left: 150, right: 150 } })) }),
    ...Array.from({ length: nRows }, () => new TableRow({
      height: { value: rowHeight, rule: HeightRule.ATLEAST },
      children: widths.map((w) => cell([new Paragraph({ spacing: { line: 300 }, children: [new TextRun({ text: '', size: 21 })] })], { w })),
    })),
  ],
});

/* A table of real data: header row plus supplied rows. gridTable's sibling,
   for evidence documents rather than write-in sheets. */
const dataTable = (cols, widths, rows, opts = {}) => new Table({
  width: { size: FULL, type: WidthType.DXA }, columnWidths: widths, borders: borders(),
  rows: [
    new TableRow({ tableHeader: true, children: cols.map((t, i) => cell(
      [new Paragraph({ children: [new TextRun({ text: String(t).toUpperCase(), size: 17, bold: true, color: 'FFFFFF', characterSpacing: 10 })] })],
      { w: widths[i], fill: HEAD, margins: { top: 100, bottom: 100, left: 150, right: 150 } })) }),
    ...rows.map((r) => new TableRow({
      children: r.map((v, i) => cell(
        [new Paragraph({ spacing: { line: 285 }, children: [new TextRun({
          text: String(v), size: opts.size || 20, color: INK,
          bold: opts.boldFirstCol && i === 0,
        })] })],
        { w: widths[i], fill: opts.boldFirstCol && i === 0 ? TINT : undefined,
          margins: { top: 110, bottom: 110, left: 150, right: 150 } },
      )),
    })),
  ],
});

const numberedList = (items, color = BLUE) => items.map((r, i) => new Paragraph({
  spacing: { after: 75, line: 285 }, indent: { left: 340, hanging: 340 },
  children: [new TextRun({ text: `${i + 1}.  `, size: 19, bold: true, color }), ...rich(r, 19)],
}));

/* ------------------------------------------------------------ Canvas setup */
/* One block per Canvas assignment: the settings on the left, then the
   description text the teacher pastes straight into Canvas. The pasted text is
   student-facing, so it is set in normal weight and quoted visually rather
   than styled like teacher instructions. */
const canvasBlock = (a, i) => {
  const accent = a.hidden ? WARN : HEAD;
  const rows = [
    new TableRow({ children: [cell([new Paragraph({ children: [
      new TextRun({ text: `ASSIGNMENT ${a.label || i + 1}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 30 }),
      new TextRun({ text: `    ${a.title.toUpperCase()}`, size: 17, bold: true, color: 'FFFFFF', characterSpacing: 20 }),
    ] })], { w: FULL, span: 2, fill: accent, margins: { top: 110, bottom: 110, left: 170, right: 170 } })] }),
  ];
  const setting = (k, v, bold) => new TableRow({
    children: [
      cell([new Paragraph({ children: [new TextRun({ text: k, size: 16, bold: true, color: PROMPT })] })],
        { w: 2200, fill: TINT, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
      cell([new Paragraph({ spacing: { line: 280 }, children: [new TextRun({ text: v, size: 19, color: bold ? accent : INK, bold })] })],
        { w: FULL - 2200, margins: { top: 90, bottom: 90, left: 150, right: 150 } }),
    ],
  });
  rows.push(setting('ATTACH', a.files.join('   \u00b7   ')));
  rows.push(setting('POINTS', a.points));
  rows.push(setting('SUBMISSION', a.submission));
  rows.push(setting('PUBLISH', a.publish, true));
  rows.push(new TableRow({ children: [cell([
    new Paragraph({ spacing: { after: 90 }, children: [new TextRun({ text: 'PASTE THIS AS THE DESCRIPTION', size: 16, bold: true, color: accent, characterSpacing: 20 })] }),
    ...a.description.map((t, j) => new Paragraph({
      spacing: { after: j === a.description.length - 1 ? 0 : 110, line: 300 },
      children: [new TextRun({ text: t, size: 20, color: INK })],
    })),
  ], { w: FULL, span: 2, margins: { top: 150, bottom: 150, left: 190, right: 190 } })] }));
  return [
    new Table({ width: { size: FULL, type: WidthType.DXA }, columnWidths: [2200, FULL - 2200], borders: borders(accent, 8), rows }),
    P('', { after: 220 }),
  ];
};

const canvasSection = (C) => {
  const out = [
    new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'Canvas Setup', size: 38, bold: true, color: HEAD })] }),
    P(C.blurb, { size: 21, color: PROMPT, after: 150, line: 290 }),
    calloutBox('HOW TO USE THIS PAGE', [
      P('Build each assignment exactly as the box says, then copy the description text underneath straight into the Canvas description field. Nothing else on this page goes to students.', { size: 20, after: 70, line: 285 }),
      P('An assignment in orange starts hidden. Do not publish it until the minute given \u2014 the lesson depends on it.', { size: 20, after: 0, line: 285 }),
    ]),
    P('', { after: 230 }),
  ];
  C.assignments.forEach((a, i) => out.push(...canvasBlock(a, i)));
  if (C.notes && C.notes.length) {
    out.push(calloutBox('ALSO', C.notes.map((t) => new Paragraph({
      spacing: { after: 70, line: 285 }, indent: { left: 300, hanging: 300 },
      children: [new TextRun({ text: '\u2014   ', size: 19, bold: true, color: BLUE }), ...rich(t, 19)],
    }))));
  }
  return out;
};

const makeDoc = (title, children) => new Document({
  creator: 'Criminal Justice Operations', title,
  styles: { default: { document: { run: { font: FONT, size: 21, color: INK } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1000, bottom: 1000, left: 1080, right: 1080 } } }, children }],
});

const save = (name, doc) => Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(name, b); console.log(' ', name, (b.length / 1024).toFixed(1) + ' KB');
});

const nameDateLine = () => new Paragraph({
  spacing: { after: 160 },
  children: [new TextRun({ text: 'Name: ______________________________          Date: ____________', size: 21, color: INK })],
});

module.exports = {
  Paragraph, TextRun, PageBreak, Table, TableRow, WidthType, HeightRule, AlignmentType,
  INK, HEAD, BLUE, PROMPT, WARN, LINE, TINT, WARNTINT, FULL, FONT,
  rich, P, borders, cell, kicker, bigTitle, sub, sectionHead, calloutBox,
  statementPanel, labelValueTable, field, fieldHeight, blockTable, gridTable, dataTable,
  numberedList, canvasBlock, canvasSection, makeDoc, save, nameDateLine,
};
