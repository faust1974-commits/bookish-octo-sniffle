# Criminal Justice Operations — working notes

Florida high school Criminal Justice program. Two FLDOE frameworks, one
indexed app, plus classroom lessons.

- `data/programs/8918000/` — Criminal Justice Operations (CJO 1/2/3)
- `data/programs/8607100/` — Careers in Public Service
- `lessons/` — the actual classroom materials

The two programs are **separate shells**. No shared storage, no shared topic
vocabulary, no cross-contamination. Topics live in each program's
`topics.json`, never hardcoded.

## The room

~150 students. 90-minute blocks. CJO 1, 2 and 3 are compressed into one
mixed-level room, so a lesson should hit a benchmark in *some* course for
everyone present — it does not need to hit all three.

Hard constraints:

- **No printing.** Everything is Chromebooks and Canvas.
- Must present **and be editable** on a Promethean board.
- Mac at home, **all Microsoft at school** → `.docx` and `.pptx`, emailable.
- Nearpod is available, but **Nearpod activities cannot be embedded in a
  file**. They only exist inside Nearpod. Supply the content and say where it
  goes; the clicking is the teacher's.
- **The materials carry the content.** The teacher is not yet deeply aligned
  with the subject matter and should never have to improvise it or perform a
  character. Give the words.

## Every lesson ships as this package

One zip, flat, numbered in the order it is used. No exceptions, no extra
files.

```
<Lesson Name>.zip
  0 - TEACHER - Run Sheet - <lesson>.docx    teacher only
  1 - <first thing students touch>.docx
  2 - <next>.docx
  ...
```

The teacher run sheet always contains, in this order:

1. **Canvas setup** — assignment by assignment: the exact title, the
   points, the submission type, which files attach, whether it starts
   published or stays hidden until a given minute, and a **paste-ready
   student-facing description**. The teacher should be able to build Canvas
   from this page without reading anything else.
2. **The one idea** of the lesson.
3. **Standards covered**, by benchmark number, per course level.
4. **Before class** — the physical setup, and anything to test in advance.
5. **Grading** — what to actually grade, given 150 students. Name the one
   section worth reading and say what to skip.
6. **Your parts** — numbered speaking parts with a cue and the lines in
   full. Spoken text large; stage directions small, grey, italic and
   bracketed in the source. Send-offs (the moment students are turned loose
   on an assignment) are accented in orange.
7. **If it comes up** — off-script lines for what reliably happens.
8. **Answer key / where the lesson lands** — last page, marked *do not give
   this to students*.

Student files never contain any of section 1, 5, 6, 7 or 8. There is a
leakage check in each lesson's build; keep it.

## Building lesson documents

`lessons/kit.js` is the shared document furniture — fonts, colours,
callout boxes, statement panels, write-in grids, typeable fields. Both
lessons use it so everything looks like one course.

Lesson builders are CommonJS (`lessons/package.json` pins this; the repo
root is `"type": "module"`). `docx` is not a repo dependency — install it
somewhere and run:

```
NODE_PATH=/path/to/node_modules node "lessons/03 - probable cause/build.js"
```

Content lives in `content-*.js` as plain data, separate from the renderer,
so the teacher can be handed a wording change without touching layout.

Typeable fields must use `HeightRule.ATLEAST` so cells grow as students
type in Word for the web instead of clipping.

## Lesson continuity

Lessons 02 and 03 run one continuous case — Lincoln Community Center,
overnight burglary. Keep using it. The payoff of a second week is that
students recognise their own earlier work; a fresh scenario throws that
away and costs a re-teach of context.

Case facts established so far (do not contradict these):

- Call received 0107, unit on scene 0116.
- Ray Delgado, night custodian, two years employed. Found the equipment room
  door open, light off, shelf looked empty. Did not enter. Called his
  supervisor "around 1". Back door to the lot unlocked.
- Marisa Vance, operations supervisor. Says Ray called at 1250. Nine Dell
  laptops, asset tags CC-0041 to CC-0049, about $520 each, counted Friday
  ~1740 when she locked up. Three keys to the equipment room; Ray has none.
  Back door is on a 9pm timer that does not always latch — two unanswered
  work orders. Camera over the back door dead since summer, work order filed
  in July. Dontae Rivers, part-time rec aide, last day 15 August, never
  returned a **building** key (not the equipment room key).
- Pawn record: two laptops, CC-0043 and CC-0047, pawned Saturday 1042 at
  Westside Pawn & Jewelry for $60 each by Dontae M. Rivers, licence and
  thumbprint on file. **Seven laptops remain unaccounted for.**

The case gives probable cause for **theft** and deliberately never gives it
for **burglary** — nobody ever proved entry. That gap is the spine of the
whole unit. Do not close it.

## Florida law in student materials

Verify before printing a citation. `flsenate.gov` is **not reachable from
this container** (DNS fails, and the proxy 403s `m.flsenate.gov`), so a
statute number cannot be confirmed here. Options, in order of preference:

1. Make locating the statute the student task — benchmark 13.10 asks for
   exactly that — and keep the number off the sheet.
2. Put the expected answer in the teacher answer key only, flagged for the
   teacher to eyeball.
3. Tell the user plainly it is unverified. Never quietly assert it.

Known good: speedy trial Rule 3.191 was revised **effective 1 July 2025** —
the clock now runs from formal charges, not arrest, so most lesson material
online is out of date. Capital crimes require a grand jury indictment.
Gideon v. Wainwright is a Florida case.

## Working style

Ask before building. Build one thing, show it, take the correction. The
teacher drives the design and does not want alternatives surveyed or scope
widened unasked.

**Reply short.** Hand over the files and say what they are in a sentence or
two, like a colleague would. No summaries of the work, no tables of what
changed, no bulleted tours of your own reasoning. If something genuinely
needs flagging — unverified law, a file that has to stay unpublished — say
that one thing and stop.
