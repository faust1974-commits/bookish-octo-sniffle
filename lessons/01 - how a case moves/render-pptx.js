const pptxgen = require('pptxgenjs');
const { S, FONT } = require('./spec.js');

const p = new pptxgen();
p.layout = 'LAYOUT_WIDE';

S.forEach(({ els, notes }) => {
  const s = p.addSlide();
  s.background = { color: 'FFFFFF' };
  els.forEach((e) => {
    if (e.type === 'rect' || e.type === 'roundRect') {
      s.addShape(e.type === 'roundRect' ? p.ShapeType.roundRect : p.ShapeType.rect, {
        x: e.x, y: e.y, w: e.w, h: e.h, fill: { color: e.fill },
        ...(e.type === 'roundRect' ? { rectRadius: 0.08 } : {}),
      });
    } else if (e.type === 'ellipse') {
      s.addShape(p.ShapeType.ellipse, { x: e.x, y: e.y, w: e.w, h: e.h, fill: { color: e.fill } });
    } else {
      s.addText(e.text, {
        x: e.x, y: e.y, w: e.w, h: e.h, isTextBox: true, margin: 0,
        fontFace: FONT, fontSize: e.size, bold: !!e.bold, color: e.color,
        align: e.align || 'left', valign: e.valign || 'top',
        ...(e.line ? { lineSpacing: e.line } : {}),
        ...(e.spacing ? { charSpacing: e.spacing } : {}),
      });
    }
  });
  s.addNotes(notes);
});

p.writeFile({ fileName: 'How a Case Moves - NEARPOD SLIDES.pptx' }).then((f) => console.log('wrote', f));
