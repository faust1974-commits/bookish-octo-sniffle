const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, LevelFormat,
} = require('docx');

const NAVY = '1F4E79';
const GREY = '5A6779';
const LIGHT = 'EEF1F5';
const BOXBORDER = 'C3CCD8';
const FULL = 9360;

const P = (t, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, line: 276 },
  indent: o.indent,
  alignment: o.align,
  children: [new TextRun({ text: t, size: o.size ?? 22, color: o.color, bold: o.bold, italics: o.italics })],
});
const RUNS = (runs, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, line: 276 },
  indent: o.indent,
  children: runs.map((r) => new TextRun({ size: 22, ...r })),
});
const BULLET = (t, level = 0) => new Paragraph({
  numbering: { reference: 'bullets', level },
  spacing: { after: 60, line: 276 },
  children: [new TextRun({ text: t, size: 22 })],
});
const NUM = (t) => new Paragraph({
  numbering: { reference: 'steps', level: 0 },
  spacing: { after: 80, line: 276 },
  children: [new TextRun({ text: t, size: 22 })],
});
const RULE = () => new Paragraph({
  spacing: { before: 120, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'D8DEE7' } },
  children: [],
});
const BOX = (title, lines) => new Table({
  width: { size: FULL, type: WidthType.DXA },
  columnWidths: [FULL],
  rows: [new TableRow({
    children: [new TableCell({
      width: { size: FULL, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: LIGHT },
      margins: { top: 160, bottom: 160, left: 200, right: 200 },
      children: [
        new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, size: 22, color: NAVY })] }),
        ...lines.map((l) => new Paragraph({ spacing: { after: 60, line: 276 }, children: [new TextRun({ text: l, size: 21 })] })),
      ],
    })],
  })],
});

// A cell students type into: visible box, generous height, grey prompt.
const answerCell = (width, prompt) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  margins: { top: 120, bottom: 120, left: 140, right: 140 },
  children: [
    new Paragraph({ spacing: { after: 0, line: 276 }, children: [new TextRun({ text: prompt || '', size: 20, color: 'A8B2BF', italics: true })] }),
    new Paragraph({ spacing: { after: 0, line: 276 }, children: [] }),
  ],
});
const labelCell = (width, text, { bold = true, fill } = {}) => new TableCell({
  width: { size: width, type: WidthType.DXA },
  shading: fill ? { type: ShadingType.CLEAR, fill } : undefined,
  margins: { top: 120, bottom: 120, left: 140, right: 140 },
  children: String(text).split('|').map((line) => new Paragraph({
    spacing: { after: 30, line: 276 },
    children: [new TextRun({ text: line, size: 21, bold })],
  })),
});
const headerCells = (cols, widths) => new TableRow({
  tableHeader: true,
  children: cols.map((t, i) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: NAVY },
    margins: { top: 100, bottom: 100, left: 140, right: 140 },
    children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, color: 'FFFFFF', size: 20 })] })],
  })),
});
const table = (widths, rows) => new Table({
  width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
  columnWidths: widths,
  borders: {
    top: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
    bottom: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
    left: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
    right: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
    insideVertical: { style: BorderStyle.SINGLE, size: 4, color: BOXBORDER },
  },
  rows,
});

const docShell = (title, children) => new Document({
  creator: 'Criminal Justice Operations',
  title,
  numbering: {
    config: [
      { reference: 'bullets', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 230 } } } },
      ] },
      { reference: 'steps', levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 280 } } } },
      ] },
    ],
  },
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22, color: '16202C' } },
      heading1: { run: { font: 'Calibri', size: 32, bold: true, color: NAVY }, paragraph: { spacing: { before: 360, after: 160 } } },
      heading2: { run: { font: 'Calibri', size: 26, bold: true, color: NAVY }, paragraph: { spacing: { before: 280, after: 120 } } },
      heading3: { run: { font: 'Calibri', size: 23, bold: true, color: '2A5F8F' }, paragraph: { spacing: { before: 200, after: 80 } } },
    },
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, bottom: 1080, left: 1080, right: 1080 } } },
    children,
  }],
});

module.exports = {
  NAVY, GREY, LIGHT, FULL, P, RUNS, BULLET, NUM, RULE, BOX,
  answerCell, labelCell, headerCells, table, docShell,
  Paragraph, TextRun, HeadingLevel, PageBreak, Packer,
};
