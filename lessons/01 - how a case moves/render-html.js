// Same spec, rendered as HTML at 96 px per inch, so the layout can be inspected.
// Liberation Sans is metric-compatible with Arial, so widths here match the deck.
const fs = require('fs');
const { S } = require('./spec.js');
const PX = 96, W = 13.333 * PX, H = 7.5 * PX;
const px = (i) => Math.round(i * PX * 100) / 100;

const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const slideHtml = ({ els }, i) => `
<section class="slide" id="s${i + 1}">
  ${els.map((e) => {
    const base = `left:${px(e.x)}px;top:${px(e.y)}px;width:${px(e.w)}px;height:${px(e.h)}px;`;
    if (e.type === 'rect') return `<div class="shape" style="${base}background:#${e.fill}"></div>`;
    if (e.type === 'roundRect') return `<div class="shape" style="${base}background:#${e.fill};border-radius:${px(0.08)}px"></div>`;
    if (e.type === 'ellipse') return `<div class="shape" style="${base}background:#${e.fill};border-radius:50%"></div>`;
    const lh = e.line ? `line-height:${e.line * (96 / 72)}px;` : 'line-height:1.18;';
    const va = e.valign === 'middle' ? 'display:flex;align-items:center;justify-content:center;' : '';
    return `<div class="tx" style="${base}font-size:${e.size * (96 / 72)}px;color:#${e.color};${e.bold ? 'font-weight:700;' : ''}text-align:${e.align || 'left'};${lh}${va}${e.spacing ? `letter-spacing:${e.spacing / 10}px;` : ''}">${esc(e.text).replace(/\n/g, '<br>')}</div>`;
  }).join('\n  ')}
  <div class="num">${i + 1}</div>
</section>`;

fs.writeFileSync('preview.html', `<!doctype html><meta charset="utf-8">
<style>
  body { margin:0; background:#555; font-family:'Liberation Sans',Arial,sans-serif; }
  .slide { position:relative; width:${W}px; height:${H}px; background:#fff; margin:0 auto 24px; overflow:hidden; }
  .shape { position:absolute; }
  .tx { position:absolute; white-space:pre-wrap; box-sizing:border-box; }
  .num { position:absolute; right:8px; bottom:6px; font-size:11px; color:#c8c8c8; }
</style>
${S.map(slideHtml).join('\n')}
`);
console.log('preview.html written with', S.length, 'slides');
