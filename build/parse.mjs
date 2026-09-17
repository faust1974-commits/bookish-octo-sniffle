// Parser for .cjo source files -> structured course objects.
// Format:
//   @key value            course metadata
//   ## 01.0 :: text       standard
//   - 01.01 :: text       benchmark
//     * text              bullet (2 spaces per nesting level)
import fs from 'node:fs';

export function parseCourse(path) {
  const raw = fs.readFileSync(path, 'utf8');
  const meta = {};
  const standards = [];
  let standard = null;
  let benchmark = null;

  raw.split(/\r?\n/).forEach((line, i) => {
    const lineNo = i + 1;
    if (!line.trim()) return;

    const metaMatch = /^@(\w+)\s+(.*)$/.exec(line);
    if (metaMatch) {
      const [, key, value] = metaMatch;
      meta[key] = key === 'certifications' ? value.split('|').map((s) => s.trim())
        : /^(credit|level|position)$/.test(key) ? Number(value)
        : value.trim();
      return;
    }

    const stdMatch = /^##\s+([\d.]+)\s*::\s*(.*)$/.exec(line);
    if (stdMatch) {
      standard = { id: stdMatch[1], text: stdMatch[2].trim(), benchmarks: [], line: lineNo };
      benchmark = null;
      standards.push(standard);
      return;
    }

    const benchMatch = /^-\s+([\d.]+)\s*::\s*(.*)$/.exec(line);
    if (benchMatch) {
      if (!standard) throw new Error(`${path}:${lineNo} benchmark before any standard`);
      benchmark = { id: benchMatch[1], text: benchMatch[2].trim(), bullets: [], line: lineNo };
      standard.benchmarks.push(benchmark);
      return;
    }

    const bulletMatch = /^(\s*)\*\s+(.*)$/.exec(line);
    if (bulletMatch) {
      if (!benchmark) throw new Error(`${path}:${lineNo} bullet before any benchmark`);
      const depth = Math.floor(bulletMatch[1].length / 2);
      benchmark.bullets.push({ depth, text: bulletMatch[2].trim() });
      return;
    }

    throw new Error(`${path}:${lineNo} unrecognized line: ${line.slice(0, 80)}`);
  });

  if (!meta.course) throw new Error(`${path}: missing @course`);

  // Normalise bullet nesting so the shallowest bullet of each benchmark is depth 0.
  standards.forEach((std) => std.benchmarks.forEach((b) => {
    if (!b.bullets.length) return;
    const base = Math.min(...b.bullets.map((x) => x.depth));
    b.bullets.forEach((x) => { x.depth -= base; });
  }));

  return { meta, standards };
}
