# Criminal Justice Operations — indexed curriculum program

A fully indexed, reactive version of the Florida Department of Education
**Criminal Justice Operations** curriculum framework (program `8918000`, CIP `0743010305`,
Law, Public Safety & Security cluster).

Every standard and benchmark in all six courses is transcribed verbatim, machine-indexed, and
queryable — so the framework can answer lesson-design, unit-planning and administrative
questions instead of being a PDF you scroll through.

| | |
| --- | --- |
| Courses | 6 (4 credits; three fourth-credit options) |
| Standards | 80 (01.0 – 65.0; 28.0+ repeat per option) |
| Benchmarks | 535, plus 223 sub-points |
| Legal references indexed | 44 Florida Statutes, F.A.C. rules, CFR, 3 cases, 20 named references |
| Topic tags | 32 |
| Instructional threads | 16, covering all 80 standards |

## Use it

**Web app** — open `docs/index.html` in a browser (works from `file://`, any static host, or
GitHub Pages). No build step, no dependencies, nothing to install.

```bash
npm run serve        # or just double-click docs/index.html
```

* **Ask** — one search box over every benchmark, standard, statute and the administrative
  sections. Typing `15.04`, `Miranda`, `493`, `how many credits`, `teacher certification` or
  `CIP number` returns a direct answer card plus ranked benchmark matches.
* **Browse** — course → standard → benchmark, with filters for course, cognitive level,
  performance vs knowledge, optional, mock activities, statute citations and topic.
* **Sequence** — the connective layer. Pick two benchmarks anywhere in the app and it finds
  the instructional path between them, says *why* they connect ("4 steps along Report writing
  and Criminal investigation"), fills in the benchmarks that have to be taught between, and
  groups the result into lessons and units with day ranges, prerequisite links ("builds on
  13.04") and spiral markers ("revisits 13.04 in 8918020"). Five scopes widen the same
  sequence: **Bridge** (just the connection) → **Full standards** → **Whole thread** (the
  pathway end to end across courses) → **Whole course** → **Whole program** (all four credits
  with one capstone option, ~690 instructional days). Save it into the planner, export it, or
  open any generated lesson as a full lesson plan.
* **Units** — build units from a selection (or scaffold one unit per standard for a whole
  course), with day counts seeded from framework-weighted pacing. Exports Markdown.
* **Lesson** — turn any selection of benchmarks into a lesson plan: objectives written from the
  benchmark verbs, essential question, legal references, materials, sequence, a knowledge-check
  list and a performance checklist, accommodations and CTSO tie-in. Copy, download or print.
* **Coverage** — mark benchmarks *taught* / *assessed* anywhere in the app; roll-ups by course
  and standard; CSV export for program review.
* **Crosswalk** — what is required in more than one course, how topics spread across the
  program, and which statutes carry the most weight.
* **Program** — the administrative front matter: codes, certifications, SOC, CTSO, OJT,
  accommodations, ELD, lab activities, Career Ready Practices.

Deep links work everywhere: `#/b/8918030:22.15`, `#/standard/8918020:13.0`,
`#/course/8918070`, `#/ask?q=fingerprint`.

Selections, units and coverage marks are stored in the browser (localStorage) — nothing leaves
the machine. Export the CSV/Markdown for anything that needs to be kept or shared.

The app is also published as a private hosted page (same code, built by
`build/artifact.mjs` into `dist/artifact/`): <https://claude.ai/artifact/6rUJPmh2rmiMPVedeNCerY>.
File downloads are blocked inside that embedded viewer, so every export there opens a copy
panel instead of saving a file.

**Command line**

```bash
node tools/cjo.mjs search miranda      # full-text search
node tools/cjo.mjs show 22.15          # one benchmark or standard in full
node tools/cjo.mjs course 8918020      # course outline
node tools/cjo.mjs topic forensics     # everything tagged to a topic
node tools/cjo.mjs law 493             # benchmarks tied to a statute
node tools/cjo.mjs crosswalk           # content required more than once
node tools/cjo.mjs plan 8918020        # pacing outline
node tools/cjo.mjs stats               # program totals
```

**Data files** (`dist/`, rebuilt by `npm run build`)

| File | What it is |
| --- | --- |
| `dist/framework.json` | The whole program: courses, standards, benchmarks, indexes, crosswalk, stats |
| `dist/benchmarks.csv` | One row per benchmark — open in Excel/Sheets for district reporting |
| `dist/framework.md` | Printable full text of the framework |
| `docs/framework-data.js` | The same JSON wrapped for the browser app |

## How it is built

```
data/program.json          program metadata, sequence, front matter  (source of truth)
data/pathways.json         curated instructional threads: what builds on what
data/courses/*.cjo         one file per course, verbatim standards and benchmarks
build/parse.mjs            .cjo -> structured objects
build/enrich.mjs           derived fields: Bloom level, modality, topics, citations, weights
build/graph.mjs            prerequisites, spirals and the canonical teaching order
build/build.mjs            assembles indexes, crosswalk, stats -> dist/ + docs/
build/validate.mjs         structural checks (npm test)
build/artifact.mjs         packages docs/ for publishing as a hosted page
tools/cjo.mjs              CLI
docs/                      the app (index.html, app.js, styles.css, framework-data.js)
```

The `.cjo` format is plain text so the framework stays editable by hand:

```
@course 8918020
@title Criminal Justice Operations 2
...
## 13.0 :: Prepare written reports.
- 13.01 :: Identify the "who-what-when-where-why-how" elements of a report.
- 11.04 :: Describe calls for service, to include:
  * Community service
    * Assisting the public
```

After editing any source file:

```bash
npm run check     # build + validate
```

`npm test` verifies standard numbering is contiguous, benchmarks belong to their standard, ids
are unique and sequential, the core sequence 01.0–27.0 runs exactly once across the three core
courses, 28.0+ appears only in fourth-credit options, totals match (80 / 535), and the built
artifacts are not stale.

## What is framework text and what is derived

**Verbatim from FLDOE** — course numbers, titles, credits, levels, SOC codes, CIP, teacher
certifications, CTSO, every standard and benchmark, all sub-bullets, and the additional
information sections. Source typos are preserved deliberately (e.g. 33.11 "Determining how the
crash occurred.", the stray `q)` list marker in 36.01, 42.05 "the circumstances and officer must
consider"). Course `8918050` is titled *Police Service Officer* on its standards page and
*Public Service Officer* in the program-structure table; both are kept (`title` / `altTitle`).

**Derived planning aids — not FLDOE requirements:**

| Field | How it is derived |
| --- | --- |
| `cognitiveLevel` / `cognitiveLabel` | Bloom level of the highest-order verb in the benchmark's first eight words; falls back to the bullets when the benchmark is a noun heading (Code Enforcement 29.x–31.x), else defaults to *Understand* |
| `modality` | `performance` when a verb requires observable student action (demonstrate, perform, conduct, create, process…), else `knowledge` |
| `topics` | Keyword/phrase patterns per topic (32 topics); a benchmark can carry several |
| `citations` | Pattern extraction of F.S., F.A.C., CFR, case names and named references (Miranda, Baker Act, CPTED, AFIS…); subsection detail is kept when the source spells it out |
| `weight` / `suggestedPeriods` | Weight = modality + sub-point count + length, with a bump for mock/scenario work and a reduction for optional; distributed across 170 instructional periods per 1-credit course |
| `crosswalk` | Normalized-text comparison across different course numbers, 0.7 token-overlap threshold |
| `graph` / sequencing | Prerequisite edges come from the 16 curated threads in `data/pathways.json`; the framework's own numbering is the tie-break, not a prerequisite. Spiral edges come from the crosswalk. Lessons group consecutive benchmarks (same standard, ≤6 benchmarks, ≤3.5 periods, breaking on a topic shift); day numbers run off a cumulative pacing total so rounding never compounds |

Sequencing is the most opinionated layer here — it encodes a teaching judgement about what has
to come first. `data/pathways.json` is where that judgement lives: 16 threads, each with a
rationale, covering all 80 standards. Reorder a thread, add one, or split one, run
`npm run check`, and every generated sequence changes with it.

Treat pacing as a starting point, not a mandate — adjust for your schedule, lab access and
students. The `4 optional` benchmarks (15.05, 15.12, 22.14, 25.01) are the only ones the
framework itself marks optional.

## Source

Florida Department of Education, *Criminal Justice Operations* curriculum framework, secondary
career preparatory, program 8918000. CTE program resources:
<http://www.fldoe.org/academics/career-adult-edu/career-tech-edu/program-resources.stml>
