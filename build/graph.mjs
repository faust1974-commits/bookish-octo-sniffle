// Builds the instructional graph: what must be taught before what, what revisits
// what, and the canonical order the whole program can be walked in.
//
// Edge types
//   thread         consecutive standards on a curated pathway (data/pathways.json)
//   course-order   standard N -> standard N+1 inside one course
//   sequence       consecutive benchmarks inside one standard
//   scaffold       knowledge benchmark -> performance benchmark, same standard and topic
//   spiral         the same content required again in a later course (crosswalk)
// Weight is the cost used when finding a path between two points: a tighter
// instructional coupling costs less.

const WEIGHT = { thread: 1, 'course-order': 2, sequence: 1, scaffold: 1, spiral: 3 };

export function buildGraph({ courses, threads, clusters }) {
  const standards = courses.flatMap((c) => c.standards);
  const byUid = new Map(standards.map((s) => [s.uid, s]));
  const benchmarks = standards.flatMap((s) => s.benchmarks);
  const benchByUid = new Map(benchmarks.map((b) => [b.uid, b]));

  const standardEdges = [];
  const seen = new Set();
  const addStandardEdge = (from, to, type, extra = {}) => {
    if (from === to || !byUid.has(from) || !byUid.has(to)) return;
    const key = `${from}>${to}>${type}`;
    if (seen.has(key)) return;
    seen.add(key);
    standardEdges.push({ from, to, type, weight: WEIGHT[type], ...extra });
  };

  threads.forEach((t) => {
    t.standards.forEach((uid, i) => {
      if (i === 0) return;
      addStandardEdge(t.standards[i - 1], uid, 'thread', { thread: t.id, why: t.label });
    });
  });

  courses.forEach((c) => {
    c.standards.forEach((s, i) => {
      if (i === 0) return;
      addStandardEdge(c.standards[i - 1].uid, s.uid, 'course-order', {
        why: `${c.title} teaches ${c.standards[i - 1].id} before ${s.id}`,
      });
    });
  });

  // Cross-course repeats: the earlier course introduces it, the later one revisits it.
  const position = new Map(courses.map((c) => [c.courseNumber, c.position]));
  (clusters || []).forEach((cl) => {
    const members = cl.members.map((uid) => benchByUid.get(uid)).filter(Boolean)
      .sort((a, b) => position.get(a.courseNumber) - position.get(b.courseNumber));
    for (let i = 1; i < members.length; i += 1) {
      addStandardEdge(
        `${members[0].courseNumber}:${members[0].standardId}`,
        `${members[i].courseNumber}:${members[i].standardId}`,
        'spiral',
        { why: `${members[i].id} repeats ${members[0].id}`, cluster: cl.id },
      );
    }
  });

  // ---------------------------------------------------------- benchmark edges
  const benchmarkEdges = [];
  standards.forEach((s) => {
    s.benchmarks.forEach((b, i) => {
      if (i > 0) {
        benchmarkEdges.push({ from: s.benchmarks[i - 1].uid, to: b.uid, type: 'sequence', weight: WEIGHT.sequence });
      }
    });
    const knowledge = s.benchmarks.filter((b) => b.modality === 'knowledge');
    s.benchmarks.filter((b) => b.modality === 'performance').forEach((perf) => {
      knowledge.filter((k) => k.topics.some((t) => perf.topics.includes(t)) && k.id < perf.id)
        .slice(-2)
        .forEach((k) => benchmarkEdges.push({ from: k.uid, to: perf.uid, type: 'scaffold', weight: WEIGHT.scaffold }));
    });
  });
  (clusters || []).forEach((cl) => {
    const members = cl.members.map((uid) => benchByUid.get(uid)).filter(Boolean)
      .sort((a, b) => position.get(a.courseNumber) - position.get(b.courseNumber));
    for (let i = 1; i < members.length; i += 1) {
      benchmarkEdges.push({ from: members[0].uid, to: members[i].uid, type: 'spiral', weight: WEIGHT.spiral, cluster: cl.id });
    }
  });

  // ------------------------------------------------------------ per-standard
  const threadsOf = new Map(standards.map((s) => [s.uid, []]));
  threads.forEach((t) => t.standards.forEach((uid) => {
    if (threadsOf.has(uid)) threadsOf.get(uid).push(t.id);
  }));

  const prereqs = new Map(standards.map((s) => [s.uid, []]));
  const unlocks = new Map(standards.map((s) => [s.uid, []]));
  standardEdges.forEach((e) => {
    prereqs.get(e.to).push(e);
    unlocks.get(e.from).push(e);
  });

  // Canonical program order. Only curated thread edges are hard constraints:
  // a course's own numbering is the framework's presentation order, so it is the
  // tie-breaker rather than a prerequisite (treating it as one would force every
  // sequence back into strict numeric order and deadlock any thread that differs).
  const isHard = (e) => e.type === 'thread';
  const indegree = new Map(standards.map((s) => [s.uid, prereqs.get(s.uid).filter(isHard).length]));
  // Tie-break on the course's place in the sequence, then its standard number, so
  // each course stays contiguous - the three fourth-credit options are alternatives,
  // not parallel work, and must not interleave.
  const courseIndex = new Map(courses.map((c, i) => [c.courseNumber, i]));
  const rank = (uid) => {
    const s = byUid.get(uid);
    return courseIndex.get(s.courseNumber) * 100 + Number(s.id.split('.')[0]);
  };
  const ready = standards.filter((s) => indegree.get(s.uid) === 0).map((s) => s.uid);
  const order = [];
  const cycles = [];
  while (ready.length) {
    ready.sort((a, b) => rank(a) - rank(b));
    const uid = ready.shift();
    order.push(uid);
    unlocks.get(uid).filter(isHard).forEach((e) => {
      indegree.set(e.to, indegree.get(e.to) - 1);
      if (indegree.get(e.to) === 0) ready.push(e.to);
    });
  }
  if (order.length !== standards.length) {
    standards.map((s) => s.uid).filter((uid) => !order.includes(uid))
      .sort((a, b) => rank(a) - rank(b))
      .forEach((uid) => { cycles.push(uid); order.push(uid); });
  }
  const orderIndex = new Map(order.map((uid, i) => [uid, i]));

  // Teaching depth: longest dependency chain ending at this standard.
  const depth = new Map(order.map((uid) => [uid, 0]));
  order.forEach((uid) => {
    prereqs.get(uid).filter(isHard).forEach((e) => {
      depth.set(uid, Math.max(depth.get(uid), (depth.get(e.from) ?? 0) + 1));
    });
  });

  const standardMeta = Object.fromEntries(standards.map((s) => [s.uid, {
    threads: threadsOf.get(s.uid),
    prereqs: prereqs.get(s.uid).map((e) => ({ uid: e.from, type: e.type, why: e.why || null, thread: e.thread || null })),
    unlocks: unlocks.get(s.uid).map((e) => ({ uid: e.to, type: e.type, why: e.why || null, thread: e.thread || null })),
    order: orderIndex.get(s.uid),
    depth: depth.get(s.uid),
  }]));

  return {
    threads,
    standardEdges,
    benchmarkEdges,
    standardMeta,
    programOrder: order,
    cycles,
    weights: WEIGHT,
  };
}
